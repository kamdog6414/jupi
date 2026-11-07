import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/jupi"
loader = importlib.machinery.SourceFileLoader("jupi", str(CLI))
spec = importlib.util.spec_from_loader(loader.name, loader)
jupi = importlib.util.module_from_spec(spec)
loader.exec_module(jupi)


class ShellTests(unittest.TestCase):
    def test_mapping_is_explanation_only(self):
        result = subprocess.run([sys.executable, "-B", str(CLI), "map", "network", "--os", "linux"],
                                capture_output=True, text=True, check=True)
        self.assertIn("linux: ip -brief address", result.stdout)
        self.assertNotIn("powershell:", result.stdout)

    def test_command_arguments_are_not_shell_evaluated(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "must-not-exist"
            literal = "$(touch " + str(marker) + ")"
            result = subprocess.run([sys.executable, "-B", str(CLI), "run", "--", "/usr/bin/printf", "%s", literal],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn(literal, result.stdout)
            self.assertFalse(marker.exists())

    def test_exit_status_is_preserved(self):
        result = subprocess.run([sys.executable, "-B", str(CLI), "run", "--", sys.executable, "-c", "raise SystemExit(7)"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 7)

    def test_probe_timeout_is_reported(self):
        result = jupi.probe([sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.05)
        self.assertEqual(result["returncode"], 124)

    def test_missing_program_does_not_crash_inventory(self):
        self.assertEqual(jupi.probe(["/jupi-no-such-program"])['returncode'], 127)

    def test_health_receipt_is_atomic_and_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "health.json"
            jupi.atomic_json(dest, {"boot_id": "first"})
            jupi.atomic_json(dest, {"boot_id": "second"})
            self.assertEqual(json.loads(dest.read_text()), {"boot_id": "second"})
            self.assertEqual(dest.stat().st_mode & 0o777, 0o640)
            self.assertEqual([item.name for item in dest.parent.iterdir()], ["health.json"])


if __name__ == "__main__":
    unittest.main()
