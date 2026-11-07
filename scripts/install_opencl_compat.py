#!/usr/bin/python3
"""Restore signed LLVM 13 compiler dependencies for the existing PS4 Mesa."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo")
    source = Path(__file__).resolve().parents[1] / ".cache/gpu-archive"
    stage = Path("/var/backups/jupi") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-opencl")
    stage.mkdir(mode=0o700)
    hashes, installed = {}, {}
    for package in ("clang-13.0.1-2-x86_64.pkg.tar.zst", "libclc-13.0.1-1-any.pkg.tar.zst"):
        archive = stage / package
        shutil.copyfile(source / package, archive)
        shutil.copyfile(source / (package + ".sig"), stage / (package + ".sig"))
        os.chmod(archive, 0o600)
        subprocess.run(["pacman-key", "--verify", str(stage / (package + ".sig")), str(archive)], check=True)
        with archive.open("rb") as handle:
            hashes[package] = hashlib.file_digest(handle, "sha256").hexdigest()
        with tarfile.open(archive, "r:zst") as contents:
            for member in contents:
                name = PurePosixPath(member.name)
                destination = None
                if member.name == "usr/lib/libclang-cpp.so.13":
                    destination = Path("/usr/local/lib/jupi-gpu-compat/libclang-cpp.so.13")
                elif member.name.startswith("usr/lib/clang/13.0.1/include/") and member.isfile():
                    destination = Path("/") / member.name
                elif member.name.startswith("usr/include/clc/") and member.isfile():
                    destination = Path("/") / member.name
                elif name.parent == PurePosixPath("usr/share/clc") and name.suffix == ".bc":
                    destination = Path("/") / member.name
                if destination is None:
                    continue
                if ".." in name.parts or not (member.isfile() or member.issym()):
                    raise RuntimeError("Unexpected compiler archive member")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if member.issym():
                    if PurePosixPath(member.linkname).name != member.linkname:
                        raise RuntimeError("Unexpected compiler link target")
                    if destination.is_symlink() and os.readlink(destination) == member.linkname:
                        continue
                    if destination.exists() or destination.is_symlink():
                        raise RuntimeError("Existing compiler path would change: " + str(destination))
                    destination.symlink_to(member.linkname)
                    installed[str(destination)] = {"symlink": member.linkname}
                    continue
                data = contents.extractfile(member).read()
                if destination.is_symlink():
                    raise RuntimeError("Symlink library destination refused")
                if destination.exists():
                    if destination.read_bytes() != data:
                        raise RuntimeError("Existing compiler file would change: " + str(destination))
                    continue
                with destination.open("xb") as output:
                    output.write(data)
                os.chmod(destination, 0o644)
                installed[str(destination)] = {"sha256": hashlib.sha256(data).hexdigest()}
    subprocess.run(["ldconfig"], check=True)
    dependencies = subprocess.check_output(["ldd", "/usr/lib/libMesaOpenCL.so.1"], text=True)
    if "not found" in dependencies:
        raise RuntimeError("OpenCL still has unresolved shared libraries")
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "checkpoint": str(stage),
               "signed_arch_archive_sha256": hashes, "installed_files": installed,
               "scope": "compiler library, matching resource headers and legacy bitcode; existing Mesa unchanged",
               "compute_test": "pending"}
    (stage / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    Path("/var/lib/jupi/opencl-compat.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"checkpoint": str(stage), "installed_file_count": len(installed), "dependencies_resolved": True}))


if __name__ == "__main__":
    main()
