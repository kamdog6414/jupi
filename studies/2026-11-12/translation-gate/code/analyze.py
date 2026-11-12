# box-side analysis (post-run; reads node verdicts, never edits them)
import json, hashlib, collections, statistics as st, os, sys
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(f"{B}/protocol/PROTOCOL.json")); ITEM = {i["id"]: i for i in P["items"]}
V1b = open(f"{B}/JUPI/VERDICTS.json", 'rb').read(); V2b = open(f"{B}/JUPI2/VERDICTS.json", 'rb').read()
V = json.loads(V1b); V2 = json.loads(V2b)
outs = [json.loads(l) for l in open(f"{B}/raw/outputs.jsonl", encoding="utf-8")]
S = json.load(open(f"{B}/raw/translate-summary.json"))
vs = V["verdicts"]; t0 = [v for v in vs if v["phase"] == "T0"]
cats = sorted({i["cat"] for i in P["items"]}, key=lambda c: [i["cat"] for i in P["items"]].index(c))
def rate(xs, f): return (sum(1 for x in xs if f(x)), len(xs))
A = {"protocol_sha256": V["protocol_sha256"], "outputs_sha256": V["outputs_sha256"], "n_outputs": len(vs), "translate_summary": S}
A["T0"] = {"raw_correct": rate(t0, lambda v: v["raw_correct"]), "parsed": rate(t0, lambda v: v["parsed"]), "schema_ok": rate(t0, lambda v: v["schema_ok"]),
           "truly_correct": rate(t0, lambda v: v["truly_correct"]), "gate_pass": rate(t0, lambda v: v["gate"] == "PASS"),
           "by_cat": {c: {"raw": rate([v for v in t0 if ITEM[v["id"]]["cat"] == c], lambda v: v["raw_correct"]),
                          "gate_pass": rate([v for v in t0 if ITEM[v["id"]]["cat"] == c], lambda v: v["gate"] == "PASS"),
                          "schema_silent_wrong": rate([v for v in t0 if ITEM[v["id"]]["cat"] == c], lambda v: v["silent_wrong_schema_only"])} for c in cats},
           "hold_reasons": dict(collections.Counter(v["gate_reason"] for v in t0 if v["gate"] == "HOLD"))}
A["all"] = {"silent_wrong_full_gate": sum(v["silent_wrong_full_gate"] for v in vs), "silent_wrong_schema_only": sum(v["silent_wrong_schema_only"] for v in vs),
            "gate_pass": sum(v["gate"] == "PASS" for v in vs), "raw_correct": sum(v["raw_correct"] for v in vs),
            "unsafe_actuation_full_gate": sum(v.get("unsafe_actuation_full_gate", False) for v in vs),
            "unsafe_actuation_schema_only": sum(v.get("unsafe_actuation_schema_only", False) for v in vs),
            "silent_wrong_full_gate_JUPI2_seat": sum(v["silent_wrong_full_gate"] for v in V2["verdicts"])}
# consensus
kt = S["plan"].get("k_total", 1)
by = collections.defaultdict(dict)
for v in vs: by[v["id"]][v["framing"]] = v
rows = []
for iid, d in by.items():
    if not all(f in d for f in range(kt)): continue
    ans = [d[f]["norm_answer"] for f in range(kt)]
    unan = all(a is not None for a in ans) and len(set(ans)) == 1
    rows.append({"id": iid, "unanimous": unan, "f0_raw_correct": d[0]["raw_correct"], "answers": ans,
                 "all_truly_correct": all(d[f]["truly_correct"] for f in range(kt))})
tp = sum(r["unanimous"] and r["f0_raw_correct"] for r in rows); fp = sum(r["unanimous"] and not r["f0_raw_correct"] for r in rows)
fn = sum((not r["unanimous"]) and r["f0_raw_correct"] for r in rows); tn = sum((not r["unanimous"]) and not r["f0_raw_correct"] for r in rows)
A["consensus"] = {"k": kt, "n_items": len(rows), "2x2": {"unanimous_correct": tp, "unanimous_wrong": fp, "split_correct": fn, "split_wrong": tn},
                  "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
                  "consensus_gate_silent_wrong": fp, "rows": rows}
