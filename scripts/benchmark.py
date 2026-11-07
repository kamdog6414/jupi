#!/usr/bin/python3
"""JUPI bounded, repeatable instrument benchmarks and offline qualification."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid

BASE=Path('/var/lib/jupi-agent/benchmarks')
LIB=Path('/usr/local/lib/jupi-agent')
SSH=['ssh','-T','-F','/etc/jupi/ssh/roach.conf','-o','BatchMode=yes','-o','ClearAllForwardings=yes','-o','LogLevel=ERROR','-o','Compression=no','jupi-peer']


def utc():return datetime.now(timezone.utc).isoformat()
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    temp=p.with_name('.'+p.name+'.'+str(uuid.uuid4()))
    with temp.open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,p)


def resources():
    mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.split(':')[0] in ('MemAvailable','SwapFree','SwapTotal')}
    sensors=[]
    for hw in Path('/sys/class/hwmon').glob('hwmon*'):
        if not (hw/'name').exists() or (hw/'name').read_text().strip()!='k10temp':continue
        p=hw/'temp1_input'
        if not p.exists():continue
        sensors.append({'path':str(p),'relative_Tctl':int(p.read_text())/1000,'critical_raw':int((hw/'temp1_crit').read_text()) if (hw/'temp1_crit').exists() else None,'critical_alarm':int((hw/'temp1_crit_alarm').read_text()) if (hw/'temp1_crit_alarm').exists() else None})
    return {'utc':utc(),'memory':mem,'sensors':sensors,'load':os.getloadavg()}


def guard(sample):
    if sample['memory']['MemAvailable']<512*1024**2:return 'Available memory below 512 MiB'
    for s in sample['sensors']:
        if s['critical_alarm']:return 'Kernel critical thermal alarm'
        if s['critical_raw'] and s['relative_Tctl']*1000>=s['critical_raw']-5000:return 'Relative Tctl within 5 control degrees of exported critical limit'
    return None


class Runner:
    def __init__(self,directory):self.directory=directory;self.items=[];self.phase='idle';self.stop=threading.Event();self.abort=None
    def sample(self):
        with (self.directory/'telemetry.jsonl').open('x') as f:
            while not self.stop.is_set():
                v=resources();v['phase']=self.phase;f.write(json.dumps(v)+'\n');f.flush()
                self.abort=guard(v) or self.abort
                self.stop.wait(1)
    def run(self,name,argv,timeout=60,env=None):
        if self.abort:raise RuntimeError(self.abort)
        self.phase=name;print(json.dumps({'stage':name,'utc':utc()}),flush=True)
        started=time.monotonic()
        with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
            p=subprocess.Popen(argv,stdout=out,stderr=err,env=env,start_new_session=True)
            try:
                while p.poll() is None:
                    if self.abort:raise RuntimeError(self.abort)
                    if time.monotonic()-started>timeout:raise TimeoutError(name)
                    time.sleep(.1)
            finally:
                if p.poll() is None:
                    os.killpg(p.pid,signal.SIGKILL);p.wait()
            out.seek(0);err.seek(0);stdout=out.read(2*1024*1024).decode(errors='replace');stderr=err.read(1024*1024).decode(errors='replace')
        record={'name':name,'argv':argv,'returncode':p.returncode,'wall_seconds':time.monotonic()-started,'stdout':stdout,'stderr':stderr}
        self.items.append(record);save(self.directory/'raw.json',self.items)
        if p.returncode:raise RuntimeError(name+' failed: '+stderr[-1000:])
        return stdout


def worker(kind,threads,backend):
    if kind in ('matrix','memory'):
        import numpy as np
        if kind=='matrix':
            n=384;rng=np.random.default_rng(14);a=rng.normal(size=(n,n));b=rng.normal(size=(n,n));c=a@b
            times=[]
            for _ in range(3):
                t=time.perf_counter();c=a@b;times.append(time.perf_counter()-t)
            ref=float(np.dot(a[0,:],b[:,0]));assert abs(float(c[0,0])-ref)<1e-9
            print(json.dumps({'threads_requested':threads,'backend_requested':backend,'n':n,'seconds':times,'median_GFLOP_s':2*n**3/statistics.median(times)/1e9,'validation_error':abs(float(c[0,0])-ref),'loaded_math_libraries':[line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if any(x in line for x in ('libblas','libcblas','libopenblas'))]}))
        else:
            n=8*1024**2;a=np.full(n,1.25);b=np.full(n,2.5);c=np.empty(n);np.add(a,b,out=c);times=[]
            for _ in range(3):
                t=time.perf_counter()
                for _ in range(16):np.add(a,b,out=c)
                times.append(time.perf_counter()-t)
            assert np.all(c==3.75)
            print(json.dumps({'working_set_bytes':3*n*8,'iterations':16,'seconds':times,'nominal_GB_s':[3*n*8*16/t/1e9 for t in times],'validation':'all 8388608 sums exact','scope':'Three nominal float64 array transfers; cache effects remain part of this process benchmark'}))
    elif kind=='network':
        chunk=bytes(range(256))*4096;raw=chunk*32;expected=hashlib.sha256(raw).hexdigest();results=[]
        upload="import sys,hashlib,json;d=sys.stdin.buffer.read(33554433);assert len(d)==33554432;print(json.dumps({'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}))"
        download="import sys;d=bytes(range(256))*4096;[sys.stdout.buffer.write(d) for _ in range(32)]"
        for trial in range(3):
            t=time.monotonic();r=subprocess.run(SSH+[shlex.join(['python3','-B','-c',upload])],input=raw,capture_output=True,timeout=60,check=True);dt=time.monotonic()-t;v=json.loads(r.stdout);assert v['sha256']==expected
            results.append({'direction':'upload','trial':trial,'bytes':len(raw),'seconds':dt,'Mbit_s':len(raw)*8/dt/1e6,'sha256':v['sha256']})
            t=time.monotonic();r=subprocess.run(SSH+[shlex.join(['python3','-B','-c',download])],capture_output=True,timeout=60,check=True);dt=time.monotonic()-t;assert len(r.stdout)==len(raw) and hashlib.sha256(r.stdout).hexdigest()==expected
            results.append({'direction':'download','trial':trial,'bytes':len(raw),'seconds':dt,'Mbit_s':len(raw)*8/dt/1e6,'sha256':expected})
        print(json.dumps({'results':results,'scope':'Application throughput through pinned SSH including handshake, Python copying and hashing; compression disabled; not raw Ethernet throughput'}))


def local_request(payload):
    req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as r:v=json.loads(r.read(1024*1024))
    assert v['done'];return v


def model_bench():
    rows=[]
    for threads in (1,2,3,4):
        for trial in range(3):
            v=local_request({'model':'qwen3:0.6b','prompt':'List practical Linux instrument checks. Use short sentences and continue until the token limit.','stream':False,'think':False,'keep_alive':'60s','options':{'num_ctx':2048,'num_predict':48,'num_thread':threads,'temperature':0,'seed':14}})
            rows.append({'threads':threads,'trial':trial,**{k:v.get(k) for k in ('eval_count','eval_duration','prompt_eval_count','prompt_eval_duration','load_duration','total_duration')},'tokens_per_second':v['eval_count']/(v['eval_duration']/1e9),'response_sha256':hashlib.sha256(v['response'].encode()).hexdigest()})
    print(json.dumps({'model':'qwen3:0.6b','results':rows,'scope':'Host Ollama service, explicit thread counts and current inherited affinity. CPUQuota is unsupported by this kernel. Output tokens, not model quality.'}))


def offline(directory):
    directory=Path(directory).resolve();assert directory.parent==BASE and str(uuid.UUID(directory.name))==directory.name
    host_netns=json.loads((directory/'host-network-namespace.json').read_text())['host_network_namespace']
    assert str(Path('/proc/self/ns/net').readlink())!=host_netns,'Network namespace was not isolated'
    state=directory/'offline-agent';state.mkdir(mode=0o700);home=directory/'offline-home';home.mkdir(mode=0o700)
    env=dict(os.environ,HOME=str(home),OLLAMA_HOST='127.0.0.1:11434',OLLAMA_MODELS='/var/lib/ollama',OLLAMA_NO_CLOUD='1',OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',JUPI_AGENT_STATE=str(state),JUPI_AGENT_SOCKET=str(state/'control.sock'))
    procs=[];logs=[]
    def cli(*args):return json.loads(subprocess.check_output([str(LIB/'runtime.py'),*args],env=env,text=True,timeout=180))
    def wait(identifier):return cli('wait',identifier,'--timeout','160')
    try:
        for name,args in [('model',['/usr/bin/ollama','serve']),('agent',[str(LIB/'runtime.py'),'serve'])]:
            f=(directory/('offline-'+name+'.log')).open('x');logs.append(f);procs.append(subprocess.Popen(args,env=env,stdout=f,stderr=f,start_new_session=True))
        deadline=time.monotonic()+60
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=1) as r:models=json.loads(r.read())
                break
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.5)
        cli('remember','offline-proof','persistent local instrument state')
        prompt=wait(cli('prompt','Return exactly JUPI_OFFLINE_READY.')['id']);assert prompt['status']=='succeeded'
        cmd=wait(cli('run','--timeout','30','--','/usr/local/bin/jupi-unix','translate','ls -lah','--to','powershell','--json')['id']);assert cmd['status']=='succeeded'
        gpu=wait(cli('run','--timeout','30','--',str(LIB/'opencl-probe'))['id']);assert gpu['status']=='succeeded' and 'mismatches=0' in gpu['output']
        rover_job=wait(cli('run','--timeout','30','--','/usr/local/bin/jupi-rover','demo','--output',str(state/'rover-output'))['id']);assert rover_job['status']=='succeeded'
        art=cli('art','--scene','facade','--width','81','--height','41','--seed','14');art_job=wait(art['id']);assert art_job['status']=='succeeded'
        subprocess.run(['/usr/local/bin/jupi-art','verify','--output',art['directory']],check=True,capture_output=True,text=True)
        procs[1].terminate();procs[1].wait(timeout=20)
        procs[1]=subprocess.Popen([str(LIB/'runtime.py'),'serve'],env=env,stdout=logs[1],stderr=logs[1],start_new_session=True)
        recalled=cli('recall','offline-proof');assert recalled['value']=='persistent local instrument state'
        assert cli('job',art['id'])['status']=='succeeded'
        with socket.socket() as s:s.settimeout(2);peer_error=s.connect_ex(('192.168.77.3',22))
        assert peer_error!=0
        result={'utc':utc(),'network_namespace':str(Path('/proc/self/ns/net').readlink()),'host_network_namespace':host_netns,'interfaces':{p.name:(p/'operstate').read_text().strip() for p in Path('/sys/class/net').iterdir()},'ipv4_routes':Path('/proc/net/route').read_text(),'peer_connect_errno':peer_error,'local_models':models,'prompt':prompt,'translated_reference':cmd,'rover_job':rover_job,'gpu_job':gpu,'art':art,'art_job':art_job,'memory_after_agent_restart':recalled,'job_record_after_restart':'succeeded','live_host_agent_restarted':False,'scope':'Separate instances of installed native agent and model inside PrivateNetwork=yes; live SDK/SSH/agent untouched. Hybrid science requires the peer and is not claimed offline.'}
        save(directory/'offline.json',result);print(json.dumps({'offline':'pass','directory':str(directory),'peer_connect_errno':peer_error}))
    finally:
        for p in procs:
            try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=15)
            except (ProcessLookupError,subprocess.TimeoutExpired):
                try:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
                except ProcessLookupError:pass
        for f in logs:f.close()


def bench():
    os.umask(0o077);BASE.mkdir(mode=0o700,exist_ok=True);d=BASE/str(uuid.uuid4());d.mkdir(mode=0o700)
    if guard(resources()):raise RuntimeError(guard(resources()))
    for mount,reserve in [('/',20*1024**3),('/ps4hdd',16*1024**3+512*1024**2)]:
        v=os.statvfs(mount);assert v.f_bavail*v.f_frsize>reserve,'Insufficient headroom: '+mount
    manifest={'utc':utc(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'sources':{str(p):digest(p) for p in [Path(__file__),LIB/'benchmark-opencl',LIB/'benchmark-gles',LIB/'runtime.py',Path('/etc/jupi/science.json'),Path('/etc/jupi/art.json')]},'repeats':3,'background_services_retained':True,'overclock_or_voltage_changes':False,'hardware_timing_scope':'OS monotonic wall timing, not hardware counters','desktop_glx':'Unverified on current Xorg; no display restart','storage_scope':'256 MiB private regular file on the live ext4/loop/crypt/UFS stack; no global cache drops, raw devices or block layout changes','thermal_scope':'relative k10temp Tctl control value, not calibrated die temperature; no fan or power measurements exposed'}
    manifest['cpu_bandwidth_control_available']=Path('/sys/fs/cgroup/system.slice/jupi-agent.service/cpu.max').exists()
    manifest['service_cpu_affinity']={}
    for unit in ('jupi-agent.service','ollama.service'):
        pid=int(subprocess.check_output(['systemctl','show','-p','MainPID','--value',unit],text=True));manifest['service_cpu_affinity'][unit]=sorted(os.sched_getaffinity(pid))
    save(d/'host-network-namespace.json',{'utc':utc(),'host_network_namespace':str(Path('/proc/self/ns/net').readlink())})
    save(d/'manifest.json',manifest);r=Runner(d);monitor=threading.Thread(target=r.sample,daemon=True);monitor.start();errors=[]
    try:
        r.run('inventory',['lscpu']);r.run('versions',['pacman','-Q','sysbench','fio','iperf3','openblas','ffmpeg','gimp','python-numpy','ollama'])
        for trial in range(3):
            for threads in ((1,2,4,8) if trial%2==0 else (8,4,2,1)):
                r.run(f'cpu-t{threads}-r{trial}',['sysbench','--time=3','--events=0',f'--threads={threads}','cpu','--cpu-max-prime=10000','run'],20)
        r.run('memory',[sys.executable,'-B',__file__,'worker','memory'],30)
        for backend in ('reference','openblas'):
            for threads in ((1,) if backend=='reference' else (1,2,4)):
                env=dict(os.environ,OPENBLAS_NUM_THREADS=str(threads),OMP_NUM_THREADS=str(threads))
                env.pop('LD_PRELOAD',None)
                if backend=='openblas':env['LD_PRELOAD']='/usr/lib/libopenblas.so'
                r.run(f'matrix-{backend}-t{threads}',[sys.executable,'-B',__file__,'worker','matrix','--threads',str(threads),'--backend',backend],60,env)
        for trial in range(3):
            r.run(f'gpu-opencl-r{trial}',[str(LIB/'benchmark-opencl')],30)
            for resolution in ('1280x720','1920x1080'):
                env=dict(os.environ,EGL_PLATFORM='surfaceless',LD_LIBRARY_PATH='/usr/local/lib/jupi-gpu-compat',JUPI_BENCH_RESOLUTION=resolution)
                r.run(f'gpu-gles-{resolution}-r{trial}',[str(LIB/'benchmark-gles'),'--output',str(d/f'gles-{resolution}-{trial}.ppm'),'--frames','180'],30,env)
        data=d/'io-test.bin'
        common=['fio','--filename='+str(data),'--size=256m','--ioengine=psync','--direct=1','--iodepth=1','--numjobs=1','--group_reporting','--output-format=json','--eta=never','--randrepeat=1']
        for trial in range(3):
            for mode,opts in [('seq-write',['--rw=write','--bs=1m','--end_fsync=1']),('seq-read',['--rw=read','--bs=1m']),('random-read',['--rw=randread','--bs=4k','--time_based=1','--runtime=5','--allow_file_create=0']),('sync-write',['--rw=randwrite','--bs=4k','--number_ios=64','--fsync=1','--allow_file_create=0'])]:
                r.run(f'io-{mode}-r{trial}',common+['--name='+mode]+opts,90)
        data.unlink()
        r.run('network',[sys.executable,'-B',__file__,'worker','network'],180)
        for threads in (1,2,4):
            for trial in range(3):
                r.run(f'encode-t{threads}-r{trial}',['ffmpeg','-hide_banner','-benchmark','-f','lavfi','-i','testsrc2=size=1280x720:rate=30','-frames:v','90','-c:v','libx264','-preset','veryfast','-threads',str(threads),'-f','null','-'],90)
        r.run('model',[sys.executable,'-B',__file__,'model'],240)
        unit='jupi-offline-'+d.name[:8]
        r.run('offline',['sudo','-n','systemd-run','--quiet','--wait','--pipe','--collect','--unit='+unit,'--property=User=pi','--property=Group=pi','--property=PrivateNetwork=yes','--property=NoNewPrivileges=yes','--property=ProtectKernelTunables=yes','--property=ProtectKernelModules=yes','--property=ReadOnlyPaths=/var/lib/ollama','--property=MemoryMax=2300M','--property=CPUQuota=300%','--property=TasksMax=96','--property=RuntimeMaxSec=300','/usr/bin/python3','-B',str(LIB/'benchmark.py'),'offline',str(d)],330)
    except Exception as e:errors.append({'type':type(e).__name__,'message':str(e),'phase':r.phase});raise
    finally:
        r.stop.set();monitor.join(timeout=5);manifest.update(finished_utc=utc(),errors=errors,completed_commands=len(r.items),guard_abort=r.abort);save(d/'manifest.json',manifest)
        save(BASE/'latest.json',{'directory':str(d),'finished_utc':manifest['finished_utc'],'errors':errors})
        print(json.dumps({'directory':str(d),'commands':len(r.items),'errors':errors}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    s.add_parser('run');s.add_parser('model')
    s.add_parser('status')
    report=s.add_parser('report');report.add_argument('directory');report.add_argument('--offline');report.add_argument('--native-math');report.add_argument('--plot',action='store_true')
    w=s.add_parser('worker');w.add_argument('kind',choices=('matrix','memory','network'));w.add_argument('--threads',type=int,default=1);w.add_argument('--backend',default='reference')
    o=s.add_parser('offline');o.add_argument('directory')
    a=p.parse_args()
    if a.mode=='run':bench()
    elif a.mode=='status':print((BASE/'latest.json').read_text())
    elif a.mode=='report':
        argv=[sys.executable,'-B',str(LIB/'benchmark_report.py'),a.directory]
        if a.offline:argv+=['--offline',a.offline]
        if a.native_math:argv+=['--native-math',a.native_math]
        if a.plot:argv+=['--plot']
        subprocess.run(argv,check=True)
    elif a.mode=='worker':worker(a.kind,a.threads,a.backend)
    elif a.mode=='model':model_bench()
    else:offline(a.directory)


if __name__=='__main__':main()
