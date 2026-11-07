#!/usr/bin/python3
"""Verify JUPI's measured baseline or run an explicit command with scoped BLAS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

CONFIG=Path('/etc/jupi/performance-profile.json')


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def load():
    stat=CONFIG.stat()
    if stat.st_uid!=0 or stat.st_mode&0o022:raise ValueError('Baseline must be root-owned and not writable by other users')
    value=json.loads(CONFIG.read_text())
    if value.get('schema')!='jupi.performance.profile.v1':raise ValueError('Unknown baseline schema')
    expected=value.pop('profile_id')
    actual=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if expected!=actual:raise ValueError('Baseline content hash differs')
    value['profile_id']=expected;return value


def verify(value):
    drift=[]
    for path,expected in value['files_sha256'].items():
        try:
            if sha(path)!=expected:drift.append({'path':path,'issue':'sha256 changed'})
        except OSError as e:drift.append({'path':path,'issue':type(e).__name__})
    if os.uname().release!=value['kernel_release']:drift.append({'issue':'kernel release changed'})
    root=subprocess.check_output(['findmnt','-n','-o','UUID','/'],text=True).strip()
    if root!=value['root_uuid']:drift.append({'issue':'root UUID changed'})
    packages=subprocess.check_output(['pacman','-Q'],text=True)
    if hashlib.sha256(packages.encode()).hexdigest()!=value['packages_sha256']:drift.append({'issue':'installed package versions changed; compare with /etc/jupi/packages.lock'})
    for path,expected in value['kernel_settings'].items():
        try:
            if Path(path).read_text().strip()!=expected:drift.append({'path':path,'issue':'kernel setting changed'})
        except OSError as e:drift.append({'path':path,'issue':type(e).__name__})
    for unit,expected in value['service_cpu_affinity'].items():
        try:
            pid=int(subprocess.check_output(['systemctl','show','-p','MainPID','--value',unit],text=True))
            if pid<=0 or sorted(os.sched_getaffinity(pid))!=expected:drift.append({'service':unit,'issue':'active CPU affinity differs'})
        except (OSError,ValueError,subprocess.SubprocessError) as e:drift.append({'service':unit,'issue':type(e).__name__})
    return {'profile_id':value['profile_id'],'baseline_matches':not drift,'drift':drift,'benchmark':value['benchmark_directory'],'offline_qualification':value['offline_qualification_directory'],'scope':'Read-only drift detection; no automatic system changes'}


def compute(argv,batch=False):
    value=load();math=value['math'];library=Path('/usr/lib/libopenblas.so.0.3')
    if str(library)!=math['library'] or library.stat().st_uid!=0 or library.stat().st_mode&0o022 or sha(library)!=math['library_sha256']:raise ValueError('Pinned math library differs')
    threads=math['batch_threads'] if batch else math['interactive_threads']
    if type(threads) is not int or not 1<=threads<=4:raise ValueError('Thread bound')
    if argv[:1]==['--']:argv=argv[1:]
    if not argv:raise ValueError('Provide an explicit command after --')
    env=dict(os.environ,LD_PRELOAD=str(library),OPENBLAS_NUM_THREADS=str(threads),OMP_NUM_THREADS=str(threads))
    os.execvpe(argv[0],argv,env)


def main():
    if sys.argv[1:2]==['run']:
        argv=sys.argv[2:];batch=argv[:1]==['--batch'];compute(argv[1:] if batch else argv,batch);return
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('status','verify'));args=p.parse_args();value=load()
    if args.action=='status':result=value
    else:result=verify(value)
    print(json.dumps(result,indent=2))
    if args.action=='verify' and result['drift']:raise SystemExit(1)


if __name__=='__main__':main()
