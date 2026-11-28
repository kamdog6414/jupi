#!/usr/bin/env python3
# stable.py: JUPI 1 stable run on real workloads (NO test-backend-ops).
# 1) llama-bench pp512/tg128, -r 3: stock ub1/ub64/ub512, then patched ub1/ub64/ub512 (VK_ICD_FILENAMES per process only)
# 2) 60-min patched soak: llama-server -ub 64 -b 2048, the 20 prompts on repeat, temp 0 seed 1, byte-compare vs JUPI 2 patched ub64 reference
# 3) only if 2 is clean: 60-min stock control soak at -ub 1 -b 2 (stock batched output is garbage), vs JUPI 2 accepted live outputs
# Every log line is fsynced. Stops if guard writes ABORTED.
import json, os, subprocess, time, urllib.request, statistics as st, re, sys
W=os.environ.get("NODS_W","./work"); D=f"{W}/stable-20261122"; os.makedirs(D, exist_ok=True)
B=os.environ.get("LLAMA_BIN","./bin"); M=os.environ.get("MODEL","qwen3-0.6b-ollama.gguf")
SRV=f"{W}/from-jupi2/groku-infer/vk-server"; PAT=f"{W}/patched/radeon_icd.json"; K=f"{W}/from-jupi2/garlic-test"
PROMPTS=json.load(open(f"{K}/valkit/prompts20.json"))
def ref(path): return {json.loads(l)["id"]:json.loads(l)["content"] for l in open(path)}
REF_PAT=ref(f"{D}/ref/J2-A-patched-ub64.p20.jsonl"); REF_ACC=ref(f"{K}/switch-20261119T203111Z/live20_switched.jsonl")
LOG=f"{D}/run.log"; PORT=18797
def ts(): return time.strftime("%H:%M:%S")
def w(path, text):
    with open(path,"a") as f: f.write(text); f.flush(); os.fsync(f.fileno())
def L(msg): w(LOG, f"{ts()} {msg}\n")
def meminfo():
    m={l.split(":")[0]:int(l.split()[1]) for l in open("/proc/meminfo")}; return m["MemAvailable"]//1024, (m["SwapTotal"]-m["SwapFree"])//1024
def bad(): return len([l for l in subprocess.run(["sudo","-n","dmesg"],capture_output=True,text=True).stdout.splitlines() if re.search(r"amdgpu.*(ring .*timeout|GPU reset|Recovery|hang)",l)])
def aborted(): return os.path.exists(f"{D}/ABORTED")
def env_for(icd):
    e=dict(os.environ); e.pop("VK_ICD_FILENAMES",None); e.pop("VK_DRIVER_FILES",None)
    if icd: e["VK_ICD_FILENAMES"]=icd
    return e
B0=bad(); MA0,SW0=meminfo(); L(f"START bad0={B0} mem={MA0} swap0={SW0}")
# 1) bench
for name,icd,ub,b in [("stock-ub1",None,1,2),("stock-ub64",None,64,2048),("stock-ub512",None,512,2048),("patched-ub1",PAT,1,2),("patched-ub64",PAT,64,2048),("patched-ub512",PAT,512,2048)]:
    if aborted(): L("ABORTED seen, stop"); sys.exit(3)
    with open(f"{D}/B-{name}.bench.json","w") as o, open(f"{D}/B-{name}.bench.err","w") as e:
        rc=subprocess.run(["nice","-n","5",f"{B}/llama-bench","-m",M,"-ngl","99","-fa","0","-o","json","-p","512","-n","128","-ub",str(ub),"-b",str(b),"-t","6","-r","3"],env=env_for(icd),stdout=o,stderr=e).returncode
    try: rows=[(r["n_prompt"],r["n_gen"],round(r["avg_ts"],2),round(r["stddev_ts"],2)) for r in json.load(open(f"{D}/B-{name}.bench.json"))]
    except Exception as x: rows=str(x)
    ma,sw=meminfo(); L(f"BENCH {name} rc={rc} {rows} mem={ma} swap={sw} bad_new={bad()-B0}")
    if bad()>B0: L("STOP ring/reset after bench"); sys.exit(4)
# 2/3) soak
def post(body):
    r=urllib.request.Request(f"http://127.0.0.1:{PORT}/completion",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=120))
