#!/usr/bin/python3
"""Build a reviewed USB boot-key retention hook; do not activate or reboot."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path

SOURCE = Path("/var/backups/jupi/20261106T230628Z/boot-assets/initramfs.cpio.gz")
PIN = "fa7d6f7763ffb5f9f74bf1b32154bd4a961e94b3a9e98e26b53dc187b88fc4d9"


def members(data):
    position = 0
    while position + 110 <= len(data):
        header = data[position:position + 110]
        if header[:6] != b"070701":
            raise RuntimeError("Unrecognized cpio format")
        size, namesize = int(header[54:62], 16), int(header[94:102], 16)
        name = data[position + 110:position + 110 + namesize - 1].decode()
        start = (position + 110 + namesize + 3) & ~3
        end = (start + size + 3) & ~3
        yield name, position, start, size, end
        position = end
        if name == "TRAILER!!!":
            return


def patch(data, hook):
    entries = list(members(data))
    matches = [entry for entry in entries if entry[0].lstrip("./") == "usbroot.sh"]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one USB selector")
    name, position, start, size, end = matches[0]
    old = data[start:start + size]
    if b"[ -x /newroot/sbin/init ]" not in old or b"JUPI_CONSOLE_KEY" in old:
        raise RuntimeError("Unrecognized USB selector")
    body = old.rstrip(b"\n") + b"\n\n" + hook
    header = bytearray(data[position:start])
    header[54:62] = f"{len(body):08x}".encode()
    padding = b"\0" * ((-(start + len(body))) % 4)
    updated = data[:position] + header + body + padding + data[end:]
    old_members = {entry[0]: data[entry[2]:entry[2] + entry[3]] for entry in entries}
    new_members = {entry[0]: updated[entry[2]:entry[2] + entry[3]] for entry in members(updated)}
    changed = [key for key in old_members if old_members[key] != new_members[key]]
    if changed != [name] or set(old_members) != set(new_members):
        raise RuntimeError("Unexpected archive member change")
    return updated, old, body


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    compressed = SOURCE.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != PIN:
        raise SystemExit("Source archive pin mismatch")
    hook = (Path(__file__).resolve().parents[1] / "config/capture-console-key.sh").read_bytes()
    updated, old, body = patch(gzip.decompress(compressed), hook)
    result = gzip.compress(updated, mtime=0)
    destination = Path("/var/backups/jupi") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-key-capture-stage")
    destination.mkdir(mode=0o700)
    output = destination / "initramfs.key-retention.cpio.gz"
    output.write_bytes(result)
    os.chmod(output, 0o600)
    with output.open("rb") as handle:
        os.fsync(handle.fileno())
    if output.read_bytes() != result:
        raise RuntimeError("Staged archive read-back mismatch")
    (destination / "usbroot.before.sh").write_bytes(old)
    (destination / "usbroot.after.sh").write_bytes(body)
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "source_sha256": PIN,
               "staged_archive": str(output), "staged_sha256": hashlib.sha256(result).hexdigest(),
               "only_member_body_changed": "usbroot.sh", "root_selection_preserved": True,
               "purpose": "Retain the key dynamically appended by a compatible PS4 loader, inside protected USB recovery storage before switch_root",
               "active_boot_archive_changed": False, "reboot_performed": False,
               "loader_key_availability": "not yet tested on hardware"}
    (destination / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
