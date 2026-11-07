#!/usr/bin/python3
"""JUPI seed: durable memory, observations, explicit jobs and model access."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import glob
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import selectors
import shlex
import signal
import socket
import socketserver
import sqlite3
import struct
import subprocess
import threading
import time
import urllib.request
import uuid

STATE = Path(os.environ.get("JUPI_AGENT_STATE", "/var/lib/jupi-agent"))
SOCKET = os.environ.get("JUPI_AGENT_SOCKET", "/run/jupi-agent/control.sock")
WORKSPACE = "/home/pi/ChatGPT/JUPI"
MODEL = "qwen3:0.6b"
STOP = threading.Event()
SSH = ["/usr/bin/ssh", "-T", "-F", "/etc/jupi/ssh/roach.conf", "-o", "BatchMode=yes",
       "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "jupi-peer"]


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database():
    connection = sqlite3.connect(STATE / "seed.sqlite3", timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA synchronous=FULL")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def event(connection, kind, body):
    connection.execute("INSERT INTO events(utc,kind,body) VALUES(?,?,?)", (now(), kind, json.dumps(body)))
    connection.execute("DELETE FROM events WHERE id <= (SELECT coalesce(max(id),0)-10000 FROM events)")


def initialize():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with database() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS memory(key TEXT PRIMARY KEY, value TEXT NOT NULL, utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, utc TEXT, kind TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, payload TEXT, status TEXT,
            created TEXT, started TEXT, finished TEXT, code INTEGER, output TEXT);
        CREATE TABLE IF NOT EXISTS science_runs(run_id TEXT PRIMARY KEY,job_id TEXT UNIQUE NOT NULL,
            request_sha256 TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS art_runs(request_id TEXT PRIMARY KEY,job_id TEXT UNIQUE NOT NULL,
            parameters_sha256 TEXT NOT NULL,source_sha256 TEXT NOT NULL);
        """)
        # A command that was running may already have changed the world. Never replay it.
        db.execute("UPDATE jobs SET status='interrupted',finished=?,output=coalesce(output,'') || ? WHERE status='running'",
                   (now(), "\nRuntime restarted; no automatic replay."))
        event(db, "runtime_start", {"boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()})


def observe():
    memory = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
              if line.startswith(('MemTotal:', 'MemAvailable:', 'SwapTotal:', 'SwapFree:'))}
    temperatures, temperature_controls = {}, {}
    for name in glob.glob('/sys/class/hwmon/hwmon*/temp*_input'):
        try:
            value = int(Path(name).read_text()) / 1000
            driver = (Path(name).parent / 'name').read_text().strip()
            if driver == 'k10temp' and Path(name).name == 'temp1_input':
                temperature_controls[name] = value
            else:
                temperatures[name] = value
        except (OSError, ValueError):
            pass
    filesystem = os.statvfs('/')
    return {"utc": now(), "boot_id": Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            "uptime_seconds": float(Path('/proc/uptime').read_text().split()[0]),
            "load_average": list(os.getloadavg()), "memory_kib": memory,
            "root_available_bytes": filesystem.f_bavail * filesystem.f_frsize,
            "temperatures_c": temperatures,
            "temperature_control_degrees": temperature_controls,
            "temperature_scope": "k10temp temp1 is Tctl. Use jupi-observe inventory for sensor semantics and exported limits; Tctl is not a calibrated die temperature.",
            "devices": {kind: sorted(glob.glob(pattern)) for kind, pattern in
                        {"gpu": "/dev/dri/renderD*", "cameras": "/dev/video*",
                         "usb_serial": "/dev/ttyUSB*", "usb_acm": "/dev/ttyACM*"}.items()}}


def command(argv, cwd, timeout):
    """Run an argv vector with a deadline, process-group cleanup and bounded output."""
    environment = dict(os.environ)
    environment.pop('LD_LIBRARY_PATH', None)
    process = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    end, output, total, expired = time.monotonic() + timeout, bytearray(), 0, False
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if STOP.is_set() or time.monotonic() >= end:
                expired = True
                break
            for key, _ in selector.select(0.1):
                block = os.read(key.fileobj.fileno(), 8192)
                if not block:
                    selector.unregister(key.fileobj)
                else:
                    total += len(block)
                    output.extend(block[:max(0, 65536-len(output))])
        code = process.wait(timeout=max(0.1, end-time.monotonic())) if not expired else 124
    except subprocess.TimeoutExpired:
        expired, code = True, 124
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()
        selector.close()
    result = output.decode(errors='replace')
    if total > len(output):
        result += '\n[output truncated at 65536 bytes]'
    if expired:
        result += '\n[deadline or runtime shutdown reached]'
    return code, result


def generate(payload):
    with database() as db:
        row = db.execute("SELECT value FROM memory WHERE key='mission'").fetchone()
    mission = row[0] if row else 'Joint Unix Platform Integrator for science and engineering.'
    state = observe()
    context = {key: state[key] for key in ('memory_kib', 'root_available_bytes', 'devices')}
    context['latest_science'] = science_context()
    context['latest_art'] = art_context()
    body = json.dumps({"model": MODEL, "prompt": payload['prompt'], "stream": False, "think": False,
                       "system": "You are JUPI, the Joint Unix Platform Integrator. Be concise and factual. Never claim actions were performed. Propose commands for the operator to review; model text is not executed. Mission: " + mission[:2000] + " Observed hardware: " + json.dumps(context),
                       "keep_alive": "60s", "options": {"num_ctx": 2048, "num_predict": 128, "num_thread": 4}})
    if payload.get('peer'):
        response = subprocess.run(SSH + ["curl -fsS --max-time 150 http://127.0.0.1:11434/api/generate -H 'Content-Type: application/json' --data-binary @-"],
                                  input=body, text=True, capture_output=True, timeout=165, check=True).stdout
        data = json.loads(response)
    else:
        request = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=body.encode(),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=150) as response:
            raw = response.read(1024*1024+1)
        if len(raw) > 1024*1024:
            raise ValueError('Model response exceeded limit')
        data = json.loads(raw)
    if not data.get('done') or not isinstance(data.get('response'), str):
        raise ValueError('Model did not return a completed response')
    return 0, json.dumps({k: data.get(k) for k in ('model', 'response', 'eval_count', 'eval_duration', 'total_duration')})


