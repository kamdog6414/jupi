#!/usr/bin/python3
"""Stream a private verified environment archive into root-only Roach storage."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

RECEIVE = r'''
import hashlib,json,os,sys
from pathlib import Path
os.umask(0o077)
expected=sys.argv[1]
base=Path('/var/backups/jupi')
if base.is_symlink(): raise SystemExit('Symlink backup store refused')
base.mkdir(mode=0o700,exist_ok=True)
if base.stat().st_uid!=0: raise SystemExit('Backup store must belong to root')
os.chmod(base,0o700)
target=base/('JUPI-ENV-'+expected+'.tar.gz')
temporary=base/('.JUPI-ENV-'+expected+'-'+str(os.getpid())+'.partial')
fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
h=hashlib.sha256()
with os.fdopen(fd,'wb') as output:
 while True:
  block=sys.stdin.buffer.read(1024*1024)
  if not block: break
  h.update(block); output.write(block)
 output.flush(); os.fsync(output.fileno())
if h.hexdigest()!=expected:
 temporary.unlink(); raise SystemExit('Received hash differs')
with temporary.open('rb') as handle:
 readback=hashlib.file_digest(handle,'sha256').hexdigest()
if readback!=expected: raise SystemExit('Remote file read-back differs')
if target.exists():
 with target.open('rb') as handle:
  if hashlib.file_digest(handle,'sha256').hexdigest()!=expected: raise SystemExit('Existing backup differs')
 temporary.unlink()
else: os.replace(temporary,target)
fd=os.open(base,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps({'remote_archive':str(target),'sha256':readback,'bytes':target.stat().st_size,'root_only':True}))
'''


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit("Usage: sudo python3 -B export_checkpoint.py COMPLETE-RECEIPT.json")
    receipt_path = Path(sys.argv[1]).resolve()
    receipt = json.loads(receipt_path.read_text())
    source = Path(receipt["archive"])
    if receipt["snapshot_errors"] or source.stat().st_uid != 0 or source.stat().st_mode & 0o077:
        raise SystemExit("Archive is incomplete or insufficiently protected")
    with source.open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha256").hexdigest()
    if actual != receipt["archive_sha256"]:
        raise SystemExit("Local archive hash changed")
    command = ["ssh", "-T", "-F", "/etc/jupi/ssh/roach.conf", "-o", "ClearAllForwardings=yes",
               "jupi-peer", shlex.join(["sudo", "-n", "python3", "-B", "-c", RECEIVE, actual])]
    print(json.dumps({"event": "private_checkpoint_transfer_started", "bytes": source.stat().st_size}), flush=True)
    with source.open("rb") as handle:
        result = subprocess.run(command, stdin=handle, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError("Private transfer failed: " + result.stderr[-1500:])
    remote = json.loads(result.stdout)
    verify = ["ssh", "-T", "-F", "/etc/jupi/ssh/roach.conf", "-o", "ClearAllForwardings=yes", "jupi-peer",
              shlex.join(["sudo", "-n", "sha256sum", remote["remote_archive"]])]
    independent = subprocess.run(verify, capture_output=True, text=True, timeout=180, check=True)
    if independent.stdout.split()[0] != actual:
        raise RuntimeError("Independent remote hash check failed")
    result_receipt = {"utc": datetime.now(timezone.utc).isoformat(), "local_archive": str(source),
                      "remote_host": "roach@192.168.77.3", **remote,
                      "independent_remote_process_readback": "pass", "independent_device_backup": True}
    (receipt_path.parent / "REMOTE-BACKUP-RECEIPT.json").write_text(json.dumps(result_receipt, indent=2) + "\n")
    print(json.dumps(result_receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
