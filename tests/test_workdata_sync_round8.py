"""Synchronization regression contracts: fixed numbers and synthetic sidecars."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validation.sample_segments import read_session, sample_session
from tools.workdata.common import hash_file
from tools.workdata.proxies import ROLES
from tools.workdata.calibrated_frames import uncertain_ranges, is_uncertain, calibrated_frames
from tools.workdata.sync_validate import ProxyClockReader
from tools.workdata.sync_calibrate import fit_calibration, refine_breakpoints


# Accepted 0903/0911 coefficients and uncertainty intervals, copied as numbers
# so the default gate never opens formal mappings, sidecars, or media.
CASES = (
    dict(session='20260903', origin=1788307200.2, t0=1788307200., N=17995,
         cuts=[961.247810273165, 1835.6953119026002], end=3599.6000000000004,
         coefficients=[(1.1482794826666376, 4.70923049409764e-05),
                       (1.9432060977726422, -0.0005341543856068891),
                       (1.5361520023308213, -0.0001350483751837271)],
         intervals=[[781.146046697371,1141.349573848959],
                    [1810.1575513700504,1861.2330724351498]],
         ranges=[[1788307979.820093,1788308340.347546],
                 [1788309009.065858,1788309060.484052]],
         steps=[(3900,5701,1802),(9046,9302,257)], total=2059),
    dict(session='20260911', origin=1788818385.4, t0=1788818386.6, N=18065,
         cuts=[533.7943862981242,899.0190546660601], end=3613.8,
         coefficients=[(-1.2778748920208032,0.0004046573611839277),
                       (-1.777779825010639,0.0008655383920514677),
                       (-0.8701659507133739,0.00014967609776085584)],
         intervals=[[518.9774561348647,548.6113164613837],
                    [868.9676908830984,929.0704184490219]],
         ranges=[[1788818905.445323,1788818935.314252],
                 [1788819255.107793,1788819315.444052]],
         steps=[(2595,2743,149),(4343,4644,302)], total=451),
)


class SyncRound8Test(unittest.TestCase):
    def test_read_session_unions_every_camera_and_sampling_excludes_the_union(self):
        for marked in ({'cam_a': {250}}, {'cam_a': {105,250}, 'cam_b': {105,450}}):
            with self.subTest(marked=marked), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);grid=dict(t0=100.,N=9000,step=.2,step_hz=5.)
                cameras={}
                for camera,role in ROLES.items():
                    video=root/(role+'.mp4');video.write_bytes(camera.encode())
                    digest=hash_file(video)
                    rows=[dict(k=k,t_k=100.+k*.2,source=camera,pts=k*.2,
                               delta_seconds=0.,gap=False,sync_uncertain=k in marked.get(camera,set()))
                          for k in range(grid['N'])]
                    sidecar=root/(role+'.json')
                    sidecar.write_text(json.dumps(dict(camera=camera,role=role,grid=grid,
                                                       frames=rows,video_sha256=digest)))
                    cameras[camera]=dict(role=role,video=video.name,frames=sidecar.name,sha256=digest)
                path=root/'session.json'
                path.write_text(json.dumps(dict(version=1,session='fixture',grid=grid,cameras=cameras,
                                                time_map_version=3,time_map_sha256='a'*64)))
                session,gaps=read_session(path)
                expected=set().union(*marked.values())
                self.assertEqual({k for k,flag in enumerate(session['sync_uncertain']) if flag},expected)
                class Draws:
                    values=iter([100,500,5000])
                    def randint(self,a,b): return next(self.values)
                sampled=sample_session(session,gaps,Draws())
                self.assertEqual(sampled[0]['start_frame'],500)
                self.assertEqual(sampled[0]['attempts'][0]['sync_uncertain_steps'],len(expected & set(range(100,400))))
                self.assertEqual(sampled[0]['attempts'][1]['sync_uncertain_steps'],0)

    def test_actual_cut_coefficients_include_endpoints_and_expected_grid_counts(self):
        for case in CASES:
            with self.subTest(session=case['session']):
                bounds=[0.]+case['cuts']+[case['end']]
                fit=dict(valid=True,time_domain='base',origin=case['origin'],
                         segments=[dict(start=a,end=b,c0=c0,c1=c1) for a,b,(c0,c1) in
                                   zip(bounds,bounds[1:],case['coefficients'])],
                         breakpoints=[dict(seconds=c,uncertainty_seconds=i) for c,i in
                                      zip(case['cuts'],case['intervals'])])
                ranges=uncertain_ranges(fit)
                for interval,expected,(first,last,count) in zip(ranges,case['ranges'],case['steps']):
                    for actual,wanted in zip(interval,expected): self.assertAlmostEqual(actual,wanted,delta=1e-6)
                    self.assertTrue(is_uncertain(interval[0],[interval]))
                    self.assertTrue(is_uncertain(interval[1],[interval]))
                    self.assertFalse(is_uncertain(interval[0]-.00001,[interval]))
                    self.assertFalse(is_uncertain(interval[1]+.00001,[interval]))
                    indices=[k for k in range(case['N']) if is_uncertain(case['t0']+k*.2,[interval])]
                    self.assertEqual((indices[0],indices[-1],len(indices)),(first,last,count))
                self.assertEqual(sum(is_uncertain(case['t0']+k*.2,ranges) for k in range(case['N'])),case['total'])

    def test_transition_gap_and_overlap_extend_the_evidence_ranges(self):
        for jump in (.4,-.4):
            with self.subTest(jump=jump):
                fit=dict(valid=True,time_domain='base',origin=0.,segments=[
                    dict(start=0.,end=100.,c0=0.,c1=0.),dict(start=100.,end=200.,c0=jump,c1=0.)],
                    breakpoints=[dict(seconds=100.,uncertainty_seconds=[100.,100.])])
                ranges=uncertain_ranges(fit);before=deepcopy(ranges);stats={}
                list(calibrated_frames(iter([dict(wall_time=99.),dict(wall_time=100.5)]),fit,ranges,stats))
                self.assertFalse(is_uncertain(99.2,before))
                self.assertTrue(is_uncertain(99.2,ranges))
                self.assertEqual(ranges[-1],[99.,100.5-jump])
                self.assertEqual(stats['transitions'][0]['range'],ranges[-1])

    def test_base_at_uses_selected_source_pts_and_its_base_mapping(self):
        rows=[dict(source='first',pts=1.,t_k=900.),dict(source='second',pts=8.,t_k=901.)]
        sources={'first':dict(segments=[dict(pts_start=0.,pts_end=10.,a=100.,b=1.1)]),
                 'second':dict(segments=[dict(pts_start=0.,pts_end=10.,a=200.,b=.9)])}
        reader=ProxyClockReader(None,rows,sources,'cam_a',reader=object())
        with patch.object(reader,'_pair') as pair:
            self.assertAlmostEqual(reader.base_at(0),101.1)
            self.assertAlmostEqual(reader.base_at(1),207.2)
        self.assertEqual([call.args for call in pair.call_args_list],[(0,),(1,)])

    def test_refinement_centers_use_base_time_with_plus_lag(self):
        windows=[dict(valid=True,t_mid_seconds=30.+60*k,lag_seconds=.3 if k<22 else .7,
                      b_mid_seconds=30.+60*k+(.3 if k<22 else .7)) for k in range(60)]
        fit=fit_calibration(windows,3600.);fit['time_domain']='base'
        local=[dict(valid=True,t_mid_seconds=float(t),lag_seconds=.3 if t<1320 else .7) for t in range(1210,1440,10)]
        with patch('tools.workdata.sync_calibrate.window_lags',return_value=local):
            refine_breakpoints(fit,[0.]*18000,[0.]*18000)
        self.assertEqual(len(fit['breakpoints']),1)
        rows=fit['breakpoints'][0]['refinement_windows']
        self.assertTrue(rows)
        for row in rows:
            self.assertAlmostEqual(row['b_mid_seconds'],row['t_mid_seconds']+row['lag_seconds'])


if __name__=='__main__': unittest.main()
