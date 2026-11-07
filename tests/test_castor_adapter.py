import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
import io
import sys
import subprocess
import time
from contextlib import redirect_stdout
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('castor_adapter', Path(__file__).resolve().parents[1]/'scripts/castor_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def fixture(count):
    rows, previous = [], adapter.ANCHOR
    for n in range(1,count+1):
        body = {'author':'TEST','kind':'fixture','n':n,'prev_hash':previous,'text':'synthetic','ts':'2026-01-01T00:00:00Z'}
        body['hash'] = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        previous = body['hash']; rows.append(body)
    return rows, ('\n'.join(json.dumps(row) for row in rows)+'\n').encode()


class CastorAdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        adapter.STATE=Path(self.directory.name)
    def tearDown(self): self.directory.cleanup()
    def test_valid_prefix_and_append(self):
        rows, raw = fixture(2)
        self.assertEqual(len(adapter.verify(raw,{'rows':1,'tip':rows[0]['hash']})),2)

    def test_tampered_row_is_refused(self):
        _, raw = fixture(2)
        with self.assertRaises(ValueError): adapter.verify(raw.replace(b'synthetic',b'changed',1))

    def test_rollback_and_partial_line_are_refused(self):
        rows, _ = fixture(2); _, short = fixture(1)
        with self.assertRaises(ValueError): adapter.verify(short,{'rows':2,'tip':rows[1]['hash']})
        with self.assertRaises(ValueError): adapter.verify(short[:-1])

    def test_duplicate_fields_are_refused(self):
        _, raw = fixture(1)
        with self.assertRaises(ValueError): adapter.verify(raw.replace(b'"n": 1',b'"n": 1, "n": 1'))

    def test_invalid_saved_prefix_count_is_refused(self):
        rows, raw = fixture(2)
        for count in (0,-1,True):
            with self.assertRaises(ValueError): adapter.verify(raw,{'rows':count,'tip':rows[-1]['hash']})

    def test_concurrent_reader_waits_for_snapshot_receipt_commit(self):
        _, old = fixture(1); rows, new = fixture(2)
        def receipt(raw, count, tip):
            return json.dumps({'rows':count,'tip':tip,'snapshot_sha256':hashlib.sha256(raw).hexdigest()}).encode()
        adapter.atomic(adapter.STATE/'chain.jsonl', old)
        adapter.atomic(adapter.STATE/'receipt.json', receipt(old,1,rows[0]['hash']))
        code = "import importlib.util,sys;from pathlib import Path;s=importlib.util.spec_from_file_location('a',sys.argv[1]);a=importlib.util.module_from_spec(s);s.loader.exec_module(a);a.STATE=Path(sys.argv[2]);print(a.read_snapshot('status')[1]['rows'])"
        with adapter.snapshot_lock(exclusive=True):
            adapter.atomic(adapter.STATE/'chain.jsonl', new)
            child=subprocess.Popen([sys.executable,'-B','-c',code,str(Path(adapter.__file__)),str(adapter.STATE)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            time.sleep(0.2)
            self.assertIsNone(child.poll(), 'Reader consumed a half-committed snapshot')
            adapter.atomic(adapter.STATE/'receipt.json', receipt(new,2,rows[-1]['hash']))
        stdout,stderr=child.communicate(timeout=5)
        self.assertEqual(child.returncode,0,stderr)
        self.assertEqual(stdout.strip(),'2')

    def test_native_author_refusal_does_not_claim_success(self):
        response=SimpleNamespace(stdout=json.dumps({'state':'not_enrolled','new_write':False}))
        with patch.object(adapter.subprocess,'run',return_value=response):
            result=adapter.publish('Synthetic enrollment fixture')
        self.assertEqual(result['state'],'not_enrolled')
        self.assertFalse(result['new_write'])

    def test_uncertain_delivery_only_reconciles(self):
        with patch.object(adapter.subprocess,'run',side_effect=TimeoutError('fixture')):
            self.assertEqual(adapter.publish('Synthetic fixture')['state'],'unknown')
        response=SimpleNamespace(stdout=json.dumps({'state':'unknown_not_found','new_write':False}))
        with patch.object(adapter.subprocess,'run',return_value=response) as call:
            result=adapter.publish('Synthetic fixture')
        self.assertEqual(result['state'],'unknown_not_found')
        self.assertEqual(json.loads(call.call_args.kwargs['input'])['mode'],'reconcile')

    def test_accepted_post_is_not_repeated(self):
        text='Synthetic fixture'
        operation='jupi-'+hashlib.sha256(text.encode()).hexdigest()
        row={'author':'JUPI','kind':'chat','n':1,'prev_hash':adapter.ANCHOR,
             'text':'JUPI operation '+operation+'\n'+text,'ts':'2026-01-01T00:00:00Z'}
        row['hash']=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        response=SimpleNamespace(stdout=json.dumps({'state':'accepted','duplicate':False,'row':row}))
        with patch.object(adapter.subprocess,'run',return_value=response) as call:
            self.assertEqual(adapter.publish(text)['state'],'accepted')
            self.assertEqual(adapter.publish(text)['row']['hash'],row['hash'])
        self.assertEqual(call.call_count,1)

    def test_native_trailing_newline_is_accepted(self):
        text='Synthetic file with a trailing newline\n'
        operation='jupi-'+hashlib.sha256(text.encode()).hexdigest()
        row={'author':'JUPI','kind':'chat','n':1,'prev_hash':adapter.ANCHOR,
             'text':('JUPI operation '+operation+'\n'+text).strip(),'ts':'2026-01-01T00:00:00Z'}
        row['hash']=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        response=SimpleNamespace(stdout=json.dumps({'state':'accepted','duplicate':False,'row':row}))
        with patch.object(adapter.subprocess,'run',return_value=response):
            self.assertEqual(adapter.publish(text)['state'],'accepted')

    def test_remote_reconcile_finds_native_trimmed_row_without_append(self):
        text='Synthetic uncertain delivery\n'
        operation='jupi-'+hashlib.sha256(text.encode()).hexdigest()
        row={'author':'JUPI','text':('JUPI operation '+operation+'\n'+text).strip()}
        native=SimpleNamespace(CASTOR_ROOT=adapter.ANCHOR,load_chain=lambda:[row])
        request={'operation_id':operation,'text':text,'mode':'reconcile'}
        output=io.StringIO()
        # No append_row exists on the stub: a mistaken write fails the test.
        with patch.dict(sys.modules,{'castor_lte':native}), patch.object(sys,'path',sys.path.copy()), \
             patch.object(sys,'stdin',io.StringIO(json.dumps(request))), \
             patch.object(Path,'home',return_value=adapter.STATE), redirect_stdout(output):
            exec(adapter.PUBLISH,{})
        result=json.loads(output.getvalue())
        self.assertEqual(result['state'],'accepted')
        self.assertTrue(result['duplicate'])


if __name__ == '__main__': unittest.main()
