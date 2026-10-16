from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.validation.labels import expand_runs, validate_document, LabelStore


def fixture():
    manifest=dict(version=2,segments=[dict(segment_id='s1',session='session',start_wall_time=100.,step_hz=5.,step_count=5)])
    classes=dict(version=1,classes=[dict(key=1,label='target',name_zh='Target',color='#112233'),
                                   dict(key=0,label='unknown',name_zh='Unknown',color='#cccccc')])
    return manifest,classes


class LabelTest(unittest.TestCase):
    def test_expand_requires_exact_nonoverlapping_coverage(self):
        rows=[dict(start_step=0,end_step_exclusive=2,label='target'),
              dict(start_step=2,end_step_exclusive=5,label='unknown')]
        self.assertEqual(expand_runs(rows,5,{'target','unknown'}),['target']*2+['unknown']*3)
        for bad in (rows[:-1],[dict(rows[0],end_step_exclusive=3),rows[1]],
                    [dict(start_step=0,end_step_exclusive=5,label='invalid')]):
            with self.assertRaises(ValueError):expand_runs(bad,5,{'target','unknown'})
        with self.assertRaises(ValueError):expand_runs([dict(start_step=0,end_step_exclusive=5,label=None)],5,{'unknown'})

    def test_atomic_backup_resume_and_immutable_manifest_metadata(self):
        manifest,classes=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,data in [('manifest.json',manifest),('classes.json',classes)]:
                (root/name).write_text(json.dumps(data),encoding='utf-8')
            path=root/'trial.json'
            store=LabelStore(root,path,'reviewer')
            self.assertFalse(path.exists())
            initial=store.document()
            self.assertEqual(store.resume(),('s1',0))
            payload=dict(segment_id='s1',revision=0,labels=[dict(start_step=0,end_step_exclusive=5,label='target')],
                         other_people=[],note='',active_seconds_delta=3.)
            result=store.update(payload)
            self.assertIsNotNone(result['segments'][0]['finished_at'])
            validate_document(result,manifest,classes)
            with self.assertRaisesRegex(ValueError,'revision'):store.update(payload)
            payload.update(revision=1,labels=[dict(start_step=0,end_step_exclusive=5,label=None)])
            store.update(payload)
            self.assertTrue(path.with_suffix('.json.bak').exists())
            resumed=LabelStore(root,path,'reviewer')
            self.assertEqual(resumed.resume(),('s1',0))
            self.assertIsNone(resumed.document()['segments'][0]['finished_at'])
            with self.assertRaises(ValueError):validate_document(resumed.document(),manifest,classes)
            changed=deepcopy(resumed.document());changed['segments'][0]['step_count']=6
            with self.assertRaises(ValueError):validate_document(changed,manifest,classes,allow_incomplete=True)
            path.write_text(path.read_text(encoding='utf-8')+'\n',encoding='utf-8')
            payload['revision']=2
            with self.assertRaisesRegex(ValueError,'outside this editor'):resumed.update(payload)

    def test_other_people_ranges_and_class_config_are_checked(self):
        manifest,classes=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'manifest.json').write_text(json.dumps(manifest))
            (root/'classes.json').write_text(json.dumps(classes))
            store=LabelStore(root,root/'labels.json','test')
            row=store.document()
            row['segments'][0]['other_people']=[dict(start_step=1,end_step_exclusive=4),dict(start_step=3,end_step_exclusive=5)]
            with self.assertRaises(ValueError):validate_document(row,manifest,classes,allow_incomplete=True)
