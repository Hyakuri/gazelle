import json
from pathlib import Path
import tempfile
import unittest

from tools.validation.annotate_server import AnnotationApplication
from tools.workdata.common import hash_file
from tests.test_validation_labels import fixture


class AnnotationServerTest(unittest.TestCase):
    def test_request_logic_loads_segment_and_saves_without_opening_a_port(self):
        manifest,classes=fixture()
        row=manifest['segments'][0]
        row.update(start_frame=0,end_frame_exclusive=5,proxy_t0=100.,pilot=True,
                   proxies={c:dict(path='fake.mp4',sha256='a'*64) for c in ('cam_a','cam_b','cam_e')})
        manifest.update(seed=20261015,method='stratified-uniform-grid')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'classes.json').write_text(json.dumps(classes))
            manifest['classes_sha256']=hash_file(root/'classes.json')
            row['frames']=[]
            for step in range(5):
                relative='frames/s1/{:04d}.jpg'.format(step)
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fake image')
                row['frames'].append(dict(step=step,path=relative,sha256=hash_file(path)))
            (root/'manifest.json').write_text(json.dumps(manifest))
            path=root/'trial.json'
            app=AnnotationApplication(root,path,'reviewer')
            status,data,kind=app.dispatch('GET','/api/state')
            self.assertEqual(status,200)
            state=json.loads(data)
            self.assertEqual(state['resume'],['s1',0])
            self.assertFalse(path.exists())
            self.assertEqual(app.dispatch('GET','/frame/s1/0')[1],b'fake image')
            payload=dict(segment_id='s1',revision=0,labels=[dict(start_step=0,end_step_exclusive=5,label='unknown')],
                         other_people=[],note='',active_seconds_delta=1)
            with self.assertRaises(PermissionError):app.dispatch('POST','/api/save',payload,'bad')
            self.assertEqual(app.dispatch('POST','/api/save',payload,app.token)[0],200)
            self.assertTrue(path.exists())
            with self.assertRaises(ValueError):app.dispatch('GET','/frame/../0')
            with self.assertRaises(ValueError):app.dispatch('GET','/frame/s1/5')
            (root/'frames/s1/0000.jpg').write_bytes(b'changed')
            with self.assertRaises(ValueError):app.dispatch('GET','/frame/s1/0')
            self.assertEqual(app.dispatch('GET','/unknown')[0],404)

    def test_page_contains_inline_controls_without_remote_resources(self):
        text=Path('tools/validation/annotation_page.html').read_text(encoding='utf-8')
        for token in ('nextUnlabeled','otherStart','deleteChange','undo','0.5','timeline','keydown'):
            self.assertIn(token,text)
        for token in ('https://','http://','<script src=','<link '):
            self.assertNotIn(token,text)
