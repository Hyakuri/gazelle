import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tools.workdata.sync_calibrate import fit_calibration, refine_breakpoints
from tools.workdata.timemap import map_file_time
from tools.workdata.sync_validate import residual_summary


def windows(values):
    return [dict(t_mid_seconds=30.+60*i, lag_seconds=float(value), valid=True,reason='valid')
            for i, value in enumerate(values)]


class SynchronizationV3Test(unittest.TestCase):
    def test_optional_webcam_residual_does_not_gate_required_camera_pairs(self):
        from tools.workdata.sync_validate import residual_pairs,session_passed
        rng=np.random.default_rng(150);signal=rng.normal(size=6000)
        pairs=residual_pairs(dict(cam_a=signal,cam_b=signal,cam_e=signal,cam_w=np.roll(signal,4)),1200.)
        self.assertTrue(session_passed(pairs))
        self.assertFalse(pairs['W-B']['passed'])
        self.assertAlmostEqual(pairs['W-B']['windows'][3]['lag_seconds'],.8,delta=.02)

    def test_optional_webcam_validation_never_reads_a_clock(self):
        from contextlib import ExitStack
        from tools.workdata.sync_validate import webcam_evidence
        from tools.workdata.common import hash_file
        class Capture:
            def __init__(self,*args): self.k=0
            def read(self):
                self.k+=1
                return (True,np.zeros((54,96,3),dtype=np.uint8)) if self.k<=4 else (False,None)
            def get(self,key): return (self.k-1)*200.
            def release(self): pass
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory);video=root/'w.mp4';video.write_bytes(b'fake')
            grid=dict(t0=0.,step=.2,N=4,step_hz=5.)
            rows=[dict(k=k,t_k=k*.2,source='w',pts=k*.2,delta_seconds=0.,gap=False) for k in range(4)]
            (root/'w.json').write_text(json.dumps(dict(frames=rows,video_sha256=hash_file(video))))
            session=dict(N=4,grid=grid,auxiliary_cameras={'cam_w':dict(available=True,video='w.mp4',frames='w.json',sha256=hash_file(video))})
            with patch('tools.workdata.sync_validate.ClockReader',side_effect=AssertionError('W has no OSD')), \
                 patch('tools.workdata.sync_validate.source_keyframes',return_value={'w':[]}), \
                 patch('tools.workdata.sync_validate.scan_keyframes',return_value={'pts':[]}), \
                 patch('tools.workdata.sync_validate.cv2.VideoCapture',side_effect=Capture):
                cells,thumbs,audit=webcam_evidence(session,root,root,dict(files=[dict(camera='cam_w',source='w')]),root,stack)
            self.assertEqual(cells.shape,(3,72))
            self.assertEqual(thumbs.shape,(4,54,96))
            self.assertEqual(audit['decoded_frames'],4)

    def test_sampling_fingerprint_covers_base_wrapper_but_not_motion_fitting(self):
        from tools.workdata.sampling_fingerprint import COMPONENTS, sampling_hash

        root = Path(__file__).resolve().parents[1] / 'tools' / 'workdata'
        sources = {name: (root / name).read_text(encoding='utf-8') for name in COMPONENTS}
        original = sampling_hash(sources)[0]
        changed = dict(sources)
        changed['timemap.py'] = changed['timemap.py'].replace(
            '    return base\n', '    return base + 1.\n', 1)
        self.assertNotEqual(original, sampling_hash(changed)[0])
        changed = dict(sources)
        changed['sync_calibrate.py'] = changed['sync_calibrate.py'].replace(
            'return np.log1p(cells)', 'return np.zeros_like(cells)', 1)
        self.assertEqual(original, sampling_hash(changed)[0])

    def test_source_keyframes_reject_changed_media_before_cache_lookup(self):
        from tools.workdata.keyframes import source_keyframes

        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / 'source.mp4'
            media.write_bytes(b'original')
            stat = media.stat()
            row = dict(source='source', media_path=str(media), fingerprint=dict(
                media_size=stat.st_size, media_mtime_ns=stat.st_mtime_ns,
                source_sha256='mapped-sha'))
            with patch('tools.workdata.keyframes.scan_keyframes', return_value=dict(pts=[0.])) as scan:
                self.assertEqual(source_keyframes([row], directory), {'source': [0.]})
                scan.reset_mock()
                media.write_bytes(b'changed media')
                with self.assertRaisesRegex(ValueError, 'Source changed since mapping'):
                    source_keyframes([row], directory)
                scan.assert_not_called()

    def test_validation_run_consumes_actual_map_schema_and_masks_proxy_packets(self):
        from tools.workdata.sync_validate import run
        from tools.workdata.proxies import ROLES
        class Capture:
            def __init__(self,*args):self.k=0
            def read(self):
                self.k+=1
                return (True,np.zeros((54,96,3),dtype=np.uint8)) if self.k<=4 else (False,None)
            def get(self,key):return (self.k-1)*200.
            def release(self):pass
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);session=root/'proxies/s';session.mkdir(parents=True)
            grid=dict(t0=0.,step=.2,N=4,step_hz=5.)
            cameras={};files=[]
            for camera,role in ROLES.items():
                cameras[camera]=dict(video=role+'.mp4',frames=role+'.json',sha256='hash')
                rows=[dict(k=k,t_k=k*.2,source=camera,pts=k*.2,delta_seconds=0.,gap=False) for k in range(4)]
                (session/(role+'.json')).write_text(json.dumps(dict(frames=rows,video_sha256='hash')))
                files.append(dict(source=camera))
            (session/'session.json').write_text(json.dumps(dict(session='s',grid=grid,N=4,cameras=cameras,time_map_version=2)))
            (root/'s.json').write_text(json.dumps(dict(version=3,calibrated=True,files=files,calibration={})))
            (root/'clock.json').write_text(json.dumps(dict(sessions=[dict(session='s',indices=[])])))
            with patch('tools.workdata.sync_validate.hash_file',return_value='hash'), \
                 patch('tools.workdata.sync_validate.source_keyframes',return_value={c:[] for c in ROLES}), \
                 patch('tools.workdata.sync_validate.scan_keyframes',return_value=dict(pts=[.2])), \
                 patch('tools.workdata.sync_validate.cv2.VideoCapture',side_effect=Capture), \
                 patch('tools.workdata.sync_validate.export_events',return_value=[]) as events:
                result=run(root/'proxies',root/'out','s',root/'clock.json',root,root/'keys')
            self.assertEqual(result['proxy_time_map_version'],2)
            self.assertAlmostEqual(result['audit']['cam_b']['masked_fraction'],1/3)
            self.assertEqual(events.call_args.args[-1],{})

    def test_contract_noisy_steps_and_line(self):
        rng=np.random.default_rng(7);t=np.arange(60)*60.+30;i=np.arange(60)
        cases=[(-.6+.0002*t+rng.normal(0,.03,60),[]),
               (np.where(i<30,0.,.4)+rng.normal(0,.02,60),[1800.]),
               (np.where((i>=20)&(i<28),.4,0.)+rng.normal(0,.02,60),[1200.,1680.]),
               (np.where(i<40,.1,-.2)+rng.normal(0,.04,60),[2400.])]
        for values,cuts in cases:
            fit=fit_calibration(windows(values),3600.)
            self.assertTrue(fit['valid'])
            self.assertEqual([p['seconds'] for p in fit['breakpoints']],cuts)

    def test_event_reread_requires_identical_validation_pixels(self):
        from tools.workdata.sync_validate import checked_thumbnail
        image=np.zeros((54,96,3),dtype=np.uint8)
        checked_thumbnail(image,np.zeros((54,96),dtype=np.uint8))
        with self.assertRaisesRegex(ValueError,'differs'):
            checked_thumbnail(image,np.ones((54,96),dtype=np.uint8))

    def test_comparison_uses_same_base_time_across_domains(self):
        from tools.workdata.calibration_compare import maximum_lag_difference
        old=dict(valid=True,origin=0.,segments=[dict(start=0.,end=3600.,c0=2.,c1=.00001)])
        new=dict(old,time_domain='base')
        result=maximum_lag_difference(old,new,0.,3600.)
        self.assertTrue(result['retain_proxy'])
        self.assertLess(result['maximum_seconds'],.000021)

    def test_clock_uses_source_base_and_half_open_integer_second_limits(self):
        from tools.workdata.sync_calibrate import clock_sample
        row=clock_sample(0,1,100.,.2,'cam_a',lambda k:{'wall_time':102.},lambda k:102.82)
        self.assertTrue(row['passed'])
        self.assertAlmostEqual(row['delta_seconds'],.82)
        self.assertEqual(row['reading_minus_grid_seconds'],2.)
        for camera,lo,hi in (('cam_a',-.5,1.5),('cam_e',-1.5,2.5)):
            for delta,expected in ((lo,True),(hi,False),(lo-.01,False)):
                result=clock_sample(0,1,100.,.2,camera,lambda k:{'wall_time':100.},lambda k:100.+delta)
                self.assertEqual(result['passed'],expected)

    def test_closure_and_insufficient_third_pair_are_reported_without_new_gate(self):
        from tools.workdata.sync_validate import closure_summary, session_passed
        pairs={name:dict(windows=windows([value]*20),conclusion='passed')
               for name,value in (('A-B',.04),('E-B',-.02),('A-E',.06))}
        result=closure_summary(pairs)
        self.assertAlmostEqual(result['median_closure_seconds'],0.)
        self.assertAlmostEqual(result['inferred_A_minus_E_seconds'],.06)
        pairs['A-E']['conclusion']='insufficient_evidence'
        self.assertTrue(session_passed(pairs))
        pairs['E-B']['conclusion']='insufficient_evidence'
        self.assertFalse(session_passed(pairs))

    def test_step_selection_excludes_overlap_against_actual_first_postcut_frame(self):
        from tools.workdata.calibrated_frames import calibrated_frames, uncertain_ranges, is_uncertain
        for jump,expected in ((.4,[99.5,99.65,99.75]),(-.4,[99.5,99.9,100.45,100.55])):
            fit=dict(valid=True,time_domain='base',origin=0.,segments=[
                dict(start=0.,end=100.,c0=0.,c1=0.),dict(start=100.,end=200.,c0=jump,c1=0.)],
                breakpoints=[dict(seconds=100.,uncertainty_seconds=[90.,110.])])
            stats={};ranges=uncertain_ranges(fit)
            rows=[dict(wall_time=b) for b in (99.5,99.9,100.05,100.15)]
            selected=list(calibrated_frames(iter(rows),fit,ranges,stats))
            np.testing.assert_allclose([r['wall_time'] for r in selected],expected)
            self.assertTrue(is_uncertain(100.,ranges))
            self.assertFalse(is_uncertain(80.,ranges))
            self.assertEqual(stats['excluded_overlap_frames'],int(jump>0))
            self.assertTrue(all(a['wall_time']<b['wall_time'] for a,b in zip(selected,selected[1:])))

    def test_crossing_keyframe_mask_uses_half_open_intervals(self):
        from tools.workdata.keyframes import step_mask
        rows=[dict(source='a',pts=10.),dict(source='a',pts=10.2)]
        for key,expected in ((10.2,True),(10.12,True),(10.,False),(10.4,False)):
            with self.subTest(key=key):
                self.assertEqual(step_mask(rows,{'a':[key]}).tolist(),[False,expected])
        rows[1]['source']='b'
        self.assertEqual(step_mask(rows,{'a':[],'b':[]}).tolist(),[False,True])

    def test_antialiased_thumbnail_paths_agree_on_high_frequency_pattern(self):
        import av
        from tools.workdata.keyframes import validation_thumbnail
        gray=np.random.default_rng(140).integers(16,241,(1080,1920),dtype=np.uint8)
        image=np.repeat(gray[:,:,None],3,axis=2)
        frame=av.VideoFrame.from_ndarray(image,format='bgr24')
        sampled=frame.reformat(width=96,height=54,format='gray').to_ndarray()
        compared=validation_thumbnail(image)
        self.assertLessEqual(np.mean(abs(sampled.astype(float)-compared)),2.)

    def test_keyframe_scan_uses_all_packets_without_decoding_and_reuses_verified_key(self):
        from types import SimpleNamespace
        from tools.workdata.keyframes import scan_keyframes
        class Container:
            streams=SimpleNamespace(video=[object()])
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def demux(self,stream):
                return iter([SimpleNamespace(pts=k,time_base=.1,is_keyframe=k in (0,2)) for k in range(4)])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);video=root/'input';video.write_bytes(b'mock')
            with patch('tools.workdata.keyframes.av.open',return_value=Container()) as opened:
                first=scan_keyframes(video,root/'cache','sha')
                second=scan_keyframes(video,root/'cache','sha')
            self.assertEqual(first['pts'],[0.,.2])
            self.assertEqual(first,second)
            opened.assert_called_once()

    def test_sampling_fingerprint_mismatch_is_rejected_before_pixels_are_read(self):
        from tools.workdata.sample_cache import read_sample_cache
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            fingerprint=dict(mapping_sha256='map',grid={'N':1},camera='cam_a',
                             implementation_sha256='old-fit',sampling_sha256='old-sampler')
            (root/'cam_a.json').write_text(json.dumps(dict(fingerprint=fingerprint,grid={'N':1})))
            current=dict(fingerprint,sampling_sha256='different-sampler')
            with self.assertRaisesRegex(ValueError,'sampling implementation'):
                read_sample_cache(root,'cam_a',current)

    def test_zero_noise_minority_step_is_found_even_with_zero_mad(self):
        fit = fit_calibration(windows([0.]*22+[.4]*38), 3600.)
        self.assertTrue(fit['valid'])
        self.assertEqual(len(fit['breakpoints']), 1)
        self.assertAlmostEqual(fit['breakpoints'][0]['seconds'], 1320.)

    def test_short_bump_requires_two_cuts(self):
        values = np.zeros(60)
        values[20:28] = .4
        fit = fit_calibration(windows(values), 3600.)
        self.assertTrue(fit['valid'])
        self.assertEqual([p['seconds'] for p in fit['breakpoints']], [1200., 1680.])

    def test_mad_and_tail_failures_are_not_hidden(self):
        for values, reason in ((np.tile([-.15,.15],30), 'residual_mad_exceeds_0_08'),
                               (np.where(np.arange(60)%4==0,.5,0.), 'residual_tail_exceeds_0_2')):
            with self.subTest(reason=reason):
                fit = fit_calibration(windows(values),3600.)
                self.assertFalse(fit['valid'])
                self.assertEqual(fit['reason'],reason)

    def test_base_domain_mapping_has_explicit_minus_sign(self):
        fit = dict(valid=True, time_domain='base', origin=0.,
                   segments=[dict(start=0.,end=1000.,c0=.4,c1=.001)])
        row = dict(segments=[dict(pts_start=0.,pts_end=1000.,a=0.,b=1.)],calibration=fit)
        self.assertAlmostEqual(map_file_time(row,100.),99.5)
        fit['segments']=[dict(start=0.,end=100.,c0=0.,c1=0.),
                         dict(start=100.,end=200.,c0=.4,c1=0.)]
        self.assertAlmostEqual(map_file_time(row,99.9),99.9)
        self.assertAlmostEqual(map_file_time(row,100.),99.6)

    def test_validation_requires_ten_windows_and_temporal_coverage(self):
        self.assertEqual(residual_summary(windows([0.]*9),3600.)['conclusion'],'insufficient_evidence')
        self.assertEqual(residual_summary(windows([0.]*10),3600.)['conclusion'],'insufficient_evidence')
        result=residual_summary(windows([0.]*20),3600.)
        self.assertEqual(result['conclusion'],'passed')
        self.assertEqual(result['maximum_endpoint_bias_seconds'],0.)

    def test_refinement_is_executed_and_records_uncertainty(self):
        fit=fit_calibration(windows([0.]*22+[.4]*38),3600.)
        local=[dict(t_mid_seconds=float(t),lag_seconds=0. if t<1320 else .4,valid=True)
               for t in range(1210,1440,10)]
        with patch('tools.workdata.sync_calibrate.window_lags',return_value=local) as measured:
            refine_breakpoints(fit,np.zeros(18000),np.zeros(18000))
        measured.assert_called_once()
        point=fit['breakpoints'][0]
        self.assertTrue(point['refined'])
        good=[r['t_mid_seconds'] for r in local]
        left=max(t for t in good if t<point['seconds'])
        right=min(t for t in good if t>=point['seconds'])
        self.assertEqual(point['uncertainty_seconds'],[left-10,right+10])


if __name__=='__main__':
    unittest.main()
