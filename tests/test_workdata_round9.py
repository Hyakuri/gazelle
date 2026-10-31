"""Round-9 contracts with temporary sources and numerical calibration evidence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from av.error import ExternalError

from tools.workdata import sync_calibrate as calibration


class BreakpointBoundsTest(unittest.TestCase):
    def test_1016_e_actual_windows_refine_inside_evidence_and_pass_exact_tail_gate(self):
        from tests.workdata_1016_windows import DURATION,WINDOWS,SHORT_WINDOWS
        def rows(values):
            return [dict(valid=valid,t_mid_seconds=t,lag_seconds=lag,
                         **(dict(b_mid_seconds=t+lag) if valid else {})) for t,lag,valid in values]
        fit=calibration.fit_calibration(rows(WINDOWS),DURATION);fit['time_domain']='base'
        with patch.object(calibration,'window_lags',return_value=rows(SHORT_WINDOWS)):
            calibration.refine_breakpoints(fit,[0.]*18018,[0.]*18018)
        self.assertTrue(fit['valid'],fit['reason'])
        self.assertEqual(fit['valid_windows'],50)
        self.assertAlmostEqual(fit['breakpoints'][0]['seconds'],1135.2,delta=.1)
        for actual,expected in zip(fit['breakpoints'][0]['uncertainty_seconds'],[1110.3,1160.2]):
            self.assertAlmostEqual(actual,expected,delta=.1)
        residuals=[abs(row['lag_seconds']-seg['c0']-seg['c1']*row['b_mid_seconds'])
                   for seg in fit['segments'] for row in fit['windows']
                   if row['valid'] and seg['start']<=row['b_mid_seconds']<seg['end']]
        self.assertEqual(sum(value>.2 for value in residuals),5)

    def test_refinement_rejects_outside_candidates_and_accepts_closed_endpoints(self):
        windows=[dict(valid=True,t_mid_seconds=30.+60*k,lag_seconds=.3 if k<22 else .7,
                      b_mid_seconds=30.+60*k+(.3 if k<22 else .7)) for k in range(60)]
        original=calibration.fit_calibration(windows,3600.)
        original['time_domain']='base'
        local=[dict(valid=True,t_mid_seconds=float(t),lag_seconds=.3 if t<1320 else .7)
               for t in range(1210,1440,10)]
        candidate_cuts=[((a['t_mid_seconds']+a['lag_seconds'])+(b['t_mid_seconds']+b['lag_seconds']))/2
                        for a,b in zip(local,local[1:])]
        for bounds in ((candidate_cuts[6],candidate_cuts[6]),(candidate_cuts[18],candidate_cuts[18]),(1200.,1201.)):
            with self.subTest(bounds=bounds):
                fit=deepcopy(original);point=fit['breakpoints'][0]
                point['adjacent_window_centers']=list(bounds)
                coarse=point['seconds']
                with patch.object(calibration,'window_lags',return_value=deepcopy(local)):
                    calibration.refine_breakpoints(fit,[0.]*18000,[0.]*18000)
                allowed=[cut for cut in candidate_cuts if bounds[0]<=cut<=bounds[1]]
                self.assertEqual(point['refined'],bool(allowed))
                self.assertEqual(point['seconds'],allowed[0] if allowed else coarse)


class RelocatedSourceTest(unittest.TestCase):
    def test_moved_sources_reach_sampling_proxies_keyframes_and_exact_clock_pair(self):
        from tools.workdata import proxies,keyframes
        from tools.workdata.sync_validate import ProxyClockReader
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir();files=[];entries=[];opened=[]
            for camera in ('cam_a','cam_b','cam_e','cam_w'):
                media=raw/(camera+'.mp4');media.write_bytes(b'fake')
                files.append(dict(camera=camera,status='valid',source=media.name,media_path=str(media),
                    fingerprint=dict(media_size=4,media_mtime_ns=media.stat().st_mtime_ns,source_sha256='a'*64),
                    segments=[dict(a=100.,b=1.,valid=True,pts_start=0.,pts_end=.6)]))
                entries.append(dict(relative_path=media.name,sha256='a'*64,size_bytes=4,mtime_ns=media.stat().st_mtime_ns))
            original=deepcopy(files);raw.rename(root/'moved')
            inventory=dict(root=str(root/'moved'),files=entries)
            path=root/'base.json';path.write_text(json.dumps(dict(version=2,session='20261016',files=files,overlap=[[100.,100.6]])))
            class Frame:
                def reformat(self,**kwargs):self.format=kwargs['format'];return self
                def to_ndarray(self,format=None):return np.zeros((54,96) if getattr(self,'format',format)=='gray' else (54,96,3),np.uint8)
            class Source:
                def __init__(self,path):
                    self.path=Path(path);opened.append(self.path);self.path.read_bytes()
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def frames(self,start=0.):return iter((p,Frame()) for p in (0.,.2,.4,.6) if p>=start)
            class Capture:
                def __init__(self,*args):pass
                def get(self,*args):return 4
                def release(self):pass
            original_frames=proxies.full_mapped_frames
            def frames(files,counts):return original_frames(files,counts,source_factory=Source)
            def keys(path,*args):
                self.assertTrue(Path(path).is_file());return dict(pts=[])
            def fit(*args):return dict(valid=True,reason='valid',valid_windows=0,windows=[],duration=.6,
                                      segments=[dict(start=0.,end=.6,c0=0.,c1=0.)],breakpoints=[])
            with patch.object(proxies.cv2,'VideoCapture',side_effect=Capture), \
                 patch.object(proxies,'full_mapped_frames',side_effect=frames), \
                 patch.object(keyframes,'scan_keyframes',side_effect=keys), \
                 patch.object(calibration,'window_lags',return_value=[]), \
                 patch.object(calibration,'fit_calibration',side_effect=fit):
                result=calibration.run(path,root/'cal',root/'samples',inventory=inventory)
            self.assertTrue(result['calibrated'])
            self.assertTrue(result['auxiliary_cameras']['cam_w']['available'])
            self.assertIn('calibration',result['files'][-1])
            self.assertEqual([r['media_path'] for r in result['files']],[r['media_path'] for r in original])
            self.assertEqual([r['fingerprint'] for r in result['files']],[r['fingerprint'] for r in original])
            def generate(files,grid,size,target,sidecar,fingerprint,camera,*args):
                counts=[];self.assertEqual(len(list(frames(files,counts))),4)
                return dict(video_sha256='fake',video_size_bytes=4,gap_count=0,source_decode=counts,elapsed_seconds=0.)
            with patch.object(proxies.cv2,'VideoCapture',side_effect=Capture), \
                 patch.object(proxies,'generate_camera',side_effect=generate),patch.object(proxies.subprocess,'run') as command:
                command.return_value.stdout='test'
                output=proxies.run(root/'cal/20261016.json',root/'out',inventory=inventory)
            self.assertEqual(len(output['cameras']),3)
            reader=ProxyClockReader(None,[dict(source=files[0]['source'],pts=.2,t_k=100.2)],
                                    {r['source']:r for r in original},'cam_a',Source,reader=object(),inventory=inventory)
            with patch('tools.workdata.sync_validate.read_frame',return_value=np.zeros((54,96,3),np.uint8)):
                self.assertAlmostEqual(reader.base_at(0),100.2)
            self.assertEqual(len(opened),9)
            self.assertTrue(all(p.parent==root/'moved' for p in opened))

    def test_resolve_without_rewriting_evidence_or_hashing_original(self):
        from tools.workdata.source_paths import resolve_source
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/'old';old.mkdir()
            media=old/'video.mp4';media.write_bytes(b'video')
            row=dict(source='video.mp4',media_path=str(media),camera='cam_b',
                     fingerprint=dict(source_sha256='a'*64,media_size=5,media_mtime_ns=media.stat().st_mtime_ns))
            before=deepcopy(row);new=root/'moved';old.rename(new)
            inventory=dict(root=str(new),files=[dict(relative_path='video.mp4',size_bytes=5,sha256='a'*64,
                                                   mtime_ns=row['fingerprint']['media_mtime_ns'])])
            with patch('tools.workdata.common.hash_file',side_effect=AssertionError('no full source hash')):
                resolved=resolve_source(row,inventory)
            self.assertEqual(resolved['media_path'],str(new/'video.mp4'))
            self.assertEqual(row,before)
            for field,value in (('sha256','b'*64),('size_bytes',6)):
                invalid=deepcopy(inventory);invalid['files'][0][field]=value
                with self.assertRaisesRegex(ValueError,'provenance'):
                    resolve_source(row,invalid)
            (new/'video.mp4').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'size'):
                resolve_source(row,inventory)

    def test_existing_remux_path_does_not_use_inventory(self):
        from tools.workdata.source_paths import resolve_source
        with tempfile.TemporaryDirectory() as directory:
            media=Path(directory)/'remux.mp4';media.write_bytes(b'remux')
            row=dict(source='original.avi',media_path=str(media))
            self.assertEqual(resolve_source(row,dict(root='absent',files=[])),row)


class WebcamPipelineTest(unittest.TestCase):
    def test_calibration_sign_mask_invalid_fit_and_decode_errors(self):
        from tools.workdata.webcam import calibrate_webcam
        from tools.workdata import keyframes
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);media=root/'w.mp4';media.write_bytes(b'fake')
            row=dict(camera='cam_w',status='valid',source='w',media_path=str(media),fingerprint=dict(
                media_size=4,media_mtime_ns=media.stat().st_mtime_ns))
            sidecar=dict(fingerprint={},sha256='pixels',frames=[dict(source='w',pts=k*.2,gap=False) for k in range(4)])
            (root/'cam_w.json').write_text('{}')
            pixels=np.zeros((4,54,96),np.uint8);pixels[1:]=20
            reference=np.arange(216,dtype=float).reshape(3,72)
            signal=np.array([.2,.4,.1]);mapping=dict(files=[row])
            grid=dict(t0=100.,step=.2,N=4,step_hz=5.)
            for valid in (True,False):
                row.pop('calibration',None)
                fit=dict(valid=valid,reason='valid' if valid else 'residual_tail_exceeds_0_2',segments=[],breakpoints=[])
                with patch.object(calibration,'sample_camera',return_value=sidecar), \
                     patch.object(keyframes,'source_keyframes',return_value={'w':[.2]}), \
                     patch('numpy.load',return_value=pixels), \
                     patch('tools.workdata.webcam.select_webcam_signal',return_value=(signal,{})) as select, \
                     patch.object(calibration,'window_lags',return_value=[dict(valid=True,t_mid_seconds=20.,lag_seconds=.4)]) as lags, \
                     patch.object(calibration,'fit_calibration',return_value=fit) as fitting, \
                     patch.object(calibration,'refine_breakpoints') as refine:
                    result=calibrate_webcam(mapping,root,grid,{},reference,root)
                np.testing.assert_array_equal(lags.call_args.args[0],reference.mean(axis=1))
                np.testing.assert_array_equal(lags.call_args.args[1],signal)
                np.testing.assert_array_equal(refine.call_args.args[1],reference.mean(axis=1))
                np.testing.assert_array_equal(refine.call_args.args[2],signal)
                self.assertEqual(fitting.call_args.args[0][0]['b_mid_seconds'],20.4)
                self.assertTrue(np.isnan(select.call_args.args[1][0]).all())
                self.assertTrue(np.isfinite(select.call_args.args[1][1:]).all())
                self.assertEqual(result['available'],valid)
                self.assertEqual('calibration' in row,valid)
            for error in (ExternalError(1,'bad W'),KeyError('W metadata')):
                with patch.object(calibration,'sample_camera',side_effect=error):
                    result=calibrate_webcam(mapping,root,grid,{},reference,root)
                self.assertFalse(result['available'])
                self.assertEqual(result['error_type'],type(error).__name__)

    def test_timemap_dispatch_uses_filename_clock_and_w_errors_do_not_set_exit_failure(self):
        from tools.workdata import timemap
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir();entries=[]
            for camera in ('cam_a','cam_b','cam_e','cam_w'):
                media=raw/(camera+'.mp4');media.write_bytes(b'fake');stat=media.stat()
                entries.append(dict(session='20261016',relative_path=media.name,physical_camera=camera,
                    size_bytes=4,mtime_ns=stat.st_mtime_ns,sha256='a'*64,needs_remux=False))
            inventory=root/'inventory.json';inventory.write_text(json.dumps(dict(root=str(raw),files=entries)))
            sampled=dict(pts_start=0.,pts_end=20.,windows=3,decoded_samples=3,recognized_samples=3,
                anchors=[dict(pts=t,wall_time=100.+t,frame_index=i) for i,t in enumerate((0.,10.,20.))],
                pts_runs=[dict(pts_start=0.,pts_end=20.,frame_start=0,frame_end=2)])
            webcam=dict(sampled,segments=[dict(a=100.,b=1.,valid=True,pts_start=0.,pts_end=20.)],
                        clock_source='filename_clock',clock_description='fixture')
            with patch.object(timemap,'sample_file',return_value=sampled) as osd, \
                 patch('tools.workdata.webcam.sample_filename_clock',return_value=webcam) as filename:
                result=timemap.run(inventory,root/'remux',root/'maps')
            self.assertEqual(osd.call_count,3);filename.assert_called_once()
            self.assertEqual(result[0]['files'][-1]['clock_source'],'filename_clock')
            for index,error in enumerate((ExternalError(1,'bad W'),KeyError('W metadata'),ArithmeticError('W failure'))):
                with patch.object(timemap,'sample_file',return_value=sampled), \
                     patch('tools.workdata.webcam.sample_filename_clock',side_effect=error):
                    result=timemap.run(inventory,root/'remux',root/('bad'+str(index)))
                self.assertTrue(all(r['status']=='valid' for r in result[0]['files'][:-1]))
                self.assertEqual(result[0]['files'][-1]['status'],'failed')
                self.assertEqual(result[0]['files'][-1]['error_type'],type(error).__name__)
            with patch.object(timemap,'run',return_value=result):
                self.assertEqual(timemap.main(['--inventory',str(inventory),'--remux-root',str(root/'remux'),
                                              '--out-root',str(root/'exit')]),0)

    def test_webcam_filename_rules_are_shared_and_configurable(self):
        from tools.workdata import inventory,webcam
        from datetime import datetime,timezone
        from types import SimpleNamespace
        roles=inventory.load_roles();roles['filename_clock_patterns'].append(dict(
            regex=r'test_\d{8}_\d{6}\.mp4',format='test_%Y%m%d_%H%M%S.mp4'))
        name='test_20261014_120536.mp4'
        self.assertEqual(inventory.identify('20261016',name,roles),('cam_w','filename_clock',None))
        class Source:
            start=0.
            def __init__(self,path): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def frames(self): return iter([(0.,None),(.2,None)])
        with patch.object(webcam,'load_roles',return_value=roles):
            result=webcam.sample_filename_clock(name,Source)
        self.assertEqual(result['segments'][0]['a'],datetime(2026,10,14,12,5,36,tzinfo=timezone.utc).timestamp())


if __name__=='__main__': unittest.main()
