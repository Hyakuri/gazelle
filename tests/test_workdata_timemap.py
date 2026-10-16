import unittest
from unittest.mock import Mock, patch
import numpy as np

from tools.workdata.timemap import assemble_session, fit_time_map, map_time, overlap_intervals, sample_file


class TimeMapTest(unittest.TestCase):
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

    def test_two_residual_clusters_produce_explicit_piecewise_mapping(self):
        rows=[dict(pts=float(i*10),wall_time=float(1000+i*10+(3 if i>=30 else 0))) for i in range(60)]
        result=fit_time_map(rows,0,600)
        self.assertEqual(len(result),2)
        self.assertAlmostEqual(map_time(result,200),1200)
        self.assertAlmostEqual(map_time(result,400),1403)
        self.assertEqual(result[0]['pts_end'], result[1]['pts_start'])
        self.assertTrue(result[1]['breakpoint'])

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
            def frames(self,start,end):
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