def science_context():
    """Only typed receipt facts enter model context; labels and imported prose do not."""
    try:
        path=STATE/'science/latest.json'
        if path.stat().st_size>8192: return None
        value=json.loads(path.read_text())
        if value.get('state')!='passed' or str(uuid.UUID(value['run_id']))!=value['run_id']: return None
        if value.get('operation') not in ('calibrate','apply') or type(value.get('samples')) is not int: return None
        if value.get('data_origin') not in ('synthetic_demo','operator_supplied'): return None
        model=value['model']
        if any(type(model.get(k)) not in (int,float) or not math.isfinite(model[k]) for k in ('slope','intercept')): return None
        if type(value.get('gpu_mismatches')) is not int or value['gpu_mismatches']!=0: return None
        if not isinstance(value.get('receipt_sha256'),str) or len(value['receipt_sha256'])!=64: return None
        return {'run_id':value['run_id'],'operation':value['operation'],'samples':value['samples'],
                'data_origin':value['data_origin'],
                'slope':model['slope'],'intercept':model['intercept'],'gpu_mismatches':value['gpu_mismatches'],
                'receipt_sha256':value['receipt_sha256'],
                'scope':'Stored measured computation; no command authority or physical sensor certification'}
    except (OSError,ValueError,KeyError,TypeError):
        return None


def art_context():
    try:
        path=STATE/'artwork/latest.json'
        if path.stat().st_size>8192:return None
        value=json.loads(path.read_text())
        if value.get('scene') not in ('facade','nave') or value.get('style') not in ('engraving','nocturne','ruins'):return None
        if any(type(value.get(k)) is not int for k in ('width','height','seed')):return None
        if str(uuid.UUID(value['request_id']))!=value['request_id']:return None
        if not isinstance(value.get('receipt_sha256'),str) or len(value['receipt_sha256'])!=64:return None
        return {k:value.get(k) for k in ('request_id','scene','style','width','height','seed','receipt_sha256','classification')}
    except (OSError,ValueError,KeyError,TypeError):return None


