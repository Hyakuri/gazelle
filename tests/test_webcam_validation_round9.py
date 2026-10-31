"""Exercise optional-camera isolation through the complete validation caller."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from av.error import InvalidDataError
import cv2
import numpy as np
from PIL import Image

from tools.workdata import sync_validate as validation
from tools.workdata.common import hash_file
from tools.workdata.proxies import ROLES


class Capture:
    event_failure=None
    def __init__(self,path):self.k=0;self.path=path;self.seeking=False
    def set(self,key,k):self.k=k;self.seeking=True;return True
    def read(self):
        if self.seeking and 'webcam.mp4' in self.path and self.event_failure:
            raise self.event_failure
        self.k+=1
        return (True,np.zeros((54,96,3),np.uint8)) if self.k<=40 else (False,None)
    def get(self,key):return self.k if key==cv2.CAP_PROP_POS_FRAMES else (self.k-1)*200.
    def release(self):pass


def proxy_fixture(root):
    folder=root/'proxies/20261016';folder.mkdir(parents=True)
    raw=root/'raw';raw.mkdir();files=[];cameras={};entries=[]
    grid=dict(t0=0.,step=.2,N=40,step_hz=5.)
    for camera,role in {**ROLES,'cam_w':'webcam'}.items():
        source=raw/(camera+'.mp4');source.write_bytes(b'source')
        video=folder/(role+'.mp4');video.write_bytes(b'proxy')
        digest=hash_file(video)
        sidecar=folder/(role+'.json');sidecar.write_text(json.dumps(dict(video_sha256=digest,
            frames=[dict(k=k,t_k=k*.2,source=camera+'.mp4',pts=k*.2,delta_seconds=0.,gap=False) for k in range(40)])))
        cameras[camera]=dict(video=video.name,frames=sidecar.name,sha256=digest,available=True)
        files.append(dict(camera=camera,source=source.name,media_path=str(source),fingerprint=dict(
            source_sha256='a'*64,media_size=6,media_mtime_ns=source.stat().st_mtime_ns)))
        entries.append(dict(relative_path=source.name,sha256='a'*64,size_bytes=6))
    webcam=cameras.pop('cam_w')
    session=dict(session='20261016',grid=grid,N=40,cameras=cameras,time_map_version=3,
                 auxiliary_cameras={'cam_w':webcam})
    (folder/'session.json').write_text(json.dumps(session))
    mapping=dict(version=3,calibrated=True,files=files,calibration={})
    (root/'20261016.json').write_text(json.dumps(mapping))
    (root/'clock.json').write_text(json.dumps(dict(sessions=[dict(session='20261016',indices=[])])))
    raw.rename(root/'moved')
    return dict(root=str(root/'moved'),files=entries)


class WebcamValidationTest(unittest.TestCase):
    def test_run_preserves_abe_for_w_residual_decode_and_event_failures(self):
        for failure in (None,'residual','decode','metadata','event','thumbnail'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);inventory=proxy_fixture(root)
                def keys(files,*args):
                    for row in files:self.assertTrue(Path(row['media_path']).is_file())
                    return {r['source']:[.2] for r in files}
                pairs={name:dict(passed=True,conclusion='passed',reason='passed',windows=[])
                       for name in ('A-B','E-B','A-E','W-B')}
                if failure=='residual':pairs['W-B'].update(passed=False,conclusion='failed',reason='median_absolute_seconds > 0.1')
                real_webcam=validation.webcam_evidence
                def webcam(*args):
                    if failure=='decode':raise InvalidDataError(1,'W decode')
                    if failure=='metadata':raise KeyError('W field')
                    cells,thumbs,audit=real_webcam(*args)
                    self.assertTrue(np.isnan(cells[0]).all(),'source keyframe mask reaches W motion')
                    if failure=='thumbnail':thumbs=np.ones_like(thumbs)
                    return cells,thumbs,audit
                Capture.event_failure=ValueError('W event seek') if failure=='event' else None
                with patch.object(validation,'source_keyframes',side_effect=keys), \
                     patch.object(validation,'scan_keyframes',return_value={'pts':[]}), \
                     patch.object(validation.cv2,'VideoCapture',side_effect=Capture), \
                     patch.object(validation,'residual_pairs',side_effect=lambda signals,duration:
                         {name:value for name,value in pairs.items() if name!='W-B' or 'cam_w' in signals}), \
                     patch.object(validation,'event_indices',return_value=[8,18,28]), \
                     patch.object(validation,'clock_summary',return_value=dict(passed=True)), \
                     patch.object(validation,'webcam_evidence',side_effect=webcam):
                    result=validation.run(root/'proxies',root/'out','20261016',root/'clock.json',root,root/'keys',inventory)
                self.assertTrue(result['passed'])
                self.assertTrue((root/'out/20261016.json').is_file())
                self.assertEqual(result['auxiliary_cameras']['cam_w']['available'],failure is None)
                if failure is not None:self.assertNotEqual(result['auxiliary_cameras']['cam_w']['reason'],'failed')
                expected_rows=3 if failure in ('decode','metadata','event','thumbnail') else 4
                for event in result['events']:
                    with Image.open(event['path']) as image:self.assertEqual(image.height,expected_rows*180+36)
                Capture.event_failure=None

    def test_failed_w_summary_names_the_unsatisfied_conditions(self):
        rows=[dict(valid=True,reason='valid',t_mid_seconds=30.+i*60,lag_seconds=.3+i*.03) for i in range(15)]
        result=validation.residual_summary(rows,900.)
        self.assertFalse(result['passed'])
        for name in ('fraction_within_0_2','median_absolute_seconds','c0_at_midpoint','c1_seconds_per_hour'):
            self.assertIn(name,result['reason'])


if __name__=='__main__':unittest.main()
