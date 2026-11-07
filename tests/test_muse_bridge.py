import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('muse_bridge',Path(__file__).resolve().parents[1]/'scripts/muse_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)


class MuseBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();bridge.STATE=Path(self.directory.name)
    def tearDown(self): self.directory.cleanup()
    def test_acceptance_is_saved_and_not_repeated(self):
        row=bridge.prepare('Synthetic fixture')
        with patch.object(bridge,'transmit',return_value={'ok':True,'status':200,'response':{'message_id':'fixture'}}) as call:
            receipt=bridge.send(row['id'])
            self.assertEqual(receipt['state'],'sdk_accepted')
            self.assertFalse(receipt['agent_read_acknowledged'])
            with self.assertRaises(ValueError): bridge.send(row['id'])
            self.assertEqual(call.call_count,1)
    def test_unknown_delivery_is_held(self):
        row=bridge.prepare('Synthetic fixture')
        with patch.object(bridge,'transmit',side_effect=TimeoutError('fixture')):
            self.assertEqual(bridge.send(row['id'])['state'],'unknown')
        with self.assertRaises(ValueError): bridge.send(row['id'])
    def test_disconnected_preflight_can_be_explicitly_retried(self):
        row=bridge.prepare('Synthetic fixture')
        with patch.object(bridge,'transmit',return_value={'ok':False,'error':'not connected to the Muse'}):
            self.assertEqual(bridge.send(row['id'])['state'],'not_connected')
        with patch.object(bridge,'transmit',return_value={'ok':True,'status':200,'response':{'message_id':'fixture'}}):
            self.assertEqual(bridge.send(row['id'])['state'],'sdk_accepted')
    def test_changed_message_is_not_transmitted(self):
        row=bridge.prepare('Synthetic fixture')
        with bridge.database() as db: db.execute('UPDATE messages SET message=? WHERE id=?',('changed',row['id']))
        with patch.object(bridge,'transmit') as call:
            with self.assertRaises(ValueError): bridge.send(row['id'])
            call.assert_not_called()


if __name__=='__main__': unittest.main()
