"""Closed relocation provenance and optional-camera boundary regressions."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from av.error import ExternalError
from tools.workdata import source_paths, timemap, sync_calibrate, sync_validate, proxies
from tools.validation import sample_segments
from tools.workdata.common import hash_file


class RelocationClosureTest(unittest.TestCase):
    def fixture(self,root):
        media=root/'moved.mp4';media.write_bytes(b'first')
        stamp=media.stat().st_mtime_ns
        row=dict(source=media.name,media_path=str(root/'old.mp4'),fingerprint=dict(
            source_sha256='a'*64,media_size=5,media_mtime_ns=stamp))
        inventory=dict(root=str(root),files=[dict(relative_path=media.name,sha256='a'*64,
                                               size_bytes=5,mtime_ns=stamp,needs_remux=False)])
        return media,row,inventory

    def test_mtime_closes_disk_inventory_mapping_and_unchanged_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            media,row,inventory=self.fixture(Path(directory));before=deepcopy(row)
            resolved=source_paths.checked_source(row,inventory)
            self.assertIs(resolved['fingerprint'],row['fingerprint'])
            self.assertEqual(row,before)
            for target in ('disk','inventory','mapping','same-size-content'):
                with self.subTest(target=target):
                    media,row,inventory=self.fixture(Path(directory))
                    stamp=inventory['files'][0]['mtime_ns']
                    if target in ('disk','same-size-content'):
                        if target=='same-size-content':media.write_bytes(b'other')
                        os.utime(media,ns=(stamp,stamp+10000000))
                    elif target=='inventory':inventory['files'][0]['mtime_ns']+=10000000
                    else:row['fingerprint']['media_mtime_ns']+=10000000
                    with self.assertRaisesRegex(ValueError,'mtime|provenance'):
                        source_paths.checked_source(row,inventory)

    def test_missing_remux_or_ambiguous_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            media,row,inventory=self.fixture(Path(directory))
            inventory['files'][0]['needs_remux']=True
            with self.assertRaisesRegex(ValueError,'remux'):source_paths.resolve_source(row,inventory)
            inventory['files'][0]['needs_remux']=False
            inventory['files'].append(deepcopy(inventory['files'][0]))
            with self.assertRaisesRegex(ValueError,'ambiguous'):source_paths.resolve_source(row,inventory)

    def test_checked_source_rechecks_size_and_mtime_even_after_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            media,row,inventory=self.fixture(Path(directory))
            for field in ('media_size','media_mtime_ns'):
                changed=deepcopy(row);changed['fingerprint'][field]+=1
                for resolved in (changed,dict(changed,media_path=str(media))):
                    with patch.object(source_paths,'resolve_source',return_value=resolved):
                        if resolved is changed:resolved['media_path']=str(media)
                        with self.assertRaisesRegex(ValueError,'Source changed'):
                            source_paths.checked_source(changed,inventory)


class BoundaryIsolationTest(unittest.TestCase):
    def test_calibrate_opt_in_runs_after_refinement_before_rows_and_outer_w_catches(self):
        import numpy as np
        from tools.workdata import keyframes,webcam
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.write_bytes(b'fake')
            files=[dict(camera=c,status='valid',source=c,media_path=str(source),fingerprint=dict(
                media_size=4,media_mtime_ns=source.stat().st_mtime_ns),segments=[dict(pts_start=0.,pts_end=800.,a=0.,b=1.,valid=True)])
                for c in ('cam_a','cam_b','cam_e','cam_w')]
            path=root/'base.json';path.write_text(json.dumps(dict(version=2,session='20261023',files=files,overlap=[[0.,800.]])))
            for enabled in (False,True):
                observed=[]
                def fit(*args):return dict(valid=False,reason='residual_tail_exceeds_0_2',valid_windows=12,
                                          segments=[dict(start=0.,end=800.,c0=0.,c1=0.)],breakpoints=[])
                def refine(fit,*args):fit['refined_marker']=True
                def recheck(fit,*args):
                    self.assertTrue(fit['refined_marker']);observed.append(fit);fit.update(valid=True,reason='valid_second_look')
                def sample(mapping,camera,folder,*args):
                    folder.mkdir(parents=True,exist_ok=True);(folder/(camera+'.json')).write_text('{}')
                    return dict(fingerprint={},sha256='fake',frames=[dict(source=camera,pts=i*.2,gap=False) for i in range(4)])
                with patch.object(sync_calibrate,'sample_camera',side_effect=sample), \
                     patch.object(keyframes,'source_keyframes',side_effect=lambda rows,*a:{r['source']:[] for r in rows}), \
                     patch('numpy.load',return_value=np.zeros((4,54,96),np.uint8)), \
                     patch.object(sync_calibrate,'window_lags',return_value=[]), \
                     patch.object(sync_calibrate,'fit_calibration',side_effect=fit), \
                     patch.object(sync_calibrate,'refine_breakpoints',side_effect=refine), \
                     patch.object(sync_calibrate,'second_look_fit',side_effect=recheck), \
                     patch.object(webcam,'calibrate_webcam',side_effect=ArithmeticError('outer W')):
                    result=sync_calibrate.run(path,root/'maps',root/'samples',second_look=enabled)
                self.assertEqual(len(observed),2 if enabled else 0)
                self.assertEqual(result['calibrated'],enabled)
                self.assertEqual('calibration' in result['files'][0],enabled)
                self.assertEqual(result['auxiliary_cameras']['cam_w']['error_type'],'ArithmeticError')

    def test_unknown_filename_is_rejected_before_opening_media(self):
        from tools.workdata.webcam import sample_filename_clock
        factory=unittest.mock.Mock()
        with self.assertRaisesRegex(ValueError,'Unknown webcam filename'):
            sample_filename_clock('unknown.mp4',factory)
        factory.assert_not_called()

    def test_timemap_only_w_first_failure_is_written_and_returned_and_abe_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir()
            for camera in ('cam_w','cam_a'):
                inventory=root/'inventory.json';inventory.write_text(json.dumps(dict(root=str(raw),files=[dict(
                    session='20261016',relative_path='missing.mp4',physical_camera=camera)])))
                for error in (KeyError('missing'),ExternalError(1,'external'),ArithmeticError('arithmetic')):
                    with self.subTest(camera=camera,error=type(error).__name__), \
                         patch.object(timemap,'source_path',side_effect=error):
                        if camera=='cam_a':
                            with self.assertRaises(type(error)):timemap.run(inventory,root/'remux',root/'out')
                        else:
                            result=timemap.run(inventory,root/'remux',root/'out')
                            row=result[0]['files'][0]
                            self.assertEqual(row['status'],'failed')
                            self.assertEqual(row['error_type'],type(error).__name__)
                            self.assertEqual(json.loads((root/'out/20261016.json').read_text()),result[0])

    def test_webcam_reference_unexpected_failure_is_visible(self):
        for error in (KeyError('stale'),ExternalError(1,'external'),ArithmeticError('arithmetic')):
            session={}
            with patch.object(sample_segments,'_read_webcam_reference',side_effect=error):
                self.assertIsNone(sample_segments.read_webcam_reference(Path('fixture'),session,{}))
            self.assertEqual(session['webcam_error_type'],type(error).__name__)
            self.assertIn(str(error),session['webcam_unavailable'])

    def test_cli_inventory_and_second_look_are_forwarded(self):
        with patch('psutil.Process'):
            for module,args,flag in (
                (sync_calibrate,['--timemaps','maps','--samples-root','samples'],True),
                (proxies,['--timemaps','maps'],False),
                (sync_validate,['--proxies','proxies','--timemaps','maps','--clock-samples','clock',
                                '--keyframes-root','keys'],True)):
                with self.subTest(module=module.__name__),patch.object(module,'run',return_value=dict(calibrated=True,passed=True)) as run:
                    argv=args+['--out-root','out','--session','20261023','--inventory','inventory.json']
                    if flag:argv+=['--second-look']
                    module.main(argv)
                    self.assertIn(Path('inventory.json'),run.call_args.args)
                    if flag:self.assertTrue(run.call_args.kwargs.get('second_look') or run.call_args.args[-1] is True)


class WorkerEvidenceTest(unittest.TestCase):
    def test_headers_privacy_hash_span_names_and_handover_bounds(self):
        from tools.workdata.workers import HEADER_VALUES,validate_worker_spans
        original=dict(version=1,**HEADER_VALUES,source_draft_sha256='a'*64,
                      spans=[dict(session='20261016',span_id='20261016_worker_1',worker_id='P1',start_wall=10.,end_wall=20.)],
                      handover_intervals=[dict(session='20261016',start_wall=20.,end_wall=30.)])
        self.assertEqual(validate_worker_spans(original,{'20261016':(0.,40.)}),original)
        for key,value in HEADER_VALUES.items():
            bad=deepcopy(original);bad[key]='private' if isinstance(value,str) else value+1
            with self.assertRaises(ValueError):validate_worker_spans(bad)
            if key!='status':
                bad=deepcopy(original);del bad[key]
                with self.assertRaisesRegex(ValueError,'header'):validate_worker_spans(bad)
        for digest in ('a'*63,'g'*64,'person-name'):
            bad=deepcopy(original);bad['source_draft_sha256']=digest
            with self.assertRaisesRegex(ValueError,'draft hash'):validate_worker_spans(bad)
        for name in ('first','20261023_worker_1','20261016_worker_0','20261016_worker_1_name'):
            bad=deepcopy(original);bad['spans'][0]['span_id']=name
            with self.assertRaisesRegex(ValueError,'anonymous'):validate_worker_spans(bad)
        for gap in (dict(session='20261016',start_wall=-10.,end_wall=0.),dict(session='20261016',start_wall=40.,end_wall=50.)):
            bad=deepcopy(original);bad['handover_intervals']=[gap]
            with self.assertRaisesRegex(ValueError,'Handover interval outside'):validate_worker_spans(bad,{'20261016':(0.,40.)})

    def test_worker_coverage_uses_all_intervals_verified_accepted_map_or_last_grid_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);workers=dict(spans=[dict(session='20260821')])
            session=dict(grid=dict(t0=10.,N=101,step=.2),overlap=[[12.,15.],[18.,29.]])
            self.assertEqual(sample_segments.worker_coverages(root,workers,{'20260821':session}),{'20260821':(12.,29.)})
            session.pop('overlap')
            self.assertEqual(sample_segments.worker_coverages(root,workers,{'20260821':session}),{'20260821':(10.,30.)})
            folder=root/'20260821';folder.mkdir();(folder/'session.json').write_text(json.dumps(session))
            mapping=root/'map.json';mapping.write_text(json.dumps(dict(overlap=[[11.,15.],[18.,28.]])))
            index=dict(sessions={'20260821':dict(accepted_mapping_path=str(mapping),accepted_mapping_sha256=hash_file(mapping))})
            (root/'manifest.json').write_text(json.dumps(index))
            self.assertEqual(sample_segments.worker_coverages(root,workers,{}),{'20260821':(11.,28.)})
            mapping.write_text(mapping.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'mapping hash'):sample_segments.worker_coverages(root,workers,{})


class InventoryMergeTest(unittest.TestCase):
    def test_changed_root_size_and_mtime_fail_and_disappeared_selected_file_is_removed(self):
        from tools.workdata import inventory
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';(raw/'20261016').mkdir(parents=True);(raw/'20261023').mkdir()
            for session in ('20261016','20261023'):
                (raw/session/'WIN_20261014_12_05_36_Pro.mp4').write_bytes(b'video')
            out=root/'inventory.json'
            with patch.object(inventory,'probe_metadata',return_value={}),patch.object(inventory,'probe_packets',return_value=dict(small_count=0)):
                original=inventory.create_inventory(raw,out);before=out.read_bytes();raw.rename(root/'moved')
                source=root/'moved'/original['files'][0]['relative_path'];stamp=source.stat().st_mtime_ns
                for data,mtime in ((b'longer',stamp),(b'video',stamp+10000000)):
                    source.write_bytes(data);os.utime(source,ns=(stamp,mtime))
                    with self.assertRaisesRegex(ValueError,'existing inventory'):
                        inventory.create_inventory(root/'moved',out,sessions=['20261016'])
                    self.assertEqual(out.read_bytes(),before)
                source.write_bytes(b'video');os.utime(source,ns=(stamp,stamp))
                moved=inventory.create_inventory(root/'moved',out,sessions=['20261016'])
                source.unlink()
                result=inventory.create_inventory(root/'moved',out,sessions=['20261016'])
                self.assertEqual(result['files'],[moved['files'][1]])

    def test_failed_remux_retains_only_previously_completed_or_skipped_valid_rows(self):
        from tools.workdata import remux
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir();(raw/'e.avi').write_bytes(b'fake')
            out=root/'out';out.mkdir();target=out/'e.mp4'
            inv=root/'inventory.json';inv.write_text(json.dumps(dict(root=str(raw),files=[dict(session='20261016',relative_path='e.avi',needs_remux=True)])))
            failure=dict(output=str(target),status='failed',validation=dict(valid=False),marker='new')
            for status,valid,keep in (('completed',True,True),('skipped',True,True),('failed',True,False),('completed',False,False)):
                old=dict(output=str(target),status=status,validation=dict(valid=valid),marker='old')
                report=out/'remux_report.json';report.write_text(json.dumps(dict(files=[old])))
                with patch.object(remux,'remux_one',return_value=failure):remux.run_inventory(inv,out)
                self.assertEqual(json.loads(report.read_text())['files'],[old if keep else failure])


if __name__=='__main__':unittest.main()
