import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import unittest
from datetime import datetime,timezone

loader=importlib.machinery.SourceFileLoader('cluster',str(Path(__file__).resolve().parents[1]/'bin/jupi-cluster'))
spec=importlib.util.spec_from_loader(loader.name,loader)
cluster=importlib.util.module_from_spec(spec);loader.exec_module(cluster)


class ClusterBindingTests(unittest.TestCase):
    def test_old_or_unconfirmed_cached_observation_is_not_fresh(self):
        ref=datetime(2026,11,7,12,tzinfo=timezone.utc)
        self.assertTrue(cluster.observation_age('2026-11-07T11:59:00Z',ref)['fresh'])
        self.assertFalse(cluster.observation_age('2026-11-07T06:00:00Z',ref)['fresh'])
        self.assertFalse(cluster.observation_age('2026-11-07T12:02:00Z',ref)['fresh'])
        self.assertFalse(cluster.observation_age(None,ref)['fresh'])
    def fixture(self):
        identity=json.dumps({'endpoint_id':'fixture-jupi'}).encode();authorization=b'explicit synthetic operator authorization'
        membership={'schema':'jupi.cluster.membership.v1','endpoint_id':'fixture-jupi','actor':'agape:agent:JUPI','seat_or_author':'JUPI',
                    'config_hash':hashlib.sha256(identity).hexdigest(),'authorization_sha256':hashlib.sha256(authorization).hexdigest()}
        return identity,membership,authorization
    def test_matching_identity_and_authorization(self):
        self.assertTrue(cluster.identity_binding(*self.fixture()))
    def test_changed_identity_or_permission_is_not_current_membership(self):
        identity,membership,authorization=self.fixture()
        self.assertFalse(cluster.identity_binding(identity+b' ',membership,authorization))
        self.assertFalse(cluster.identity_binding(identity,membership,authorization+b'changed'))
        membership['endpoint_id']='other-device'
        self.assertFalse(cluster.identity_binding(identity,membership,authorization))


if __name__=='__main__':unittest.main()
