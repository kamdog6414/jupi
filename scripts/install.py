#!/usr/bin/python3
"""Install JUPI's reversible baseline on the inspected USB-root PS4 only."""
from datetime import datetime, timezone
import hashlib
from ipaddress import ip_address
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

SOURCE = Path(__file__).resolve().parents[1]
STATE = Path("/var/lib/jupi")
EXPECTED_ROOT_UUID = "2ec1035f-9275-4d5b-bd46-c6e40122ea8d"


def run(argv, **kwargs):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=45, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{argv!r}: {result.returncode}: {result.stderr.strip()} {result.stdout.strip()}")
    return result.stdout.strip()


def emit(event, **fields):
    print(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "event": event, **fields}), flush=True)


def confirms_plain_pi_key(message, authorized):
    prefix = "Accepted publickey for pi from "
    if not isinstance(message, str) or not message.startswith(prefix) or "\n" in message or "\r" in message:
        return False
    fields = message[len(prefix):].split()
    if len(fields) != 6:
        return False
    address, port_word, port, protocol, key_type, fingerprint = fields
    try:
        ip_address(address)
    except ValueError:
        return False
    return (port_word == "port" and port.isascii() and port.isdecimal() and len(port) <= 5
            and 1 <= int(port) <= 65535 and protocol == "ssh2:"
            and key_type in {"RSA", "ECDSA", "ED25519"} and fingerprint in authorized)


