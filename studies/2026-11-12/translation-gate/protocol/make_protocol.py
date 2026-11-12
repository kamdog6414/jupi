import json, hashlib, time, os, keys
D = os.path.dirname(os.path.abspath(__file__))
sha = lambda f: hashlib.sha256(open(os.path.join(D, f), 'rb').read()).hexdigest()
K = keys.all_keys()
items = [{"id": i[0], "cat": i[1], "type": i[2], "spec": i[3], "schema": keys.SCHEMA[i[2]], "recompute_expr": i[4], "key": K[i[0]]} for i in keys.ITEMS]
P = {
 "study": "JUPI TRANSLATION GATE v0",
 "created_local": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
 "thesis_under_test": "Argon/Kam: LLMs as semantic compilers upstream of deterministic verifiers; MODEL_CONSENSUS != GOVERNING_AUTHORITY; assistive AI needs zero silent corruption.",
 "seats": {"translator": "JUPI 2 (groku-muse, qwen3-0.6b, on-node local model server, requests only)",
           "verifier_primary": "JUPI -- no model server; verifies JUPI 2 outputs",
           "verifier_secondary": "JUPI 2 -- verifies the same outputs and re-derives the answer key; JUPI re-derives it too",
           "orchestration": "orchestration host via the lab peer; analysis on the orchestration host"},
 "translator": {"endpoint": "<local-model-endpoint>", "model": "qwen3-0.6b", "max_tokens": 64, "timeout_s": 150,
                "server_facts_read_only": "groku-muse-server-v1.py hard-codes --temp 0 --seed 1, caps max_tokens at 64, -c 512; gpu-disabled flag present -> CPU llama-cli path. Direct llama-server on the local GPU port is the Vulkan path and is NOT used (GPU stays off per standing rules).",
                "abort_rule": "stop all calls if any response reports backend other than cpu"},
 "sampling": {"T0": "framing F0, temperature 0, seed 1 (server-fixed)",
              "consensus_samples": "temperature 0.7 with seeds is NOT exposed by groku-muse v1 (server forces temp 0 seed 1) and the only sampler-capable endpoint is the GPU server, which is off-limits. Substitute frozen here: k samples = k deterministic prompt framings F0..F(k-1) of the same item (paraphrase self-consistency). Stated as a deviation from the brief.",
              "k_target": 5},
 "framings": [
   "{spec}\nReply with only one line of JSON: {schema} /no_think",
   "You are a precise engineering assistant. Task: {spec}\nOutput exactly one JSON object like {schema} and nothing else. /no_think",
   "Return JSON {schema}.\nQuestion: {spec} /no_think",
   "Translate this request into structured data.\nRequest: {spec}\nJSON ({schema}): /no_think",
   "Answer carefully. {spec}\nFormat: {schema}\nJSON only. /no_think"],
 "assist_prefix": keys.ASSIST_PREFIX,
 "items": items,
 "verifier": {
   "extraction": "strip <think>...</think>; first balanced {...} that json-parses to an object (fallback: search the unstripped text)",
   "schema": "num/int: answer is finite int|float, not bool; bool: answer is bool; str/hex: non-empty string; act: keys subset of {action,device,room,level}, action in {turn_on,turn_off,set_level,hold}, device in {light,tv,thermostat,lock,null}, room in {hall,kitchen,bedroom,living_room,front_door,null}, level int|null",
   "recompute": "num/int/bool/hex/str: verifier re-evaluates recompute_expr with stdlib (keys.py) and compares; act: verifier runs an independent rule-based intent parser (keys.parse_intent) on the command text and requires agreement (hold-vs-hold needs only action=hold)",
   "tolerance": {"num": keys.TOL["num"], "int": keys.TOL["int"]},
   "string_norm": "strip, strip trailing .!?。, lowercase; str correct iff in accept list; hex exact",
   "gate": "PASS iff parsed AND schema_ok AND recompute agrees; else HOLD (system emits hold / no answer)",
   "raw_correct": "lenient read with no schema demands: JSON answer if present (strings coerced), else first number / true|false|yes|no / hex run / accept-term substring in text",
   "truly_correct": "schema-valid answer equal to the FROZEN key in this file (human-written for jp_en and assist)",
   "silent_wrong": "gate PASS and not truly_correct",
   "baselines": {"schema_only_gate": "PASS iff parsed AND schema_ok (typical JSON-mode pipeline)",
                 "consensus_gate": "PASS iff all k framings give the same normalized answer"},
   "norm_answer": "num -> %.6g; bool -> str; str -> norm; act -> json tuple; unparsed -> None (breaks unanimity)"},
 "hypotheses": {
   "H1": {"claim": "raw model accuracy is well below 100%", "metric": "raw_correct rate over all 50 items at T0 (F0)", "pass_if": "<= 0.85"},
   "H2": {"claim": "with the deterministic gate, silent wrong answers passed = 0", "metric": "count silent_wrong over ALL outputs (T0 + consensus framings), each verifier seat", "pass_if": "== 0 on both seats",
          "secondary_prediction_S2": "schema-only gate passes >= 1 silent wrong answer (shows the recompute step is what matters)",
          "known_limit": "for numeric items recompute and key share keys.py, so H2 mainly tests that the gate is wired correctly and runs identically on two seats; the non-trivial part is jp_en (dictionary oracle) and assist (independent parser vs human key)"},
   "H3": {"claim": "agreement among k samples is not a reliable proxy for correctness", "metric": "2x2 of unanimous(k framings) vs raw_correct(F0) over items with all k samples; precision=P(correct|unanimous), recall=P(unanimous|correct); count unanimous-wrong",
          "pass_if": "unanimous_wrong >= 1 AND precision < 0.95"},
   "H4": {"claim": "verifier runs on the other node with byte-identical verdicts", "metric": "sha256(VERDICTS.json) on JUPI == on JUPI 2; key_check.recomputed_equals_frozen true on both", "pass_if": "both true"}},
 "budget": {"model_time_s": 900, "gate": "MemAvailable > 800 MB and swap < 25% before each phase and every 10 calls (4 tries, 30 s apart, then abort phase)",
            "shrink_rule": "after T0 (50 calls): L = mean call s; rem = 900 - T0 model s. If 50*4*L <= rem: k_extra=4 (k=5). Elif 50*2*L <= rem: k_extra=2 (k=3). Else k_extra=2 on the first floor(rem/(2L)) items in frozen order. Hard stop at 1.10*900 s model time. H3 uses only items with all k samples.",
            "verifier": "stdlib, CPU, no installs"},
 "rules": "no installs; no GPU; no service changes; requests only to the on-node local model server",
 "code_sha256": {f: sha(f) for f in ("keys.py", "translate.py", "verify.py")}}
open(os.path.join(D, "..", "protocol", "PROTOCOL.json"), "w").write(json.dumps(P, indent=1, ensure_ascii=False, sort_keys=True))
print(hashlib.sha256(open(os.path.join(D, "..", "protocol", "PROTOCOL.json"), 'rb').read()).hexdigest())
