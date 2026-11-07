#!/usr/bin/python3
"""Stage the reviewed observer and offline image builder in private Roach storage."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

RECEIVE = r'''
import hashlib,json,os,sys
from pathlib import Path
os.umask(0o077)
name=sys.argv[1]
if name not in ['watch_reboot_on_roach.py','prepare_candidate_on_roach.py']: raise SystemExit('Unexpected tool name')
base=Path('/var/backups/jupi/tools')
base.mkdir(parents=True,mode=0o700,exist_ok=True)
if base.is_symlink() or base.stat().st_uid!=0: raise SystemExit('Unexpected tool directory')
os.chmod(base,0o700)
body=sys.stdin.buffer.read()
target=base/name
if target.is_symlink(): raise SystemExit('Symlink target refused')
if target.exists() and target.read_bytes()!=body:
 old=target.read_bytes();backup=base/(name+'.'+hashlib.sha256(old).hexdigest()[:12]+'.previous')
 if not backup.exists():
  fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o700)
  with os.fdopen(fd,'wb') as f: f.write(old);f.flush();os.fsync(f.fileno())
 temporary=base/(name+'.'+str(os.getpid())+'.new')
 fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o700)
 with os.fdopen(fd,'wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
 os.replace(temporary,target)
if not target.exists():
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o700)
 with os.fdopen(fd,'wb') as f: f.write(body); f.flush(); os.fsync(f.fileno())
print(json.dumps({'staged_tool':str(target),'sha256':hashlib.sha256(body).hexdigest()}))
'''


def main():
    directory = Path(__file__).resolve().parent
    for name in ["watch_reboot_on_roach.py", "prepare_candidate_on_roach.py"]:
        body = (directory / name).read_bytes()
        command = ["ssh", "-T", "-F", "/etc/jupi/ssh/roach.conf", "-o", "ClearAllForwardings=yes", "jupi-peer",
                   shlex.join(["sudo", "-n", "python3", "-B", "-c", RECEIVE, name])]
        result = subprocess.run(command, input=body, capture_output=True, timeout=30, check=True)
        receipt = json.loads(result.stdout)
        if receipt["sha256"] != hashlib.sha256(body).hexdigest():
            raise RuntimeError("Remote tool bytes differ")
        print(json.dumps(receipt), flush=True)
    preflight = ["ssh", "-T", "-F", "/etc/jupi/ssh/roach.conf", "-o", "ClearAllForwardings=yes", "jupi-peer",
                 "sudo -n python3 -B /var/backups/jupi/tools/watch_reboot_on_roach.py --preflight-only"]
    result = subprocess.run(preflight, capture_output=True, text=True, timeout=90, check=True)
    print(result.stdout.strip(), flush=True)


if __name__ == "__main__":
    main()