def art_recipe(request):
    config=json.loads(Path('/etc/jupi/art.json').read_text())
    source=Path('/usr/local/lib/jupi-agent/gothic_art.py')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if config.get('schema')!='jupi.art.config.v1' or config.get('renderer_sha256')!=digest:raise ValueError('Reviewed art source differs')
    spec=importlib.util.spec_from_file_location('jupi_reviewed_art',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    defaults={'scene':'facade','style':'engraving','width':121,'height':65,'seed':14,'paper':'black','title':'JUPI','video':False}
    return module.parameters(**{k:request.get(k,v) for k,v in defaults.items()}),digest,str(source)


def worker():
    observed = 0
    while not STOP.is_set():
        if time.monotonic() - observed >= 60:
            with database() as db:
                event(db, 'observation', observe())
            observed = time.monotonic()
        with database() as db:
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE jobs SET status='running',started=? WHERE id=?", (now(), row['id']))
                event(db, 'job_started', {'id': row['id'], 'kind': row['kind']})
        if row:
            try:
                payload = json.loads(row['payload'])
                if row['kind'] == 'prompt':
                    code, output = generate(payload)
                else:
                    argv = payload['argv']
                    if payload.get('peer'):
                        argv = SSH + [shlex.join(argv)]
                    code, output = command(argv, payload['cwd'], payload['timeout'])
            except Exception as error:
                code, output = 1, type(error).__name__ + ': ' + str(error)[:2000]
            with database() as db:
                status = 'succeeded' if code == 0 else ('timed_out' if code == 124 else 'failed')
                db.execute('UPDATE jobs SET status=?,finished=?,code=?,output=? WHERE id=?',
                           (status, now(), code, output, row['id']))
                event(db, 'job_finished', {'id': row['id'], 'status': status, 'code': code})
        else:
            STOP.wait(0.25)


def dispatch(request):
    action = request.get('action')
    with database() as db:
        if action == 'status':
            return {"observation": observe(), "jobs": dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status').fetchall()),
                    "memory_entries": db.execute('SELECT count(*) FROM memory').fetchone()[0],
                    "model": MODEL, "socket": SOCKET, "automatic_model_command_execution": False}
        if action == 'capabilities':
            return json.loads(Path('/etc/jupi/platform.json').read_text())
        if action == 'identity':
            return json.loads(Path('/etc/jupi/identity.json').read_text())
        if action=='art':
            request_id=request.get('request_id') or str(uuid.uuid4())
            if not isinstance(request_id,str) or str(uuid.UUID(request_id))!=request_id:raise ValueError('Canonical art request UUID required')
            params,source_sha,program=art_recipe(request)
            parameters_sha=hashlib.sha256(json.dumps(params,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT a.job_id,a.parameters_sha256,a.source_sha256,j.status FROM art_runs a JOIN jobs j ON a.job_id=j.id WHERE a.request_id=?',(request_id,)).fetchone()
            if previous:
                if previous['parameters_sha256']!=parameters_sha:raise ValueError('Art request ID already binds another recipe')
                return {'id':previous['job_id'],'request_id':request_id,'status':previous['status'],'duplicate':True,'directory':str(STATE/'artwork'/request_id)}
            directory=STATE/'artwork'/request_id
            if directory.is_symlink():raise ValueError('Symlink artwork directory refused')
            directory.mkdir(mode=0o700,parents=True,exist_ok=True)
            identifier=str(uuid.uuid4())
            argv=['/usr/bin/python3','-B',program,'cathedral','--output='+str(directory),
                  '--job-id='+identifier,'--expected-source='+source_sha]
            argv += ['--'+k+'='+str(v) for k,v in params.items() if k!='video']
            if params['video']:argv.append('--video')
            payload={'peer':False,'cwd':str(directory),'timeout':120,'argv':argv,'art_parameters':params,'request_id':request_id}
            db.execute('INSERT INTO jobs(id,kind,payload,status,created) VALUES(?,?,?,?,?)',(identifier,'art',json.dumps(payload),'queued',now()))
            db.execute('INSERT INTO art_runs VALUES(?,?,?,?)',(request_id,identifier,parameters_sha,source_sha))
            event(db,'job_queued',{'id':identifier,'kind':'art','request_id':request_id,'classification':'procedural artwork'})
            return {'id':identifier,'request_id':request_id,'status':'queued','duplicate':False,'directory':str(directory)}
        if action in ('science','science-status'):
            run_id=request.get('run_id')
            if not isinstance(run_id,str) or str(uuid.UUID(run_id))!=run_id: raise ValueError('Canonical science run UUID required')
            if action=='science': db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT s.job_id,s.request_sha256,j.status,j.created,j.finished FROM science_runs s JOIN jobs j ON s.job_id=j.id WHERE s.run_id=?',(run_id,)).fetchone()
            if action=='science-status':
                return {'id':previous['job_id'],'run_id':run_id,'request_sha256':previous['request_sha256'],
                        'status':previous['status'],'created':previous['created'],'finished':previous['finished']} if previous else None
            directory=STATE/'science/runs'/run_id
            manifest=directory/'request.json'
            if directory.is_symlink() or manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>16384:
                raise ValueError('Prepared bounded science manifest required')
            raw=manifest.read_bytes();expected=hashlib.sha256(raw).hexdigest()
            if request.get('request_sha256')!=expected: raise ValueError('Prepared science manifest hash differs')
            prepared=json.loads(raw)
            if prepared.get('schema')!='jupi.science.request.v1' or prepared.get('run_id')!=run_id or prepared.get('operation') not in ('calibrate','apply'):
                raise ValueError('Prepared science manifest schema differs')
            if previous:
                if previous['request_sha256']!=expected: raise ValueError('Run ID already binds a different manifest')
                return {'id':previous['job_id'],'run_id':run_id,'request_sha256':expected,'status':previous['status'],'duplicate':True}
            identifier=str(uuid.uuid4())
            payload={'peer':False,'run_id':run_id,'request_sha256':expected,'cwd':str(directory),'timeout':180,
                     'argv':['/usr/bin/python3','-B','/usr/local/lib/jupi-agent/science_workflow.py','execute',run_id,
                             '--request-sha256',expected,'--job-id',identifier]}
            db.execute('INSERT INTO jobs(id,kind,payload,status,created) VALUES(?,?,?,?,?)',
                       (identifier,'science',json.dumps(payload),'queued',now()))
            db.execute('INSERT INTO science_runs VALUES(?,?,?)',(run_id,identifier,expected))
            event(db,'job_queued',{'id':identifier,'kind':'science','run_id':run_id,'automatic':False})
            return {'id':identifier,'run_id':run_id,'request_sha256':expected,'status':'queued','duplicate':False}
        if action == 'events':
            return [dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 30')]
        if action == 'jobs':
            return [dict(r) for r in db.execute('SELECT id,kind,status,created,finished,code FROM jobs ORDER BY created DESC LIMIT 50')]
        if action == 'job':
            row = db.execute('SELECT * FROM jobs WHERE id=?', (request.get('id'),)).fetchone()
            if not row: raise ValueError('Unknown job')
            return dict(row)
        if action in ('remember', 'recall'):
            key = request.get('key')
            if not isinstance(key, str) or not 1 <= len(key) <= 128: raise ValueError('Invalid memory key')
            if action == 'remember':
                value = request.get('value')
                if not isinstance(value, str) or len(value.encode()) > 16384: raise ValueError('Invalid memory value')
                db.execute('INSERT INTO memory VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,utc=excluded.utc',
                           (key, value, now()))
                event(db, 'memory_written', {'key': key})
            row = db.execute('SELECT * FROM memory WHERE key=?', (key,)).fetchone()
            return dict(row) if row else None
        if action in ('run', 'prompt'):
            payload = {'peer': request.get('peer', False)}
            if type(payload['peer']) is not bool: raise ValueError('Invalid peer selection')
            if action == 'run':
                argv = request.get('argv')
                if not isinstance(argv, list) or not 1 <= len(argv) <= 128 or not all(isinstance(s,str) and s and '\0' not in s for s in argv):
                    raise ValueError('Provide an argv list, not shell text')
                if len(json.dumps(argv).encode()) > 16384: raise ValueError('Command too long')
                cwd = Path(request.get('cwd', WORKSPACE)).resolve(strict=True)
                if not cwd.is_dir(): raise ValueError('Working directory is not a directory')
                timeout = request.get('timeout', 60)
                if type(timeout) is not int or not 1 <= timeout <= 600: raise ValueError('Deadline must be 1..600 seconds')
                payload.update(argv=argv, cwd=str(cwd), timeout=timeout)
            else:
                prompt = request.get('prompt')
                if not isinstance(prompt, str) or not 1 <= len(prompt.encode()) <= 8192: raise ValueError('Invalid prompt')
                payload['prompt'] = prompt
            identifier = str(uuid.uuid4())
            db.execute('INSERT INTO jobs(id,kind,payload,status,created) VALUES(?,?,?,?,?)',
                       (identifier, 'prompt' if action == 'prompt' else 'command', json.dumps(payload), 'queued', now()))
            event(db, 'job_queued', {'id': identifier, 'kind': action, 'peer': payload['peer']})
            return {'id': identifier, 'status': 'queued'}
    raise ValueError('Unknown action')


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            _, uid, _ = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid not in (0, os.getuid()): raise PermissionError('Socket user is not authorized')
            line = self.rfile.readline(32769)
            if len(line) > 32768 or not line.endswith(b'\n'): raise ValueError('Request limit exceeded')
            result = {'ok': True, 'result': dispatch(json.loads(line))}
        except Exception as error:
            result = {'ok': False, 'error': type(error).__name__ + ': ' + str(error)[:2000]}
        self.wfile.write(json.dumps(result).encode() + b'\n')


def serve():
    os.umask(0o077)
    initialize()
    Path(SOCKET).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    Path(SOCKET).unlink(missing_ok=True)
    with socketserver.UnixStreamServer(SOCKET, Handler) as server:
        os.chmod(SOCKET, 0o600)
        signal.signal(signal.SIGTERM, lambda *_: STOP.set())
        signal.signal(signal.SIGINT, lambda *_: STOP.set())
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        server.timeout = 0.5
        while not STOP.is_set():
            server.handle_request()
            if not thread.is_alive() and not STOP.is_set(): raise RuntimeError('Job worker stopped unexpectedly')
    Path(SOCKET).unlink(missing_ok=True)


def client(request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(20)
        for attempt in range(51):
            try:
                connection.connect(SOCKET)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if attempt == 50: raise
                time.sleep(0.1)
        connection.sendall(json.dumps(request).encode()+b'\n')
        with connection.makefile('rb') as response:
            result = json.loads(response.readline(2*1024*1024))
    if not result.get('ok'): raise RuntimeError(result.get('error'))
    return result['result']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('serve', 'status', 'identity', 'capabilities', 'jobs', 'events'): sub.add_parser(name)
    for name in ('job',): sub.add_parser(name).add_argument('id')
    wait = sub.add_parser('wait'); wait.add_argument('id'); wait.add_argument('--timeout', type=int, default=180)
    memory = sub.add_parser('remember'); memory.add_argument('key'); memory.add_argument('value')
    sub.add_parser('recall').add_argument('key')
    run = sub.add_parser('run'); run.add_argument('--peer', action='store_true'); run.add_argument('--timeout', type=int, default=60)
    run.add_argument('--cwd', default=WORKSPACE); run.add_argument('argv', nargs=argparse.REMAINDER)
    prompt = sub.add_parser('prompt'); prompt.add_argument('--peer', action='store_true'); prompt.add_argument('prompt')
    science = sub.add_parser('science'); science.add_argument('run_id'); science.add_argument('--request-sha256',required=True)
    sub.add_parser('science-status').add_argument('run_id')
    art=sub.add_parser('art');art.add_argument('--request-id');art.add_argument('--scene',choices=('facade','nave'),default='facade')
    art.add_argument('--style',choices=('engraving','nocturne','ruins'),default='engraving');art.add_argument('--width',type=int,default=121);art.add_argument('--height',type=int,default=65)
    art.add_argument('--seed',type=int,default=14);art.add_argument('--paper',choices=('black','white'),default='black');art.add_argument('--title',default='JUPI');art.add_argument('--video',action='store_true')
    args = vars(parser.parse_args())
    if args['action'] == 'serve': return serve()
    if args['action'] == 'wait':
        end = time.monotonic() + args['timeout']
        while time.monotonic() < end:
            result = client({'action': 'job', 'id': args['id']})
            if result['status'] not in ('queued', 'running'):
                print(json.dumps(result, indent=2))
                raise SystemExit(0 if result['status'] == 'succeeded' else 1)
            time.sleep(0.5)
        raise SystemExit('Job is still pending; it remains in the durable queue.')
    if args['action'] == 'run' and args['argv'][:1] == ['--']: args['argv'] = args['argv'][1:]
    print(json.dumps(client(args), indent=2))


if __name__ == '__main__':
    main()
