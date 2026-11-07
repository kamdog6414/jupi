#!/usr/bin/python3
"""Install signature-proven legacy GPU dependencies in root-owned storage."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOURCE = Path("/home/pi/fullcircle-recovery/computer-gates-20261106T213323Z/gpu-compat")
PINS = {"libLLVM-13.so": "afa3957b487814a49af25e052d49336c56f306d52f799d19c3aba8e4622d7bf6",
        "libxml2.so.2": "7e05bdfecc5871ebb5628e501e94e7ea51af592dc8f285decb679177c45dda7f"}
DESTINATION = Path("/usr/local/lib/jupi-gpu-compat")


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo")
    bodies = {}
    for name, pin in PINS.items():
        data = (SOURCE / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != pin:
            raise SystemExit("GPU dependency differs from the retained signature-verified artifact")
        bodies[name] = data
    if DESTINATION.is_symlink():
        raise SystemExit("Symlink GPU library directory refused")
    DESTINATION.mkdir(mode=0o755, exist_ok=True)
    os.chown(DESTINATION, 0, 0)
    os.chmod(DESTINATION, 0o755)
    for name, data in bodies.items():
        destination = DESTINATION / name
        if destination.is_symlink():
            raise SystemExit("Symlink GPU library target refused")
        temporary = DESTINATION / (name + ".jupi-new")
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    configuration = Path("/etc/ld.so.conf.d/jupi-gpu-compat.conf")
    configuration.write_text(str(DESTINATION) + "\n")
    os.chmod(configuration, 0o644)
    subprocess.run(["ldconfig"], check=True)
    # sudo has removed the user launcher's private LD_LIBRARY_PATH.
    dependencies = subprocess.check_output(["ldd", "/usr/lib/dri/radeonsi_dri.so"], text=True)
    if "not found" in dependencies:
        raise RuntimeError("The system Radeon driver still has unresolved dependencies")
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "library_directory": str(DESTINATION),
               "verified_sha256": PINS, "owner": "root:root", "mode": "0644 libraries; 0755 directory",
               "source_provenance": "Retained signature-verified Arch archive artifacts; previous bounded GPU render passed",
               "system_radeon_dependencies": dependencies.strip(), "display_restarted": False,
               "next_gate": "Repeat render probes and activate a fresh Xorg session for desktop DRI/glamor"}
    Path("/var/lib/jupi/gpu-compat.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
