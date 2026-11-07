#!/usr/bin/python3
"""Search the existing root-owned OS archive; keep recovered key bytes private."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tarfile
import time

SOURCE = Path("/psxitarch-live.tar.gz")
DIRECTORY = Path("/var/backups/jupi/device-secrets")
DESTINATION = DIRECTORY / "eap_hdd_key.bin"


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    if SOURCE.is_symlink() or SOURCE.stat().st_uid != 0:
        raise SystemExit("Unexpected source ownership")
    DIRECTORY.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(DIRECTORY, 0o700)
    if DESTINATION.exists():
        raise SystemExit("A recovered key already exists; inspect without overwriting it")
    count = 0
    last = time.monotonic()
    with tarfile.open(SOURCE, "r|gz") as archive:
        for member in archive:
            count += 1
            if time.monotonic() - last >= 30:
                print(json.dumps({"event": "archive_search_progress", "members_scanned": count}), flush=True)
                last = time.monotonic()
            if member.isfile() and Path(member.name).name == "eap_hdd_key.bin" and member.size in (32, 64):
                body = archive.extractfile(member).read()
                fd = os.open(DESTINATION, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(body)
                    handle.flush()
                    os.fsync(handle.fileno())
                receipt = {"utc": datetime.now(timezone.utc).isoformat(), "source_archive": str(SOURCE),
                           "member_path": member.name, "bytes": member.size,
                           "protected_destination": str(DESTINATION), "key_contents_reported": False,
                           "validation": "pending read-only UFS validation"}
                (DIRECTORY / "recovery-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
                print(json.dumps({"event": "candidate_recovered", "protected_path": str(DESTINATION),
                                  "members_scanned": count, "key_contents_reported": False}), flush=True)
                return 0
    print(json.dumps({"event": "archive_search_complete", "members_scanned": count, "candidate_found": False}), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
