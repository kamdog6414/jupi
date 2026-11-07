#!/usr/bin/python3
"""JUPI hybrid calibration: durable jobs, fixed GPU arithmetic and SSH reference work."""
import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import shlex
import socket
import struct
import subprocess
import sys
import tempfile
import time
import uuid

STATE = Path('/var/lib/jupi-agent/science')
CONFIG = Path('/etc/jupi/science.json')
SOCKET = '/run/jupi-agent/control.sock'
MAX_INPUT = 8*1024*1024
SSH = ['/usr/bin/ssh','-T','-F','/etc/jupi/ssh/roach.conf','-o','BatchMode=yes',
       '-o','ClearAllForwardings=yes','-o','LogLevel=ERROR','jupi-peer']


def now(): return datetime.now(timezone.utc).isoformat()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(raw): return hashlib.sha256(raw).hexdigest()


def atomic(path, raw):
    fd, temporary = tempfile.mkstemp(prefix='.science-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
        fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path,value): atomic(path,canonical(value)+b'\n')
def read_json(path): return json.loads(path.read_bytes())


def run_dir(identifier):
    if str(uuid.UUID(identifier))!=identifier:
        raise ValueError('Canonical run UUID required')
    directory=STATE/'runs'/identifier
    if directory.is_symlink(): raise ValueError('Symlink run directory refused')
    return directory


def configuration():
    raw=CONFIG.read_bytes();config=json.loads(raw)
    if config.get('schema')!='jupi.science.config.v1': raise ValueError('Science config schema differs')
    if set(config.get('components',{}))!={'workflow','peer','gpu_source','gpu_binary'}:
        raise ValueError('Science component manifest differs')
    for component in config['components'].values():
        p=Path(component['path'])
        if not p.is_absolute() or p.is_symlink() or digest(p.read_bytes())!=component['sha256']:
            raise ValueError('Reviewed science component source differs')
    return raw,config


