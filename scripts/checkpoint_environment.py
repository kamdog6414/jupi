#!/usr/bin/python3
"""Create a root-only environment checkpoint with SQLite backup snapshots."""
from datetime import datetime, timezone
from contextlib import closing
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import time
from urllib.parse import quote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operations-only", action="store_true", help="capture latest chat/source/operations state without recopying the browser profile")
    parser.add_argument("--metadata-only", action="store_true", help="capture a later integration delta and recovery package cache; reuse the preceding model/GPU checkpoint")
    args = parser.parse_args()
    if args.metadata_only:
        args.operations_only = True
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    directory = Path("/var/backups/jupi") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ("-operations" if args.operations_only else "-environment"))
    directory.mkdir(mode=0o700)
    databases = directory / "sqlite"
    databases.mkdir(mode=0o700)
    roots = [Path(path) for path in ["/home/pi/.codex", "/home/pi/.config", "/home/pi/.ssh",
             "/home/pi/.local/bin", "/home/pi/.local/share/applications", "/home/pi/.local/share/pki",
             "/home/pi/.local/share/keyrings", "/home/pi/Desktop", "/home/pi/.bash_profile", "/home/pi/.bashrc",
             "/home/pi/ChatGPT/JUPI", "/etc/jupi", "/etc/ssh", "/etc/NetworkManager/system-connections",
             "/etc/systemd/system", "/etc/fstab", "/fullcircle/ps4-rescue-inventory"] if Path(path).exists()]
    if args.operations_only:
        roots = [Path(path) for path in ["/home/pi/.codex", "/home/pi/.ssh", "/home/pi/ChatGPT/JUPI",
                 "/home/pi/.config/autostart", "/home/pi/.local/bin", "/var/lib/jupi", "/etc/jupi",
                 "/etc/systemd/system", "/etc/ssh", "/etc/fstab"] if Path(path).exists()]
    # Native platform additions are part of recovery, including the local model.
    roots.extend(Path(path) for path in [
        "/var/lib/jupi-agent", "/var/lib/ollama", "/usr/bin/ollama", "/usr/lib/ollama",
        "/usr/lib/systemd/system/ollama.service", "/usr/local/lib/jupi-agent",
        "/usr/local/lib/jupi-gpu-compat", "/usr/local/sbin/jupi-zram",
        "/usr/lib/clang/13.0.1/include", "/usr/include/clc", "/usr/share/clc",
        "/etc/ld.so.conf.d/jupi-gpu-compat.conf", "/etc/systemd/logind.conf.d",
        "/etc/sysctl.d", "/home/pi/.config/xfce4", "/home/pi/.config/gtk-3.0",
        "/home/pi/.config/gtk-4.0", "/home/pi/.config/dconf", "/etc/passwd", "/etc/group",
        "/etc/shadow", "/etc/gshadow", "/etc/subuid", "/etc/subgid", "/var/lib/pacman/local"
    ] if Path(path).exists())
    roots.extend(Path(path) for path in ["/home/pi/.config/GIMP", "/home/pi/.local/share/applications"]
                 if Path(path).exists() and not any(Path(path).is_relative_to(root) for root in roots))
    # Enrollment adds native fleet sources, a private HMAC key, qualified
    # chains and local entry points. Keep them in the same protected recovery
    # archive as the SSH and SDK identity; never put their bytes in room posts.
    roots.extend(Path(path) for path in [
        "/home/pi/fc-link", "/home/pi/xchain", "/home/pi/.config/fclink",
        "/home/pi/.config/xchain"
    ] if Path(path).exists() and not any(Path(path).is_relative_to(root) for root in roots))
    roots.extend(path for path in Path("/usr/local/bin").glob("jupi*") if path.is_file())
    if args.metadata_only:
        heavy = {"/var/lib/ollama", "/usr/bin/ollama", "/usr/lib/ollama", "/usr/local/lib/jupi-gpu-compat",
                 "/usr/lib/clang/13.0.1/include", "/usr/include/clc", "/usr/share/clc"}
        roots = [path for path in roots if str(path) not in heavy]
        roots.extend(Path(path) for path in ["/var/lib/musegadget", "/home/pi/musegadget-build/sdk",
                     "/home/pi/musegadget-build/venv", "/home/pi/AGENTS.md", "/etc/machine-info",
                     "/var/cache/pacman/pkg", "/etc/profile.d/jupi-context.sh"] if Path(path).exists())
    excluded = ["home/pi/.codex/plugins", "home/pi/.codex/cache", "home/pi/.codex/tmp",
                "home/pi/.codex/ipc", "home/pi/.codex/app-server-control"]
    skip_names = {".cache", "Cache", "Code Cache", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache",
                  "Crashpad", "__pycache__", "CacheStorage", "cache2"}
    copied = {}
    errors = []

    def keep(name):
        path = Path(name)
        dependency_locks = {"packages.lock", "Cargo.lock", "Pipfile.lock", "poetry.lock",
                            "uv.lock", "yarn.lock", "flake.lock", "composer.lock"}
        return not (any(name == prefix or name.startswith(prefix + "/") for prefix in excluded)
                    or bool(set(path.parts) & skip_names)
                    or name.endswith(("-wal", "-shm"))
                    or (name.endswith(".lock") and path.name not in dependency_locks))

    def filter_member(member):
        if not keep(member.name) or member.isfifo() or member.isdev():
            return None
        source = Path("/") / member.name
        if member.isfile() and member.size >= 16:
            try:
                with source.open("rb") as handle:
                    is_database = handle.read(16) == b"SQLite format 3\x00"
                if is_database:
                    dest = databases / member.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    deadline = time.monotonic() + 5
                    def progress(status, remaining, total):
                        if time.monotonic() > deadline:
                            raise TimeoutError("SQLite live backup exceeded five seconds")
                    with closing(sqlite3.connect("file:" + quote(str(source), safe="/") + "?mode=ro", uri=True, timeout=1)) as original:
                        with closing(sqlite3.connect(dest)) as snapshot:
                            original.backup(snapshot, pages=128, progress=progress, sleep=0.05)
                            integrity = snapshot.execute("PRAGMA quick_check").fetchone()[0]
                            if integrity != "ok":
                                raise RuntimeError("SQLite snapshot quick_check failed")
                    os.chmod(dest, 0o600)
                    copied[member.name] = (dest, member)
                    return None
            except Exception as error:
                errors.append({"path": member.name, "error_class": type(error).__name__})
                print(json.dumps({"event": "sqlite_snapshot_unavailable", "path": member.name,
                                  "error_class": type(error).__name__}), flush=True)
                return None
        return member

    archive_path = directory / "environment-state.tar.gz"
    with tarfile.open(archive_path, "w:gz", compresslevel=1) as archive:
        for root in roots:
            archive.add(root, arcname=str(root).lstrip("/"), filter=filter_member)
        for name, (snapshot, metadata) in copied.items():
            metadata.size = snapshot.stat().st_size
            with snapshot.open("rb") as handle:
                archive.addfile(metadata, handle)
    os.chmod(archive_path, 0o600)
    with archive_path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
        os.fsync(handle.fileno())
    # Read every archived member to detect truncation/decompression errors.
    members = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            members += 1
            if member.isfile():
                handle = archive.extractfile(member)
                while handle.read(1024 * 1024):
                    pass
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "archive": str(archive_path),
               "archive_sha256": digest, "bytes": archive_path.stat().st_size,
               "sqlite_snapshots_checked": len(copied), "archive_members_read_back": members,
               "snapshot_errors": errors, "archive_readback": "pass",
               "independent_device_backup": False,
               "scope": ("integration metadata, Muse SDK and private pairing state, current package cache; apply after the preceding operations/model/GPU checkpoint; package database is recovery reference until matching binaries are restored" if args.metadata_only else "latest chat/source/identity/operations delta; restore after the full system and complete environment archive" if args.operations_only else "settings, sessions, identities, launchers, JUPI source and system configuration; application binaries remain in their existing installation and signed recovery archives"),
               "contains_private_session_data": True, "permissions": "root only"}
    (directory / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
