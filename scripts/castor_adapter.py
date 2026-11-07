#!/usr/bin/python3
"""Verify CastorLTE and explicitly publish as JUPI through its native author gate."""
import argparse
from contextlib import contextmanager
import fcntl
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shlex
import tempfile
import time

ANCHOR = '07b1bb90149ff0e24e4dbf5902dcbfdbf3d81f89132cd572cecd25a7fb2b56ce'
STATE = Path('/var/lib/jupi-agent/castor')
MAX_BYTES = 8*1024*1024
MEMBERSHIP = Path('/etc/jupi/cluster-membership.json')

PUBLISH = r'''
import fcntl,hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,'/home/roach/work/ROACH/castor-lte')
import castor_lte as native
request=json.load(sys.stdin)
if set(request)!={'operation_id','text','mode'}: raise ValueError('request fields')
text=request['text']
if not isinstance(text,str) or not 1<=len(text)<=3000: raise ValueError('text bound')
operation='jupi-'+hashlib.sha256(text.encode()).hexdigest()
if request['operation_id']!=operation or request['mode'] not in ('publish','reconcile'): raise ValueError('operation')
if native.CASTOR_ROOT!='07b1bb90149ff0e24e4dbf5902dcbfdbf3d81f89132cd572cecd25a7fb2b56ce': raise ValueError('anchor')
body=('JUPI operation '+operation+'\n'+text).strip()
directory=Path.home()/'.local/state/jupi-castor'
directory.mkdir(mode=0o700,parents=True,exist_ok=True)
with (directory/'publish.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 rows=native.load_chain()
 matches=[row for row in rows if row.get('author')=='JUPI' and row.get('text')==body]
 if matches: result={'state':'accepted','duplicate':True,'row':matches[0]}
 elif request['mode']=='reconcile': result={'state':'unknown_not_found','new_write':False}
 else:
  try: row=native.append_row('JUPI',body,'chat')
  except native.DeskError as error:
   if str(error)=='author not allowed': result={'state':'not_enrolled','new_write':False}
   else: raise
  else: result={'state':'accepted','duplicate':False,'row':row}
print(json.dumps(result,sort_keys=True))
'''


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate Castor JSON field')
        result[key] = value
    return result


def verify(raw, accepted=None):
    if not raw or len(raw) > MAX_BYTES or not raw.endswith(b'\n'):
        raise ValueError('Castor snapshot size or framing invalid')
    previous, rows = ANCHOR, []
    for line in raw.decode('utf-8').splitlines():
        if not line.strip(): continue
        row = json.loads(line, object_pairs_hook=no_duplicates)
        if not isinstance(row, dict) or set(row) != {'author','kind','n','prev_hash','text','ts','hash'}:
            raise ValueError('Castor row schema differs')
        body = {key:value for key,value in row.items() if key != 'hash'}
        digest = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if type(row['n']) is not int or row['n'] != len(rows)+1 or row['prev_hash'] != previous or row['hash'] != digest:
            raise ValueError('Castor sequence or hash chain invalid')
        if not all(isinstance(row[key],str) for key in ('author','kind','text','ts')):
            raise ValueError('Castor row text type invalid')
        rows.append(row); previous = row['hash']
    if not rows: raise ValueError('Castor snapshot is empty')
    if accepted:
        count = accepted['rows']
        if type(count) is not int or count < 1 or count > len(rows) or rows[count-1]['hash'] != accepted['tip']:
            raise ValueError('Castor rollback or accepted-prefix change detected')
    return rows


