import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install", ROOT / "scripts/install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class AuthenticationEvidenceTests(unittest.TestCase):
    def test_success_is_bound_to_account_outcome_and_plain_key(self):
        expected = {"SHA256:test-key"}
        good = "Accepted publickey for pi from 192.0.2.3 port 12345 ssh2: ED25519 SHA256:test-key"
        accepted = [good, good.replace("192.0.2.3", "2001:db8::1"), good.replace("ED25519", "RSA"), good.replace("ED25519", "ECDSA")]
        rejected = [good.replace("Accepted", "Failed"), good.replace("Accepted", "Partial"),
                    good.replace("for pi", "for root"), "quoted: " + good,
                    good.replace("test-key", "other-key"), good.replace("12345", "１２３４５"),
                    good.replace("12345", "0"), good.replace("12345", "65536"),
                    good.replace("12345", "012345"), good.replace("192.0.2.3", "unknown-host"),
                    good + " ID certificate CA SHA256:test-key", good + " signature counter 1", None, good + "\n"]
        for message in accepted:
            with self.subTest(message=message):
                self.assertTrue(install.confirms_plain_pi_key(message, expected))
        for message in rejected:
            with self.subTest(message=message):
                self.assertFalse(install.confirms_plain_pi_key(message, expected))


if __name__ == "__main__":
    unittest.main()
