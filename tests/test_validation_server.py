import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from tools.validation.annotate_server import AnnotationApplication, make_handler
from tools.workdata.common import hash_file
from tests.test_validation_labels import fixture


class AnnotationServerTest(unittest.TestCase):
    def test_host_origin_and_token_reject_before_body_parsing(self):
        app=object.__new__(AnnotationApplication);app.token='token'
        app.dispatch=Mock()
        handler=object.__new__(make_handler(app))
        handler.server=Mock(server_port=8766);handler.path='/api/save';handler.send=Mock()
        valid={'Host':'127.0.0.1:8766','Origin':'http://127.0.0.1:8766','Content-Type':'application/json',
               'Content-Length':'2','X-Editor-Token':'token'}
        for changes in ({'Host':'evil.invalid:8766'},{'Origin':'http://evil.invalid'},{'X-Editor-Token':'wrong'}):
            handler.headers={**valid,**changes};handler.rfile=Mock()
            handler.do_POST()
            self.assertEqual(handler.send.call_args.args[0],403)
            handler.rfile.read.assert_not_called()
        for changes in ({'Host':'evil.invalid'},{'Origin':'null'}):
            handler.headers={**valid,**changes};handler.do_GET()
            self.assertEqual(handler.send.call_args.args[0],403)
        app.dispatch.assert_not_called()
        handler.headers=valid;handler.rfile=io.BytesIO(b'[]');handler.do_POST()
        self.assertEqual(handler.send.call_args.args[0],400)

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
                reference=root/'webcam/s1'/(str(step).zfill(4)+'.jpg')
                reference.parent.mkdir(parents=True,exist_ok=True);reference.write_bytes(b'webcam image')
                row['frames'][-1]['webcam']=dict(path=reference.relative_to(root).as_posix(),sha256=hash_file(reference),
                                               gap=False,sync_uncertain=step==2)
            row['auxiliary_proxies']={'cam_w':dict(path='w.mp4',sha256='a'*64)}
            (root/'manifest.json').write_text(json.dumps(manifest))
            path=root/'trial.json'
            app=AnnotationApplication(root,path,'reviewer')
            status,data,kind=app.dispatch('GET','/api/state')
            self.assertEqual(status,200)
            state=json.loads(data)
            self.assertEqual(state['resume'],['s1',0])
            self.assertFalse(path.exists())
            self.assertTrue(state['segments'][0]['has_webcam'])
            self.assertEqual(state['segments'][0]['webcam_uncertain_steps'],[2])
            self.assertEqual(app.dispatch('GET','/webcam/s1/2')[1],b'webcam image')
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