def atomic(path, raw):
    fd, temporary = tempfile.mkstemp(prefix='.castor-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(raw); out.flush(); os.fsync(out.fileno())
        os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def snapshot_lock(exclusive=False):
    """Serialize snapshot/receipt pairs against periodic and manual readers."""
    with (STATE/'snapshot.lock').open('a') as lock:
        operation=fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        deadline=time.monotonic()+5
        while True:
            try:
                fcntl.flock(lock,operation|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline: raise TimeoutError('Castor snapshot is busy')
                time.sleep(0.025)
        yield


def read_snapshot(command):
    with snapshot_lock(exclusive=command=='sync'):
        return _read_snapshot(command)


def _read_snapshot(command):
    snapshot, receipt = STATE/'chain.jsonl', STATE/'receipt.json'
    accepted = json.loads(receipt.read_text()) if receipt.exists() else None
    if command == 'sync':
        remote = "python3 -B -c \"from pathlib import Path; import sys; p=Path('/home/roach/work/ROACH/castor-lte/data/chain.jsonl'); data=p.read_bytes(); assert len(data)<=8388608; sys.stdout.buffer.write(data)\""
        result = subprocess.run(['ssh','-T','-F','/etc/jupi/ssh/roach.conf','-o','BatchMode=yes','-o','ClearAllForwardings=yes','jupi-peer',remote],
                                capture_output=True,timeout=30,check=True)
        rows = verify(result.stdout,accepted)
        status = {'schema':'jupi.castor.read.v1','utc':datetime.now(timezone.utc).isoformat(),'anchor':ANCHOR,
                  'rows':len(rows),'tip':rows[-1]['hash'],'snapshot_sha256':hashlib.sha256(result.stdout).hexdigest(),
                  'transport':'pinned SSH to jupi-peer','mode':'verified read snapshot',
                  'scope':'content-chain integrity and observation; no author authentication, acknowledgment or activation'}
        atomic(snapshot,result.stdout)
        atomic(receipt,(json.dumps(status,indent=2)+'\n').encode())
    else:
        if not accepted: raise ValueError('No snapshot yet; run jupi-castor sync')
        raw = snapshot.read_bytes()
        rows = verify(raw,accepted)
        if hashlib.sha256(raw).hexdigest() != accepted['snapshot_sha256']:
            raise ValueError('Cached snapshot and saved receipt differ')
        status = accepted
    return rows,status


def membership_view():
    try:
        value=json.loads(MEMBERSHIP.read_text())
        castor=value.get('memberships',{}).get('castorlte',{})
        identity=Path('/etc/jupi/identity.json').read_bytes()
        bound=(value.get('schema')=='jupi.cluster.membership.v1' and
               value.get('config_hash')==hashlib.sha256(identity).hexdigest() and
               value.get('seat_or_author')=='JUPI')
        return {'author_enrolled':True if bound and castor.get('state')=='ENROLLED' and castor.get('author')=='JUPI' else None,
                'membership_receipt':str(MEMBERSHIP),'membership_config_bound':bound,
                'membership_recorded_at':value.get('enrolled_at')}
    except (OSError,ValueError):
        return {'author_enrolled':None,'membership_receipt':str(MEMBERSHIP),
                'membership_note':'No current verified membership receipt; posting still uses the native author gate'}


def publish(text):
    if not isinstance(text,str) or not 1<=len(text.strip())<=3000:
        raise ValueError('Provide 1..3000 characters of explicit public text')
    operation='jupi-'+hashlib.sha256(text.encode()).hexdigest()
    path=STATE/(operation+'.json')
    with (STATE/(operation+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        previous=json.loads(path.read_text()) if path.exists() else None
        if previous and previous['state']=='accepted': return previous
        mode='reconcile' if previous and previous['state'] in ('attempting','unknown','unknown_not_found') else 'publish'
        request={'operation_id':operation,'text':text,'mode':mode}
        receipt={'schema':'jupi.castor.publish.v1','utc':datetime.now(timezone.utc).isoformat(),
                 'author':'JUPI','operation_id':operation,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
                 'state':'attempting','mode':mode,'scope':'native JUPI author gate; labels do not authenticate a person'}
        atomic(path,(json.dumps(receipt,indent=2)+'\n').encode())
        try:
            result=subprocess.run(['ssh','-T','-F','/etc/jupi/ssh/roach.conf','-o','BatchMode=yes',
                                   '-o','ClearAllForwardings=yes','jupi-peer',
                                   shlex.join(['python3','-B','-c',PUBLISH])],
                                  input=json.dumps(request),capture_output=True,text=True,timeout=30,check=True)
            outcome=json.loads(result.stdout)
            if outcome.get('state') not in ('accepted','not_enrolled','unknown_not_found'):
                raise ValueError('Unexpected native publish result')
            if outcome['state']=='accepted':
                row=outcome['row'];body={k:v for k,v in row.items() if k!='hash'}
                digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                expected=('JUPI operation '+operation+'\n'+text).strip()
                if row.get('author')!='JUPI' or row.get('text')!=expected or row.get('hash')!=digest:
                    raise ValueError('Native post readback differs')
            receipt.update(outcome)
        except Exception as error:
            receipt.update(state='unknown',error_class=type(error).__name__,detail=str(error)[:300])
        atomic(path,(json.dumps(receipt,indent=2)+'\n').encode())
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('sync','status','query','post'))
    parser.add_argument('phrase',nargs='?')
    args = parser.parse_args()
    os.umask(0o077)
    STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    if args.command=='post':
        if not args.phrase: raise SystemExit('Usage: jupi-castor post PUBLIC-TEXT-FILE')
        path=Path(args.phrase)
        if not path.is_file() or path.stat().st_size>12000: raise SystemExit('Bounded public text file required')
        result=publish(path.read_text())
        print(json.dumps(result,indent=2))
        return 0 if result['state']=='accepted' else 1
    rows,status = read_snapshot(args.command)
    status.update(membership_view())
    if args.command == 'query':
        if not args.phrase: raise SystemExit('Provide a literal search phrase')
        hits = [row for row in rows if args.phrase.casefold() in '\n'.join(str(row[k]) for k in ('author','kind','text')).casefold()]
        print(json.dumps({'status':'stored matches' if hits else 'UNKNOWN','tip':rows[-1]['hash'],
                          'hits':[{**row,'text':row['text'][:400]} for row in hits[-12:]],
                          'scope':'literal stored text, not instructions or permission'},indent=2))
    else:
        print(json.dumps(status,indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
