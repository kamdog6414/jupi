#!/usr/bin/env python3
# stockdrv.py: STOCK system RADV (VK_ICD_FILENAMES removed) MUL_MAT sweep on JUPI 1, chunks of 40.
# Before each chunk, CURRENT.txt gets the exact case list (fsync), so a hang shows which chunk it was in.
# The log is appended and fsynced after every chunk. Stops on any new amdgpu ring timeout/reset. Then CRASH cases are re-run one by one, also logged.
import os, re, subprocess, json, time
D=os.environ.get("NODS_OUT","./stock-sweep"); os.makedirs(D, exist_ok=True)
TBO=os.environ.get("TBO","test-backend-ops")
env=dict(os.environ); env.pop("VK_ICD_FILENAMES",None)
ansi=re.compile(r"\x1b\[[0-9;]*m")
def bad(): return len([l for l in subprocess.run(["sudo","-n","dmesg"],capture_output=True,text=True).stdout.splitlines() if re.search(r"amdgpu.*(ring .*timeout|GPU reset|Recovery|hang)",l)])
def memavail(): return int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1])//1024
def wsync(path, text, mode="a"):
    with open(path, mode) as f: f.write(text); f.flush(); os.fsync(f.fileno())
B0=bad(); LOG=f"{D}/sweep.log"; wsync(LOG, f"{time.strftime('%T')} START stock bad0={B0}\n")
sup=subprocess.run([TBO,"support","-b","Vulkan0","-o","MUL_MAT"],env=env,capture_output=True,text=True,timeout=300).stdout
cases=[ansi.sub("",l).strip().rsplit(":",1)[0] for l in sup.splitlines() if "SUPPORTED" in ansi.sub("",l) and "NOT SUPPORTED" not in ansi.sub("",l) and "(" in l]
wsync(LOG, f"cases {len(cases)}\n")
def run(part, tag):
    wsync(f"{D}/CURRENT.txt", f"{time.strftime('%T')} {tag}\n" + "\n".join(part) + "\n", "w")
    p=subprocess.run(["timeout","-s","KILL","300","nice","-n","5",TBO,"test","-b","Vulkan0","-o",",".join(part)],env=env,capture_output=True,text=True)
    done={}
    for l in p.stdout.splitlines():
        l2=ansi.sub("",l).strip(); m=re.match(r"(?:\[\w+\].*?\s)?\s*(\w+\(.*\)):\s*(OK|FAIL)\s*$", l2)
        if m: done[m.group(1)]=m.group(2)
        elif re.search(r"\): not supported \[CPU\]", l2): done[l2.split(":")[0].strip()]="SKIP_CPU"
    tail=(p.stderr.strip().splitlines() or [""])[-1][:160]
    wsync(LOG, f"{time.strftime('%T')} {tag} rc={p.returncode} n={len(part)} ok={sum(v=='OK' for v in done.values())} fail={sum(v=='FAIL' for v in done.values())} mem={memavail()} bad_new={bad()-B0} | {tail}\n")
    return done, p.returncode
res={}; i=0; stop=False; k=0
while i < len(cases):
    while memavail() < 1500: time.sleep(30)
    part=cases[i:i+40]; k+=1; done,rc=run(part, f"chunk{k} [{i}:{i+len(part)}]")
    for c in part:
        if c in done: res[c]=done[c]
    nxt=next((j for j,c in enumerate(part) if c not in done), None)
    if nxt is None: i+=len(part)
    else: res[part[nxt]]="CRASH"; wsync(LOG, f"CRASH at {part[nxt]}\n"); i+=nxt+1
    if bad()>B0: wsync(LOG, f"STOP: amdgpu ring timeout/reset after chunk{k}; hung chunk = CURRENT.txt\n"); stop=True; break
if not stop:
    for c in [c for c,v in res.items() if v=="CRASH"]:
        done,rc=run([c], "solo")
        res[c]=done.get(c,"CRASH")
        if bad()>B0: wsync(LOG, f"STOP: amdgpu ring timeout/reset in solo {c}\n"); stop=True; break
for c in cases: res.setdefault(c,"NOTRUN")
cnt={v:sum(1 for x in res.values() if x==v) for v in ("OK","FAIL","CRASH","NOTRUN","SKIP_CPU")}
json.dump({"name":"mm-stock-j1","icd":"system","n":len(cases),"final_counts":cnt,"stopped":stop,"dmesg_new_bad":bad()-B0,"results":res},open(f"{D}/mm-stock-j1-final.json","w"),indent=0)
wsync(LOG, f"{time.strftime('%T')} END counts={cnt} stopped={stop} bad_new={bad()-B0}\n")
