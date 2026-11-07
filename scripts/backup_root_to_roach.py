#!/usr/bin/python3
"""Stream the running root to protected Roach storage, compressing on Roach.

The separate consistent environment checkpoint supplies live-database recovery.
This archive preserves installed binaries, ownership, ACLs and extended attrs.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess

RECEIVER = r'''
import gzip,hashlib,json,os,shutil,sys,tarfile,time
from pathlib import Path
os.umask(0o077)
base=Path('/var/backups/jupi')
if base.is_symlink(): raise SystemExit('Refusing symlink backup directory')
base.mkdir(mode=0o700,exist_ok=True)
if base.stat().st_uid!=0: raise SystemExit('Backup directory must belong to root')
os.chmod(base,0o700)
if shutil.disk_usage(base).free<20*1024**3: raise SystemExit('Less than 20 GiB free on receiving filesystem')
target=base/('JUPI-ROOT-'+sys.argv[1]+'.tar.gz')
partial=target.with_suffix('.gz.partial')
fd=os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
total=0;last=time.monotonic()
print(json.dumps({'event':'root_receiver_ready','private_destination':str(target)}),flush=True)
with os.fdopen(fd,'wb') as raw:
 with gzip.GzipFile(filename='',mode='wb',compresslevel=1,fileobj=raw,mtime=0) as output:
  while True:
   block=sys.stdin.buffer.read(1024*1024)
   if not block: break
   output.write(block);total+=len(block)
   if time.monotonic()-last>=30:
    print(json.dumps({'event':'root_backup_progress','uncompressed_bytes_received':total}),flush=True);last=time.monotonic()
 raw.flush();os.fsync(raw.fileno())
count=0
with tarfile.open(partial,'r|gz') as archive:
 for member in archive:
  count+=1
  if member.isfile():
   stream=archive.extractfile(member)
   while stream.read(1024*1024): pass
with partial.open('rb') as handle: digest=hashlib.file_digest(handle,'sha256').hexdigest()
if target.exists(): raise SystemExit('Final archive already exists')
os.replace(partial,target)
directory=os.open(base,os.O_RDONLY|os.O_DIRECTORY);os.fsync(directory);os.close(directory)
print(json.dumps({'event':'root_backup_received_and_verified','remote_archive':str(target),'sha256':digest,'compressed_bytes':target.stat().st_size,'uncompressed_bytes':total,'archive_members_read_back':count,'permissions':'root only'}),flush=True)
'''


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    local = Path("/var/backups/jupi") / (stamp + "-full-root-transfer")
    local.mkdir(mode=0o700)
    ssh = ["ssh", "-T", "-F", "/etc/jupi/ssh/roach.conf", "-o", "ClearAllForwardings=yes", "jupi-peer",
           shlex.join(["sudo", "-n", "python3", "-u", "-B", "-c", RECEIVER, stamp])]
    excluded = ["./proc", "./sys", "./dev", "./run", "./tmp", "./mnt", "./media", "./lost+found",
                "./var/backups/jupi", "./psxitarch-live.tar.gz", "./home/pi/.cache", "./home/pi/Downloads",
                "./var/cache/pacman/pkg"]
    tar = ["tar", "--create", "--file=-", "--one-file-system", "--acls", "--xattrs", "--numeric-owner", "--sparse"]
    tar.extend("--exclude=" + name for name in excluded)
    tar.extend(["-C", "/", "."])
    print(json.dumps({"event": "full_root_backup_started", "utc": datetime.now(timezone.utc).isoformat(),
                      "local_receipt_directory": str(local), "compression_host": "Roach"}), flush=True)
    result = None
    with (local / "source-tar.stderr").open("w") as tar_errors, (local / "transport.stderr").open("w") as ssh_errors:
        source = subprocess.Popen(tar, stdout=subprocess.PIPE, stderr=tar_errors)
        remote = subprocess.Popen(ssh, stdin=source.stdout, stdout=subprocess.PIPE, stderr=ssh_errors, text=True)
        source.stdout.close()
        for line in remote.stdout:
            print(line.rstrip(), flush=True)
            event = json.loads(line)
            if event.get("event") == "root_backup_received_and_verified":
                result = event
        remote_code = remote.wait()
        source_code = source.wait()
    if remote_code != 0 or source_code not in (0, 1) or result is None:
        raise RuntimeError(f"Root backup incomplete: source={source_code}, transport={remote_code}; inspect protected logs")
    verify = ["ssh", "-T", "-F", "/etc/jupi/ssh/roach.conf", "-o", "ClearAllForwardings=yes", "jupi-peer",
              shlex.join(["sudo", "-n", "sha256sum", result["remote_archive"]])]
    readback = subprocess.run(verify, capture_output=True, text=True, timeout=600, check=True)
    if readback.stdout.split()[0] != result["sha256"]:
        raise RuntimeError("Independent root archive hash differs")
    receipt = {**result, "utc": datetime.now(timezone.utc).isoformat(), "source_tar_exit_code": source_code,
               "source_changed_during_backup": source_code == 1,
               "consistent_environment_checkpoint_required_for_live_databases": True,
               "independent_remote_process_readback": "pass", "independent_device_backup": True,
               "exclusions": excluded}
    (local / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
