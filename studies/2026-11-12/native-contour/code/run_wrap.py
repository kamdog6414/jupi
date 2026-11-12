#!/usr/bin/env python3
"""Stdlib wrapper: preflight snapshot, run child, capture stdout/stderr, wall, child rusage. No installs."""
import json,os,resource,subprocess,sys,time
outjson,stdout_p,stderr_p=sys.argv[1],sys.argv[2],sys.argv[3];cmd=sys.argv[4:]
def mem():
 d={}
 for l in open('/proc/meminfo'):
  k,v=l.split(':');d[k]=int(v.split()[0])*1024
 return d
m=mem();sw=(m['SwapTotal']-m['SwapFree'])/m['SwapTotal']*100 if m['SwapTotal'] else 0.0
pre={'mem_available_bytes':m['MemAvailable'],'swap_used_pct':round(sw,3),'loadavg':open('/proc/loadavg').read().split()[:3],'nproc':os.cpu_count()}
gate={'mem_ge_256MiB':m['MemAvailable']>=256*1024*1024,'jupi_gate_mem_gt_800MB':m['MemAvailable']>800*1000*1000,'swap_lt_25pct':sw<25}
if not all(gate.values()):
 json.dump({'status':'HOLD_PREFLIGHT','pre':pre,'gate':gate,'cmd':cmd},open(outjson,'w'),indent=1);print('HOLD_PREFLIGHT');sys.exit(3)
t0=time.monotonic();w0=time.time()
with open(stdout_p,'wb') as so,open(stderr_p,'wb') as se:rc=subprocess.call(cmd,stdout=so,stderr=se)
wall=time.monotonic()-t0;ru=resource.getrusage(resource.RUSAGE_CHILDREN)
m2=mem()
json.dump({'status':'RAN','cmd':cmd,'returncode':rc,'start_unix':w0,'wall_s':wall,'child_utime_s':ru.ru_utime,'child_stime_s':ru.ru_stime,'child_maxrss_bytes':ru.ru_maxrss*1024,'pre':pre,'gate':gate,'post_mem_available_bytes':m2['MemAvailable'],'note':'/usr/bin/time not present on node; child rusage via stdlib resource.getrusage(RUSAGE_CHILDREN)'},open(outjson,'w'),indent=1)
print(open(stdout_p).read().strip());sys.exit(rc)
