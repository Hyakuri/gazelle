import random
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validation.sample_segments import create_dataset, sample_session, validate_manifest, plan, PILOT_TIME
from tools.validation import roi_regions
from tests.test_validation_roi import document


class SamplingTest(unittest.TestCase):
    def test_webcam_reference_requires_passing_bound_validation(self):
        from tools.validation.sample_segments import read_webcam_reference
        from tools.workdata.common import hash_file
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);session_root=root/'20261016';session_root.mkdir()
            path=session_root/'session.json';path.write_text('{}')
            video=session_root/'w.mp4';video.write_bytes(b'fake')
            grid=dict(t0=10.,N=3,step=.2,step_hz=5.)
            webcam=dict(video='w.mp4',frames='w.json',sha256=hash_file(video))
            session=dict(session='20261016',grid=grid,time_map_sha256='m'*64)
            sidecar=dict(camera='cam_w',role='webcam',grid=grid,video_sha256=hash_file(video),
                         frames=[dict(k=k,t_k=10+k*.2,pts=k*.2,source='w',delta_seconds=0.,gap=False) for k in range(3)])
            (session_root/'w.json').write_text(json.dumps(sidecar))
            self.assertIsNone(read_webcam_reference(path,session,webcam))
            self.assertIn('index is missing',session['webcam_unavailable'])
            validation=dict(auxiliary_cameras={'cam_w':dict(available=True)},pairs={'W-B':dict(passed=True)},
                calibration_map_sha256='m'*64,proxy_session_sha256=hash_file(path),audit={'cam_w':dict(sha256=hash_file(video))})
            checked=root/'validation.json'
            def save():
                checked.write_text(json.dumps(validation))
                (root/'manifest.json').write_text(json.dumps(dict(sessions={'20261016':dict(
                    validation_path=str(checked),validation_sha256=hash_file(checked))})))
            save()
            self.assertEqual(read_webcam_reference(path,session,webcam)['sha256'],hash_file(video))
            validation['auxiliary_cameras']['cam_w']['available']=False;save()
            self.assertIsNone(read_webcam_reference(path,session,webcam))
            validation['auxiliary_cameras']['cam_w']['available']=True
            validation['calibration_map_sha256']='changed';save()
            self.assertIsNone(read_webcam_reference(path,session,webcam))
            self.assertIn('provenance',session['webcam_unavailable'])
            validation['calibration_map_sha256']='m'*64
            validation['pairs']['W-B']['passed']=False;save()
            self.assertIsNone(read_webcam_reference(path,session,webcam))
            self.assertIn('provenance',session['webcam_unavailable'])
            validation['pairs']['W-B']['passed']=True;save()
            checked.write_text(checked.read_text()+' ')
            self.assertIsNone(read_webcam_reference(path,session,webcam))
            self.assertIn('hash differs',session['webcam_unavailable'])
            checked.unlink()
            self.assertIsNone(read_webcam_reference(path,session,webcam))
            self.assertTrue(session['webcam_unavailable'])

    def test_no_pilot_cohort_keeps_session_rng_and_assigns_spans_without_redraw(self):
        def read(path):
            return dict(session=path.parent.name,grid=dict(t0=100.,N=18000,step_hz=5.,step=.2),overlap=[[100.,3700.]],
                        cameras={c:dict(path='fake',sha256='a'*64) for c in ('cam_a','cam_b','cam_e')},
                        time_map_version=3,time_map_sha256='b'*64),[False]*18000
        with tempfile.TemporaryDirectory() as directory, patch('tools.validation.sample_segments.read_session',side_effect=read):
            root=Path(directory)
            for session in ('20261016','20261023'):
                (root/session).mkdir();(root/session/'session.json').touch()
            spans=dict(version=1,spans=[dict(session=s,span_id=s+'_01',start_wall=100.,end_wall=3700.,worker_id='P1')
                                        for s in ('20261016','20261023')])
            path=root/'workers.json';path.write_text(json.dumps(spans))
            result=plan(root,sessions=['20261016','20261023'],include_pilot=False,cohort='2026-10',worker_spans=path)
            plain=plan(root,sessions=['20261016'],include_pilot=False)
            self.assertEqual(result['cohort'],'2026-10')
            self.assertEqual(result['pilot_policy'],'none')
            self.assertEqual(len(result['segments']),8)
            self.assertTrue(all(not r['pilot'] for r in result['segments']))
            self.assertEqual([r['start_frame'] for r in result['segments'][:4]],[r['start_frame'] for r in plain['segments']])
            self.assertTrue(all(r['span_id']==r['session']+'_01' for r in result['segments']))
            for change in (dict(status='review-only'),dict(private_name='forbidden')):
                path.write_text(json.dumps({**spans,**change}))
                with self.assertRaises(ValueError):
                    plan(root,sessions=['20261016','20261023'],include_pilot=False,worker_spans=path)
            for field,value in (('start_wall',99.),('end_wall',3701.)):
                invalid=deepcopy(spans);invalid['spans'][0][field]=value;path.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(ValueError,'outside overlap'):
                    plan(root,sessions=['20261016','20261023'],include_pilot=False,worker_spans=path)

    def test_worker_spans_exclude_handover_and_use_maximum_overlap_then_nearest(self):
        from tools.workdata.workers import validate_worker_spans,assign_span
        rows=[dict(session='20261016',span_id='s1',start_wall=100.,end_wall=200.,worker_id='P1'),
              dict(session='20261016',span_id='s2',start_wall=300.,end_wall=500.,worker_id='P2')]
        document=dict(version=1,spans=rows,handover_intervals=[dict(session='20261016',start_wall=200.,end_wall=300.)])
        self.assertEqual(validate_worker_spans(document,{'20261016':(100.,500.)}),document)
        self.assertEqual(assign_span(rows,'20261016',180,350),'s2')
        self.assertEqual(assign_span(rows,'20261016',210,220),'s1')
        self.assertEqual(assign_span(rows,'20261016',280,290),'s2')
        self.assertEqual(assign_span(rows,'20261016',240,260),'s1')
        for change in (dict(start_wall=190.),dict(worker_id='person-name'),dict(end_wall=501.),dict(name='forbidden')):
            bad=deepcopy(document);bad['spans'][1].update(change)
            with self.assertRaises(ValueError):validate_worker_spans(bad,{'20261016':(100.,500.)})
        for change in (dict(start_wall=199.),dict(name='forbidden'),dict(session='person-name')):
            bad=deepcopy(document);bad['handover_intervals'][0].update(change)
            with self.assertRaises(ValueError):validate_worker_spans(bad,{'20261016':(100.,500.)})
        bad=deepcopy(document);bad['spans'][0]['start_wall']=99.
        with self.assertRaisesRegex(ValueError,'outside overlap'):validate_worker_spans(bad,{'20261016':(100.,500.)})
        with self.assertRaisesRegex(ValueError,'No worker spans'):
            assign_span(rows,'20261023',100,150)

    def test_uncertain_segment_is_redrawn_within_same_stratum_and_audited(self):
        session=dict(session='short',grid=dict(t0=100.,N=9000,step_hz=5.,step=.2),
                     cameras={},time_map_version=3,time_map_sha256='a'*64,sync_uncertain=[False]*9000)
        session['sync_uncertain'][250]=True
        class Draws:
            values=iter([100,500,5000])
            def randint(self,a,b):return next(self.values)
        rows=sample_session(session,[False]*9000,Draws())
        self.assertEqual(rows[0]['start_frame'],500)
        self.assertEqual(rows[0]['attempts'][0]['sync_uncertain_steps'],1)
        self.assertEqual(rows[0]['attempts'][1]['sync_uncertain_steps'],0)
        self.assertEqual(rows[0]['stratum']['index'],0)

    def test_session_seeds_ignore_other_sessions_redraws_and_exclude_pilot(self):
        dates=['20260821','20260911']
        def read(path):
            date=path.parent.name
            session=dict(session=date,grid=dict(t0=PILOT_TIME-100 if date=='20260911' else PILOT_TIME-90000,N=18000,step_hz=5.,step=.2),
                         cameras={c:dict(path='fake',sha256='a'*64) for c in ('cam_a','cam_b','cam_e')},
                         time_map_version=1,time_map_sha256='a'*64)
            return session,[False]*18000
        with tempfile.TemporaryDirectory() as tmp, patch('tools.validation.sample_segments.read_session',side_effect=read) as reader:
            root=Path(tmp)
            for date in dates+['20261016']:
                (root/date).mkdir();(root/date/'session.json').touch()
            first=plan(root,sessions=dates)
            def extra_draw(session,gaps,rng,*args):
                if session['session']=='20260821':rng.random()
                return sample_session(session,gaps,rng,*args)
            with patch('tools.validation.sample_segments.sample_session',side_effect=extra_draw):
                second=plan(root,sessions=dates)
            self.assertEqual(first['sessions'],dates)
            self.assertFalse(any(call.args[0].parent.name=='20261016' for call in reader.call_args_list))
            self.assertEqual([r for r in first['segments'] if r['session']=='20260911'],
                             [r for r in second['segments'] if r['session']=='20260911'])
            pilot=first['segments'][0]
            for row in first['segments'][1:]:
                if row['session']==pilot['session']:
                    self.assertFalse(row['start_frame']<pilot['end_frame_exclusive'] and pilot['start_frame']<row['end_frame_exclusive'])
        class Draws:
            values=iter([100,500,5000])
            def randint(self,a,b):return next(self.values)
        session,_=read(Path('20260911/session.json'));session['grid']['N']=9000
        rows=sample_session(session,[False]*9000,Draws(),excluded=[(100,400)])
        self.assertEqual(rows[0]['start_frame'],500)
        self.assertTrue(rows[0]['attempts'][0]['pilot_overlap'])

    def test_seeded_strata_cover_whole_session_without_content_selection(self):
        session=dict(session='test',grid=dict(t0=100.,N=18000,step_hz=5.,step=.2),
                     cameras={},time_map_version=1,time_map_sha256='a'*64)
        first=sample_session(session,[False]*18000,random.Random(20261015),4,60)
        second=sample_session(session,[False]*18000,random.Random(20261015),4,60)
        self.assertEqual(first,second)
        self.assertEqual(len(first),4)
        for index,row in enumerate(first):
            self.assertGreaterEqual(row['start_frame'],index*4500)
            self.assertLessEqual(row['end_frame_exclusive'],(index+1)*4500)
            self.assertEqual(row['step_count'],300)

    def test_short_session_has_two_strata_and_gap_redraws_are_recorded(self):
        session=dict(session='short',grid=dict(t0=100.,N=9000,step_hz=5.,step=.2),
                     cameras={},time_map_version=1,time_map_sha256='a'*64)
        class Draws:
            def __init__(self):self.values=iter([100,500,5000])
            def randint(self,a,b):return next(self.values)
        gaps=[False]*9000
        gaps[100:115]=[True]*15
        result=sample_session(session,gaps,Draws(),4,60)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['start_frame'],500)
        self.assertEqual(len(result[0]['attempts']),2)
        self.assertEqual(result[0]['attempts'][0]['gap_seconds'],3.)
        with self.assertRaisesRegex(ValueError,'redraw'):
            sample_session(session,[True]*9000,random.Random(1),4,60)

    def test_manifest_rejects_duplicate_ids_and_bad_grid_alignment(self):
        row=dict(segment_id='test_s01',session='test',start_wall_time=100.,step_hz=5.,step_count=300,
                 start_frame=0,end_frame_exclusive=300,proxy_t0=100.,pilot=False,
                 proxies={c:dict(path='fake.mp4',sha256='a'*64) for c in ('cam_a','cam_b','cam_e')},time_map_version=1)
        manifest=dict(version=2,seed=1,method='stratified-uniform-grid',segments=[row])
        validate_manifest(manifest)
        with self.assertRaises(ValueError):validate_manifest(dict(manifest,segments=[row,row]))
        row['start_wall_time']=100.1
        with self.assertRaises(ValueError):validate_manifest(manifest)

    def test_dataset_requires_completed_roi_and_preserves_overwritten_dataset(self):
        row=dict(segment_id='s',session='s',start_wall_time=100.,step_hz=5.,step_count=300,
                 start_frame=0,end_frame_exclusive=300,proxy_t0=100.,pilot=False,
                 proxies={c:dict(path='fake.mp4',sha256='a'*64) for c in ('cam_a','cam_b','cam_e')},time_map_version=1)
        manifest=dict(version=2,seed=1,method='stratified-uniform-grid',segments=[row])
        with tempfile.TemporaryDirectory() as directory, patch('tools.validation.sample_segments.plan',side_effect=lambda *args:deepcopy(manifest)):
            base=Path(directory);regions=base/'roi_regions.json';dataset=base/'dataset'
            payload=document()
            payload['regions'].append(dict(payload['regions'][0],key='work_cell',kind='cell',color='#9b59b6'))
            roi_regions.save(regions,payload)
            with self.assertRaisesRegex(ValueError,'completed'):
                create_dataset(base/'proxies',dataset,regions_path=regions)
            first=create_dataset(base/'proxies',dataset)
            self.assertEqual(first['annotation_schema_version'],3)
            self.assertEqual(first['classes_source'],'default-trial')
            self.assertIsNone(first['regions_sha256'])
            (dataset/'labels.json').write_text('preserved user labels')
            exported=base/'custom';exported.mkdir()
            (exported/'roi_reference.png').write_bytes(b'synthetic reference')
            (exported/'classes.json').write_text(json.dumps(roi_regions.make_classes(payload)))
            roi_regions.mark_complete(regions,out_root=exported)
            with self.assertRaises(FileExistsError):create_dataset(base/'proxies',dataset,regions_path=regions)
            second=create_dataset(base/'proxies',dataset,regions_path=regions,overwrite=True)
            self.assertEqual(second['annotation_schema_version'],3)
            self.assertEqual(second['classes_source'],'completed-regions')
            self.assertEqual((Path(second['previous_dataset_backup'])/'labels.json').read_text(),'preserved user labels')
            self.assertEqual(json.loads((dataset/'classes.json').read_text(encoding='utf-8'))['classes'][0]['label'],'desk')
            self.assertEqual((dataset/'roi_reference.png').read_bytes(),b'synthetic reference')
            for name in ('roi_reference.png','classes.json'):
                file=exported/name;original=file.read_bytes();file.write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError,'matching hashes'):
                    create_dataset(base/'proxies',base/'hash-mismatch',regions_path=regions)
                self.assertFalse((base/'hash-mismatch').exists())
                file.write_bytes(original)
            payload['regions'][0]['name_zh']='Changed'
            roi_regions.save(regions,payload)
            with self.assertRaises(ValueError):create_dataset(base/'proxies',base/'different',regions_path=regions)
