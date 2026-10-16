import random
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validation.sample_segments import create_dataset, sample_session, validate_manifest
from tools.validation import roi_regions
from tests.test_validation_roi import document


class SamplingTest(unittest.TestCase):
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
            first=create_dataset(base/'proxies',dataset,regions_path=regions)
            self.assertEqual(first['classes_source'],'default-trial')
            self.assertIsNone(first['regions_sha256'])
            (dataset/'labels.json').write_text('preserved user labels')
            roi_regions.mark_complete(regions)
            (base/'roi_reference.png').write_bytes(b'synthetic reference')
            with self.assertRaises(FileExistsError):create_dataset(base/'proxies',dataset,regions_path=regions)
            second=create_dataset(base/'proxies',dataset,regions_path=regions,overwrite=True)
            self.assertEqual(second['classes_source'],'completed-regions')
            self.assertEqual((Path(second['previous_dataset_backup'])/'labels.json').read_text(),'preserved user labels')
            self.assertEqual(json.loads((dataset/'classes.json').read_text(encoding='utf-8'))['classes'][0]['label'],'desk')
            self.assertEqual((dataset/'roi_reference.png').read_bytes(),b'synthetic reference')
            payload['regions'][0]['name_zh']='Changed'
            roi_regions.save(regions,payload)
            third=create_dataset(base/'proxies',base/'different',regions_path=regions)
            self.assertEqual(third['classes_source'],'default-trial')
