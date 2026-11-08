#!/usr/bin/env python3
"""JUPI inference bench: qwen3:0.6b via the local ollama API.
Server-side eval_count/eval_duration are the numbers of record."""
import json, statistics, urllib.request

PROMPTS = [
    "What is 17 multiplied by 24? Answer with just the number.",
    "Write a haiku about a lighthouse in winter.",
    "Explain in two sentences why a hash function cannot be reversed.",
    "List the first ten prime numbers.",
    "Summarize in one sentence: The council verified the receipts, checked the hashes twice, and sealed the record before dawn.",
]
URL = "http://127.0.0.1:11434/api/generate"
rates = []
for i, p in enumerate(PROMPTS, 1):
    body = json.dumps({"model": "qwen3:0.6b", "prompt": p, "stream": False,
                       "options": {"num_predict": 128, "seed": 42, "temperature": 0}}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    ec, ed = d.get("eval_count", 0), d.get("eval_duration", 0)
    pc, pd = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 0)
    rate = ec / (ed / 1e9) if ed else 0.0
    prate = pc / (pd / 1e9) if pd else 0.0
    rates.append(rate)
    print(f"RUN {i}: gen {rate:.2f} tok/s ({ec} tok in {ed/1e9:.2f} s), prompt {prate:.1f} tok/s ({pc} tok)")
print(f"MEDIAN gen {statistics.median(rates):.2f} tok/s; runs: " + ", ".join(f"{r:.2f}" for r in rates))
print("INFERBENCH DONE")
