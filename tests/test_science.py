import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
peer=load('science_peer_test','scripts/science_peer.py')
workflow=load('science_workflow_test','scripts/science_workflow.py')


def fixture():
    return {'schema':'jupi.science.input.v1','operation':'calibrate','data_origin':'synthetic_demo',
            'x_unit':'counts','y_unit':'synthetic units','samples':[[float(i),3.0*i+2.0] for i in range(8)]}


def gpu_fixture(value,model):
    raw=[];gain=peer.f32(model['gain'])
    for u,v in peer.normalized(value,model):
        pred=peer.f32(gain*u);raw.append(struct.pack('<ff',pred,peer.f32(v-pred)))
    return b''.join(raw)


class ReferenceTests(unittest.TestCase):
    def test_known_linear_fit_and_float32_validation(self):
        value=fixture();fit=peer.fit(value)
        self.assertAlmostEqual(fit['model']['slope'],3.0)
        self.assertAlmostEqual(fit['model']['intercept'],2.0)
        self.assertAlmostEqual(fit['fit_metrics']['rmse'],0.0)
        self.assertTrue(peer.verify_gpu(value,fit['model'],gpu_fixture(value,fit['model']))['verified'])

    def test_centering_preserves_variation_at_large_input_offset(self):
        value=fixture();value['samples']=[[1e9+i,3.0*i+2.0] for i in range(8)]
        self.assertEqual(len({peer.f32(p[0]) for p in value['samples']}),1)
        fit=peer.fit(value);self.assertAlmostEqual(fit['model']['slope'],3.0)
        result=peer.verify_gpu(value,fit['model'],gpu_fixture(value,fit['model']))
        self.assertTrue(result['verified'])
        self.assertLess(result['maximum_prediction_error_vs_float64_in_y_units'],1e-5)

    def test_corrupt_and_nonfinite_gpu_results_fail(self):
        value=fixture();model=peer.fit(value)['model'];raw=gpu_fixture(value,model)
        changed=struct.pack('<f',1000.0)+raw[4:]
        self.assertFalse(peer.verify_gpu(value,model,changed)['verified'])
        changed=struct.pack('<f',float('nan'))+raw[4:]
        self.assertFalse(peer.verify_gpu(value,model,changed)['verified'])
        with self.assertRaises(ValueError):peer.verify_gpu(value,model,raw[:-1])

    def test_invalid_calibration_inputs_fail(self):
        for points in ([[1.0,2.0]],[[1.0,2.0]]*3,[[0.0,1.0],[1.0,float('nan')],[2.0,3.0]],[[False,1.0],[1.0,2.0],[2.0,3.0]]):
            value=fixture();value['samples']=points
            with self.assertRaises(ValueError):peer.fit(value)

    def test_apply_requires_explicit_extrapolation(self):
        model=peer.fit(fixture())['model']
        value={'schema':'jupi.science.input.v1','operation':'apply','samples':[[8.0]],'calibration':model}
        with self.assertRaises(ValueError):peer.fit(value)
        value['allow_extrapolation']=True
        self.assertEqual(peer.fit(value)['extrapolated_samples'],1)
        self.assertTrue(peer.verify_gpu(value,model,gpu_fixture(value,model))['verified'])

    def test_transmitted_worker_measures_actual_source_and_refuses_wrong_hash(self):
        source=(ROOT/'scripts/science_peer.py').read_bytes();value=fixture()
        request={'operation':'fit','worker_sha256':hashlib.sha256(source).hexdigest(),'dataset':value,
                 'dataset_sha256':hashlib.sha256(peer.canonical(value)).hexdigest()}
        result=subprocess.run([sys.executable,'-B','-c',source.decode()],input=peer.canonical(request),capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        response=json.loads(result.stdout);self.assertEqual(response['worker_sha256'],request['worker_sha256'])
        request['worker_sha256']='0'*64
        result=subprocess.run([sys.executable,'-B','-c',source.decode()],input=peer.canonical(request),capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0)

    def test_peer_verification_rejects_changed_input_digest(self):
        source=(ROOT/'scripts/science_peer.py').read_bytes();value=fixture()
        request={'operation':'fit','worker_sha256':hashlib.sha256(source).hexdigest(),'dataset':value,'dataset_sha256':'0'*64}
        result=subprocess.run([sys.executable,'-B','-c',source.decode()],input=peer.canonical(request),capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0)


class WorkflowIntegrityTests(unittest.TestCase):
    def test_csv_formulas_are_data_and_are_not_executed(self):
        with tempfile.TemporaryDirectory() as d:
            marker=Path(d)/'must-not-exist'
            raw=('x,y\n1,2\n2,3\n$(touch '+str(marker)+'),4\n').encode()
            with self.assertRaises(ValueError):workflow.parse_csv(raw,'calibrate')
            self.assertFalse(marker.exists())
        with self.assertRaises(ValueError):workflow.parse_csv(b'x,x\n1,2\n','calibrate')

    def test_run_paths_require_canonical_uuid(self):
        for value in ('../elsewhere','not-a-uuid',str(uuid.uuid4()).upper()):
            with self.assertRaises(ValueError):workflow.run_dir(value)

    def make_receipt(self,directory):
        identifier=str(uuid.uuid4());run=directory/'runs'/identifier;run.mkdir(parents=True)
        data=peer.canonical(fixture());source=b'x,y\n0,2\n1,5\n2,8\n'
        (run/'sources').mkdir()
        components={}
        for name in ('workflow','peer','gpu_source','gpu_binary'):
            (run/'sources'/name).write_bytes(b'synthetic source')
            components[name]={'sha256':workflow.digest(b'synthetic source')}
        software=peer.canonical({'schema':'jupi.science.config.v1','components':components})
        request={'schema':'jupi.science.request.v1','run_id':identifier,'dataset_sha256':workflow.digest(data),'source_csv_sha256':workflow.digest(source),'software_sha256':workflow.digest(software)}
        request_raw=peer.canonical(request)
        for name,raw in [('input.json',data),('source.csv',source),('software.json',software),('request.json',request_raw)]: (run/name).write_bytes(raw)
        for i in range(5):(run/('artifact'+str(i))).write_bytes(b'synthetic')
        receipt={'schema':'jupi.science.receipt.v1','run_id':identifier,'state':'passed','request_sha256':workflow.digest(request_raw),
                 'artifacts':{str(p.relative_to(run)):workflow.digest(p.read_bytes()) for p in run.rglob('*') if p.is_file()}}
        (run/'receipt.json').write_bytes(peer.canonical(receipt))
        return identifier,run

    def test_artifact_and_request_changes_are_detected(self):
        with tempfile.TemporaryDirectory() as d,patch.object(workflow,'STATE',Path(d)):
            identifier,run=self.make_receipt(Path(d));workflow.verify_run(identifier)
            (run/'artifact0').write_bytes(b'changed')
            with self.assertRaises(ValueError):workflow.verify_run(identifier)
        with tempfile.TemporaryDirectory() as d,patch.object(workflow,'STATE',Path(d)):
            identifier,run=self.make_receipt(Path(d));(run/'request.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):workflow.verify_run(identifier)

    def test_artifact_path_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as d,patch.object(workflow,'STATE',Path(d)):
            identifier,run=self.make_receipt(Path(d));r=json.loads((run/'receipt.json').read_bytes())
            r['artifacts']['../outside']='0'*64;(run/'receipt.json').write_bytes(peer.canonical(r))
            with self.assertRaises(ValueError):workflow.verify_run(identifier)

    def test_gpu_failure_retains_failed_receipt_without_reference_substitution(self):
        with tempfile.TemporaryDirectory() as d,patch.object(workflow,'STATE',Path(d)):
            identifier=str(uuid.uuid4());run=Path(d)/'runs'/identifier;run.mkdir(parents=True)
            value=fixture();data=peer.canonical(value);source=b'x,y\n0,2\n1,5\n2,8\n'
            config={'components':{'gpu_binary':{'path':'/usr/bin/false'}}};config_raw=peer.canonical(config)
            request={'dataset_sha256':workflow.digest(data),'source_csv_sha256':workflow.digest(source),'software_sha256':workflow.digest(config_raw)}
            request_raw=peer.canonical(request)
            for name,raw in [('input.json',data),('source.csv',source),('request.json',request_raw)]: (run/name).write_bytes(raw)
            with patch.object(workflow,'configuration',return_value=(config_raw,config)), \
                 patch.object(workflow,'reference',return_value=peer), \
                 patch.object(workflow,'peer_call',return_value=peer.fit(value)) as calls:
                code=workflow.execute(identifier,workflow.digest(request_raw),str(uuid.uuid4()))
            self.assertEqual(code,1)
            receipt=json.loads((run/'receipt.json').read_bytes())
            self.assertEqual(receipt['state'],'failed');self.assertEqual(receipt['stage'],'gpu_application')
            self.assertEqual(calls.call_count,1)
            self.assertFalse((Path(d)/'latest.json').exists())

    def test_internal_execution_never_overwrites_an_attempted_run(self):
        with tempfile.TemporaryDirectory() as d,patch.object(workflow,'STATE',Path(d)):
            identifier,run=self.make_receipt(Path(d))
            before=(run/'receipt.json').read_bytes();request=(run/'request.json').read_bytes()
            with self.assertRaises(ValueError):workflow.execute(identifier,workflow.digest(request),str(uuid.uuid4()))
            self.assertEqual((run/'receipt.json').read_bytes(),before)
            (run/'receipt.json').unlink();(run/'attempt.json').write_bytes(b'committed earlier attempt')
            with self.assertRaises(FileExistsError):workflow.execute(identifier,workflow.digest(request),str(uuid.uuid4()))
            self.assertFalse((run/'receipt.json').exists())


if __name__=='__main__':unittest.main()
