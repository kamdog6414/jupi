#!/usr/bin/python3
"""Install the reviewed toolbox without replacing the PS4 graphics/kernel stack."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

PROTECTED = {"mesa", "mesa-ps4", "vulkan-radeon", "xf86-video-amdgpu", "xf86-video-amdgpu-ps4",
             "xorg-server", "xorg-server-common", "xorg-server-devel", "libglvnd", "libdrm",
             "llvm", "llvm-libs", "linux", "linux-lts", "linux-zen", "linux-hardened"}


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo")
    source = Path(__file__).resolve().parents[1]
    packages = [row.strip() for row in (source / "config/toolbox-packages.txt").read_text().splitlines()
                if row.strip() and not row.lstrip().startswith("#")]
    current = subprocess.check_output(["pacman", "-Q"], text=True)
    installed = dict(line.split(maxsplit=1) for line in current.splitlines())
    command = ["pacman", "-Sp", "--needed", "--print-format", "%n|%v|%s", *packages]
    plan = subprocess.run(command, capture_output=True, text=True, check=True)
    rows = [line.split("|") for line in plan.stdout.splitlines() if line.count("|") == 2]
    blocked = sorted({row[0] for row in rows} & PROTECTED)
    if blocked:
        raise SystemExit("Toolbox would replace a protected platform package: " + ", ".join(blocked))
    stage = Path("/var/backups/jupi") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-toolbox")
    stage.mkdir(mode=0o700)
    (stage / "packages-before.txt").write_text(current)
    (stage / "planned-packages.txt").write_text(plan.stdout)
    upgrades = [{"name": name, "before": installed[name], "after": version}
                for name, version, _ in rows if name in installed and installed[name] != version]
    print(json.dumps({"event": "toolbox_plan_reviewed", "planned_package_count": len(rows),
                      "download_bytes": sum(int(row[2]) for row in rows), "existing_package_updates": upgrades,
                      "protected_platform_replacements": blocked, "checkpoint": str(stage)}), flush=True)
    subprocess.run(["pacman", "-S", "--needed", "--noconfirm", *packages], check=True)
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "requested_packages": packages,
               "package_versions": subprocess.check_output(["pacman", "-Q", *packages], text=True),
               "protected_platform_replacements": [], "checkpoint": str(stage)}
    (stage / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    Path("/var/lib/jupi/toolbox.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"event": "toolbox_installation_complete", "receipt": "/var/lib/jupi/toolbox.json"}), flush=True)


if __name__ == "__main__":
    main()
