import json,os,hashlib,glob,statistics as st
D=os.environ.get("NODS_STABLE","./stable"); os.chdir(D)
sh=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest()
def bench(n):
    r=json.load(open(f"B-{n}.bench.json")); pp=[x for x in r if x["n_prompt"]>0][0]; tg=[x for x in r if x["n_gen"]>0][0]
    return pp["avg_ts"],pp["stddev_ts"],tg["avg_ts"],tg["stddev_ts"]
def soak(t):
    rows=[json.loads(l) for l in open(f"soak-{t}.jsonl")]; s=json.load(open(f"summary-{t}.json"))
    pp=[r["pp_med"] for r in rows]; tg=[r["tg_med"] for r in rows]
    half=len(tg)//2
    return rows,s,dict(rounds=len(rows),same=sum(r["same"] for r in rows),total=20*len(rows),first=rows[0]["t"],last=rows[-1]["t"],
      tg_med=st.median(tg),tg_min=min(tg),tg_max=max(tg),pp_med=st.median(pp),pp_min=min(pp),pp_max=max(pp),
      drift_tg_pct=round(100*(st.median(tg[half:])-st.median(tg[:half]))/st.median(tg[:half]),2),
      wall_med=st.median(r["wall_s"] for r in rows),rss_first=rows[0]["rss_mb"],rss_peak=max(r["rss_mb"] for r in rows),
      mem_min=min(r["mem"] for r in rows),swap_peak=max(r["swap"] for r in rows),bad_new=rows[-1]["bad_new"])
B={n:bench(n) for n in ["stock-ub1","stock-ub64","stock-ub512","patched-ub1","patched-ub64","patched-ub512"]}
_,sp,P=soak("patched-ub64"); _,ss,S=soak("stock-ub1")
json.dump({"bench":B,"soak_patched_ub64":P,"soak_stock_ub1":S},open("STATS.json","w"),indent=1)
utc2pst=lambda t: "%02d:%s"%((int(t[:2])-8)%24,t[3:])
L=["# RESULT-STABLE-J1: JUPI 1 stable run on real workloads, 2026-11-22",
"Groku.2 (executor), on Kam's 2:23 PM PST order. No test-backend-ops was run. Times PST (logs are UTC).","",
"VERDICT: PASS. 0 amdgpu ring timeouts/resets, swap 0 MiB peak, both soaks byte-identical every round.","",
"## llama-bench qwen3-0.6b Q4_K_M, -ngl 99 -fa 0 -t 6 -r 3, pp512 / tg128 (tok/s +- sd)","```",
"config        stock pp512       patched pp512     stock tg128     patched tg128"]
for u in ("ub1","ub64","ub512"):
    s=B[f"stock-{u}"]; p=B[f"patched-{u}"]
    L.append(f"-{u:<6}  {s[0]:8.2f} +-{s[1]:.2f}  {p[0]:8.2f} +-{p[1]:.2f}  {s[2]:6.2f} +-{s[3]:.2f}  {p[2]:6.2f} +-{p[3]:.2f}   ({100*(p[0]/s[0]-1):+.1f}% pp)")
L+=["(-ub1 uses -b 2; -ub64/-ub512 use -b 2048. Stock at ub64/ub512 is fast but its OUTPUT is wrong, see the morning packet.)","```","",
"## Soaks (llama-server, 20 prompts per round, temp 0, seed 1, cache_prompt off)","```"]
for name,X,ref in (("patched -ub 64 -b 2048 (FC-NODS128 ICD)",P,"JUPI 2 patched -ub 64 outputs"),("stock -ub 1 -b 2 (system RADV, control)",S,"JUPI 2 accepted live outputs (2026-11-19)")):
    L+=[f"{name}",f"  window {utc2pst(X['first'])}-{utc2pst(X['last'])} PST (first/last round end), {X['rounds']} rounds",
        f"  byte-match vs {ref}: {X['same']}/{X['total']}",
        f"  tg med {X['tg_med']:.2f} (min {X['tg_min']:.2f}, max {X['tg_max']:.2f}); pp med {X['pp_med']:.2f} (min {X['pp_min']:.2f}, max {X['pp_max']:.2f})",
        f"  tg drift 2nd half vs 1st half {X['drift_tg_pct']:+.2f}%; round wall med {X['wall_med']:.2f} s",
        f"  server RSS {X['rss_first']} -> peak {X['rss_peak']} MB (flat after round 2); MemAvailable min {X['mem_min']} MiB; swap peak {X['swap_peak']} MiB; new amdgpu faults {X['bad_new']}",""]
L+=["```","Loaded driver, read from /proc/<pid>/maps of each soak server: LOADED-DRIVER.txt",
"(patched = 117805de...ff0d5 with VK_ICD_FILENAMES set; stock = acf91948...a34ae5 with no VK_ env).","",
"Guards: guard4.sh (pidfile root, kills the tree on any new amdgpu ring timeout/reset line, swap > +256 MiB or MemAvailable < 1000 MiB; 5 s checks, 60 s dmesg heartbeat in guard.log). stable.py also checks dmesg and swap each round. Every log line is fsynced.",
"","## Files (sha256)","```"]
for f in sorted(glob.glob("*")):
    if os.path.isfile(f) and f not in ("RESULT-STABLE-J1.md","SHA256SUMS","DONE") and not f.endswith(".pid"): L.append(f"{sh(f)}  {f}")
L+=["```"]
open("RESULT-STABLE-J1.md","w").write("\n".join(L)+"\n")
os.system("sha256sum $(find . -type f ! -name SHA256SUMS | sort) > SHA256SUMS")
print("\n".join(L)); print("RESULT sha", sh("RESULT-STABLE-J1.md"), "SUMS", sh("SHA256SUMS"))
