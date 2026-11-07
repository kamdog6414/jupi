import importlib.util
from pathlib import Path
import math
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('rover_test',Path(__file__).resolve().parents[1]/'scripts/rover_odometry.py');rover=importlib.util.module_from_spec(spec);spec.loader.exec_module(rover)


class RoverTests(unittest.TestCase):
    def test_straight_motion_and_nonzero_encoder_origin(self):
        poses,distance=rover.integrate([(0,5,8),(2,7,10)],.4)
        self.assertEqual(poses[-1],(2,2.,0.,0.,1.,0.));self.assertEqual(distance,2)

    def test_in_place_rotation_does_not_translate(self):
        poses,distance=rover.integrate([(0,0,0),(1,-.2,.2)],.4)
        self.assertEqual(poses[-1][1:3],(0.,0.));self.assertAlmostEqual(poses[-1][3],1);self.assertEqual(distance,0)

    def test_exact_quarter_circle(self):
        poses,_=rover.integrate([(0,0,0),(1,.8*math.pi/2,1.2*math.pi/2)],.4)
        self.assertAlmostEqual(poses[-1][1],1);self.assertAlmostEqual(poses[-1][2],1);self.assertAlmostEqual(poses[-1][3],math.pi/2)

    def test_bad_sensor_frames_are_rejected(self):
        for raw in [b'time_s,left_m,right_m\n0,0,0\n0,1,1\n',b'time_s,left_m,right_m\n0,0,0\n1,nan,1\n',b'time_s,left_m,right_m,command\n0,0,0,run\n',b'time_s,left_m,right_m\n0,0,0\n']:
            with self.assertRaises(ValueError):rover.parse(raw)
        with self.assertRaises(ValueError):rover.integrate([(0,0,0),(1,1,1)],0)

    def test_artifacts_bind_input_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'run';result=rover.execute(rover.demo(),.4,True,output)
            self.assertEqual(result['classification'],'synthetic_demo');self.assertEqual(result['samples'],501)
            (output/'poses.csv').write_text('changed')
            with self.assertRaises(ValueError):rover.verify(output)
            with self.assertRaises(FileExistsError):rover.execute(rover.demo(),.4,True,output)
