#!/usr/bin/python3
"""Prepare a bounded offline root-image candidate on Roach, never a device.

Requires verified archive hashes. It writes only a newly created 40 GiB
regular file in root-only backup storage and validates ext4 after restoration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sqlite3
import subprocess
import tarfile
from urllib.parse import quote


def run(argv, timeout=1800):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): {result.stderr[-1000:]}")
    return result.stdout.strip()


def checked_archive(path, expected):
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
        raise RuntimeError("Expected a protected root-owned archive")
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
            raise RuntimeError("Archive hash mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    parser.add_argument("root_sha256")
    parser.add_argument("environment_archive", type=Path)
    parser.add_argument("environment_sha256")
    args = parser.parse_args()
    if os.geteuid() != 0 or os.uname().nodename != "roach":
        raise SystemExit("Run as root on Roach")
    checked_archive(args.root_archive, args.root_sha256)
    checked_archive(args.environment_archive, args.environment_sha256)
    directory = Path("/var/backups/jupi") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-candidate")
    directory.mkdir(mode=0o700)
    image = directory / "jupi-root-candidate.img"
    fd = os.open(image, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    size = 40 * 1024**3
    with os.fdopen(fd, "wb") as handle:
        handle.truncate(size)
        handle.flush()
        os.fsync(handle.fileno())
    metadata = image.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size != size:
        raise RuntimeError("Candidate is not the newly created bounded regular file")
    print(json.dumps({"event": "candidate_regular_file_created", "path": str(image), "bytes": size}), flush=True)
    run(["mkfs.ext4", "-F", "-L", "JUPIROOT", str(image)])
    mount = directory / "root"
    mount.mkdir(mode=0o700)
    loop = None
    mounted = False
    try:
        loop = run(["losetup", "--find", "--show", str(image)])
        run(["mount", "-t", "ext4", "-o", "rw,nosuid,nodev,noexec", loop, str(mount)])
        mounted = True
        run(["tar", "--extract", "--file", str(args.root_archive), "--directory", str(mount),
             "--acls", "--xattrs", "--numeric-owner", "--same-owner"])
        database_names = []
        removed_sidecars = 0
        # Consolidated snapshots must not inherit journals from the live tar.
        with tarfile.open(args.environment_archive, "r:gz") as archive:
            for member in archive:
                if member.isfile() and archive.extractfile(member).read(16) == b"SQLite format 3\x00":
                    database_names.append(member.name)
                    for suffix in ["-wal", "-shm", "-journal"]:
                        sidecar = mount / (member.name + suffix)
                        if not sidecar.resolve().is_relative_to(mount.resolve()):
                            raise RuntimeError("SQLite restore path escaped candidate")
                        if sidecar.exists():
                            sidecar.unlink()
                            removed_sidecars += 1
        run(["tar", "--extract", "--file", str(args.environment_archive), "--directory", str(mount),
             "--acls", "--xattrs", "--numeric-owner", "--same-owner"])
        for name in database_names:
            database = mount / name
            # immutable mode verifies offline files without creating sidecars.
            connection = sqlite3.connect("file:" + quote(str(database), safe="/") + "?mode=ro&immutable=1", uri=True)
            try:
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("Restored SQLite snapshot failed quick_check")
            finally:
                connection.close()
        for name in ["dev", "proc", "sys", "run", "tmp", "mnt"]:
            (mount / name).mkdir(exist_ok=True)
        os.chmod(mount / "tmp", 0o1777)
        required = ["usr/lib/systemd/systemd", "etc/ssh/sshd_config.d/10-jupi.conf",
                    "home/pi/.ssh/authorized_keys", "home/pi/.codex/auth.json",
                    "home/pi/.local/bin/chatgpt", "usr/local/bin/jupi"]
        if not all((mount / name).is_file() for name in required):
            raise RuntimeError("A required runtime/identity/launcher file is missing from the restored candidate")
        autostart = mount / "home/pi/.config/autostart/jupi-session.desktop"
        autostart.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not autostart.exists():
            autostart.write_text("[Desktop Entry]\nType=Application\nName=JUPI research environment\nExec=/home/pi/.local/bin/chatgpt\nTryExec=/home/pi/.local/bin/chatgpt\nTerminal=false\nOnlyShowIn=XFCE;\n")
        os.chown(autostart.parent, 1000, 1000)
        os.chown(autostart, 1000, 1000)
        os.chmod(autostart, 0o644)
        uuid = run(["blkid", "-s", "UUID", "-o", "value", loop])
        run(["sync", "-f", str(mount)])
    finally:
        if mounted:
            run(["umount", str(mount)])
        if loop:
            run(["losetup", "--detach", loop])
        mount.rmdir()
    check = run(["e2fsck", "-f", "-n", str(image)])
    print(json.dumps({"event": "candidate_filesystem_validated", "uuid": uuid}), flush=True)
    with image.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "image": str(image), "logical_bytes": size,
               "allocated_bytes": image.stat().st_blocks * 512, "image_uuid": uuid, "image_sha256": digest,
               "source_root_sha256": args.root_sha256, "source_environment_sha256": args.environment_sha256,
               "restored_sqlite_databases_checked": len(database_names), "stale_sqlite_sidecars_removed": removed_sidecars,
               "filesystem_read_only_check": "pass", "e2fsck_summary": check,
               "installed_on_ps4_internal_drive": False, "booted_on_ps4": False,
               "next_gate": "Inspect and back up the existing internal image, verify free space, and copy candidate under a new filename before boot activation"}
    (directory / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
