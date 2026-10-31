"""Optional webcam and worker contracts using temporary annotation fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validation import sample_segments as sampling
from tools.workdata.common import hash_file
from tools.workdata.proxies import ROLES


class ValidationRound9Test(unittest.TestCase):
    def test_plan_keeps_reference_and_assigns_interval_overlap_not_start_point(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'20261016';folder.mkdir();(folder/'session.json').touch()
            proxy=dict(path='fake',sha256='a'*64)
            session=dict(session='20261016',grid=dict(t0=0.,N=10001,step=.2,step_hz=5.),
                overlap=[[0.,2000.]],cameras={c:proxy for c in ROLES},time_map_version=3,time_map_sha256='b'*64,
                webcam_reference=dict(proxy,role='webcam'))
            workers=dict(version=1,spans=[dict(session='20261016',span_id='first',worker_id='P1',start_wall=0.,end_wall=100.),
                dict(session='20261016',span_id='second',worker_id='P2',start_wall=120.,end_wall=2000.)])
            path=root/'workers.json';path.write_text(json.dumps(workers))
            def sample(session,*args):return [sampling._segment(session,450,300,'segment')]
            with patch.object(sampling,'read_session',return_value=(session,[False]*10001)), \
                 patch.object(sampling,'sample_session',side_effect=sample):
                result=sampling.plan(root,sessions=['20261016'],include_pilot=False,worker_spans=path)
                row=result['segments'][0]
                self.assertEqual(row['span_id'],'second')
                self.assertEqual(row['auxiliary_proxies']['cam_w'],session['webcam_reference'])
                session.pop('webcam_reference');session['webcam_unavailable']='W validation index record is missing'
                absent=sampling.plan(root,sessions=['20261016'],include_pilot=False)
            self.assertNotIn('auxiliary_proxies',absent['segments'][0])
            self.assertEqual(absent['webcam_unavailable'],{'20261016':'W validation index record is missing'})

    def test_unavailable_webcam_is_not_read_and_reason_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);grid=dict(t0=0.,N=3,step=.2,step_hz=5.);cameras={}
            for camera,role in ROLES.items():
                video=root/(role+'.mp4');video.write_bytes(b'fake');sidecar=root/(role+'.json')
                sidecar.write_text(json.dumps(dict(camera=camera,role=role,grid=grid,video_sha256=hash_file(video),
                    frames=[dict(k=k,t_k=k*.2,source=camera,pts=k*.2,delta_seconds=0.,gap=False) for k in range(3)])))
                cameras[camera]=dict(role=role,video=video.name,frames=sidecar.name,sha256=hash_file(video))
            path=root/'session.json';path.write_text(json.dumps(dict(version=1,session='20261016',grid=grid,cameras=cameras,
                auxiliary_cameras={'cam_w':dict(available=False,reason='failed W fit')})))
            with patch.object(sampling,'read_webcam_reference',side_effect=AssertionError('unavailable W must not be read')):
                session,_=sampling.read_session(path)
            self.assertNotIn('webcam_reference',session)
            self.assertEqual(session['webcam_unavailable'],'failed W fit')

    def test_manifest_rejects_wrong_reference_path_and_partial_reference_frames(self):
        proxy=dict(path='fake',sha256='a'*64)
        session=dict(session='20261016',grid=dict(t0=0.,N=20,step=.2,step_hz=5.),cameras={c:proxy for c in ROLES},
                     time_map_version=3,time_map_sha256='b'*64,webcam_reference=proxy)
        row=sampling._segment(session,0,2,'segment')
        row['frames']=[dict(step=k,path=f'frames/segment/{k:04d}.jpg',sha256='a'*64,
                           webcam=dict(path=f'webcam/segment/{k:04d}.jpg',sha256='a'*64,gap=False,sync_uncertain=False))
                       for k in range(2)]
        manifest=dict(version=2,seed=1,method='stratified-uniform-grid',segments=[row])
        sampling.validate_manifest(manifest)
        bad=deepcopy(manifest);bad['segments'][0]['frames'][0]['webcam']['path']='webcam/other/0000.jpg'
        with self.assertRaisesRegex(ValueError,'reference schema'):sampling.validate_manifest(bad)
        bad=deepcopy(manifest);bad['segments'][0]['frames'][1].pop('webcam')
        with self.assertRaisesRegex(ValueError,'Missing or unexpected'):sampling.validate_manifest(bad)
        bad=deepcopy(manifest);bad['segments'][0].pop('auxiliary_proxies')
        with self.assertRaisesRegex(ValueError,'Missing or unexpected'):sampling.validate_manifest(bad)


if __name__=='__main__':unittest.main()
