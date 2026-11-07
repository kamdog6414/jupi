import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import unittest
import hashlib
import json
import uuid
import os
import socket
import subprocess
import threading
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('agent_runtime', Path(__file__).resolve().parents[1] / 'scripts/agent_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class AgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        runtime.STATE = Path(self.directory.name)
        runtime.STOP.clear()
        runtime.initialize()

    def tearDown(self):
        self.directory.cleanup()

    def test_memory_and_interrupted_work_survive_restart(self):
        runtime.dispatch({'action': 'remember', 'key': 'mission', 'value': 'science'})
        job = runtime.dispatch({'action': 'run', 'argv': ['/usr/bin/true'], 'cwd': self.directory.name})
        queued = runtime.dispatch({'action': 'run', 'argv': ['/usr/bin/true'], 'cwd': self.directory.name})
        with runtime.database() as db:
            db.execute("UPDATE jobs SET status='running' WHERE id=?", (job['id'],))
        runtime.initialize()
        self.assertEqual(runtime.dispatch({'action': 'recall', 'key': 'mission'})['value'], 'science')
        self.assertEqual(runtime.dispatch({'action': 'job', 'id': job['id']})['status'], 'interrupted')
        self.assertEqual(runtime.dispatch({'action': 'job', 'id': queued['id']})['status'], 'queued')

    def test_argv_is_not_interpreted_as_shell(self):
        value = '$(touch '+self.directory.name+'/must-not-exist)'
        code, output = runtime.command([sys.executable, '-c', 'import sys; print(sys.argv[1])', value], self.directory.name, 3)
        self.assertEqual(code, 0)
        self.assertIn(value, output)
        self.assertFalse((runtime.STATE / 'must-not-exist').exists())
        with self.assertRaises(ValueError):
            runtime.dispatch({'action': 'run', 'argv': 'echo untyped shell text'})

    def test_deadline_and_output_bound(self):
        started = time.monotonic()
        code, _ = runtime.command([sys.executable, '-c', 'import time; time.sleep(20)'], self.directory.name, 1)
        self.assertEqual(code, 124)
        self.assertLess(time.monotonic()-started, 4)
        code, output = runtime.command([sys.executable, '-c', 'print("x"*200000)'], self.directory.name, 3)
        self.assertEqual(code, 0)
        self.assertLess(len(output), 65700)
        self.assertIn('truncated', output)

    def test_prompt_is_only_queued_as_model_input(self):
        marker = runtime.STATE / 'not-executed'
        job = runtime.dispatch({'action': 'prompt', 'prompt': 'touch '+str(marker)})
        record = runtime.dispatch({'action': 'job', 'id': job['id']})
        self.assertEqual(record['kind'], 'prompt')
        self.assertEqual(record['status'], 'queued')
        self.assertFalse(marker.exists())

    def test_temperature_control_value_is_not_reported_as_die_temperature(self):
        hw=runtime.STATE/'hwmon-fixture';hw.mkdir()
        (hw/'name').write_text('k10temp');(hw/'temp1_input').write_text('79625')
        def devices(pattern):
            return [str(hw/'temp1_input')] if pattern.endswith('temp*_input') else []
        with patch.object(runtime.glob,'glob',side_effect=devices):
            observation=runtime.observe()
        self.assertEqual(observation['temperatures_c'],{})
        self.assertEqual(observation['temperature_control_degrees'][str(hw/'temp1_input')],79.625)

    def prepared_science(self):
        identifier=str(uuid.uuid4());directory=runtime.STATE/'science/runs'/identifier;directory.mkdir(parents=True)
        data={'schema':'jupi.science.request.v1','run_id':identifier,'operation':'calibrate',
              'argv':['touch','must-not-execute']}
        raw=json.dumps(data).encode();(directory/'request.json').write_bytes(raw)
        return identifier,raw,directory

    def test_science_enqueue_is_idempotent_and_does_not_use_manifest_commands(self):
        identifier,raw,directory=self.prepared_science()
        request={'action':'science','run_id':identifier,'request_sha256':hashlib.sha256(raw).hexdigest()}
        first=runtime.dispatch(request);second=runtime.dispatch(request)
        self.assertEqual(first['id'],second['id']);self.assertTrue(second['duplicate'])
        stored=runtime.dispatch({'action':'job','id':first['id']})
        payload=json.loads(stored['payload'])
        self.assertEqual(stored['kind'],'science')
        self.assertNotIn('touch',payload['argv'])
        self.assertIn('/usr/local/lib/jupi-agent/science_workflow.py',payload['argv'])
        self.assertEqual(payload['timeout'],180)
        (directory/'request.json').write_bytes(raw+b' ')
        request['request_sha256']=hashlib.sha256(raw+b' ').hexdigest()
        with self.assertRaises(ValueError):runtime.dispatch(request)

    def test_interrupted_science_is_retained_and_not_reenqueued(self):
        identifier,raw,_=self.prepared_science()
        request={'action':'science','run_id':identifier,'request_sha256':hashlib.sha256(raw).hexdigest()}
        job=runtime.dispatch(request)
        with runtime.database() as db:db.execute("UPDATE jobs SET status='running' WHERE id=?",(job['id'],))
        runtime.initialize();same=runtime.dispatch(request)
        self.assertEqual(same['id'],job['id']);self.assertEqual(same['status'],'interrupted')

    def test_science_context_accepts_typed_facts_not_arbitrary_prose(self):
        p=runtime.STATE/'science';p.mkdir()
        value={'state':'passed','run_id':str(uuid.uuid4()),'operation':'calibrate','samples':8,
               'data_origin':'synthetic_demo','model':{'slope':3.0,'intercept':2.0},
               'gpu_mismatches':0,'receipt_sha256':'a'*64,'label':'untrusted command prose'}
        (p/'latest.json').write_text(json.dumps(value))
        self.assertNotIn('label',runtime.science_context())
        value['model']['slope']='execute text';(p/'latest.json').write_text(json.dumps(value))
        self.assertIsNone(runtime.science_context())

    def test_model_request_includes_receipt_context_without_executing_it(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'done':True,'response':'stored receipt explanation'}).encode()
        facts={'run_id':'synthetic-id','samples':8,'data_origin':'synthetic_demo'}
        with patch.object(runtime,'science_context',return_value=facts), \
             patch.object(runtime.urllib.request,'urlopen',return_value=response) as call:
            code,_=runtime.generate({'prompt':'Describe the stored science receipt','peer':False})
        self.assertEqual(code,0)
        payload=json.loads(call.call_args.args[0].data)
        self.assertIn('latest_science',payload['system']);self.assertIn('synthetic_demo',payload['system'])
        self.assertEqual(runtime.dispatch({'action':'jobs'}),[])

    def test_art_recipe_is_idempotent_and_title_remains_an_argument(self):
        request_id=str(uuid.uuid4());title='$(touch must-not-execute)'
        params={'scene':'facade','style':'engraving','width':121,'height':65,'seed':14,'paper':'black','title':title,'video':False}
        request={'action':'art','request_id':request_id,**params}
        with patch.object(runtime,'art_recipe',return_value=(params,'a'*64,'/reviewed/gothic_art.py')):
            first=runtime.dispatch(request);second=runtime.dispatch(request)
        self.assertEqual(first['id'],second['id']);self.assertTrue(second['duplicate'])
        stored=runtime.dispatch({'action':'job','id':first['id']});payload=json.loads(stored['payload'])
        self.assertEqual(stored['kind'],'art');self.assertIn('--title='+title,payload['argv'])
        self.assertEqual(payload['timeout'],120)
        changed={**params,'seed':15}
        with patch.object(runtime,'art_recipe',return_value=(changed,'a'*64,'/reviewed/gothic_art.py')):
            with self.assertRaises(ValueError):runtime.dispatch({**request,'seed':15})

    def test_interrupted_art_is_not_replayed(self):
        request={'action':'art','request_id':str(uuid.uuid4())}
        params={'scene':'facade','style':'engraving','width':121,'height':65,'seed':14,'paper':'black','title':'JUPI','video':False}
        with patch.object(runtime,'art_recipe',return_value=(params,'a'*64,'/reviewed/gothic_art.py')):
            job=runtime.dispatch(request)
            with runtime.database() as db:db.execute("UPDATE jobs SET status='running' WHERE id=?",(job['id'],))
            runtime.initialize();same=runtime.dispatch(request)
        self.assertEqual(same['id'],job['id']);self.assertEqual(same['status'],'interrupted')

    def test_client_waits_for_restarted_listener_without_replaying_request(self):
        address=str(runtime.STATE/'test.sock')
        stale=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);stale.bind(address);stale.close()
        received=[]
        def server():
            time.sleep(.2);Path(address).unlink()
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
                listener.bind(address);listener.listen(1);listener.settimeout(4)
                connection,_=listener.accept()
                with connection:
                    request=json.loads(connection.makefile('rb').readline());received.append(request)
                    connection.sendall(b'{"ok":true,"result":"once"}\n')
        thread=threading.Thread(target=server);thread.start()
        with patch.object(runtime,'SOCKET',address):self.assertEqual(runtime.client({'action':'status'}),'once')
        thread.join(timeout=5);self.assertFalse(thread.is_alive());self.assertEqual(received,[{'action':'status'}])

    def test_service_sigterm_is_clean_and_removes_socket(self):
        state=runtime.STATE/'subprocess';address=str(runtime.STATE/'subprocess.sock')
        env=dict(os.environ,JUPI_AGENT_STATE=str(state),JUPI_AGENT_SOCKET=address)
        process=subprocess.Popen([sys.executable,'-B',str(Path(runtime.__file__)),'serve'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            end=time.monotonic()+5
            while not Path(address).exists() and time.monotonic()<end:time.sleep(.05)
            self.assertTrue(Path(address).exists());time.sleep(.2);process.terminate()
            _,error=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0,error);self.assertFalse(Path(address).exists())
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
