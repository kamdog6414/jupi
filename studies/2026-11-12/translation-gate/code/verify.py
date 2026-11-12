# JUPI TRANSLATION GATE v0 -- deterministic gate / verifier (stdlib only; runs on JUPI and JUPI 2)
import hashlib, json, math, re, sys, time, os, platform, resource
PROTO, PSHA, OUTPUTS, OUTDIR, SEAT = sys.argv[1:6]
t0 = time.time()
raw = open(PROTO, 'rb').read(); assert hashlib.sha256(raw).hexdigest() == PSHA, "PROTOCOL sha mismatch"
P = json.loads(raw)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ksrc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys.py'), 'rb').read()
assert hashlib.sha256(ksrc).hexdigest() == P["code_sha256"]["keys.py"], "keys.py sha mismatch"
import keys
KEY = {it["id"]: it["key"] for it in P["items"]}
RECOMP = keys.all_keys()
key_check = {"recomputed_equals_frozen": json.dumps(RECOMP, sort_keys=True, ensure_ascii=False) == json.dumps(KEY, sort_keys=True, ensure_ascii=False),
             "recomputed_keys_sha256": hashlib.sha256(json.dumps(RECOMP, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
ITEM = {it["id"]: it for it in P["items"]}
ACTS = {"turn_on", "turn_off", "set_level", "hold"}; DEVS = {"light", "tv", "thermostat", "lock", None}
ROOMS = {"hall", "kitchen", "bedroom", "living_room", "front_door", None}

def strip_think(t): return re.sub(r"<think>.*?</think>", "", t, flags=re.S)
def first_json(t):
    for i, ch in enumerate(t):
        if ch != '{': continue
        depth = 0
        for j in range(i, len(t)):
            if t[j] == '{': depth += 1
            elif t[j] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        o = json.loads(t[i:j + 1])
                        if isinstance(o, dict): return o
                    except Exception: pass
                    break
    return None
def isnum(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
def num_eq(a, k, ty):
    tol = P["verifier"]["tolerance"][ty]; return abs(a - k) <= max(tol["abs"], tol["rel"] * abs(k))
def norm_str(s): return s.strip().strip(".!?。").strip().lower()

def schema_ok(o, ty):
    if o is None: return False, "parse_fail"
    if ty == "act":
        if set(o.keys()) - {"action", "device", "room", "level"} or "action" not in o: return False, "schema_keys"
        a = o.get("action"); d = o.get("device"); r = o.get("room"); l = o.get("level")
        d = None if d in ("null", "") else d; r = None if r in ("null", "") else r
        if a not in ACTS or d not in DEVS or r not in ROOMS or not (l is None or (isinstance(l, int) and not isinstance(l, bool))):
            return False, "schema_values"
        return True, None
    if "answer" not in o: return False, "schema_keys"
    v = o["answer"]
    if ty in ("num", "int"): return (isnum(v), None if isnum(v) else "schema_type")
    if ty == "bool": return (isinstance(v, bool), None if isinstance(v, bool) else "schema_type")
    return (isinstance(v, str) and v.strip() != "", None if isinstance(v, str) and v.strip() else "schema_type")

def act_tuple(o):
    d = o.get("device"); r = o.get("room")
    d = None if d in ("null", "") else d; r = None if r in ("null", "") else r
    if o.get("action") == "hold": return ["hold", None, None, None]
    return [o.get("action"), d, r, o.get("level")]

def matches(val, k, ty):
    if ty in ("num", "int"): return isnum(val) and num_eq(val, k, ty)
    if ty == "bool": return isinstance(val, bool) and val == k
    if ty == "hex": return isinstance(val, str) and norm_str(val) == k
    if ty == "str": return isinstance(val, str) and norm_str(val) in k
    if ty == "act": return val[0] == k[0] if k[0] == "hold" else val == k

def lenient(text, o, ty, k):
    """raw correctness: best-effort reading of the model text with no schema demands"""
    if ty == "act":
        return (o is not None and "action" in o and matches(act_tuple(o), k, ty)), (act_tuple(o) if o else None)
    if o is not None and "answer" in o:
        v = o["answer"]
        if ty in ("num", "int") and isinstance(v, str):
            try: v = float(v.replace(",", ""))
            except Exception: pass
        if ty == "bool" and isinstance(v, str): v = {"true": True, "false": False, "yes": True, "no": False}.get(v.strip().lower(), v)
        return matches(v, k, ty), v
    if ty in ("num", "int"):
        m = re.search(r"-?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?", text)
        if m:
            try: v = float(m.group(0).replace(",", "")); return matches(v, k, ty), v
            except Exception: pass
        return False, None
    if ty == "bool":
        m = re.search(r"\b(true|false|yes|no)\b", text.lower())
        if m: v = m.group(1) in ("true", "yes"); return v == k, v
        return False, None
    if ty == "hex":
        m = re.search(r"[0-9a-fA-F]{8,64}", text); v = m.group(0).lower() if m else None
        return (v == k), v
    tl = text.lower(); return any(a in tl for a in k), None

def norm_answer(o, ty):
    if o is None: return None
    if ty == "act": return json.dumps(act_tuple(o)) if "action" in o else None
    if "answer" not in o: return None
    v = o["answer"]
    if isnum(v): return "%.6g" % v
    if isinstance(v, bool): return str(v)
    if isinstance(v, str): return norm_str(v)
    return json.dumps(v, sort_keys=True)

recs = [json.loads(l) for l in open(OUTPUTS, encoding="utf-8")]
verdicts = []
for r in recs:
    it = ITEM[r["id"]]; ty = it["type"]; k = KEY[r["id"]]
    text = r.get("text") or ""; body = strip_think(text); o = first_json(body) or first_json(text)
    ok, why = schema_ok(o, ty)
    raw_ok, raw_val = lenient(body, o, ty, k)
    v = {"id": r["id"], "framing": r["framing"], "phase": r["phase"], "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
         "parsed": o is not None, "schema_ok": ok, "raw_correct": bool(raw_ok), "norm_answer": norm_answer(o, ty)}
    if ty == "act":
        recompute = keys.parse_intent(it["spec"])
        model_t = act_tuple(o) if ok else None
        agree = ok and (model_t == recompute if recompute[0] != "hold" else model_t[0] == "hold")
        v["recompute"] = recompute
        gate = "PASS" if agree else "HOLD"
        v["gate_reason"] = None if agree else (why or "recompute_mismatch")
        v["system_output"] = model_t if agree else ["hold", None, None, None]
        v["truly_correct"] = bool(ok and matches(model_t, k, ty))
        v["schema_only_output"] = model_t if ok else ["hold", None, None, None]
    else:
        recompute = RECOMP[r["id"]]
        val = o["answer"] if ok else None
        agree = ok and matches(val, recompute, ty)
        gate = "PASS" if agree else "HOLD"
        v["gate_reason"] = None if agree else (why or "recompute_mismatch")
        v["truly_correct"] = bool(ok and matches(val, k, ty))
    v["gate"] = gate
    v["silent_wrong_full_gate"] = (gate == "PASS" and not v["truly_correct"])
    v["silent_wrong_schema_only"] = (ok and not v["truly_correct"])
    if ty == "act":
        so = v["system_output"]; v["unsafe_actuation_full_gate"] = so[0] != "hold" and so != k
        sc = v["schema_only_output"]; v["unsafe_actuation_schema_only"] = sc[0] != "hold" and sc != k
    verdicts.append(v)
verdicts.sort(key=lambda x: (x["phase"], x["id"], x["framing"]))
doc = {"study": P["study"], "protocol_sha256": PSHA, "outputs_sha256": hashlib.sha256(open(OUTPUTS, 'rb').read()).hexdigest(),
       "key_check": key_check, "n": len(verdicts), "verdicts": verdicts}
os.makedirs(OUTDIR, exist_ok=True)
vb = json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
open(os.path.join(OUTDIR, "VERDICTS.json"), "wb").write(vb)
rc = {"seat": SEAT, "python": platform.python_version(), "machine": platform.machine(), "wall_s": round(time.time() - t0, 4),
      "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "verdicts_sha256": hashlib.sha256(vb).hexdigest(),
      "key_check": key_check, "n_verdicts": len(verdicts), "local_time": time.strftime("%Y-%m-%d %H:%M:%S %Z")}
open(os.path.join(OUTDIR, "VERIFY-RECEIPT.json"), "w").write(json.dumps(rc, indent=1))
print(json.dumps(rc))
