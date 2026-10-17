import unittest
from unittest.mock import patch
import numpy as np

from tools.workdata.sync_check import correlation_lag, nearest_frames, choose_windows, motion_energy


class SyncTest(unittest.TestCase):
    def test_lag_sign_and_constant_motion_rejection(self):
        e=np.random.default_rng(22).normal(size=1200)
        a=np.roll(e,3)
        result=correlation_lag(a,e,hz=10,max_lag=10)
        self.assertAlmostEqual(result['lag_seconds'],.3,delta=.001)
        self.assertAlmostEqual(result['r'],1)
        self.assertTrue(result['passed'])
        self.assertFalse(correlation_lag(np.roll(e,15),e)['passed'])
        self.assertIsNone(correlation_lag(np.ones(1200),np.ones(1200))['r'])

    def test_nearest_samples_cross_segments_and_report_large_gaps(self):
        frames=iter([dict(wall_time=t,source=s,pts=t) for t,s in [(0,'a'),(.18,'a'),(.43,'b'),(.9,'b')]])
        rows=list(nearest_frames(frames,[0,.2,.4,.6,.8],step=.2))
        self.assertEqual([r['source'] for r in rows],['a','a','b','b','b'])
        self.assertEqual([r['gap'] for r in rows],[False,False,False,True,False])
        self.assertAlmostEqual(rows[3]['delta_seconds'],-.17)
        epoch=1788307200.
        boundary=list(nearest_frames([dict(wall_time=epoch+.1,source='epoch',pts=.1)],
                                     [epoch+.2],step=.2))[0]
        self.assertFalse(boundary['gap'],'half-step equality must survive epoch floating-point rounding')

    def test_windows_are_inside_overlap_and_do_not_bridge_gaps(self):
        spans=[(100,300),(500,1000)]
        windows=choose_windows(spans)
        self.assertEqual(len(windows),3)
        for start in windows:
            self.assertTrue(any(a<=start and start+120<=b for a,b in spans))
        with self.assertRaises(ValueError):choose_windows([(0,100)])

    def test_energy_uses_one_prior_frame_and_requested_gray_size(self):
        class Frame:
            def __init__(self,value):self.value=value
            def reformat(self,**settings):
                self.settings=settings
                return self
            def to_ndarray(self):return np.full((108,192),self.value,dtype='uint8')
        frames=[Frame(value) for value in (0,10,30)]
        source=(dict(wall_time=t,source='fake',pts=t,frame=f) for t,f in zip((99.5,100,100.5),frames))
        with patch('tools.workdata.sync_check.mapped_frames',return_value=source) as mapped:
            result=motion_energy([],100,seconds=1,hz=2)
        self.assertEqual(result,dict(values=[10.,20.],gaps=0))
        self.assertEqual(mapped.call_args.args[1:],(99.5,100.5))
        self.assertTrue(all(f.settings==dict(width=192,height=108,format='gray') for f in frames))
