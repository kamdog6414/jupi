#!/usr/bin/python3
"""One bounded external reboot observer, intended to run on Roach.

Uses Roach's existing JUPI SSH identity. Records metadata only, and performs
one read-only internal-image audit if the new USB boot retained its HDD key.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OLD_BOOT = "b00c61e1-6e1e-4d26-ab31-0caf281bcd82"
ROOT_UUID = "2ec1035f-9275-4d5b-bd46-c6e40122ea8d"
DIRECTORY = Path("/var/backups/jupi/reboot-watch")
SSH = ["runuser", "-u", "roach", "--", "ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
       "-o", "HostKeyAlias=192.168.77.52", "-o", "ConnectTimeout=3", "-o", "ConnectionAttempts=1", "pi@192.168.77.52"]
PROBE = r'''
import json,os,subprocess
from pathlib import Path
def probe(argv):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=8)
 return {'returncode':r.returncode,'stdout':r.stdout.strip(),'stderr':r.stderr.strip()}
d={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
   'root':probe(['findmnt','-n','-o','SOURCE,FSTYPE,UUID,OPTIONS','/']),
   'uptime_seconds':float(Path('/proc/uptime').read_text().split()[0]),
   'services':{u:probe(['systemctl','is-active',u]) for u in ['sshd','NetworkManager','lightdm','jupi-link@roach']},
   'desktop_app':probe(['pgrep','-u','1000','-x','ChatGPT']),
   'console_key_metadata':probe(['sudo','-n','stat','-c','%s %a %U','/var/backups/jupi/device-secrets/eap_hdd_key.bin'])}
print(json.dumps(d))
'''


def record(event, **fields):
    value = {"utc": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    with (DIRECTORY / "events.jsonl").open("a") as handle:
        handle.write(json.dumps(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps(value), flush=True)


def inspect():
    result = subprocess.run(SSH + ["python3 -B -"], input=PROBE, capture_output=True, text=True, timeout=55)
    if result.returncode:
        return None
    return json.loads(result.stdout)


def main():
    if os.geteuid() != 0 or os.uname().nodename != "roach":
        raise SystemExit("Run this observer as root on Roach")
    DIRECTORY.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(DIRECTORY, 0o700)
    initial = inspect()
    if not initial or initial["boot_id"] != OLD_BOOT or ROOT_UUID not in initial["root"]["stdout"]:
        raise SystemExit("External control preflight failed; inspect before reboot")
    if "--preflight-only" in sys.argv:
        record("external_control_preflight_passed", baseline=initial)
        return 0
    record("observer_ready", baseline=initial, deadline_minutes=30)
    (DIRECTORY / "READY.json").write_text(json.dumps(initial, indent=2) + "\n")
    deadline = time.monotonic() + 30 * 60
    observed_new = None
    saw_disconnect = False
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            current = inspect()
        except (subprocess.TimeoutExpired, ValueError):
            current = None
        if current is None:
            if not saw_disconnect:
                record("device_ssh_unreachable")
                saw_disconnect = True
            continue
        if current["boot_id"] == OLD_BOOT:
            continue
        if observed_new is None:
            observed_new = current["boot_id"]
            record("new_linux_boot_observed", state=current)
        correct_root = ROOT_UUID in current["root"]["stdout"]
        services = all(current["services"][name]["returncode"] == 0 for name in ["sshd", "NetworkManager", "lightdm", "jupi-link@roach"])
        if correct_root and services and current["uptime_seconds"] >= 30:
            receipt = {"utc": datetime.now(timezone.utc).isoformat(), "previous_boot_id": OLD_BOOT,
                       "state": current, "loader_assisted_usb_recovery": "verified",
                       "unattended_cold_boot": "not established", "key_contents_reported": False}
            if current["console_key_metadata"]["stdout"] == "32 600 root":
                record("running_read_only_internal_audit")
                audit = subprocess.run(SSH + ["sudo -n python3 -B /home/pi/ChatGPT/JUPI/scripts/inspect_internal.py --key-file /var/backups/jupi/device-secrets/eap_hdd_key.bin"],
                                       capture_output=True, text=True, timeout=180)
                receipt["internal_audit_exit_code"] = audit.returncode
                try:
                    receipt["internal_audit"] = json.loads(audit.stdout)
                except ValueError:
                    receipt["internal_audit"] = {"status": "no valid JSON receipt"}
            else:
                receipt["internal_audit"] = {"status": "not run; protected 32-byte console key not confirmed"}
            (DIRECTORY / "POST-BOOT-RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
            subprocess.run(SSH + ["cat > /var/lib/jupi/POST-BOOT-ROACH-RECEIPT.json"], input=json.dumps(receipt, indent=2) + "\n",
                           capture_output=True, text=True, timeout=30, check=True)
            record("observer_completed", receipt=str(DIRECTORY / "POST-BOOT-RECEIPT.json"))
            return 0
    record("observer_timed_out", new_boot_seen=observed_new)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
