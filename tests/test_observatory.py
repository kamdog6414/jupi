from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('observatory', Path(__file__).resolve().parents[1]/'scripts/observatory.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class ObservatoryTests(unittest.TestCase):
    def fixture(self):
        return {'utc': '2026-11-07T12:00:00+00:00', 'boot_id': 'synthetic',
                'system': {'runtime_healthy': True}, 'cluster': {'instrument_cluster_ready': True},
                'castor_refresh': {'code': 0}, 'castor_freshness': {'fresh': True},
                'peer_health': {'nikolai': {'ok': True}},
                'resources': {'storage': {'/ps4hdd': {'available_bytes': 32*1024**3}},
                              'memory_bytes': {'MemAvailable': 1024**3}},
                'clock': {'synchronized': True}, 'hardware': {'sensors': []},
                'health': 'OK', 'issues': []}

    def test_freshness_rejects_old_future_and_ambiguous_clocks(self):
        ref = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
        self.assertTrue(observer.age('2026-11-07T11:59:00Z', ref)['fresh'])
        for stamp in ('2026-11-07T11:00:00Z', '2026-11-07T12:02:00Z', '2026-11-07T12:00:00', None, 'bad'):
            self.assertFalse(observer.age(stamp, ref)['fresh'])

    def test_relative_control_temperature_and_limits_are_not_power_samples(self):
        with tempfile.TemporaryDirectory() as d:
            hw = Path(d)/'hwmon0'; hw.mkdir()
            for name, value in {'name':'k10temp','temp1_input':'79625','temp1_max':'70000','temp1_crit':'100000'}.items():
                (hw/name).write_text(value)
            power = Path(d)/'hwmon1'; power.mkdir()
            (power/'name').write_text('fam15h_power'); (power/'power1_crit').write_text('0')
            samples = observer.sensors(Path(d), family=0x16)
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]['unit'], 'control_degrees')
            self.assertEqual(samples[0]['meaning'], 'relative_temperature_control')
            self.assertEqual(samples[0]['value'], 79.625)
            self.assertFalse(samples[0]['critical_limit_reached'])
            (hw/'temp1_input').write_text('100000')
            self.assertTrue(observer.sensors(Path(d), family=0x16)[0]['critical_limit_reached'])
            (hw/'temp1_fault').write_text('1')
            self.assertFalse(observer.sensors(Path(d), family=0x16)[0]['critical_limit_reached'])

    def test_peer_outage_degrades_availability_without_changing_membership(self):
        snapshot = self.fixture()
        self.assertEqual(observer.assess(snapshot), [])
        snapshot['peer_health']['nikolai']['ok'] = False
        self.assertEqual(observer.assess(snapshot), ['peer_health_unavailable:nikolai'])
        self.assertTrue(snapshot['cluster']['instrument_cluster_ready'])

    def test_storage_memory_clock_and_sensor_faults_are_observed(self):
        snapshot = self.fixture()
        snapshot['resources']['storage']['/ps4hdd']['available_bytes'] = 1024
        snapshot['resources']['memory_bytes']['MemAvailable'] = 1024
        snapshot['clock']['synchronized'] = False
        snapshot['hardware']['sensors'] = [{'driver':'fixture','label':'temp1','critical_limit_reached':True,'alarms':{'fault':0}}]
        issues = observer.assess(snapshot)
        self.assertIn('internal_backing_headroom_below_reserve', issues)
        self.assertIn('available_memory_below_256MiB', issues)
        self.assertIn('clock_not_confirmed_synchronized', issues)
        self.assertIn('kernel_sensor_critical:fixture:temp1', issues)

    def test_history_retention_and_state_transition(self):
        with tempfile.TemporaryDirectory() as d, patch.object(observer, 'STATE', Path(d)):
            snapshot = self.fixture()
            self.assertTrue(observer.store(snapshot, 2)['transition'])
            self.assertFalse(observer.store(snapshot, 2)['transition'])
            snapshot['issues'] = ['synthetic outage']; snapshot['health'] = 'DEGRADED'
            self.assertTrue(observer.store(snapshot, 2)['transition'])
            self.assertEqual(len(observer.saved(10)), 2)
            self.assertEqual(observer.saved()[0]['issues'], ['synthetic outage'])

    def test_changed_client_source_is_not_imported(self):
        result = observer.peer_health('0'*64)
        self.assertEqual(set(result), {'jupi', 'nikolai', 'roach'})
        self.assertTrue(all(v['error_class']=='ClientUnavailableOrChanged' for v in result.values()))

    def test_subprocess_failure_is_bounded_and_structured(self):
        with patch.object(observer.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 1)):
            self.assertEqual(observer.run_json(['fixture'], 1), {'code':-1,'error_class':'TimeoutExpired'})


if __name__ == '__main__':
    unittest.main()
