#!/usr/bin/python3
"""Pin the discovered peer and stage its persistent transport; do not enable unauthenticated retry loops."""
import json
import os
from pathlib import Path
import subprocess


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo")
    root = Path(__file__).resolve().parents[1]
    known = Path("/home/pi/.ssh/jupi_roach_known_hosts")
    result = subprocess.run(["ssh-keygen", "-lf", str(known)], text=True, capture_output=True, check=True)
    # Fail closed unless the operator supplies an independently verified pin.
    # The committed default is a placeholder, not a real host-key fingerprint.
    expected = os.environ.get("JUPI_ROACH_HOSTKEY_FP", "SHA256:<roach-hostkey-fingerprint>")
    if expected.startswith("SHA256:<") or expected not in result.stdout:
        raise SystemExit("Set JUPI_ROACH_HOSTKEY_FP to the independently verified "
                         "Roach ED25519 host-key fingerprint (SHA256:...) before enrollment")
    directory = Path("/etc/jupi/ssh")
    directory.mkdir(parents=True, exist_ok=True)
    config = (root / "config/roach.conf.example").read_text()
    config = config.replace("#    RemoteForward 127.0.0.1:22052 127.0.0.1:22", "    RemoteForward 127.0.0.1:22052 127.0.0.1:22")
    for target, text in [(directory / "roach.known_hosts", known.read_text()),
                         (directory / "roach.conf", config)]:
        if target.is_symlink():
            raise SystemExit("Symlink destination refused")
        if target.exists() and target.read_text() != text:
            raise SystemExit("Existing peer configuration differs; preserve it for review")
        target.write_text(text)
        os.chmod(target, 0o644)
    public_key = Path("/home/pi/.ssh/jupi_roach_ed25519.pub").read_text().strip()
    receipt = {"host": "<roach-lan-ip>", "user": "roach", "port": 22,
               "host_key_fingerprint": expected,
               "host_trust": "pinned key corroborated by NIKOLAI's independently measured endpoint in NIKOLAI-DEVICE-CONTEXT-20261106.txt",
               "public_key": public_key,
               "remote_authorized_keys_line": 'restrict,port-forwarding,permitlisten="127.0.0.1:22052",permitopen="127.0.0.1:22" ' + public_key,
               "reverse_listener": "127.0.0.1:22052 on Roach -> 127.0.0.1:22 on JUPI",
               "unit": "jupi-link@roach.service", "enabled_by_this_script": False,
               "authentication_status": "pending remote public-key authorization"}
    Path("/var/lib/jupi/roach-enrollment.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