def soak(tag, icd, ub, b, refd, minutes):
    sl=f"{D}/soak-{tag}.jsonl"
    p=subprocess.Popen(["nice","-n","5",f"{SRV}/llama-server","-m",M,"--host","127.0.0.1","--port",str(PORT),"-np","1","--temp","0","--seed","1","--no-webui","--no-jinja","-ngl","99","-fa","off","-t","6","-c","2048","-ub",str(ub),"-b",str(b)],
        env=dict(env_for(icd),LD_LIBRARY_PATH=f"{SRV}:{B}",LLAMA_ARG_OFFLINE="1"),stdout=open(f"{D}/server-{tag}.log","w"),stderr=subprocess.STDOUT)
    w(f"{D}/server-{tag}.pid", f"{p.pid}\n")
    for _ in range(100):
        time.sleep(2)
        try:
            if json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health",timeout=5)).get("status")=="ok": break
        except Exception: pass
        if p.poll() is not None: L(f"SOAK {tag} server died rc={p.returncode}"); return False
    L(f"SOAK {tag} START pid={p.pid} ub={ub} b={b} icd={'patched' if icd else 'system'}")
    end=time.time()+minutes*60; rnd=0; clean=True
    while time.time()<end:
        if aborted(): L("ABORTED seen"); clean=False; break
        rnd+=1; t0=time.time(); same=0; diff=[]; tgs=[]; pps=[]
        for q in PROMPTS:
            d=post({"prompt":q["prompt"],"n_predict":q.get("n_predict",64),"temperature":0,"seed":1,"cache_prompt":False})
            if d["content"]==refd[q["id"]]: same+=1
            else: diff.append(q["id"])
            tgs.append(d["timings"]["predicted_per_second"]); pps.append(d["timings"]["prompt_per_second"])
        rss=int([l for l in open(f"/proc/{p.pid}/status") if l.startswith("VmRSS")][0].split()[1])//1024
        ma,sw=meminfo(); nb=bad()-B0
        rec={"tag":tag,"round":rnd,"t":ts(),"wall_s":round(time.time()-t0,2),"same":same,"diff":diff,"tg_med":round(st.median(tgs),2),"pp_med":round(st.median(pps),2),"rss_mb":rss,"mem":ma,"swap":sw,"bad_new":nb}
        w(sl, json.dumps(rec)+"\n")
        if nb>0: L(f"SOAK {tag} STOP ring/reset round {rnd}"); clean=False; break
        if sw-SW0>256: L(f"SOAK {tag} STOP swap {sw}"); clean=False; break
        if p.poll() is not None: L(f"SOAK {tag} server died"); clean=False; break
    p.terminate()
    try: p.wait(15)
    except Exception: p.kill(); p.wait()
    rows=[json.loads(l) for l in open(sl)]; tg=[r["tg_med"] for r in rows]
    other=sorted({x for r in rows for x in r["diff"]}-{"short-3"})
    ok_rounds=sum(1 for r in rows if r["same"]>=19); stdy=max(abs(x-tg[0])/tg[0] for x in tg) if tg else 1
    summ={"tag":tag,"rounds":len(rows),"clean":clean,"rounds_ge19":ok_rounds,"min_same":min(r["same"] for r in rows),"diff_ids":sorted({x for r in rows for x in r["diff"]}),"other_mismatch":other,
          "tg_min":min(tg),"tg_med":st.median(tg),"tg_max":max(tg),"tg_first":tg[0],"max_dev_vs_first":round(stdy,4),"swap_peak":max(r["swap"] for r in rows),"rss_peak":max(r["rss_mb"] for r in rows),"bad_new":rows[-1]["bad_new"]}
    w(f"{D}/summary-{tag}.json", json.dumps(summ,indent=1)+"\n"); L(f"SOAK {tag} END {json.dumps(summ)}")
    return clean and summ["bad_new"]==0
ok=soak("patched-ub64", PAT, 64, 2048, REF_PAT, 60)
if ok and not aborted(): soak("stock-ub1", None, 1, 2, REF_ACC, 60)
else: L("stock control soak SKIPPED (patched soak not clean)")
L(f"DONE bad_new={bad()-B0}"); w(f"{D}/DONE","")
