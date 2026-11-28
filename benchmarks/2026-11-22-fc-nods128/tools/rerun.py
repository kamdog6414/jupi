# rerun.py NAME : re-run each CRASH/NOTRUN case of tests/NAME.json alone (crashes in chunks are often context: CS rejected -2 after earlier big cases)
import json,os,re,subprocess,sys,time
D=os.environ.get("NODS_OUT","./tests"); TBO=os.environ.get("TBO","test-backend-ops")
j=json.load(open(f"{D}/{sys.argv[1]}.json")); env=dict(os.environ,VK_ICD_FILENAMES=j["icd"])
ansi=re.compile(r"\x1b\[[0-9;]*m"); res=dict(j["results"]); log=open(f"{D}/{sys.argv[1]}-rerun.log","w")
def memavail(): return int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1])//1024
for c,v in j["results"].items():
    if v not in ("CRASH","NOTRUN"): continue
    while memavail()<1500: time.sleep(30)
    p=subprocess.run(["timeout","-s","KILL","300","nice","-n","5",TBO,"test","-b","Vulkan0","-o",c],env=env,capture_output=True,text=True)
    o=ansi.sub("",p.stdout); r="SKIP_CPU" if re.search(r"\): not supported \[CPU\]",o) else "OK" if re.search(r"\): OK\s*$",o,re.M) else "FAIL" if re.search(r"\): FAIL\s*$",o,re.M) else "CRASH"
    tail=(p.stderr.strip().splitlines() or [""])[-1][:160]
    res[c]=r; log.write(f"{r} rc={p.returncode} {c} | {tail}\n"); log.flush()
cnt={k:sum(1 for v in res.values() if v==k) for k in ("OK","FAIL","CRASH","NOTRUN","SKIP_CPU")}
json.dump({"name":j["name"],"icd":j["icd"],"chunk_counts":j["counts"],"final_counts":cnt,"results":res},open(f"{D}/{sys.argv[1]}-final.json","w"),indent=0)
print(sys.argv[1],"chunk",j["counts"],"final",cnt)
