# JUPI TRANSLATION GATE v0 -- translator client (runs ON JUPI 2; only sends requests to the on-node local model server)
import hashlib, json, sys, time, urllib.request, os
PROTO, PSHA, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
raw = open(PROTO, 'rb').read()
assert hashlib.sha256(raw).hexdigest() == PSHA, "PROTOCOL sha mismatch"
P = json.loads(raw)
EP = P["translator"]["endpoint"]; MODEL = P["translator"]["model"]; MAXTOK = P["translator"]["max_tokens"]
TO = P["translator"]["timeout_s"]; BUDGET = P["budget"]["model_time_s"]
FR = P["framings"]; ITEMS = P["items"]

def gate():
    m = {}
    for l in open('/proc/meminfo'):
        k, v = l.split(':'); m[k] = int(v.split()[0])
    avail = m['MemAvailable'] // 1024; st = m['SwapTotal']; su = st - m['SwapFree']
    sp = 100.0 * su / st if st else 0.0
    return {"avail_mb": avail, "swap_pct": round(sp, 2), "ok": avail > 800 and sp < 25.0}

def wait_gate(log):
    for i in range(4):
        g = gate(); log.write(json.dumps({"gate": g, "t": time.time()}) + "\n"); log.flush()
        if g["ok"]: return True
        time.sleep(30)
    return False

def prompt(item, f):
    spec = item["spec"] if item["type"] != "act" else P["assist_prefix"] + "'" + item["spec"] + "'"
    return FR[f].replace("{spec}", spec).replace("{schema}", item["schema"])

def call(p):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": p}], "max_tokens": MAXTOK,
                       "temperature": 0, "seed": 1}).encode()
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(EP, body, {"Content-Type": "application/json"}), timeout=TO) as r:
            j = json.loads(r.read()); st = r.status
    except Exception as e:
        return {"http_error": type(e).__name__ + ": " + str(e)[:200], "wall_s": time.time() - t0, "text": ""}
    x = j.get("jupi2", {})
    return {"http": st, "wall_s": time.time() - t0, "text": j["choices"][0]["message"]["content"],
            "backend": x.get("backend"), "perf": x.get("perf"), "server_elapsed_s": x.get("elapsed_s"),
            "gate_before": x.get("gate_before"), "gate_after": x.get("gate_after")}

os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "run-log.jsonl"), "a")
outf = open(os.path.join(OUT, "outputs.jsonl"), "a")
T0 = time.time(); model_s = 0.0; ncall = 0; aborted = None

def run_phase(name, pairs):
    global model_s, ncall, aborted
    if not wait_gate(log): aborted = "gate_fail_before_" + name; return
    for (item, f) in pairs:
        if ncall % 10 == 0 and ncall and not wait_gate(log): aborted = "gate_fail_mid_" + name; return
        p = prompt(item, f); r = call(p); ncall += 1; model_s += r["wall_s"]
        rec = {"phase": name, "id": item["id"], "framing": f, "prompt_sha256": hashlib.sha256(p.encode()).hexdigest(), "prompt": p, **r}
        outf.write(json.dumps(rec, ensure_ascii=False) + "\n"); outf.flush()
        if r.get("backend") not in (None, "cpu"):
            aborted = "non_cpu_backend:" + str(r.get("backend")); return
        if model_s > BUDGET * 1.10: aborted = "budget_hard_stop"; return

# phase 1: T0 baseline, framing F0, all items
run_phase("T0", [(it, 0) for it in ITEMS])
plan = {"after_T0_model_s": model_s, "calls": ncall}
if not aborted:
    L = model_s / max(ncall, 1); rem = BUDGET - model_s; n = len(ITEMS)
    if n * 4 * L <= rem: kx, items = 4, ITEMS
    elif n * 2 * L <= rem: kx, items = 2, ITEMS
    else: kx = 2; items = ITEMS[:max(0, int(rem // (2 * L)))]
    plan.update({"mean_call_s": L, "remaining_s": rem, "k_extra": kx, "k_total": kx + 1, "n_consensus_items": len(items)})
    log.write(json.dumps({"shrink_decision": plan}) + "\n"); log.flush()
    run_phase("K", [(it, f) for f in range(1, kx + 1) for it in items])
summary = {"calls": ncall, "model_s": model_s, "wall_s": time.time() - T0, "aborted": aborted, "plan": plan,
           "final_gate": gate()}
json.dump(summary, open(os.path.join(OUT, "translate-summary.json"), "w"), indent=1)
print(json.dumps(summary))
