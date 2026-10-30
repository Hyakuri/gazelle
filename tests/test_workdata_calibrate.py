import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tools.workdata.sync_calibrate import (
    lag_peak, window_lags, fit_calibration, corrected_time, motion_cells,
    clock_sample, clock_summary, select_signals, refine_breakpoints,
)
from tools.workdata.timemap import fit_time_map, detect_pts_runs, map_time, run as run_timemap
from tools.workdata.sync_validate import residual_summary, event_indices


class CalibrationTest(unittest.TestCase):
    def test_refit_reuses_signed_sample_evidence_without_decoding_or_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir()
            media=source/'sample.mp4';media.write_bytes(b'fake video')
            stat=media.stat();session='20260821'
            entry=dict(session=session,relative_path='sample.mp4',size_bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,
                       sha256='original-sha',physical_camera='cam_a',needs_remux=False)
            inventory=root/'inventory.json';inventory.write_text(json.dumps(dict(root=str(source),files=[entry])))
            cache=root/'old/anchors'/session/'sample.json';cache.parent.mkdir(parents=True)
            evidence=dict(version=2,fingerprint=dict(source_sha256='original-sha',media_size=stat.st_size,
                          media_mtime_ns=stat.st_mtime_ns,step=10.,window=2.25,implementation_sha256='original-code'),
                sampled=dict(camera='cam_a',pts_start=0.,pts_end=20.,windows=3,decoded_samples=5,recognized_samples=5,
                             anchors=[dict(pts=t,wall_time=1000+t,frame_index=i+1) for i,t in enumerate((0.,10.,20.))],
                             pts_runs=[dict(pts_start=0.,pts_end=0.,frame_start=0,frame_end=0),
                                       dict(pts_start=0.,pts_end=20.,frame_start=1,frame_end=3)]))
            cache.write_text(json.dumps(evidence));before=cache.read_bytes()
            with patch('tools.workdata.timemap.sample_file',side_effect=AssertionError('must not decode')):
                result=run_timemap(inventory,root/'remux',root/'new',sample_cache=root/'old')
            row=result[0]['files'][0]
            self.assertEqual(row['status'],'valid')
            self.assertEqual(len(row['segments']),1)
            self.assertEqual(row['fingerprint']['sampled_implementation_sha256'],'original-code')
            self.assertEqual(cache.read_bytes(),before)
            evidence['fingerprint']['media_size']+=1;cache.write_text(json.dumps(evidence))
            result=run_timemap(inventory,root/'remux',root/'rejected',sample_cache=root/'old')
            self.assertEqual(result[0]['files'][0]['status'],'failed')

    def test_coherent_clock_offsets_and_ramps_do_not_create_segments(self):
        x = np.arange(300) * 10.
        y = 1000 + .998 * x
        disturbed = y.copy()
        disturbed[40:70] += .5
        disturbed[160:190] += np.linspace(.5, .9, 30)
        fit = fit_time_map([dict(pts=a, wall_time=b) for a,b in zip(x,disturbed)],0,3000)
        self.assertEqual(len(fit),1)
        self.assertLess(np.max(np.abs([map_time(fit,t)-v for t,v in zip(x,y)])),.1)
        self.assertGreater(fit[0]['residuals']['p95'],.45)
        self.assertEqual(fit[0]['anchor_count'],300)
        bad = disturbed.copy()
        bad[::2] += 5
        fit = fit_time_map([dict(pts=a,wall_time=b) for a,b in zip(x,bad)],0,3000)
        self.assertFalse(fit[0]['valid'])

    def test_pts_breaks_are_between_actual_frames_and_disambiguate_reset(self):
        pts = [0,.1,.2,2,2.1,2.2,0,.1,.2]
        runs = detect_pts_runs(pts)
        self.assertEqual([(r['frame_start'],r['frame_end']) for r in runs],[(0,2),(3,5),(6,8)])
        rows = [dict(pts=p,wall_time=100+i*.1,frame_index=i) for i,p in enumerate(pts)]
        fit = fit_time_map(rows,0,2.3,pts_runs=runs)
        self.assertEqual(len(fit),3)
        self.assertEqual(fit[0]['pts_end'],.2)
        self.assertEqual(fit[1]['pts_start'],2)
        self.assertAlmostEqual(map_time(fit,.1,frame_index=7),100.7)
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            map_time(fit,.1)

    def test_equal_pts_is_not_a_backward_discontinuity(self):
        runs=detect_pts_runs([0.,0.,.05,.1])
        self.assertEqual(len(runs),1)
        self.assertEqual((runs[0]['frame_start'],runs[0]['frame_end']),(0,3))

    def test_lag_sign_interpolation_and_invalid_peaks(self):
        rng = np.random.default_rng(139)
        x = np.convolve(rng.normal(size=1200),np.ones(5)/5,'same')
        delayed = np.interp(np.arange(1200)-2.3,np.arange(1200),x)
        result = lag_peak(x,delayed)
        self.assertTrue(result['valid'])
        self.assertAlmostEqual(result['lag_seconds'],.46,delta=.025)
        self.assertTrue(lag_peak(x,np.roll(x,50))['at_boundary'])
        self.assertFalse(lag_peak(np.ones(300),np.ones(300))['valid'])
        periodic = np.sin(np.arange(600)*np.pi/5)
        self.assertEqual(lag_peak(periodic,periodic)['reason'],'peak_not_prominent')

    def test_step_fit_has_strict_coverage_and_mad_gates(self):
        noise=np.random.default_rng(139).normal(0,.005,60)
        rows = [dict(t_mid_seconds=t,lag_seconds=.2+.00001*t+(.4 if t>=1350 else 0)+e,valid=True)
                for t,e in zip(np.arange(30,3600,60),noise)]
        fit = fit_calibration(rows,3600)
        self.assertTrue(fit['valid'])
        self.assertEqual(len(fit['breakpoints']),1)
        self.assertAlmostEqual(fit['breakpoints'][0]['seconds'],1320,delta=60)
        self.assertAlmostEqual(fit['breakpoints'][0]['step_seconds'],.4,delta=.01)
        self.assertFalse(fit_calibration(rows[:9],3600)['valid'])
        self.assertFalse(fit_calibration(rows[:10],3600)['valid'])

    def test_fixed_point_solves_linear_clock_equation(self):
        fit = dict(valid=True,origin=1000,segments=[dict(start=0,end=3600,c0=2.5,c1=.0002)])
        base = 2800.
        actual = corrected_time(base,fit)
        self.assertAlmostEqual(actual,(base-2.5+.0002*1000)/1.0002,delta=.001)

    def test_two_iterations_are_accurate_despite_large_last_update(self):
        for origin in (1000.,1700000000.):
            fit=dict(valid=True,origin=origin,segments=[dict(start=0.,end=3600.,c0=3.,c1=-.0005)])
            exact=(origin-3.-.0005*origin)/(1.-.0005)
            with self.subTest(origin=origin):
                self.assertAlmostEqual(corrected_time(origin,fit),exact,delta=.001)

    def test_positive_step_without_a_solution_still_fails(self):
        fit=dict(valid=True,origin=0.,segments=[dict(start=0.,end=100.,c0=0.,c1=0.),
                                              dict(start=100.,end=200.,c0=.4,c1=0.)])
        with self.assertRaisesRegex(ValueError,'converge'):
            corrected_time(100.1,fit)

    def test_convergence_gate_measures_solution_error_not_unscaled_residual(self):
        fit=dict(valid=True,origin=0.,segments=[dict(start=-100.,end=100.,c0=9.91,c1=-.01)])
        candidate=-10.0091
        exact=-9.91/.99
        self.assertLess(abs(candidate-(-9.91+.01*candidate)),.001)
        self.assertGreater(abs(candidate-exact),.001)
        with self.assertRaisesRegex(ValueError,'converge'):
            corrected_time(0.,fit)

    def test_explicit_sample_reuse_verifies_pixels_grid_and_complete_decoding(self):
        from tools.workdata.sample_cache import read_sample_cache
        from tools.workdata.common import hash_file
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'cam_e.npy';sidecar=root/'cam_e.json'
            np.save(target,np.zeros((3,54,96),dtype=np.uint8))
            grid=dict(t0=10.,N=3,step=.2,step_hz=5.)
            fingerprint=dict(mapping_sha256='1'*64,implementation_sha256='2'*64,sampling_sha256='s'*64,grid=grid,camera='cam_e')
            saved=dict(fingerprint=fingerprint,grid=grid,sha256=hash_file(target),
                frames=[dict(k=k,t_k=10.+k*.2,source='source.mp4',pts=k*.2,delta_seconds=0.,gap=False) for k in range(3)],
                source_decode=[dict(source='source.mp4',decoded_frames=12,reached_eof=True)])
            sidecar.write_text(json.dumps(saved),encoding='utf-8')
            original_sidecar=sidecar.read_bytes();original_pixels=target.read_bytes()
            current=dict(fingerprint,implementation_sha256='3'*64)
            cached=read_sample_cache(root,'cam_e',current)
            self.assertEqual(cached['fingerprint']['implementation_sha256'],'2'*64)
            self.assertEqual(sidecar.read_bytes(),original_sidecar)
            self.assertEqual(target.read_bytes(),original_pixels)
            with self.assertRaisesRegex(ValueError,'source set'):
                read_sample_cache(root,'cam_e',current,{'another.mp4'})
            with self.assertRaisesRegex(ValueError,'provenance'):
                read_sample_cache(root,'cam_e',dict(current,mapping_sha256='4'*64))
            target.write_bytes(original_pixels[:-1]+b'\x01')
            with self.assertRaisesRegex(ValueError,'checksum'):
                read_sample_cache(root,'cam_e',current)
            target.write_bytes(original_pixels)
            saved['source_decode'][0]['reached_eof']=False
            sidecar.write_text(json.dumps(saved),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'complete'):
                read_sample_cache(root,'cam_e',current)
            saved['source_decode'][0]['reached_eof']=True
            np.save(target,np.zeros((3,54,95),dtype=np.uint8))
            saved['sha256']=hash_file(target)
            sidecar.write_text(json.dumps(saved),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'shape'):
                read_sample_cache(root,'cam_e',current)

    def test_calibration_refit_preserves_samples_and_checks_sources_before_reuse(self):
        from tools.workdata.common import hash_file
        from tools.workdata.sync_calibrate import run
        from tools.workdata.sampling_fingerprint import sampling_hash
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);samples=root/'samples/session';samples.mkdir(parents=True)
            files=[];original={}
            for camera in ('cam_a','cam_b','cam_e'):
                media=root/(camera+'.mp4');media.write_bytes(b'fake video')
                stat=media.stat()
                files.append(dict(camera=camera,source=media.name,media_path=str(media),status='valid',
                    fingerprint=dict(media_size=stat.st_size,media_mtime_ns=stat.st_mtime_ns)))
            mapping=root/'base.json'
            # An unusable optional W must not block the required A/B/E refit.
            files.append(dict(camera='cam_w',source='missing-webcam.mp4',status='failed',error='no frames'))
            mapping.write_text(json.dumps(dict(version=2,session='session',files=files,overlap=[[10.,10.4]])))
            grid=dict(t0=10.,N=3,step=.2,step_hz=5.)
            for row in files:
                if row['camera']=='cam_w': continue
                camera=row['camera'];target=samples/(camera+'.npy');sidecar=samples/(camera+'.json')
                np.save(target,np.zeros((3,54,96),dtype=np.uint8))
                sidecar.write_text(json.dumps(dict(grid=grid,sha256=hash_file(target),
                    fingerprint=dict(mapping_sha256=hash_file(mapping),implementation_sha256='original-code',
                                     sampling_sha256=sampling_hash()[0],grid=grid,camera=camera),
                    frames=[dict(k=k,t_k=10.+k*.2,source=row['source'],pts=k*.2,delta_seconds=0.,gap=False) for k in range(3)],
                    source_decode=[dict(source=row['source'],decoded_frames=12,reached_eof=True)])))
                original[target]=target.read_bytes();original[sidecar]=sidecar.read_bytes()
            windows=[dict(t_mid_seconds=t,lag_seconds=.03,valid=True) for t in np.linspace(.02,.38,10)]
            with patch('tools.workdata.sync_calibrate.sample_camera',side_effect=AssertionError('must not decode')), \
                 patch('tools.workdata.keyframes.source_keyframes',return_value={r['source']:[] for r in files}), \
                 patch('tools.workdata.sync_calibrate.window_lags',return_value=windows), \
                 patch('tools.workdata.timemap.assemble_session',return_value=dict(session='session')):
                result=run(mapping,root/'new',root/'samples',reuse_samples=True)
                self.assertTrue(result['calibrated'])
                for camera in ('cam_a','cam_e'):
                    for row in result['calibration'][camera]['windows']:
                        self.assertAlmostEqual(row['b_mid_seconds'], row['t_mid_seconds']+.03)
                self.assertFalse(result['auxiliary_cameras']['cam_w']['available'])
                self.assertIn('valid base map',result['auxiliary_cameras']['cam_w']['reason'])
                self.assertEqual(result['sampling_evidence']['cam_a']['fingerprint']['implementation_sha256'],'original-code')
                self.assertNotEqual(result['implementation_sha256'],'original-code')
                for path,content in original.items():
                    self.assertEqual(path.read_bytes(),content)
                import subprocess
                with patch('tools.workdata.webcam.calibrate_webcam',side_effect=subprocess.CalledProcessError(1,['ffprobe'])):
                    optional_failure=run(mapping,root/'optional-probe-failure',root/'samples',reuse_samples=True)
                self.assertTrue(optional_failure['calibrated'])
                self.assertFalse(optional_failure['auxiliary_cameras']['cam_w']['available'])
                self.assertEqual(optional_failure['auxiliary_cameras']['cam_w']['error_type'],'CalledProcessError')
                with self.assertRaisesRegex(FileExistsError,'fresh'):
                    run(mapping,root/'new',root/'samples',reuse_samples=True)
                Path(files[0]['media_path']).write_bytes(b'changed source')
                with self.assertRaisesRegex(ValueError,'Source changed'):
                    run(mapping,root/'rejected',root/'samples',reuse_samples=True)
                self.assertFalse((root/'rejected').exists())

    def test_gap_motion_and_clock_neighbor_reading_preserve_missing(self):
        thumbs = np.zeros((4,54,96),dtype=np.uint8)
        thumbs[1:] = 20
        cells = motion_cells(thumbs,np.array([False,False,True,False]))
        self.assertEqual(cells.shape,(3,72))
        self.assertTrue(np.all(np.isnan(cells[1:])))
        attempts = []
        def read(k):
            attempts.append(k)
            return {'wall_time':10.2} if k==6 else None
        row = clock_sample(5,20,9.,.2,'cam_a',read,lambda k:9.+k*.2)
        self.assertEqual(attempts,[5,4,6])
        self.assertEqual(row['used_k'],6)
        self.assertTrue(row['passed'])
        missing = clock_sample(5,20,9.,.2,'cam_a',lambda k:None,lambda k:9.+k*.2)
        self.assertFalse(missing['evaluable'])
        summary = clock_summary([row]*8+[missing])
        self.assertFalse(summary['evaluable_passed'])

    def test_window_grid_is_nonoverlapping_sixty_seconds(self):
        x = np.random.default_rng(139).normal(size=900)
        rows = window_lags(x,np.roll(x,2))
        self.assertEqual([r['t_mid_seconds'] for r in rows],[30,90,150])
        self.assertTrue(all(r['valid'] for r in rows))

    def test_clock_distribution_includes_failures_and_keeps_missing_absent(self):
        rows=[dict(camera='cam_e',evaluable=True,delta_seconds=value,reading_minus_grid_seconds=-value,passed=-1.5<=value<2.5)
              for value in (-2.,.5,2.5)]
        rows += [dict(camera='cam_e',evaluable=False,passed=False),
                 dict(camera='cam_a',evaluable=False,passed=False)]
        summary=clock_summary(rows)
        distribution=summary['delta_distribution']
        self.assertEqual(distribution['cam_e']['evaluable'],3)
        self.assertEqual(distribution['cam_e']['unevaluable'],1)
        self.assertEqual(distribution['cam_e']['passed'],1)
        self.assertEqual(distribution['cam_e']['signed_minimum_seconds'],-2.)
        self.assertEqual(distribution['cam_e']['signed_median_seconds'],.5)
        self.assertEqual(distribution['cam_e']['signed_maximum_seconds'],2.5)
        self.assertAlmostEqual(distribution['cam_e']['absolute_p90_seconds'],2.4)
        self.assertIsNone(distribution['cam_a']['signed_median_seconds'])
        self.assertIsNone(distribution['cam_a']['absolute_p90_seconds'])
        self.assertFalse(summary['passed'])

    def test_cell_selection_follows_motion_at_nonzero_lag(self):
        rng=np.random.default_rng(2)
        reference=rng.normal(size=1000)
        cells={camera:rng.normal(size=(1000,72)) for camera in ('cam_a','cam_b','cam_e')}
        cells['cam_b'][:]=reference[:,None]
        for camera in ('cam_a','cam_e'):
            cells[camera][:,:6]=np.roll(reference,20)[:,None]
        _,selection=select_signals(cells)
        for value in selection.values():
            self.assertEqual(set(value['cells']),set(range(6)))

    def test_webcam_uses_existing_fit_on_base_time_without_changing_required_rows(self):
        from tools.workdata.webcam import calibrate_webcam
        from tools.workdata.common import hash_file
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);media=root/'w.mp4';media.write_bytes(b'fake')
            stat=media.stat();grid=dict(t0=100.,N=6001,step=.2,step_hz=5.)
            row=dict(camera='cam_w',source='w',media_path=str(media),status='valid',
                     fingerprint=dict(media_size=stat.st_size,media_mtime_ns=stat.st_mtime_ns))
            required=dict(camera='cam_a',source='a',calibration={'preserved':True})
            mapping=dict(session='s',files=[required,row])
            np.save(root/'cam_w.npy',np.zeros((6001,54,96),dtype=np.uint8))
            frames=[dict(k=k,gap=False,source='w',pts=k*.2) for k in range(6001)]
            evidence=dict(frames=frames,fingerprint={'original':True},sha256=hash_file(root/'cam_w.npy'))
            (root/'cam_w.json').write_text(json.dumps(evidence))
            windows=[dict(t_mid_seconds=30.+60*i,lag_seconds=-2.,valid=True,reason='valid') for i in range(20)]
            with patch('tools.workdata.sync_calibrate.sample_camera',return_value=evidence) as sample, \
                 patch('tools.workdata.keyframes.source_keyframes',return_value={'w':[]}), \
                 patch('tools.workdata.webcam.select_webcam_signal',return_value=(np.zeros(6000),{'cells':[0]})), \
                 patch('tools.workdata.sync_calibrate.window_lags',return_value=windows):
                result=calibrate_webcam(mapping,root,grid,{},np.zeros((6000,72)),root)
            self.assertTrue(result['available'])
            self.assertEqual(result['calibration']['time_domain'],'base')
            self.assertEqual(result['calibration']['origin'],100.)
            self.assertAlmostEqual(result['calibration']['segments'][0]['c0'],-2.)
            self.assertTrue(all(w['b_mid_seconds']==w['t_mid_seconds']-2. for w in result['calibration']['windows']))
            self.assertEqual(sample.call_args.args[1],'cam_w')
            self.assertEqual(required,dict(camera='cam_a',source='a',calibration={'preserved':True}))
            self.assertIs(row['calibration'],result['calibration'])

    def test_residual_gate_keeps_failing_values_and_reports_invalid_windows(self):
        rows=[dict(t_mid_seconds=t,lag_seconds=.02,valid=True,reason='valid') for t in range(30,1200,60)]
        rows.append(dict(t_mid_seconds=1230,lag_seconds=10.,valid=False,reason='peak_at_boundary'))
        self.assertTrue(residual_summary(rows,1260)['passed'])
        for row in rows[:3]:
            row['lag_seconds']=.5
        result=residual_summary(rows,1260)
        self.assertFalse(result['passed'])
        self.assertEqual(result['valid_windows'],20)
        self.assertEqual(result['window_categories']['peak_at_boundary'],1)
        self.assertEqual(event_indices({'cam_b':np.zeros(900)}),[])

    def test_nonconvergent_clock_correction_is_rejected(self):
        calibration=dict(valid=True,origin=0,segments=[dict(start=0,end=100,c0=5,c1=.1)])
        with self.assertRaisesRegex(ValueError,'converge'):
            corrected_time(50,calibration)


if __name__ == '__main__':
    unittest.main()
