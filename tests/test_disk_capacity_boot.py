import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capacity", ROOT / "scripts/prepare_disk_only_boot.py")
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)


class CapacityGuardTests(unittest.TestCase):
    def test_only_current_and_planned_image_sizes_are_accepted(self):
        for size in [42949672960, capacity.TARGET_BYTES, 0, 42949672959, capacity.TARGET_BYTES + 4096, "bad"]:
            script = 'jupi_size() { printf "%s\\n" "$TEST_SIZE"; }; JUPI_IMAGE=fixture; if ' + capacity.NEW_TEST.decode() + '; then exit 9; else exit 0; fi'
            result = subprocess.run(["sh", "-c", script], env={"TEST_SIZE": str(size)}, capture_output=True)
            with self.subTest(size=size):
                self.assertEqual(result.returncode, 0 if size in (42949672960, capacity.TARGET_BYTES) else 9)


if __name__ == "__main__":
    unittest.main()
