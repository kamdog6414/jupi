#!/usr/bin/env python3
"""JUPI final inference bench: pinned profile lane (num_thread=4, ctx 2048).
Server-side eval_count/eval_duration are the numbers of record.
Variants: TUNED x5 prompts @128 tok; T2 x2 prompts @128 (num_thread=2);
STOCK x1 prompt @32 (no num_thread) as the in-run comparison cell."""
import json, statistics, urllib.request

PROMPTS = [
    "What is 17 multiplied by 24? Answer with just the number.",
    "Write a haiku about a lighthouse in winter.",
    "Explain in two sentences why a hash function cannot be reversed.",
    "List the first ten prime numbers.",
    "Summarize in one sentence: The council verified the receipts, checked the hashes twice, and sealed the record before dawn.",
]
URL = "http://127.0.0.1:11434/api/generate"

def run(prompt, opts):
    body = json.dumps({"model": "qwen3:0.6b", "prompt": prompt, "stream": False,
                       "options": opts}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    ec, ed = d.get("eval_count", 0), d.get("eval_duration", 0)
    pc, pd = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 0)
    ld = d.get("load_duration", 0) / 1e9
    rate = ec / (ed / 1e9) if ed else 0.0
    prate = pc / (pd / 1e9) if pd else 0.0
    return rate, ec, ed / 1e9, prate, pc, ld

base = {"num_predict": 128, "seed": 42, "temperature": 0, "num_ctx": 2048}
rates = []
for i, p in enumerate(PROMPTS, 1):
    o = dict(base); o["num_thread"] = 4
    rate, ec, es, prate, pc, ld = run(p, o)
    rates.append(rate)
    print(f"TUNED RUN {i}: gen {rate:.2f} tok/s ({ec} tok in {es:.2f} s), prompt {prate:.1f} tok/s ({pc} tok), load {ld:.2f} s")
print(f"TUNED MEDIAN gen {statistics.median(rates):.2f} tok/s; runs: " + ", ".join(f"{r:.2f}" for r in rates))

rates2 = []
for i, p in enumerate(PROMPTS[:2], 1):
    o = dict(base); o["num_thread"] = 2
    rate, ec, es, prate, pc, ld = run(p, o)
    rates2.append(rate)
    print(f"T2 RUN {i}: gen {rate:.2f} tok/s ({ec} tok in {es:.2f} s)")
print(f"T2 MEDIAN gen {statistics.median(rates2):.2f} tok/s")

o = {"num_predict": 32, "seed": 42, "temperature": 0}
rate, ec, es, prate, pc, ld = run(PROMPTS[0], o)
print(f"STOCK RUN: gen {rate:.2f} tok/s ({ec} tok in {es:.2f} s), load {ld:.2f} s")
print("INFERFINAL DONE")
