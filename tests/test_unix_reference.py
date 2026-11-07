import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('unix_reference_test',ROOT/'scripts/unix_reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class UnixReferenceTests(unittest.TestCase):
    def test_reviewed_lookup_and_compound_input_remains_unknown(self):
        book=json.loads((ROOT/'config/unix-reference.json').read_text())
        key,value,match=reference.lookup(book,'ls -lah')
        self.assertEqual(key,'files');self.assertEqual(value['powershell_windows'],'Get-ChildItem -Force')
        key,value,match=reference.lookup(book,'ls -lah; touch should-not-run')
        self.assertIsNone(value)

    def test_state_changing_templates_are_marked(self):
        book=json.loads((ROOT/'config/unix-reference.json').read_text())
        for key in ('remove','copy','service-start','service-autostart'):self.assertTrue(book['entries'][key]['changes_state'])
        self.assertFalse(book['entries']['hash']['changes_state'])


if __name__=='__main__':unittest.main()
