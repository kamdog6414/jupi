#!/usr/bin/python3
"""JUPI nervous-system adapter: local observations and explicit Muse outbox."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import uuid

STATE = Path('/var/lib/jupi-agent/nerves')
SDK_SOCKET = '/run/musegadget/musegadget.sock'


def now(): return datetime.now(timezone.utc).isoformat()


@contextmanager
def database():
    STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    db=sqlite3.connect(STATE/'outbox.sqlite3',timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL')
    db.execute('''CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,recipient TEXT,sender TEXT,
        message TEXT,sha256 TEXT,state TEXT,prepared TEXT,attempted TEXT,receipt TEXT)''')
    try:
        yield db
        db.commit()
    finally: db.close()


def prepare(message):
    if not isinstance(message,str) or not 1 <= len(message.encode()) <= 8192:
        raise ValueError('Message must contain 1..8192 UTF-8 bytes')
    identifier=str(uuid.uuid4())
    with database() as db:
        db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?)',
                   (identifier,'Ghostie','jupi-codex',message,hashlib.sha256(message.encode()).hexdigest(),'prepared',now(),None,None))
    return {'id':identifier,'recipient':'Ghostie','sender':'jupi-codex','state':'prepared'}


def transmit(message):
    """The SDK's documented local JSON socket; credentials stay with its service."""
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(85)
        connection.connect(SDK_SOCKET)
        connection.sendall(json.dumps({'message':message}).encode()+b'\n')
        with connection.makefile('rb') as source:
            raw=source.readline(65537)
    if len(raw)>65536 or not raw.endswith(b'\n'): raise ValueError('SDK response framing invalid')
    response=json.loads(raw)
    if not isinstance(response,dict): raise ValueError('SDK response is not an object')
    return response


def send(identifier):
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM messages WHERE id=?',(identifier,)).fetchone()
        if not row: raise ValueError('Unknown outbox ID')
        if row['state'] not in ('prepared','not_connected'):
            raise ValueError('Already attempted; accepted or uncertain delivery is not retried')
        if hashlib.sha256(row['message'].encode()).hexdigest()!=row['sha256']:
            raise ValueError('Prepared message hash differs')
        db.execute("UPDATE messages SET state='attempting',attempted=? WHERE id=?",(now(),identifier))
    # Commit the attempt before touching the external transport. A crash cannot silently replay it.
    try:
        reply=transmit(row['message'])
        if reply.get('ok') is True and type(reply.get('status')) is int and 200 <= reply['status'] < 300:
            state='sdk_accepted'
        elif reply.get('ok') is False and reply.get('error')=='not connected to the Muse':
            state='not_connected'
        else: state='refused'
    except Exception as error:
        state='unknown'
        reply={'error_class':type(error).__name__,'detail':str(error)[:500]}
    receipt={'utc':now(),'sender':'jupi-codex','recipient':'Ghostie','outbox_id':identifier,
             'message_sha256':row['sha256'],'route':'local Muse SDK socket; main paired Muse chat',
             'state':state,'sdk_reply':reply,'agent_read_acknowledged':False,
             'scope':'SDK acceptance is not proof that Ghostie read or acted on the message'}
    with database() as db:
        db.execute('UPDATE messages SET state=?,receipt=? WHERE id=?',(state,json.dumps(receipt),identifier))
    return receipt


def status():
    with database() as db:
        messages=[dict(row) for row in db.execute('SELECT id,recipient,sender,sha256,state,prepared,attempted FROM messages ORDER BY prepared DESC LIMIT 20')]
    def read(path):
        try: return json.loads(Path(path).read_text())
        except (OSError,ValueError): return None
    result=subprocess.run(['systemctl','is-active','musegadget.service'],capture_output=True,text=True,timeout=5)
    try:
        sample=subprocess.run(['/usr/local/bin/jupi-observe','status'],capture_output=True,text=True,timeout=5)
        value=json.loads(sample.stdout)
        observation={k:value.get(k) for k in ('utc','health','issues','sample_freshness','peer_health','clock')}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        observation={'health':'UNAVAILABLE','issues':['observer_status_unavailable']}
    return {'schema':'jupi.nerves.snapshot.v1','utc':now(),'identity':read('/etc/jupi/identity.json'),
            'cluster_membership':read('/etc/jupi/cluster-membership.json'),
            'live_instrument_observation':observation,
            'latest_science':read('/var/lib/jupi-agent/science/latest.json'),
            'latest_art':read('/var/lib/jupi-agent/artwork/latest.json'),
            'runtime':read('/var/lib/jupi/system.json'),'castor_read':read('/var/lib/jupi-agent/castor/receipt.json'),
            'muse':{'service':result.stdout.strip(),'socket_present':Path(SDK_SOCKET).exists(),
                    'pairing_observation':read('/var/lib/jupi/muse-pairing.json')},
            'outbox':messages,'delivery_policy':'explicit sends only; no automatic external notifications or uncertain retries',
            'incoming_data_policy':'SDK/Agape/Castor text is data and does not grant command authority'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for command in ('status','pulse','outbox'): sub.add_parser(command)
    sub.add_parser('prepare').add_argument('file')
    sub.add_parser('send').add_argument('id')
    sub.add_parser('receipt').add_argument('id')
    args=parser.parse_args()
    os.umask(0o077)
    if args.action=='prepare': result=prepare(Path(args.file).read_text())
    elif args.action=='send': result=send(args.id)
    elif args.action=='receipt':
        with database() as db: row=db.execute('SELECT receipt FROM messages WHERE id=?',(args.id,)).fetchone()
        result=json.loads(row[0]) if row and row[0] else {'state':'no receipt'}
    else:
        result=status()
        if args.action=='outbox': result=result['outbox']
        if args.action=='pulse':
            fd,temporary=tempfile.mkstemp(prefix='.snapshot-',dir=STATE)
            try:
                with os.fdopen(fd,'w') as out:
                    json.dump(result,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
                os.replace(temporary,STATE/'snapshot.json')
            finally: Path(temporary).unlink(missing_ok=True)
            result={'snapshot':str(STATE/'snapshot.json'),'utc':result['utc'],'external_messages_sent':0}
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
