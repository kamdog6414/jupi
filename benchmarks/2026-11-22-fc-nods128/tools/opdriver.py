#!/usr/bin/env python3
# opdriver.py NAME ICDJSON OPS CHUNK : run test-backend-ops case-by-chunk on Vulkan0 so one abort doesn't hide the rest.
# Records per case: OK / FAIL / CRASH / NOTRUN. Stops everything if dmesg shows an amdgpu ring timeout or reset.
import os, re, subprocess, sys, json, time
name, icd, ops, chunk = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
D = os.environ.get("NODS_OUT","./tests"); os.makedirs(D, exist_ok=True)
TBO = os.environ.get("TBO","test-backend-ops")
env = dict(os.environ, VK_ICD_FILENAMES=icd)
ansi = re.compile(r"\x1b\[[0-9;]*m")
def dmesg_bad():
    out = subprocess.run(["sudo","-n","dmesg"],capture_output=True,text=True).stdout
    return [l for l in out.splitlines() if re.search(r"amdgpu.*(ring .*timeout|GPU reset|Recovery|hang)", l)]
bad0 = len(dmesg_bad())
def memavail():
    return int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1])//1024
sup = subprocess.run([TBO,"support","-b","Vulkan0","-o",ops],env=env,capture_output=True,text=True,timeout=300).stdout
cases = [ansi.sub("",l).strip().rsplit(":",1)[0] for l in sup.splitlines() if "SUPPORTED" in ansi.sub("",l) and "NOT SUPPORTED" not in ansi.sub("",l) and "(" in l]
res = {}; i = 0; log = open(f"{D}/{name}.log","w")
while i < len(cases):
    if memavail() < 1500: log.write(f"PAUSE mem {memavail()}\n"); time.sleep(30); continue
    part = cases[i:i+chunk]
    p = subprocess.run(["timeout","-s","KILL","300","nice","-n","5",TBO,"test","-b","Vulkan0","-o",",".join(part)],env=env,capture_output=True,text=True)
    log.write(p.stdout[-20000:]); log.write(p.stderr[-3000:])
    done = {}
    for l in p.stdout.splitlines():
        l2 = ansi.sub("",l).strip()
        m = re.match(r"(?:\[\w+\].*?\s)?\s*(\w+\(.*\)):\s*(OK|FAIL)\s*$", l2)
        if m: done[m.group(1)] = m.group(2)
    for c in part:
        if c in done: res[c] = done[c]
    nxt = next((k for k,c in enumerate(part) if c not in done), None)
    if nxt is None: i += len(part)
    else:
        res[part[nxt]] = "CRASH"; log.write(f"CRASH at {part[nxt]} rc={p.returncode}\n"); i += nxt + 1
    if len(dmesg_bad()) > bad0:
        log.write("STOP: amdgpu ring timeout/reset in dmesg\n"); break
for c in cases: res.setdefault(c, "NOTRUN")
cnt = {k: sum(1 for v in res.values() if v == k) for k in ("OK","FAIL","CRASH","NOTRUN")}
json.dump({"name":name,"icd":icd,"ops":ops,"n":len(cases),"counts":cnt,"results":res,"dmesg_new_bad":len(dmesg_bad())-bad0},open(f"{D}/{name}.json","w"),indent=0)
print(name, len(cases), cnt, "dmesg_new_bad", len(dmesg_bad())-bad0)
