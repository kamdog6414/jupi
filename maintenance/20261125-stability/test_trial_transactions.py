"""Portable owned-directory tests; no mounts, services, network or PS4 access.

The guard's documented NOMOUNT test mode is mandatory here. Health commands
and selected file-operation failures are explicit local stubs. This verifies
transaction decisions, not FAT durability, physical power loss or kernel boot.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

GUARD = Path(__file__).resolve().parent / 'jupi-trial-guard.sh'
BOOT_A = '00000000-0000-4000-8000-000000000001'
BOOT_B = '00000000-0000-4000-8000-000000000002'
BOOT_C = '00000000-0000-4000-8000-000000000003'
STUB = r'''#!/usr/bin/python3
import os, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
fault = os.environ.get('FAULT', '')
if name == 'ip':
    print('    inet 192.0.2.1/24 scope global eth0'); sys.exit(0)
if name in ('ping', 'systemctl'):
    sys.exit(1 if fault == 'unhealthy' else 0)
if name == 'dmesg': sys.exit(77 if fault == 'dmesg-denied' else 0)
if name == 'cp' and fault == 'image-copy': sys.exit(73)
if name == 'mv':
    destination = Path(sys.argv[-1]).name
    rejected = {'pass-rename': 'TRIAL-PASSED', 'counter-rename': 'TRIAL-BOOTS',
                'trial-rename': 'TRIAL', 'image-rename': 'bzImage'}
    if destination == rejected.get(fault): sys.exit(74)
if name == 'sync' and fault == 'pass-truncate':
    for value in sys.argv[1:]:
        path = Path(value)
        if path.is_file() and b'\nresult=PASSED\n' in path.read_bytes():
            path.write_bytes(b'partial receipt\n')
if name == 'rm' and fault == 'pass-cleanup':
    if any(Path(value).name == 'TRIAL' for value in sys.argv[1:]): sys.exit(75)
os.execv('/usr/bin/' + name, ['/usr/bin/' + name, *sys.argv[1:]])
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TrialTransactions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='jupi-trial-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.media = self.root / 'media'; self.media.mkdir()
        self.stubs = self.root / 'stubs'; self.stubs.mkdir()
        for name, value in [('good', b'known-good\n'), ('cand', b'candidate\n'),
                            ('bzImage', b'known-good\n')]:
            (self.media / name).write_bytes(value)
        self.good = digest(self.media / 'good')
        self.candidate = digest(self.media / 'cand')
        self.boot = self.root / 'boot-id'; self.set_boot(BOOT_A)
        self.version = self.root / 'proc-version'
        self.version.write_text('Linux version test-trial-tag\n')
        for name in ['ip', 'ping', 'systemctl', 'dmesg', 'cp', 'mv', 'sync', 'rm']:
            path = self.stubs / name; path.write_text(STUB); path.chmod(0o755)
        self.env = {
            **os.environ, 'PATH': str(self.stubs) + ':/usr/sbin:/usr/bin:/sbin:/bin',
            'JUPI_TRIAL_CONF': str(self.root / 'absent.conf'),
            'JUPI_TRIAL_NOMOUNT': '1', 'JUPI_TRIAL_MNT': str(self.media),
            'JUPI_TRIAL_BOOT_ID_FILE': str(self.boot),
            'JUPI_TRIAL_PROC_VERSION': str(self.version),
            'JUPI_TRIAL_LOG': str(self.root / 'guard.log'),
            'JUPI_TRIAL_LOCK': str(self.root / 'guard.lock'),
            'JUPI_TRIAL_DISABLE': str(self.root / 'absent.disable'),
            'HEALTH_MIN': '1', 'BAD_LIMIT': '1', 'JUPI_TRIAL_SLEEP': '0',
        }

    def set_boot(self, value):
        self.boot.write_text(value + '\n')

    def invoke(self, *args, fault=''):
        return subprocess.run(['/bin/bash', str(GUARD), *args],
                              env={**self.env, 'FAULT': fault},
                              capture_output=True, text=True, timeout=15)

    def arm(self, fault=''):
        return self.invoke('arm', 'cand', self.candidate, 'good', self.good,
                           'test-trial-tag', fault=fault)

    def selected(self):
        return digest(self.media / 'bzImage')

    def assert_pending(self, selected):
        self.assertTrue((self.media / 'TRIAL').is_file())
        self.assertFalse((self.media / 'TRIAL-PASSED').exists())
        self.assertEqual(self.selected(), selected)

    def test_same_boot_waits_without_pass(self):
        self.assertEqual(self.arm().returncode, 0)
        result = self.invoke('check')
        self.assertEqual(result.returncode, 0)
        self.assertIn('WAIT_NEW_BOOT', result.stderr)
        self.assert_pending(self.candidate)
        self.assertEqual((self.media / 'TRIAL-BOOTS').read_text(), '0\n')

    def test_new_healthy_boot_passes_with_sealed_receipt(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertEqual(self.invoke('check').returncode, 0)
        receipt = (self.media / 'TRIAL-PASSED').read_text().rstrip('\n')
        body, recorded = receipt.rsplit('\nreceipt_sha256=', 1)
        self.assertEqual(hashlib.sha256((body + '\n').encode()).hexdigest(), recorded)
        self.assertIn('observed_boot_id=' + BOOT_B, receipt)
        self.assertFalse((self.media / 'TRIAL').exists())
        self.assertEqual(self.selected(), self.candidate)

    def test_manual_revert_restores_known_good(self):
        self.assertEqual(self.arm().returncode, 0)
        self.assertEqual(self.invoke('revert').returncode, 0)
        self.assertEqual(self.selected(), self.good)
        self.assertFalse((self.media / 'TRIAL').exists())
        self.assertTrue((self.media / 'TRIAL-REVERTED').is_file())

    def test_precommit_copy_failure_preserves_selection(self):
        self.assertNotEqual(self.arm('image-copy').returncode, 0)
        self.assertEqual(self.selected(), self.good)
        self.assertFalse((self.media / 'TRIAL').exists())

    def test_pending_record_rename_failure_preserves_selection(self):
        self.assertNotEqual(self.arm('trial-rename').returncode, 0)
        self.assertEqual(self.selected(), self.good)
        self.assertFalse((self.media / 'TRIAL').exists())

    def test_activation_failure_retains_recovery_transaction(self):
        self.assertNotEqual(self.arm('image-rename').returncode, 0)
        self.assert_pending(self.good)
        self.assertEqual(self.invoke('revert').returncode, 0)

    def test_pass_rename_failure_retains_pending_then_retries(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertNotEqual(self.invoke('check', fault='pass-rename').returncode, 0)
        self.assert_pending(self.candidate)
        self.assertEqual(self.invoke('check').returncode, 0)
        self.assertTrue((self.media / 'TRIAL-PASSED').is_file())

    def test_committed_pass_cleanup_reconciles_without_new_health_pass(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertNotEqual(self.invoke('check', fault='pass-cleanup').returncode, 0)
        receipt = (self.media / 'TRIAL-PASSED').read_bytes()
        self.assertTrue((self.media / 'TRIAL').is_file())
        result = self.invoke('check', fault='unhealthy')
        self.assertEqual(result.returncode, 0)
        self.assertIn('RECONCILED', result.stderr)
        self.assertEqual((self.media / 'TRIAL-PASSED').read_bytes(), receipt)
        self.assertFalse((self.media / 'TRIAL').exists())

    def test_truncated_pass_receipt_cannot_approve(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertNotEqual(self.invoke('check', fault='pass-truncate').returncode, 0)
        self.assertTrue((self.media / 'TRIAL').is_file())
        self.assertEqual(self.selected(), self.candidate)
        # An invalid receipt file may remain as evidence; its presence is not
        # an approval. A later unhealthy check must reject it and restore good.
        self.assertEqual(self.invoke('check', fault='unhealthy').returncode, 0)
        self.assertEqual(self.selected(), self.good)
        self.assertTrue((self.media / 'TRIAL-REVERTED').is_file())

    def test_corrupted_recovery_copy_holds(self):
        self.assertEqual(self.arm().returncode, 0)
        (self.media / 'good').write_bytes(b'corrupt\n')
        self.assertNotEqual(self.invoke('revert').returncode, 0)
        self.assert_pending(self.candidate)

    def test_second_boot_counter_failure_cannot_be_retried_into_pass(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertNotEqual(self.invoke('check', fault='pass-rename').returncode, 0)
        self.set_boot(BOOT_C)
        self.assertEqual(self.invoke('check', fault='counter-rename').returncode, 0)
        self.assertEqual(self.selected(), self.good)
        self.assertTrue((self.media / 'TRIAL-REVERTED').is_file())
        self.assertFalse((self.media / 'TRIAL-PASSED').exists())
        self.assertEqual(self.invoke('check').returncode, 0)
        self.assertFalse((self.media / 'TRIAL-PASSED').exists())

    def test_first_boot_mirror_failure_holds_retry_and_allows_revert(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertNotEqual(self.invoke('check', fault='counter-rename').returncode, 0)
        self.assertEqual((self.media / 'TRIAL-BOOTS').read_text(), '0\n')
        result = self.invoke('check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('mirror differs', result.stderr)
        self.assert_pending(self.candidate)
        self.assertEqual(self.invoke('revert').returncode, 0)
        self.assertEqual(self.selected(), self.good)

    def test_corrupt_authoritative_record_holds_retry(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertNotEqual(self.invoke('check', fault='pass-rename').returncode, 0)
        path = self.media / 'TRIAL-BOOT-ID'
        path.write_bytes(path.read_bytes().replace(b'boots=1', b'boots=2'))
        result = self.invoke('check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('content seal differs', result.stderr)
        self.assert_pending(self.candidate)

    def test_reserved_fat_aliases_are_rejected_before_mutation(self):
        for name in ['bzImage', 'BZIMAGE', 'TRIAL', 'trial-passed', 'cand.', '../cand']:
            with self.subTest(name=name):
                result = self.invoke('arm', name, self.candidate, 'good', self.good,
                                     'test-trial-tag')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.selected(), self.good)
                self.assertFalse((self.media / 'TRIAL').exists())

    def test_unreadable_kernel_log_reverts_without_qualification(self):
        self.assertEqual(self.arm().returncode, 0); self.set_boot(BOOT_B)
        self.assertEqual(self.invoke('check', fault='dmesg-denied').returncode, 0)
        self.assertEqual(self.selected(), self.good)
        self.assertFalse((self.media / 'TRIAL-PASSED').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
