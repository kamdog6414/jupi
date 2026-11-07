#!/usr/bin/python3
"""Activate only the tested key-retention hook, preserving USB root recovery."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ORIGINAL = "fa7d6f7763ffb5f9f74bf1b32154bd4a961e94b3a9e98e26b53dc187b88fc4d9"
STAGED = "53445a0849dceb3619434b386b1ec99ab890b08ddbd39ce159ba5336556d2d05"
KERNEL = "f0008d466329d07d456fda63fe03129f7af0403a4040d357d3a62658e3d17293"
SOURCE = Path("/var/backups/jupi/20261106T232922Z-key-capture-stage/initramfs.key-retention.cpio.gz")
MOUNT = Path("/run/jupi-boot-activation")


def run(argv):
    return subprocess.check_output(argv, text=True, timeout=45).strip()


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    if digest(SOURCE) != STAGED:
        raise SystemExit("Staged archive changed")
    # Independent metadata and boot-asset backups must already be verified.
    for name in ["/var/backups/jupi/20261106T232612Z-environment/REMOTE-BACKUP-RECEIPT.json",
                 "/var/backups/jupi/20261106T232922Z-key-capture-stage/REMOTE-BACKUP-RECEIPT.json",
                 "/var/backups/jupi/20261106T233405Z-full-root-transfer/RECEIPT.json"]:
        receipt = json.loads(Path(name).read_text())
        if not receipt.get("independent_device_backup") or receipt.get("independent_remote_process_readback") != "pass":
            raise SystemExit("Verified independent backup prerequisite is unmet")
    if MOUNT.exists():
        raise SystemExit("Activation mount path already exists; inspect before reuse")
    MOUNT.mkdir(mode=0o700)
    mounted = writable = False
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        run(["mount", "-t", "vfat", "-o", "ro,nosuid,nodev,noexec,umask=0077", "/dev/disk/by-uuid/891E-578E", str(MOUNT)])
        mounted = True
        if digest(MOUNT / "bzImage") != KERNEL or digest(MOUNT / "initramfs.cpio.gz") != ORIGINAL:
            raise RuntimeError("Current USB boot assets changed; inspect before activation")
        run(["mount", "-o", "remount,rw,nosuid,nodev,noexec", str(MOUNT)])
        writable = True
        backup = MOUNT / ("initramfs.jupi-before-key-retention-" + stamp + ".cpio.gz")
        temp = MOUNT / ("initramfs.jupi-key-retention-staged-" + stamp + ".cpio.gz")
        for target, source in [(backup, MOUNT / "initramfs.cpio.gz"), (temp, SOURCE)]:
            with target.open("xb") as output:
                output.write(source.read_bytes())
                output.flush()
                os.fsync(output.fileno())
        if digest(backup) != ORIGINAL or digest(temp) != STAGED:
            raise RuntimeError("FAT backup/staged read-back failed")
        if digest(MOUNT / "initramfs.cpio.gz") != ORIGINAL:
            raise RuntimeError("Active archive changed during activation")
        os.replace(temp, MOUNT / "initramfs.cpio.gz")
        run(["sync", "-f", str(MOUNT)])
        if digest(MOUNT / "initramfs.cpio.gz") != STAGED or digest(MOUNT / "bzImage") != KERNEL:
            raise RuntimeError("Activated boot assets did not read back correctly")
        receipt = {"utc": datetime.now(timezone.utc).isoformat(), "active_initramfs_sha256": STAGED,
                   "previous_initramfs_sha256": ORIGINAL, "kernel_sha256": KERNEL,
                   "fat_rollback_filename": backup.name, "usb_root_selection_preserved": True,
                   "internal_disk_written": False, "reboot_performed": False,
                   "next_gate": "Console-loader-assisted USB restart, retained key and read-only internal image audit"}
        Path("/var/lib/jupi/boot-activation.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, indent=2), flush=True)
    finally:
        if mounted:
            if writable:
                run(["mount", "-o", "remount,ro,nosuid,nodev,noexec", str(MOUNT)])
            run(["umount", str(MOUNT)])
        MOUNT.rmdir()


if __name__ == "__main__":
    main()
