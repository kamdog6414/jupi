import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = (ROOT / "config/capture-console-key.sh").read_text()
spec = importlib.util.spec_from_file_location("stage", ROOT / "scripts/stage_key_capture.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def entry(name, body):
    name = name.encode() + b"\0"
    fields = [1, 0o100755, 0, 0, 1, 123, len(body), 0, 0, 0, 0, len(name), 0]
    header = b"070701" + b"".join(f"{field:08x}".encode() for field in fields)
    prefix = header + name
    prefix += b"\0" * (-len(prefix) % 4)
    result = prefix + body
    return result + b"\0" * (-len(result) % 4)


class BootCaptureTests(unittest.TestCase):
    def fixture(self, root, key=None, existing=None):
        newroot = root / "newroot"
        keydir = root / "key"
        keydir.mkdir()
        newroot.mkdir()
        if key is not None:
            (keydir / "eap_hdd_key.bin").write_bytes(key)
        destination = newroot / "var/backups/jupi/device-secrets/eap_hdd_key.bin"
        if existing is not None:
            destination.parent.mkdir(parents=True)
            destination.write_bytes(existing)
        script = HOOK.replace("/key/eap_hdd_key.bin", str(keydir / "eap_hdd_key.bin")).replace("/newroot", str(newroot))
        shell = os.environ.get("JUPI_TEST_SHELL")
        command = [shell, "ash", "-c", script] if shell else ["sh", "-c", script]
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0)
        return result, destination

    def test_loader_key_captured_privately_without_printing_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            result, dest = self.fixture(Path(folder), key=b"K" * 32)
            self.assertEqual(dest.read_bytes(), b"K" * 32)
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            self.assertEqual(dest.parent.stat().st_mode & 0o777, 0o700)
            self.assertIn("JUPI_CONSOLE_KEY_RETAINED", result.stdout)
            self.assertNotIn("K" * 32, result.stdout)

    def test_no_loader_key_keeps_usb_boot_available(self):
        with tempfile.TemporaryDirectory() as folder:
            result, dest = self.fixture(Path(folder))
            self.assertFalse(dest.exists())
            self.assertIn("JUPI_NO_LOADER_CONSOLE_KEY", result.stdout)

    def test_invalid_key_length_is_not_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            _, dest = self.fixture(Path(folder), key=b"bad")
            self.assertFalse(dest.exists())

    def test_existing_different_key_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            result, dest = self.fixture(Path(folder), key=b"A" * 32, existing=b"B" * 32)
            self.assertEqual(dest.read_bytes(), b"B" * 32)
            self.assertIn("DIFFERENT_EXISTING_FILE_PRESERVED", result.stdout)

    def test_archive_patch_changes_only_selector_body(self):
        original = entry("init", b"existing init\n") + entry("usbroot.sh", b"[ -x /newroot/sbin/init ]\n") + entry("TRAILER!!!", b"")
        updated, old, new = stage.patch(original, HOOK.encode())
        before = {name: original[start:start + size] for name, _, start, size, _ in stage.members(original)}
        after = {name: updated[start:start + size] for name, _, start, size, _ in stage.members(updated)}
        self.assertEqual(before["init"], after["init"])
        self.assertTrue(new.startswith(old.rstrip(b"\n") + b"\n"))
        self.assertEqual(set(before), set(after))


if __name__ == "__main__":
    unittest.main()