uw = []
for r in rows:
    if r["unanimous"] and not r["f0_raw_correct"]:
        o = next(x for x in outs if x["id"] == r["id"] and x["framing"] == 0)
        uw.append({"id": r["id"], "cat": ITEM[r["id"]]["cat"], "spec": ITEM[r["id"]]["spec"], "key": ITEM[r["id"]]["key"],
                   "unanimous_answer": r["answers"][0], "F0_text_verbatim": o["text"],
                   "gate_verdict_F0": by[r["id"]][0]["gate"], "gate_reason_F0": by[r["id"]][0]["gate_reason"]})
A["unanimous_wrong_examples"] = uw
# H4
A["H4"] = {"JUPI_sha": hashlib.sha256(V1b).hexdigest(), "JUPI2_sha": hashlib.sha256(V2b).hexdigest(),
           "identical": V1b == V2b, "key_check_JUPI": V["key_check"], "key_check_JUPI2": V2["key_check"]}
# latency / throughput
w = [o["wall_s"] for o in outs if "wall_s" in o]
A["latency"] = {"calls": len(w), "mean_s": st.mean(w), "median_s": st.median(w), "min_s": min(w), "max_s": max(w), "sum_s": sum(w),
                "per_item_T0": {o["id"]: round(o["wall_s"], 3) for o in outs if o["phase"] == "T0"},
                "backends": dict(collections.Counter(o.get("backend") for o in outs)), "http_errors": sum("http_error" in o for o in outs)}
pf = f"{B}/raw/perf-tps.json"
if os.path.exists(pf):
    T = json.load(open(pf)); g = [t["gen_tps"] for t in T if t.get("gen_tps")]; p = [t["prompt_tps"] for t in T if t.get("prompt_tps")]
    A["throughput"] = {"n_logs": len(T), "gen_tps_mean": st.mean(g) if g else None, "gen_tps_median": st.median(g) if g else None,
                       "prompt_tps_mean": st.mean(p) if p else None, "source": "llama-cli per-request logs written by groku-muse (read-only)"}
# hypotheses
h1v = A["T0"]["raw_correct"][0] / A["T0"]["raw_correct"][1]
c = A["consensus"]
A["hypotheses"] = {
  "H1": {"value": h1v, "criterion": "<= 0.85", "result": "PASS" if h1v <= 0.85 else "FAIL"},
  "H2": {"value": [A["all"]["silent_wrong_full_gate"], A["all"]["silent_wrong_full_gate_JUPI2_seat"]], "criterion": "== 0 both seats",
         "result": "PASS" if A["all"]["silent_wrong_full_gate"] == 0 and A["all"]["silent_wrong_full_gate_JUPI2_seat"] == 0 else "FAIL",
         "S2_schema_only_silent_wrong": A["all"]["silent_wrong_schema_only"], "S2_result": "PASS" if A["all"]["silent_wrong_schema_only"] >= 1 else "FAIL"},
  "H3": {"value": {"unanimous_wrong": c["2x2"]["unanimous_wrong"], "precision": c["precision"], "recall": c["recall"]}, "criterion": "unanimous_wrong >= 1 AND precision < 0.95",
         "result": "PASS" if c["2x2"]["unanimous_wrong"] >= 1 and (c["precision"] is not None and c["precision"] < 0.95) else "FAIL"},
  "H4": {"value": A["H4"]["identical"] and V["key_check"]["recomputed_equals_frozen"] and V2["key_check"]["recomputed_equals_frozen"],
         "criterion": "byte-identical verdicts + key recompute == frozen on both", "result": "PASS" if (A["H4"]["identical"] and V["key_check"]["recomputed_equals_frozen"] and V2["key_check"]["recomputed_equals_frozen"]) else "FAIL"}}
os.makedirs(f"{B}/compare", exist_ok=True)
json.dump(A, open(f"{B}/compare/ANALYSIS.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: A[k] for k in ("T0", "all", "hypotheses", "latency")}, indent=1, ensure_ascii=False)[:6000])
print(json.dumps(c["2x2"]), c["precision"], c["recall"])