def reference(config):
    path=config['components']['peer']['path']
    spec=importlib.util.spec_from_file_location('jupi_science_reference',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def label(value, maximum):
    if not isinstance(value,str) or not 1<=len(value)<=maximum or any(ord(c)<32 for c in value):
        raise ValueError('Label or unit is empty, too long, or contains control characters')
    return value


def parse_csv(raw, operation):
    if not 1<=len(raw)<=MAX_INPUT: raise ValueError('CSV must contain 1 byte through 8 MiB')
    rows=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
    expected=['x','y'] if operation=='calibrate' else ['x']
    if [v.strip() for v in next(rows,[])]!=expected: raise ValueError('Required CSV columns: '+','.join(expected))
    points=[]
    for row in rows:
        if not row: continue
        if len(row)!=len(expected): raise ValueError('CSV column count differs')
        points.append([float(v) for v in row])
        if len(points)>65536: raise ValueError('At most 65536 samples are supported')
    return points


def verify_run(identifier):
    directory=run_dir(identifier);receipt=read_json(directory/'receipt.json')
    if receipt.get('schema')!='jupi.science.receipt.v1' or receipt.get('state')!='passed' or receipt.get('run_id')!=identifier:
        raise ValueError('Run is not a passed science result')
    request_raw=(directory/'request.json').read_bytes();request=json.loads(request_raw)
    if request.get('schema')!='jupi.science.request.v1' or request.get('run_id')!=identifier:
        raise ValueError('Request schema differs')
    if digest(request_raw)!=receipt['request_sha256']: raise ValueError('Request binding differs')
    if digest((directory/'input.json').read_bytes())!=request['dataset_sha256']:
        raise ValueError('Input binding differs')
    if digest((directory/'source.csv').read_bytes())!=request['source_csv_sha256']:
        raise ValueError('Source CSV binding differs')
    if digest((directory/'software.json').read_bytes())!=request['software_sha256']:
        raise ValueError('Software manifest binding differs')
    software=read_json(directory/'software.json')
    if software.get('schema')!='jupi.science.config.v1' or set(software.get('components',{}))!={'workflow','peer','gpu_source','gpu_binary'}:
        raise ValueError('Captured software schema differs')
    for name,component in software['components'].items():
        if name not in ('workflow','peer','gpu_source','gpu_binary') or digest((directory/'sources'/name).read_bytes())!=component['sha256']:
            raise ValueError('Captured source differs from the software manifest')
    artifacts=receipt['artifacts']
    if not 8<=len(artifacts)<=32: raise ValueError('Artifact manifest bound differs')
    for name, expected in artifacts.items():
        relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts: raise ValueError('Unsafe artifact path')
        p=directory/str(relative)
        if any(part.is_symlink() for part in [p,*list(p.parents)[:len(relative.parts)-1]]):
            raise ValueError('Symlink artifact refused')
        if not p.is_file() or p.stat().st_size>32*1024**2 or digest(p.read_bytes())!=expected:
            raise ValueError('Artifact contents differ')
    return receipt


def prepare(raw, operation='calibrate', provenance='operator_supplied', title='Linear calibration',
            x_unit='unspecified',y_unit='unspecified',parent=None,extrapolate=False):
    config_raw,config=configuration();peer=reference(config)
    points=parse_csv(raw,operation)
    value={'schema':'jupi.science.input.v1','operation':operation,'samples':points,
           'data_origin':provenance,'x_unit':label(x_unit,40),'y_unit':label(y_unit,40)}
    parent_ref=None
    if operation=='apply':
        prior=verify_run(parent)
        native=client({'action':'science-status','run_id':parent})
        if not native or native['status']!='succeeded' or native['id']!=prior['job_id'] or native['request_sha256']!=prior['request_sha256']:
            raise ValueError('Parent native science job binding is not a succeeded match')
        if prior['operation']!='calibrate': raise ValueError('Parent must be a calibration run')
        value.update({'calibration':prior['reference']['model'],'allow_extrapolation':extrapolate,
                      'x_unit':prior['x_unit'],'y_unit':prior['y_unit']})
        parent_ref={'run_id':parent,'receipt_sha256':digest((run_dir(parent)/'receipt.json').read_bytes())}
    peer.fit(value)  # Reject undefined fits and unapproved extrapolation before enqueuing.
    identifier=str(uuid.uuid4());directory=run_dir(identifier)
    directory.mkdir(mode=0o700,parents=True)
    sources=directory/'sources';sources.mkdir(mode=0o700)
    atomic(directory/'source.csv',raw)
    input_raw=canonical(value);atomic(directory/'input.json',input_raw)
    atomic(directory/'software.json',config_raw)
    for name,component in config['components'].items():
        atomic(sources/name,Path(component['path']).read_bytes())
    request={'schema':'jupi.science.request.v1','run_id':identifier,'created':now(),
             'operation':operation,'label':label(title,120),'dataset_sha256':digest(input_raw),
             'source_csv_sha256':digest(raw),'software_sha256':digest(config_raw),
             'identity_sha256':digest(Path('/etc/jupi/identity.json').read_bytes()),
             'data_origin':provenance,'samples':len(points),'parent':parent_ref,
             'peer':'pinned SSH alias jupi-peer (Ubuntu Roach)',
             'execution_policy':'Explicit native job; fixed reviewed kernels/worker; no automatic retries or CPU substitution'}
    write_json(directory/'request.json',request)
    return {'run_id':identifier,'request_sha256':digest((directory/'request.json').read_bytes()),
            'directory':str(directory),'state':'prepared'}


def client(request):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(20);connection.connect(SOCKET)
        connection.sendall(canonical(request)+b'\n')
        with connection.makefile('rb') as f:
            raw=f.readline(2*1024**2+1)
    if len(raw)>2*1024**2 or not raw.endswith(b'\n'): raise ValueError('Agent response framing differs')
    response=json.loads(raw)
    if response.get('ok') is not True: raise ValueError(response.get('error','Agent request failed'))
    return response['result']


def enqueue(identifier):
    directory=run_dir(identifier)
    result=client({'action':'science','run_id':identifier,'request_sha256':digest((directory/'request.json').read_bytes())})
    write_json(directory/'job.json',result)
    return result


def peer_call(config,value,operation,directory,model=None,gpu=None):
    component=config['components']['peer'];source=Path(component['path']).read_text()
    body={'operation':operation,'worker_sha256':component['sha256'],'dataset':value,
          'dataset_sha256':digest(canonical(value))}
    if gpu is not None:
        body.update({'model':model,'gpu_output_b64':base64.b64encode(gpu).decode(),
                     'gpu_output_sha256':digest(gpu)})
    command=['/usr/bin/timeout','--signal=TERM','--kill-after=2s','45s','/usr/bin/nice','-n','10','/usr/bin/python3','-B','-c',source]
    result=subprocess.run(SSH+[shlex.join(command)],input=canonical(body),capture_output=True,timeout=55)
    atomic(directory/('peer-'+operation+'.stderr'),result.stderr[:8192])
    if result.returncode or len(result.stdout)>65536:
        raise RuntimeError('Ubuntu '+operation+' failed; bounded stderr retained with the run')
    response=json.loads(result.stdout)
    if response.get('worker_sha256')!=component['sha256'] or response.get('dataset_sha256')!=body['dataset_sha256']:
        raise ValueError('Peer result source/input binding differs')
    if response.get('execution_host',{}).get('hostname')!=config['expected_peer_hostname']:
        raise ValueError('Peer execution hostname differs from enrolled route')
    write_json(directory/('peer-'+operation+'.json'),response)
    return response


def render(directory,value,model,gpu):
    os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    predictions=[]
    with (directory/'predictions.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['x','observed_y','calibrated_y','residual_y'])
        for point,(pred,residual) in zip(value['samples'],struct.iter_unpack('<ff',gpu)):
            y=model['y_mean']+model['y_scale']*pred
            writer.writerow([point[0],point[1] if len(point)==2 else '',y,
                             model['y_scale']*residual if len(point)==2 else ''])
            predictions.append(y)
        f.flush();os.fsync(f.fileno())
    stride=max(1,math.ceil(len(predictions)/4096));indices=list(range(0,len(predictions),stride))
    order=sorted(indices,key=lambda i:value['samples'][i][0])
    fig,axis=plt.subplots(figsize=(7,4.5))
    if value['operation']=='calibrate':
        axis.scatter([value['samples'][i][0] for i in indices],[value['samples'][i][1] for i in indices],s=8,label='Input samples')
    axis.plot([value['samples'][i][0] for i in order],[predictions[i] for i in order],label='GPU model application')
    axis.set_xlabel('x / '+value['x_unit'],parse_math=False);axis.set_ylabel('y / '+value['y_unit'],parse_math=False)
    axis.set_title('JUPI '+value['operation']+' — '+value['data_origin'],parse_math=False)
    axis.legend();fig.tight_layout();fig.savefig(directory/'calibration.png',dpi=140);plt.close(fig)
    return {'plot_samples':len(indices),'csv_samples':len(predictions)}


def execute(identifier,expected_request,job_id):
    directory=run_dir(identifier);request_raw=(directory/'request.json').read_bytes()
    if digest(request_raw)!=expected_request: raise ValueError('Queued request hash differs')
    if str(uuid.UUID(job_id))!=job_id:raise ValueError('Canonical native job UUID required')
    if (directory/'receipt.json').exists():raise ValueError('Run was already attempted; prepare a new explicit run')
    # Commit the attempt before any peer/GPU work. Even an interrupted internal
    # invocation cannot overwrite an earlier run or silently repeat its work.
    fd=os.open(directory/'attempt.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(canonical({'job_id':job_id,'request_sha256':expected_request,'attempted':now()})+b'\n')
        f.flush();os.fsync(f.fileno())
    request=json.loads(request_raw)
    receipt={'schema':'jupi.science.receipt.v1','run_id':identifier,'job_id':job_id,'state':'running',
             'started':now(),'request_sha256':expected_request,'stage':'preflight'}
    write_json(directory/'receipt.json',receipt)
    started=time.monotonic()
    try:
        config_raw,config=configuration()
        if digest(config_raw)!=request['software_sha256']: raise ValueError('Queued software version changed; prepare a new explicit run')
        input_raw=(directory/'input.json').read_bytes()
        if digest(input_raw)!=request['dataset_sha256']: raise ValueError('Queued input changed')
        if digest((directory/'source.csv').read_bytes())!=request['source_csv_sha256']: raise ValueError('Queued source CSV changed')
        value=json.loads(input_raw);peer=reference(config)
        if request.get('parent'):
            parent=verify_run(request['parent']['run_id'])
            if digest((run_dir(parent['run_id'])/'receipt.json').read_bytes())!=request['parent']['receipt_sha256']:
                raise ValueError('Parent calibration receipt changed')
        before={'utc':now(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'load_average':list(os.getloadavg())}
        receipt['stage']='ubuntu_reference';write_json(directory/'receipt.json',receipt)
        t=time.monotonic();fitted=peer_call(config,value,'fit',directory);fit_seconds=time.monotonic()-t
        model=fitted['model'];normalized=peer.normalized(value,model)
        raw=b''.join(struct.pack('<ff',*p) for p in normalized)
        atomic(directory/'normalized.f32',raw)
        receipt['stage']='gpu_application';write_json(directory/'receipt.json',receipt)
        t=time.monotonic()
        gpu_command=[config['components']['gpu_binary']['path'],str(directory/'normalized.f32'),
                     str(directory/'gpu.f32'),str(len(normalized)),repr(model['gain'])]
        result=subprocess.run(gpu_command,capture_output=True,timeout=40)
        atomic(directory/'gpu.stderr',result.stderr[:8192])
        if result.returncode or len(result.stdout)>8192: raise RuntimeError('GPU execution failed; no CPU substitution')
        metadata=json.loads(result.stdout)
        if metadata.get('backend')!='OpenCL GPU' or metadata.get('samples')!=len(normalized):
            raise ValueError('GPU backend or sample count differs')
        write_json(directory/'gpu.json',metadata);gpu_raw=(directory/'gpu.f32').read_bytes()
        gpu_seconds=time.monotonic()-t
        receipt['stage']='ubuntu_verification';write_json(directory/'receipt.json',receipt)
        t=time.monotonic();verification=peer_call(config,value,'verify',directory,model,gpu_raw);verify_seconds=time.monotonic()-t
        local=peer.verify_gpu(value,model,gpu_raw)
        if verification.get('verified') is not True or local['verified'] is not True:
            raise ValueError('GPU arithmetic verification failed')
        receipt['stage']='artifact_render';write_json(directory/'receipt.json',receipt)
        plot=render(directory,value,model,gpu_raw)
        if (directory/'input.json').read_bytes()!=input_raw: raise ValueError('Input changed during execution')
        receipt.update({'state':'passed','stage':'complete','finished':now(),'operation':value['operation'],
                        'data_origin':value['data_origin'],'x_unit':value['x_unit'],'y_unit':value['y_unit'],
                        'samples':len(normalized),'dataset_sha256':request['dataset_sha256'],
                        'identity_sha256':request['identity_sha256'],'software_sha256':request['software_sha256'],
                        'reference':fitted,'gpu':metadata,'peer_verification':verification,'local_verification':local,
                        'parent':request.get('parent'),'environment':before,'render':plot,
                        'timing_seconds':{'ubuntu_fit':fit_seconds,'gpu_stage_including_setup':gpu_seconds,
                                          'ubuntu_verify':verify_seconds,'total':time.monotonic()-started},
                        'scope':'Fixed reviewed GPU math and pinned Ubuntu reference computation. Hashes bind artifacts; no physical sensor accuracy or person identity is certified.'})
        receipt['artifacts']={str(p.relative_to(directory)):digest(p.read_bytes()) for p in directory.rglob('*')
                              if p.is_file() and p.name not in ('receipt.json','job.json') and not p.name.startswith('.science-')}
        write_json(directory/'receipt.json',receipt)
        verify_run(identifier)
        summary={'run_id':identifier,'state':'passed','operation':value['operation'],'samples':len(normalized),
                 'utc':receipt['finished'],
                 'data_origin':value['data_origin'],'receipt_sha256':digest((directory/'receipt.json').read_bytes()),
                 'receipt':str(directory/'receipt.json'),'model':{k:model[k] for k in ('slope','intercept')},
                 'gpu_mismatches':verification['mismatches'],'peer_hostname':fitted['execution_host']['hostname']}
        write_json(STATE/'latest.json',summary)
        print(json.dumps(summary))
        return 0
    except Exception as error:
        receipt.update(state='failed',finished=now(),error_class=type(error).__name__,error=str(error)[:300])
        write_json(directory/'receipt.json',receipt)
        print(json.dumps({'run_id':identifier,'state':'failed','stage':receipt['stage'],
                          'error_class':type(error).__name__,'receipt':str(directory/'receipt.json')}))
        return 1


def status(identifier):
    directory=run_dir(identifier);request=read_json(directory/'request.json')
    native=client({'action':'science-status','run_id':identifier})
    if native and native['request_sha256']!=digest((directory/'request.json').read_bytes()):
        raise ValueError('Native job binds a different request')
    receipt=read_json(directory/'receipt.json') if (directory/'receipt.json').exists() else None
    result={'run_id':identifier,'label':request['label'],'operation':request['operation'],
            'data_origin':request['data_origin'],'native_job':native,
            'receipt_state':receipt.get('state') if receipt else 'prepared','directory':str(directory)}
    result['state']=native['status'] if native else 'prepared'
    if native and native['status']=='succeeded':
        verified=verify_run(identifier)
        result.update({'artifact_integrity':'pass','gpu_mismatches':verified['peer_verification']['mismatches'],
                       'model':verified['reference']['model'],'receipt':str(directory/'receipt.json'),'state':'passed'})
    return result


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    for name in ('prepare','submit'):
        p=sub.add_parser(name);p.add_argument('csv');p.add_argument('--label',default='Linear calibration')
        p.add_argument('--x-unit',default='unspecified');p.add_argument('--y-unit',default='unspecified')
        p.add_argument('--synthetic',action='store_true')
    p=sub.add_parser('apply');p.add_argument('parent');p.add_argument('csv');p.add_argument('--allow-extrapolation',action='store_true')
    p.add_argument('--synthetic',action='store_true')
    p=sub.add_parser('demo');p.add_argument('--samples',type=int,default=1024)
    for name in ('enqueue','status','verify','wait','record'):
        p=sub.add_parser(name);p.add_argument('run_id')
        if name=='wait':p.add_argument('--timeout',type=int,default=180,choices=range(1,601),metavar='1..600')
    sub.add_parser('list')
    p=sub.add_parser('execute',help='Internal native-job entry; use submit/apply');p.add_argument('run_id');p.add_argument('--request-sha256',required=True);p.add_argument('--job-id',required=True)
    args=parser.parse_args()
    if args.action=='execute':return execute(args.run_id,args.request_sha256,args.job_id)
    if args.action in ('prepare','submit','demo','apply'):
        if args.action=='demo':
            if not 3<=args.samples<=65536:raise ValueError('Demo sample bound is 3..65536')
            buffer=io.StringIO(newline='');writer=csv.writer(buffer);writer.writerow(['x','y'])
            for i in range(args.samples):
                x=20*i/(args.samples-1)-10;writer.writerow([x,2.5*x-0.75+0.02*math.sin(i*0.17)])
            result=prepare(buffer.getvalue().encode(),provenance='synthetic_demo',title='Synthetic calibration demonstration',x_unit='synthetic input',y_unit='synthetic response')
        else:
            path=Path(args.csv)
            if not path.is_file() or path.stat().st_size>MAX_INPUT:raise ValueError('Bounded regular CSV required')
            with path.open('rb') as f:raw=f.read(MAX_INPUT+1)
            if args.action=='apply':
                result=prepare(raw,operation='apply',provenance='synthetic_demo' if args.synthetic else 'operator_supplied',title='Apply calibration',parent=args.parent,extrapolate=args.allow_extrapolation)
            else:result=prepare(raw,provenance='synthetic_demo' if args.synthetic else 'operator_supplied',title=args.label,x_unit=args.x_unit,y_unit=args.y_unit)
        if args.action!='prepare':
            try:
                result.update(enqueue(result['run_id']));result['state']=result['status']
            except Exception as error:
                result.update(state='enqueue_unconfirmed',error_class=type(error).__name__,reconcile='jupi-science enqueue '+result['run_id'])
                print(json.dumps(result,indent=2));return 1
    elif args.action=='enqueue':result=enqueue(args.run_id)
    elif args.action=='status':result=status(args.run_id)
    elif args.action=='verify':
        receipt=verify_run(args.run_id);result={'run_id':args.run_id,'state':receipt['state'],'artifacts_verified':len(receipt['artifacts'])}
    elif args.action=='wait':
        end=time.monotonic()+args.timeout
        while True:
            result=status(args.run_id);job=result['native_job']
            if job and job['status'] not in ('queued','running'):
                print(json.dumps(result,indent=2));return 0 if job['status']=='succeeded' else 1
            if time.monotonic()>=end:raise TimeoutError('Wait ended; native job is retained and is not replayed')
            time.sleep(0.5)
    elif args.action=='record':
        receipt=verify_run(args.run_id)
        native=client({'action':'science-status','run_id':args.run_id})
        if not native or native['status']!='succeeded' or native['id']!=receipt['job_id'] or native['request_sha256']!=receipt['request_sha256']:
            raise ValueError('Native job binding is not a succeeded match')
        reference={'schema':'jupi.science.artifact.reference.v1','run_id':args.run_id,
                   'receipt_sha256':digest((run_dir(args.run_id)/'receipt.json').read_bytes()),
                   'data_origin':receipt['data_origin'],'samples':receipt['samples'],
                   'scope':'Receipt reference only; no raw dataset, person authentication or sensor certification'}
        subprocess.run(['/usr/local/bin/jupi-agape','note',canonical(reference).decode()],check=True)
        return 0
    else:
        directories=sorted((STATE/'runs').glob('*'),key=lambda p:p.stat().st_mtime,reverse=True)[:20]
        result=[status(p.name) for p in directories if p.is_dir() and not p.is_symlink()]
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'error_class':type(error).__name__,'error':str(error)[:300]}),file=sys.stderr)
        raise SystemExit(1)
