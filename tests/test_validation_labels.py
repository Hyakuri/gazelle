from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO

from tools.validation.labels import expand_runs, validate_document, LabelStore


def fixture():
    manifest=dict(version=2,segments=[dict(segment_id='s1',session='session',start_wall_time=100.,step_hz=5.,step_count=5)])
    classes=dict(version=1,classes=[dict(key=1,label='target',name_zh='Target',color='#112233'),
                                   dict(key=0,label='unknown',name_zh='Unknown',color='#cccccc')])
    return manifest,classes


class LabelTest(unittest.TestCase):
    def test_finish_only_counts_previously_saved_viewing_but_preserves_new_ranges(self):
        manifest,classes=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,data in [('manifest.json',manifest),('classes.json',classes)]:
                (root/name).write_text(json.dumps(data))
            store=LabelStore(root,root/'trial.json','reviewer')
            payload=dict(segment_id='s1',revision=0,labels=[dict(start_step=0,end_step_exclusive=5,label='target')],
                         viewed_ranges=[],other_people=[],note='')
            store.update(payload)
            payload.update(revision=1,viewed_ranges=[dict(start_step=0,end_step_exclusive=5)],finish=True)
            with self.assertRaisesRegex(ValueError,'previously saved'):
                store.update(payload)
            persisted=LabelStore(root,root/'trial.json','reviewer').document()
            self.assertEqual(persisted['segments'][0]['viewed_ranges'],payload['viewed_ranges'])
            self.assertIsNone(persisted['segments'][0]['finished_at'])
            payload['revision']=persisted['revision']
            self.assertIsNotNone(store.update(payload)['segments'][0]['finished_at'])

    def test_cli_segment_errors_are_one_line_and_viewed_errors_use_their_own_name(self):
        from tools.validation.labels import main,viewed_steps
        with self.assertRaisesRegex(ValueError,'viewed_ranges'):
            viewed_steps([dict(start_step=0,end_step_exclusive=6)],5)
        manifest,classes=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,data in [('manifest.json',manifest),('classes.json',classes)]:
                (root/name).write_text(json.dumps(data))
            store=LabelStore(root,root/'trial.json','reviewer')
            store.update(dict(segment_id='s1',revision=0,labels=[dict(start_step=0,end_step_exclusive=5,label='target')],
                              viewed_ranges=[],other_people=[],note=''))
            output=StringIO()
            with redirect_stderr(output):
                status=main(['validate','--dataset-root',str(root),'--labels-path',str(root/'trial.json'),'--segment','s1'])
            self.assertEqual(status,1)
            self.assertEqual(len(output.getvalue().splitlines()),1)
            self.assertIn('s1',output.getvalue())
            self.assertIn('not been completed',output.getvalue())
            self.assertNotIn('Traceback',output.getvalue())

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
            self.assertIsNone(result['segments'][0]['finished_at'])
            with self.assertRaises(ValueError):validate_document(result,manifest,classes)
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

    def test_viewed_ranges_explicit_finish_and_selected_strict_validation(self):
        manifest,classes=fixture()
        manifest['segments'].append(dict(manifest['segments'][0],segment_id='s2'))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,data in [('manifest.json',manifest),('classes.json',classes)]:
                (root/name).write_text(json.dumps(data))
            store=LabelStore(root,root/'trial.json','reviewer')
            payload=dict(segment_id='s1',revision=0,labels=[dict(start_step=0,end_step_exclusive=5,label='target')],
                         viewed_ranges=[dict(start_step=0,end_step_exclusive=1)],other_people=[],note='')
            first=store.update(payload)
            self.assertEqual(first['version'],2)
            self.assertIsNone(first['segments'][0]['finished_at'])
            self.assertEqual(store.resume(),('s1',1))
            payload['revision']=1
            with self.assertRaises(ValueError):store.update(dict(payload,finish=True))
            for ranges in ([],[dict(start_step=0,end_step_exclusive=6)],
                           [dict(start_step=0,end_step_exclusive=2),dict(start_step=1,end_step_exclusive=3)]):
                with self.assertRaises(ValueError):store.update(dict(payload,viewed_ranges=ranges))
            payload['viewed_ranges']=[dict(start_step=0,end_step_exclusive=5)]
            store.update(payload)
            self.assertEqual(store.resume(),('s1',0))
            payload.update(revision=2,finish=True)
            done=store.update(payload)
            self.assertIsNotNone(done['segments'][0]['finished_at'])
            validate_document(done,manifest,classes,segments=['s1'])
            with self.assertRaises(ValueError):validate_document(done,manifest,classes)
            with self.assertRaises(ValueError):validate_document(done,manifest,classes,segments=['missing'])
            self.assertEqual(store.resume(),('s2',0))
            payload.update(revision=3,finish=False,other_people=[dict(start_step=1,end_step_exclusive=2)])
            changed=store.update(payload)
            self.assertIsNone(changed['segments'][0]['finished_at'])
            payload.update(revision=4,finish=True)
            store.update(payload)
            payload.update(revision=5,finish=False,labels=[dict(start_step=0,end_step_exclusive=5,label='unknown')])
            self.assertIsNone(store.update(payload)['segments'][0]['finished_at'])
            legacy=deepcopy(first);legacy['version']=1
            with self.assertRaisesRegex(ValueError,'version 1.*reannotate'):
                validate_document(legacy,manifest,classes,allow_incomplete=True)

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
