import unittest
from unittest.mock import Mock, patch
import numpy as np

from tools.workdata.timemap import assemble_session, fit_time_map, map_time, overlap_intervals, sample_file


class TimeMapTest(unittest.TestCase):
    def test_filename_clock_preserves_native_pts_and_does_not_read_osd(self):
        from datetime import datetime, timezone
        from tools.workdata.webcam import sample_filename_clock
        class Source:
            start=4.
            def __init__(self,path): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def frames(self):
                for pts in (4.125,4.2,6.,6.1): yield pts,object()
        result=sample_filename_clock('WIN_20261014_12_05_36_Pro.mp4',Source)
        origin=datetime(2026,10,14,12,5,36,tzinfo=timezone.utc).timestamp()
        self.assertEqual(result['clock_source'],'filename_clock')
        self.assertEqual(result['decoded_frames'],4)
        self.assertEqual(len(result['segments']),2)
        self.assertEqual([s['b'] for s in result['segments']],[1.,1.])
        self.assertEqual(map_time(result['segments'],4.125,0),origin+4.125)
        self.assertEqual(map_time(result['segments'],6.1,3),origin+6.1)
        with self.assertRaises(ValueError):
            sample_filename_clock('WIN_20261314_12_05_36_Pro.mp4',Source)

    def test_optional_webcam_does_not_shorten_three_camera_overlap(self):
        rows=[dict(camera=c,source=c,segments=[dict(pts_start=0,pts_end=10,a=100,b=1)])
              for c in ('cam_a','cam_b','cam_e')]
        original=assemble_session('test',rows)
        self.assertNotIn('auxiliary_cameras',original)
        webcam=dict(camera='cam_w',source='w',segments=[dict(pts_start=2,pts_end=3,a=100,b=1)])
        result=assemble_session('test',rows+[webcam])
        self.assertEqual(result['overlap'],original['overlap'])
        self.assertEqual(result['cameras'],original['cameras'])
        self.assertEqual(result['auxiliary_cameras']['cam_w']['coverage'],[(102,103)])

    def test_robust_fit_recovers_drift_without_hiding_outliers(self):
        rng=np.random.default_rng(31)
        x=np.arange(100)*10.
        y=1788818400 + .998*x + rng.normal(0,.015,len(x))
        y[[0,12,41,72]] += [8,-4,9,12]
        result=fit_time_map([dict(pts=float(a),wall_time=float(b)) for a,b in zip(x,y)],0,1000)
        self.assertEqual(len(result),1)
        self.assertAlmostEqual(result[0]['a'],1788818400,delta=.02)
        self.assertAlmostEqual(result[0]['b'],.998,delta=.00003)
        self.assertEqual([row['index'] for row in result[0]['outliers']],[0,12,41,72])
        self.assertLess(result[0]['residuals']['p95'],.05)
        self.assertAlmostEqual(map_time(result,500),1788818899,delta=.02)

    def test_osd_jump_does_not_create_a_pts_breakpoint(self):
        rows=[dict(pts=float(i*10),wall_time=float(1000+i*10+(3 if i>=30 else 0))) for i in range(60)]
        result=fit_time_map(rows,0,600)
        self.assertEqual(len(result),1)
        self.assertFalse(result[0]['breakpoint'])
        self.assertEqual(len(result[0]['residuals']['signed_seconds']),60)

    def test_overlap_preserves_real_segment_gaps(self):
        self.assertEqual(overlap_intervals([[(0,10),(12,20)],[(2,18)],[(5,15)]]),[(5,10),(12,15)])
        self.assertEqual(overlap_intervals([[(0,1)],[(2,3)]]),[])

    def test_insufficient_or_duplicate_anchors_fail(self):
        for rows in ([],[dict(pts=0,wall_time=10)]*5):
            with self.assertRaises(ValueError):fit_time_map(rows,0,10)

    def test_sampler_uses_transition_native_pts_and_rejects_wrong_camera(self):
        class Source:
            start=5.; end=7.; size=(3840,2160)
            def __init__(self,path): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def frames(self):
                yield 5.125, 'first'
                yield 5.2, 'second'
        reader=Mock()
        reader.identify.return_value={'camera':'cam_b'}
        reader.read.side_effect=[{'wall_time':100.},{'wall_time':101.}]
        with patch('tools.workdata.timemap.clock_pixels',side_effect=lambda x:x):
            result=sample_file('fake','cam_b',source_factory=Source,reader=reader)
        self.assertEqual(result['anchors'][0]['pts'],5.2)
        self.assertEqual(result['anchors'][0]['wall_time'],101.)
        self.assertEqual(result['readings'][0]['pts'],5.125)
        self.assertEqual(result['pts_start'],5.125)
        self.assertEqual(result['declared_start'],5.)
        with patch('tools.workdata.timemap.clock_pixels',side_effect=lambda x:x):
            with self.assertRaisesRegex(ValueError,'Camera layout mismatch'):
                sample_file('fake','cam_a',source_factory=Source,reader=reader)

    def test_session_assembly_orders_segments_and_preserves_gaps(self):
        def row(camera,name,start,end):
            return dict(camera=camera,source=name,pts_start=0,pts_end=end-start,
                        segments=[dict(pts_start=0,pts_end=end-start,a=start,b=1)])
        result=assemble_session('synthetic',[row('cam_a','a2',12,20),row('cam_a','a1',0,10),
                                            row('cam_b','b',2,18),row('cam_e','e',5,15)])
        self.assertEqual(result['cameras']['cam_a']['files'],['a1','a2'])
        self.assertEqual(result['cameras']['cam_a']['gaps'],[dict(start=10,end=12,seconds=2)])
        self.assertEqual(result['overlap'],[(5,10),(12,15)])
