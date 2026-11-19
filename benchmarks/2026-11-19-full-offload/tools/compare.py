# Reproduces ../COMPARISON.txt from ../data. usage: python3 compare.py > ../COMPARISON.txt
import json, os, statistics as st
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","data")
def ld(n): return {r["id"]:r for r in map(json.loads,open(os.path.join(D,n)))}
A=ld("A-old-live-nkvo-20.jsonl"); B=ld("B-full-offload-test-20.jsonl"); C=ld("C-cpu-reference-20.jsonl"); L=ld("D-full-offload-live-20.jsonl")
def div(a,b):
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y: return i
    return "-" if len(a)==len(b) else min(len(a),len(b))
print("A = old live (-nkvo -ub 8 -b 8)   B = full offload, test window   C = CPU reference (-ngl 0)   D = full offload, live service")
print("div = first differing character index, '-' = byte-identical\n")
print(f"{'id':9} {'n_prompt':>8} {'A tg':>7} {'B tg':>7} {'D tg':>7} {'C tg':>7}  {'D vs A':>6} {'D vs B':>6} {'A vs C':>6} {'D vs C':>6}")
for k in A:
    print(f"{k:9} {A[k]['n_prompt']:>8} {A[k]['tg_tps']:>7} {B[k]['tg_tps']:>7} {L[k]['tg_tps']:>7} {C[k]['tg_tps']:>7}  {div(L[k]['content'],A[k]['content']):>6} {div(L[k]['content'],B[k]['content']):>6} {div(A[k]['content'],C[k]['content']):>6} {div(L[k]['content'],C[k]['content']):>6}")
def same(X,Y): return sum(X[k]["content"]==Y[k]["content"] for k in A)
print(f"\nbyte-identical  D vs A {same(L,A)}/20   D vs B {same(L,B)}/20   B vs A {same(B,A)}/20   A vs C {same(A,C)}/20   D vs C {same(L,C)}/20")
for n,X in (("A old live",A),("B full offload test",B),("D full offload live",L),("C CPU reference",C)):
    t=[r["tg_tps"] for r in X.values()]; p=[r["pp_tps"] for r in X.values()]
    print(f"{n:22} tg tok/s min {min(t):6.2f}  median {st.median(t):6.2f}  max {max(t):6.2f}   pp median {st.median(p):6.2f}")
print("\n2048-context check (truth: Day 37 temperature = 10 degrees)")
for n,f in (("E full offload test","E-deep2048-full-offload-test.jsonl"),("F old live","F-deep2048-old-live-nkvo.jsonl"),("G full offload live","G-deep2048-full-offload-live.jsonl")):
    r=json.loads(open(os.path.join(D,f)).readline())
    print(f"{n:20} n_prompt {r['n_prompt']}  n_pred {r['n_pred']}  tg {r['tg_tps']:6.2f}  pp {r['pp_tps']:6.2f}  starts {r['content'][:13]!r}")
e,fo,g=[json.loads(open(os.path.join(D,x)).readline())["content"] for x in ("E-deep2048-full-offload-test.jsonl","F-deep2048-old-live-nkvo.jsonl","G-deep2048-full-offload-live.jsonl")]
print(f"E==F {e==fo}   G==F {g==fo}")
