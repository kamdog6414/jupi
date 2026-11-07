#!/usr/bin/python3
"""Grow only the verified active internal image to 355 GiB, online.

No partition table is changed. The boot selector must already accept both
the original and target sizes, with an independently verified recovery copy.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

IMAGE = Path("/ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img")
ROOT_UUID = "70dbf870-bcb6-4be9-9fb5-f25c4718b71a"
TARGET = 355 * 1024**3
HEADROOM = 16 * 1024**3
CLI_SHA = "3f5d4eee5787f8991f9a9447e7cfc2f7e1438b77d3b885e2f98e4bdceca12bb1"


def run(argv):
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()} {result.stdout.strip()}")
    return result.stdout.strip()


def emit(event, **fields):
    print(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "event": event, **fields}), flush=True)


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    if run(["findmnt", "-n", "-o", "SOURCE", "/"]) != "/dev/loop0" or run(["findmnt", "-n", "-o", "UUID", "/"]) != ROOT_UUID:
        raise SystemExit("Unexpected root; no storage change permitted")
    info = json.loads(run(["losetup", "-J", "-l", "-O", "NAME,BACK-FILE,OFFSET,RO"]))
    loop = next(row for row in info["loopdevices"] if row["name"] == "/dev/loop0")
    if loop["back-file"] != str(IMAGE) or loop["offset"] != 0 or loop["ro"]:
        raise SystemExit("Unexpected active loop mapping")
    activation = json.loads(Path("/var/lib/jupi/disk-boot-activation.json").read_text())
    if activation.get("accepted_image_gib") != [40, 355] or not activation.get("internal_default_ready"):
        raise SystemExit("Capacity-ready boot configuration is not confirmed")
    backup = json.loads(Path("/var/backups/jupi/20261107T050054Z-operations/REMOTE-BACKUP-RECEIPT.json").read_text())
    if not backup.get("independent_device_backup") or backup.get("independent_remote_process_readback") != "pass":
        raise SystemExit("Latest operations checkpoint is not independently protected")
    with Path("/usr/local/bin/jupi").open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != CLI_SHA:
            raise SystemExit("Boot-pinned command changed")
    metadata = IMAGE.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_nlink != 1 or metadata.st_size not in (40 * 1024**3, TARGET):
        raise SystemExit("Unexpected backing image")
    space = os.statvfs("/ps4hdd")
    available = space.f_bavail * space.f_frsize
    allocated = metadata.st_blocks * 512
    if TARGET > allocated + available - HEADROOM:
        raise SystemExit("Target would consume the required backing-filesystem headroom")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    checkpoint = Path("/var/backups/jupi") / (stamp + "-root-growth")
    checkpoint.mkdir(mode=0o700)
    (checkpoint / "superblock-before.txt").write_text(run(["tune2fs", "-l", "/dev/loop0"]) + "\n")
    # Probe the UFS sparse-file/addressing path at the target's highest offset.
    probe = IMAGE.parent / (".jupi-capacity-probe-" + stamp)
    fd = os.open(probe, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    marker = (b"JUPI capacity probe\n" * 256)[:4096]
    try:
        os.ftruncate(fd, TARGET)
        os.pwrite(fd, marker, TARGET - 4096)
        os.fsync(fd)
        if os.fstat(fd).st_blocks * 512 > 16 * 1024**2:
            raise RuntimeError("Backing filesystem did not preserve the sparse probe")
    finally:
        os.close(fd)
    try:
        with probe.open("rb") as handle:
            handle.seek(TARGET - 4096)
            if handle.read(len(marker)) != marker:
                raise RuntimeError("Large-offset backing-file read-back failed")
    finally:
        probe.unlink()
    emit("backing_sparse_capacity_probe_passed", target_bytes=TARGET, backing_available_bytes=available,
         minimum_headroom_bytes=HEADROOM)
    fd = os.open(IMAGE, os.O_RDWR | os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_ino != metadata.st_ino:
            raise RuntimeError("Image inode changed")
        if metadata.st_size < TARGET:
            os.ftruncate(fd, TARGET)
        os.fsync(fd)
    finally:
        os.close(fd)
    emit("backing_image_capacity_ready", bytes=TARGET)
    run(["losetup", "--set-capacity", "/dev/loop0"])
    if int(run(["blockdev", "--getsize64", "/dev/loop0"])) != TARGET:
        raise RuntimeError("Loop capacity was not updated")
    emit("online_ext4_growth_started")
    output = run(["resize2fs", "/dev/loop0"])
    emit("online_ext4_growth_finished", output=output)
    run(["tune2fs", "-m", "1", "/dev/loop0"])
    run(["sync", "-f", "/"])
    run(["sync", "-f", "/ps4hdd"])
    superblock = run(["tune2fs", "-l", "/dev/loop0"])
    values = dict(line.split(":", 1) for line in superblock.splitlines() if ":" in line)
    filesystem_bytes = int(values["Block count"].strip()) * int(values["Block size"].strip())
    if filesystem_bytes != TARGET or run(["findmnt", "-n", "-o", "UUID", "/"]) != ROOT_UUID:
        raise RuntimeError("Filesystem capacity/identity did not verify")
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "root_uuid": ROOT_UUID,
               "image": str(IMAGE), "previous_image_bytes": metadata.st_size,
               "image_bytes": TARGET, "filesystem_bytes": filesystem_bytes,
               "reserved_root_percent": 1, "backing_headroom_minimum_bytes": HEADROOM,
               "partition_table_changed": False, "online_growth": "verified",
               "backing_image_allocated_bytes": IMAGE.stat().st_blocks * 512,
               "root_statvfs": {"total_bytes": os.statvfs("/").f_blocks * os.statvfs("/").f_frsize,
                                "available_bytes": os.statvfs("/").f_bavail * os.statvfs("/").f_frsize}}
    Path("/var/lib/jupi/root-capacity.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (checkpoint / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