def install():
    if os.geteuid() != 0:
        raise RuntimeError("Run with sudo")
    if run(["findmnt", "-n", "-o", "UUID", "/"]) != EXPECTED_ROOT_UUID:
        raise RuntimeError("Unexpected root UUID; inspect this host before installing")
    for program in ["sshd", "ssh", "ssh-keygen", "nft", "systemctl", "python3"]:
        if not shutil.which(program):
            raise RuntimeError(f"Missing required program: {program}")
    # Existing working public-key access is a prerequisite to disable passwords.
    fingerprints = run(["ssh-keygen", "-E", "sha256", "-lf", "/home/pi/.ssh/authorized_keys"])
    authorized = {fields[1] for row in fingerprints.splitlines()
                  if len(fields := row.split()) >= 2 and fields[1].startswith("SHA256:")}
    if not authorized:
        raise RuntimeError("No SHA256 authorized-key fingerprints available")
    history = run(["journalctl", "-b", "-u", "sshd", "--no-pager", "-n", "250", "-o", "json"])
    corroborated = False
    for row in history.splitlines():
        record = json.loads(row)
        if isinstance(record, dict) and confirms_plain_pi_key(record.get("MESSAGE"), authorized):
            corroborated = True
            break
    if not corroborated:
        raise RuntimeError("No successful pi plain-key login corroborated in this boot's SSH log")
    run(["/usr/bin/sshd", "-t"])
    run(["nft", "--check", "--file", str(SOURCE / "config/jupi.nft")])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path("/var/backups/jupi") / stamp
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup.parent, 0o700)
    os.chmod(backup, 0o700)
    # Private host keys and any network credentials stay inside a root-only archive.
    archive_path = backup / "configuration-before.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in ["/etc/ssh", "/etc/NetworkManager/system-connections", "/etc/fstab",
                     "/etc/systemd/system", "/etc/systemd/journald.conf.d", "/etc/sysctl.d",
                     "/home/pi/.ssh/authorized_keys"]:
            if Path(path).exists():
                archive.add(path, arcname=path.lstrip("/"))
    os.chmod(archive_path, 0o600)
    for device in ["/dev/sda", "/dev/sdb"]:
        (backup / (Path(device).name + ".partitions.txt")).write_text(run(["sfdisk", "--dump", device]) + "\n")
    (backup / "nftables-before.nft").write_text(run(["nft", "list", "ruleset"]) + "\n")
    (backup / "sshd-effective-before.txt").write_text(run(["/usr/bin/sshd", "-T"]) + "\n")
    boot_assets = {}
    boot = Path("/run/jupi-boot-audit")
    # Only read assets from the already inspected, read-only USB FAT partition.
    if boot.is_mount():
        mount = run(["findmnt", "-n", "-o", "UUID,OPTIONS", "--target", str(boot)])
        if not mount.startswith("891E-578E ") or "ro" not in mount.split()[-1].split(","):
            raise RuntimeError("Unexpected boot audit mount")
        (backup / "boot-assets").mkdir(mode=0o700)
        for name in ["bzImage", "initramfs.cpio.gz", "initramfs.cp05-rollback-20261106T210608Z.cpio.gz"]:
            src = boot / name
            if src.is_file():
                dest = backup / "boot-assets" / name
                shutil.copyfile(src, dest)
                os.chmod(dest, 0o600)
                original_hash = hashlib.sha256(src.read_bytes()).hexdigest()
                if hashlib.sha256(dest.read_bytes()).hexdigest() != original_hash:
                    raise RuntimeError("Boot backup read-back mismatch")
                boot_assets[name] = original_hash
    emit("recovery_checkpoint_created", path=str(backup), boot_asset_hashes=boot_assets)

    manifest = []

    def put(relative, target, mode=0o644):
        target = Path(target)
        if target.is_symlink():
            raise RuntimeError("Refusing symlink target: " + str(target))
        existed = target.exists()
        record = {"path": str(target), "existed": existed}
        if existed:
            old = backup / "overwritten" / target.relative_to("/")
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, old)
            record["backup"] = str(old)
        manifest.append(record)
        (backup / "changes.json").write_text(json.dumps(manifest, indent=2) + "\n")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".jupi-new")
        with open(temporary, "xb") as handle:
            handle.write((SOURCE / relative).read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)

    Path("/etc/jupi/ssh").mkdir(parents=True, exist_ok=True, mode=0o755)
    put("bin/jupi", "/usr/local/bin/jupi", 0o755)
    put("config/10-jupi.conf", "/etc/ssh/sshd_config.d/10-jupi.conf")
    os.chmod("/home/pi/.ssh/authorized_keys", 0o600)
    # Validate first. A rejected config is immediately removed/restored.
    try:
        run(["/usr/bin/sshd", "-t"])
    except Exception:
        change = manifest[-1]
        if change["existed"]:
            shutil.copy2(change["backup"], change["path"])
        else:
            Path(change["path"]).unlink()
        raise
    put("config/jupi.nft", "/etc/jupi/firewall.nft")
    put("config/journald.conf", "/etc/systemd/journald.conf.d/30-jupi.conf")
    put("config/roach.conf.example", "/etc/jupi/ssh/roach.conf.example")
    for unit in ["jupi-firewall.service", "jupi-health.service", "jupi-health.timer", "jupi-link@.service"]:
        put("systemd/" + unit, "/etc/systemd/system/" + unit)
    # Preserve desktop and existing routes. Ensure the actual Ethernet profile reconnects.
    run(["nmcli", "connection", "modify", "33a84eb2-4e7d-3115-94fc-ae27cd5cf454",
         "connection.autoconnect", "yes", "connection.autoconnect-retries", "0"])
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "sshd.service", "NetworkManager.service", "systemd-timesyncd.service"])
    run(["systemctl", "reload", "sshd.service"])
    emit("ssh_hardened_and_reloaded", existing_public_keys_preserved=True)
    run(["systemctl", "enable", "--now", "jupi-firewall.service", "jupi-health.timer"])
    # Journald restart preserves client logging sockets and the desktop session.
    run(["systemctl", "restart", "systemd-journald.service"])
    run(["journalctl", "--flush"])
    emit("baseline_services_enabled")

    # Existing formatted swap is the emergency memory reserve; do not reformat it.
    swap = Path("/dev/disk/by-uuid/7762469a-2e62-4378-bc48-63d91498d82c")
    if swap.exists() and run(["blkid", "-s", "TYPE", "-o", "value", str(swap)]) == "swap":
        fstab = Path("/etc/fstab")
        previous = fstab.read_text()
        if "7762469a-2e62-4378-bc48-63d91498d82c" not in previous and "/dev/sda3" not in previous:
            old = backup / "fstab.before-swap"
            shutil.copy2(fstab, old)
            manifest.append({"path": str(fstab), "existed": True, "backup": str(old)})
            (backup / "changes.json").write_text(json.dumps(manifest, indent=2) + "\n")
            with fstab.open("a") as handle:
                handle.write("\n# JUPI: existing USB emergency swap; optional at boot.\n"
                             "UUID=7762469a-2e62-4378-bc48-63d91498d82c none swap defaults,nofail,x-systemd.device-timeout=10s 0 0\n")
                handle.flush()
                os.fsync(handle.fileno())
        run(["swapon", "--all"])
        # Minimize routine swapping on the USB flash device.
        put("config/swappiness.conf", "/etc/sysctl.d/80-jupi-memory.conf")
        run(["sysctl", "-w", "vm.swappiness=10"])
        run(["systemctl", "daemon-reload"])
        emit("existing_swap_activated", uuid=swap.name, swappiness=10)

    key = Path("/home/pi/.ssh/jupi_roach_ed25519")
    if not key.exists():
        run(["runuser", "-u", "pi", "--", "ssh-keygen", "-q", "-t", "ed25519", "-N", "",
             "-C", "JUPI-to-Roach unattended transport", "-f", str(key)])
    os.chmod(key, 0o600)
    os.chown(key, 1000, 1000)
    run(["systemctl", "start", "jupi-health.service"])
    result = {"utc": datetime.now(timezone.utc).isoformat(), "recovery_path": str(backup),
              "root_uuid": EXPECTED_ROOT_UUID, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
              "boot_assets": boot_assets,
              "outbound_public_key_fingerprint": run(["ssh-keygen", "-lf", str(key) + ".pub"]),
              "outbound_link": "prepared; peer trust and authentication not yet established",
              "reboot_performed": False, "internal_disk_written": False,
              "installed_files": manifest}
    (backup / "INSTALL-RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    (STATE / "installation.json").write_text(json.dumps({k: v for k, v in result.items() if k != "installed_files"}, indent=2) + "\n")
    os.chmod(STATE / "installation.json", 0o644)
    for path in backup.rglob("*"):
        if path.is_file():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
    emit("installation_complete", **{k: v for k, v in result.items() if k != "installed_files"})


if __name__ == "__main__":
    try:
        install()
    except Exception as error:
        emit("installation_stopped", error=str(error))
        sys.exit(1)
