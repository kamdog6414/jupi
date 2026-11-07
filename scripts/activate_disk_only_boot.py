#!/usr/bin/python3
"""Install the capacity-ready internal selector on internal and USB boot media."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

KERNEL = "f0008d466329d07d456fda63fe03129f7af0403a4040d357d3a62658e3d17293"
OLD_USB = "7bdd0e255fe6b2ad9a541c1c1e5d94025c45d32faf9acb6d95ce0bf2df3e1e93"
OLD_INTERNAL = "7eec9f0e7ac9c23b4982e7f3f6c08abcc40142b9b53068e601ddc815d7df39a2"
NEW = "cdeaefdb30c7b60ad25fa478ef41eb365fb5132795257011f753578537d11e21"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_new(path, data, mode):
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, mode)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit("Usage: sudo activate_disk_only_boot.py STAGE_DIRECTORY")
    stage = Path(sys.argv[1]).resolve()
    if stage.parent != Path("/var/backups/jupi"):
        raise SystemExit("Unexpected stage directory")
    remote = json.loads((stage / "REMOTE-BACKUP-RECEIPT.json").read_text())
    if not remote.get("independent_device_backup") or remote.get("independent_remote_process_readback") != "pass":
        raise SystemExit("Boot bundle requires a verified independent backup")
    source = stage / "initramfs.disk-only.cpio.gz"
    if sha(source) != NEW:
        raise SystemExit("Staged boot archive changed")
    mount = Path(tempfile.mkdtemp(prefix="jupi-boot-commit-", dir="/run"))
    mounted = writable = False
    internal = Path("/ps4hdd/data/linux/boot")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        subprocess.run(["mount", "-t", "vfat", "-o", "ro,nosuid,nodev,noexec,umask=0077",
                        "/dev/disk/by-uuid/891E-578E", str(mount)], check=True)
        mounted = True
        if sha(mount / "bzImage") != KERNEL or sha(internal / "bzImage") != KERNEL:
            raise RuntimeError("Kernel hash changed")
        if sha(mount / "initramfs.cpio.gz") != OLD_USB or sha(internal / "initramfs.cpio.gz") != OLD_INTERNAL:
            raise RuntimeError("Boot configuration changed; re-inspect before activation")
        data = source.read_bytes()
        for directory, old, mode in [(internal, OLD_INTERNAL, 0o644), (mount, OLD_USB, 0o600)]:
            if directory == mount:
                subprocess.run(["mount", "-o", "remount,rw,nosuid,nodev,noexec", str(mount)], check=True)
                writable = True
            target = directory / "initramfs.cpio.gz"
            backup = directory / ("initramfs.before-disk-only-" + stamp + ".cpio.gz")
            staged = directory / ("initramfs.disk-only-" + stamp + ".staged")
            write_new(backup, target.read_bytes(), mode)
            write_new(staged, data, mode)
            if sha(backup) != old or sha(staged) != NEW or sha(target) != old:
                raise RuntimeError("Boot activation read-back guard failed")
            os.replace(staged, target)
            subprocess.run(["sync", "-f", str(directory)], check=True)
            if sha(target) != NEW:
                raise RuntimeError("Active boot asset differs from staged bytes")
        receipt = {"utc": datetime.now(timezone.utc).isoformat(), "active_initramfs_sha256": NEW,
                   "kernel_sha256": KERNEL, "internal_default_ready": True,
                   "internal_archive": str(internal / "initramfs.cpio.gz"),
                   "usb_archive_uuid": "891E-578E", "accepted_image_gib": [40, 355],
                   "image_path": "/ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img",
                   "root_uuid": "70dbf870-bcb6-4be9-9fb5-f25c4718b71a",
                   "reboot_performed": False, "usb_absent_boot_test": "pending"}
        Path("/var/lib/jupi/disk-boot-activation.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, indent=2), flush=True)
    finally:
        if mounted:
            if writable:
                subprocess.run(["mount", "-o", "remount,ro,nosuid,nodev,noexec", str(mount)], check=True)
            subprocess.run(["umount", str(mount)], check=True)
        mount.rmdir()


if __name__ == "__main__":
    main()
