#!/usr/bin/python3
"""Stage the known internal-root selector for the planned 355 GiB capacity.

The original 40 GiB size is retained as an accepted recovery state. Nothing
else in the archive, root UUID, image pathname or command pin is changed.
"""
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

PIN = "7bdd0e255fe6b2ad9a541c1c1e5d94025c45d32faf9acb6d95ce0bf2df3e1e93"
TARGET_BYTES = 355 * 1024**3
OLD_TEST = b'[ "$(jupi_size "$JUPI_IMAGE")" != 42949672960 ]'
NEW_TEST = b'{ [ "$(jupi_size "$JUPI_IMAGE")" != 42949672960 ] && [ "$(jupi_size "$JUPI_IMAGE")" != ' + str(TARGET_BYTES).encode() + b' ]; }'


def transform(data, member_parser):
    entries = list(member_parser(data))
    selected = [item for item in entries if item[0].lstrip("./") == "usbroot.sh"]
    if len(selected) != 1:
        raise RuntimeError("Expected exactly one selector")
    name, position, start, size, end = selected[0]
    body = data[start:start + size]
    if body.count(OLD_TEST) != 1:
        raise RuntimeError("The known image-size guard has changed")
    updated_body = body.replace(OLD_TEST, NEW_TEST)
    header = bytearray(data[position:start])
    header[54:62] = f"{len(updated_body):08x}".encode()
    updated = data[:position] + header + updated_body + b"\0" * (-(start + len(updated_body)) % 4) + data[end:]
    before = {n: data[s:s + z] for n, _, s, z, _ in entries}
    after = {n: updated[s:s + z] for n, _, s, z, _ in member_parser(updated)}
    if set(before) != set(after) or [n for n in before if before[n] != after[n]] != [name]:
        raise RuntimeError("Unexpected archive change")
    return updated, updated_body


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("stage", root / "scripts/stage_key_capture.py")
    stage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage)
    directory = Path("/var/backups/jupi") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-disk-only")
    directory.mkdir(mode=0o700)
    mount = Path(tempfile.mkdtemp(prefix="jupi-disk-boot-", dir="/run"))
    mounted = False
    try:
        subprocess.run(["mount", "-t", "vfat", "-o", "ro,nosuid,nodev,noexec,umask=0077",
                        "/dev/disk/by-uuid/891E-578E", str(mount)], check=True)
        mounted = True
        compressed = (mount / "initramfs.cpio.gz").read_bytes()
        if hashlib.sha256(compressed).hexdigest() != PIN:
            raise RuntimeError("Current USB selector archive pin differs")
        for source, name in [(mount / "initramfs.cpio.gz", "usb-initramfs.before.cpio.gz"),
                             (mount / "bzImage", "bzImage"),
                             (Path("/ps4hdd/data/linux/boot/initramfs.cpio.gz"), "internal-initramfs.before.cpio.gz")]:
            (directory / name).write_bytes(source.read_bytes())
            os.chmod(directory / name, 0o600)
        data, selector = transform(gzip.decompress(compressed), stage.members)
        output = directory / "initramfs.disk-only.cpio.gz"
        output.write_bytes(gzip.compress(data, mtime=0))
        os.chmod(output, 0o600)
        (directory / "usbroot.after.sh").write_bytes(selector)
        # Check using the exact BusyBox binary packaged in this initramfs.
        for name, _, start, size, _ in stage.members(data):
            if name.lstrip("./") == "bin/busybox":
                binary = directory / "busybox"
                binary.write_bytes(data[start:start + size])
                os.chmod(binary, 0o700)
                subprocess.run([str(binary), "ash", "-n", str(directory / "usbroot.after.sh")], check=True)
                break
        receipt = {"utc": datetime.now(timezone.utc).isoformat(), "stage_directory": str(directory),
                   "source_usb_sha256": PIN, "staged_archive": str(output),
                   "staged_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                   "accepted_image_bytes": [42949672960, TARGET_BYTES], "only_changed_member": "usbroot.sh",
                   "purpose": "Use the current internal root at 40 or 355 GiB; preserve USB recovery and all identity guards",
                   "active_boot_files_changed": False}
        (directory / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
        for path in directory.iterdir():
            if path.is_file():
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
        print(json.dumps(receipt, indent=2), flush=True)
    finally:
        if mounted:
            subprocess.run(["umount", str(mount)], check=True)
        mount.rmdir()


if __name__ == "__main__":
    main()
