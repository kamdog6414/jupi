#!/usr/bin/python3
"""Complete a live checkpoint by briefly quiescing Electron database writers.

Only the pi-owned ChatGPT processes are paused; a separate watchdog resumes
them even if the copying process exits unexpectedly. All bytes stay private.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import tarfile
import time


def processes():
    found = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid == 1000 and (path / "comm").read_text().strip() == "ChatGPT":
                found.append(int(path.name))
        except (OSError, ProcessLookupError):
            pass
    return found


def resume(pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGCONT)
        except ProcessLookupError:
            pass


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit("Usage: sudo python3 -B complete_environment_checkpoint.py CHECKPOINT_DIRECTORY")
    directory = Path(sys.argv[1]).resolve()
    if directory.parent != Path("/var/backups/jupi") or directory.stat().st_uid != 0:
        raise SystemExit("Unexpected checkpoint path")
    receipt_path = directory / "RECEIPT.json"
    previous = json.loads(receipt_path.read_text())
    missing = previous["snapshot_errors"]
    targets = [Path("/") / entry["path"] for entry in missing]
    if any(not str(path).startswith("/home/pi/.config/Codex/") for path in targets):
        raise SystemExit("An unavailable database is outside the expected Electron profile")
    # Warm source pages before the short pause. Copy DB + recovery journals as a set.
    files = [candidate for path in targets for candidate in [path, Path(str(path) + "-wal"), Path(str(path) + "-journal")]
             if candidate.is_file()]
    if sum(path.stat().st_size for path in files) > 32 * 1024 * 1024:
        raise SystemExit("Database set exceeds the bounded pause-copy budget")
    for path in files:
        path.read_bytes()
    pids = processes()
    if not pids:
        raise SystemExit("No live Electron writers found; inspect before capture")
    watchdog = os.fork()
    if watchdog == 0:
        time.sleep(15)
        resume(pids)
        os._exit(0)
    captured = {}
    start = time.monotonic()
    try:
        for pid in pids:
            os.kill(pid, signal.SIGSTOP)
        deadline = time.monotonic() + 3
        for pid in pids:
            while True:
                state = Path(f"/proc/{pid}/status").read_text().split("State:", 1)[1].splitlines()[0]
                if "T" in state:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("A writer did not reach its paused state")
                time.sleep(0.01)
        for path in files:
            captured[path] = path.read_bytes()
    finally:
        resume(pids)
        os.kill(watchdog, signal.SIGTERM)
        os.waitpid(watchdog, 0)
    pause_seconds = time.monotonic() - start
    print(json.dumps({"event": "database_writers_resumed", "pause_seconds": round(pause_seconds, 3),
                      "process_count": len(pids), "private_file_count": len(captured)}), flush=True)
    staging = directory / "quiesced-sqlite"
    staging.mkdir(mode=0o700)
    for path, body in captured.items():
        dest = staging / path.relative_to("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        os.chmod(dest, 0o600)
    overrides = {}
    for source in targets:
        name = str(source).lstrip("/")
        copy = staging / name
        final = copy.with_name(copy.name + ".consistent")
        with closing(sqlite3.connect(copy)) as original:
            if original.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("A copied database did not pass quick_check")
            with closing(sqlite3.connect(final)) as snapshot:
                original.backup(snapshot)
                if snapshot.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("A completed database did not pass quick_check")
        os.chmod(final, 0o600)
        overrides[name] = final
    archive_path = directory / "environment-state-complete.tar.gz"
    with tarfile.open(previous["archive"], "r:gz") as original:
        with tarfile.open(archive_path, "x:gz", compresslevel=1) as output:
            for member in original:
                if member.name in overrides:
                    continue
                if member.isfile():
                    body = original.extractfile(member).read()
                    if body.startswith(b"SQLite format 3\x00"):
                        metadata = (Path("/") / member.name).stat()
                        member.uid, member.gid = metadata.st_uid, metadata.st_gid
                        member.uname = "pi" if metadata.st_uid == 1000 else "root"
                        member.gname = "pi" if metadata.st_gid == 1000 else "root"
                    output.addfile(member, io.BytesIO(body))
                else:
                    output.addfile(member)
            for name, snapshot in overrides.items():
                member = output.gettarinfo(str(Path("/") / name), arcname=name)
                member.size = snapshot.stat().st_size
                with snapshot.open("rb") as handle:
                    output.addfile(member, handle)
    os.chmod(archive_path, 0o600)
    with archive_path.open("rb") as handle:
        os.fsync(handle.fileno())
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    members = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            members += 1
            if member.isfile():
                handle = archive.extractfile(member)
                while handle.read(1024 * 1024):
                    pass
    receipt = {**previous, "utc": datetime.now(timezone.utc).isoformat(), "archive": str(archive_path),
               "archive_sha256": digest, "bytes": archive_path.stat().st_size,
               "sqlite_snapshots_checked": previous["sqlite_snapshots_checked"] + len(overrides),
               "archive_members_read_back": members, "snapshot_errors": [],
               "quiesced_database_count": len(overrides), "writer_pause_seconds": round(pause_seconds, 3),
               "sqlite_restore_ownership_preserved": True, "independent_device_backup": False}
    (directory / "COMPLETE-RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
