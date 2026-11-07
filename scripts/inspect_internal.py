#!/usr/bin/python3
"""Inspect the historical internal image through read-only device layers.

Unlock material is used only in a mode-0600 file in /run and is never printed.
All mappings and mounts created by this script are removed in finally blocks.
"""
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ARCHIVE = Path("/run/jupi-boot-audit/initramfs.cpio.gz")
ARCHIVE_HASH = "fa7d6f7763ffb5f9f74bf1b32154bd4a961e94b3a9e98e26b53dc187b88fc4d9"
PARTITION = Path("/dev/disk/by-partuuid/673638c8-d972-11f1-8753-709e29577e23")
BASE = Path("/run/jupi-internal-audit")
MAPPER = "jupi-audit-hdd"
OUTPUT = Path("/var/lib/jupi/internal-audit.json")


def command(argv, timeout=25):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def archive_key(data):
    require(hashlib.sha256(data).hexdigest() == ARCHIVE_HASH, "Unrecognized boot archive")
    data = gzip.decompress(data)
    position = 0
    while position + 110 <= len(data):
        header = data[position:position + 110]
        require(header[:6] in (b"070701", b"070702"), "Unrecognized cpio format")
        size, namesize = int(header[54:62], 16), int(header[94:102], 16)
        name = data[position + 110:position + 110 + namesize - 1].decode()
        body = (position + 110 + namesize + 3) & ~3
        if name.lstrip("./") == "key/eap_hdd_key.bin":
            require(size in (32, 64), "Unexpected unlock-key length")
            return data[body:body + size]
        position = (body + size + 3) & ~3
        if name == "TRAILER!!!":
            break
    raise RuntimeError("No internal-disk key in the verified boot archive")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, help="existing root-owned private console key; contents never reported")
    args = parser.parse_args()
    require(os.geteuid() == 0, "Root is required for read-only device mappings")
    require(PARTITION.exists(), "Expected internal partition is absent")
    require(not Path("/dev/mapper", MAPPER).exists(), "Audit mapping already exists")
    require(not BASE.exists(), "Audit directory already exists; inspect before reuse")
    BASE.mkdir(mode=0o700)
    disk_mount, root_mount = BASE / "ufs", BASE / "root"
    disk_mount.mkdir(mode=0o700)
    root_mount.mkdir(mode=0o700)
    mapped = ufs_mounted = root_mounted = False
    loop = None
    key_path = None
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "mode": "read-only",
               "internal_partition_partuuid": PARTITION.name, "internal_written": False,
               "boot_archive_sha256": ARCHIVE_HASH}
    try:
        if args.key_file:
            source = args.key_file
            require(not source.is_symlink() and source.is_file(), "Console key must be a regular file")
            metadata = source.stat()
            require(metadata.st_uid == 0 and metadata.st_mode & 0o077 == 0, "Console key requires root ownership and private permissions")
            require(metadata.st_size in (32, 64), "Unexpected console-key length")
            key = source.read_bytes()
            receipt["unlock_material_source"] = "existing protected root-owned key file"
        else:
            key = archive_key(ARCHIVE.read_bytes())
            receipt["unlock_material_source"] = "verified boot archive"
        fd, key_path = tempfile.mkstemp(prefix=".unlock-", dir=BASE)
        with os.fdopen(fd, "wb") as handle:
            handle.write(key)
        command(["cryptsetup", "open", "--type", "plain", "--readonly", "--cipher", "aes-xts-plain64",
                 "--key-size", "256", "--offset", "0", "--skip", "0", "--key-file", key_path,
                 str(PARTITION), MAPPER])
        mapped = True
        Path(key_path).unlink()
        key_path = None
        require(command(["blockdev", "--getro", "/dev/mapper/" + MAPPER]) == "1", "Mapping is not read-only")
        command(["mount", "-t", "ufs", "-o", "ro,ufstype=ufs2,nosuid,nodev,noexec",
                 "/dev/mapper/" + MAPPER, str(disk_mount)])
        ufs_mounted = True
        receipt["ufs_mounted_read_only"] = True
        space = shutil.disk_usage(disk_mount)
        receipt["internal_volume_space_bytes"] = {"total": space.total, "free": space.free, "used": space.used}
        images = [path for path in [disk_mount / "home/linux.img", disk_mount / "home/Arch.img"] if path.is_file()]
        receipt["images"] = [{"path": "/" + str(path.relative_to(disk_mount)), "bytes": path.stat().st_size} for path in images]
        if images:
            loop = command(["losetup", "--find", "--show", "--read-only", str(images[0])])
            require(command(["blockdev", "--getro", loop]) == "1", "Loop device is not read-only")
            command(["mount", "-t", "ext4", "-o", "ro,noload,nosuid,nodev,noexec", loop, str(root_mount)])
            root_mounted = True
            receipt["image_root_mounted_read_only"] = True
            receipt["image_root_uuid"] = command(["blkid", "-s", "UUID", "-o", "value", loop])
            # Record OS and service metadata; omit profiles, passwords and key material.
            receipt["os_release"] = (root_mount / "etc/os-release").read_text() if (root_mount / "etc/os-release").is_file() else None
            receipt["root_directories"] = sorted(path.name for path in root_mount.iterdir())
            receipt["pi_home_exists"] = (root_mount / "home/pi").is_dir()
            receipt["local_ssh_key_file_exists"] = (root_mount / "home/pi/.ssh/authorized_keys").is_file()
            receipt["enabled_multi_user_units"] = sorted(path.name for path in
                (root_mount / "etc/systemd/system/multi-user.target.wants").glob("*"))
        receipt["status"] = "inspected"
    except Exception as error:
        receipt["status"] = "inspection_stopped"
        receipt["error"] = str(error)
    finally:
        errors = []
        for needed, argv in [(root_mounted, ["umount", str(root_mount)]),
                             (bool(loop), ["losetup", "--detach", loop or ""]),
                             (ufs_mounted, ["umount", str(disk_mount)]),
                             (mapped, ["cryptsetup", "close", MAPPER])]:
            if needed:
                try:
                    command(argv)
                except Exception as error:
                    errors.append(str(error))
        if key_path:
            Path(key_path).unlink(missing_ok=True)
        receipt["cleanup_errors"] = errors
        if not errors:
            root_mount.rmdir()
            disk_mount.rmdir()
            BASE.rmdir()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(receipt, indent=2) + "\n")
        os.chmod(OUTPUT, 0o644)
        print(json.dumps(receipt, indent=2), flush=True)
    return 0 if receipt["status"] == "inspected" and not receipt["cleanup_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
