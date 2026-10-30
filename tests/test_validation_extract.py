from pathlib import Path
import tempfile
import json
import unittest
from unittest.mock import patch

import numpy as np

from tools.validation.extract_frames import montage, write_jpeg, validate_dataset


class ExtractTest(unittest.TestCase):
    def test_webcam_reference_is_separate_360p_hashed_and_does_not_change_montage(self):
        from tools.validation.extract_frames import extract
        from tools.workdata.common import hash_file
        from tests.test_validation_labels import fixture
        class Capture:
            def __init__(self,*args):self.k=0
            def isOpened(self):return True
            def set(self,key,value):self.k=value;return True
            def get(self,key):return self.k
            def read(self):self.k+=1;return True,np.full((54,96,3),55,dtype=np.uint8)
            def release(self):pass
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,classes=fixture();row=manifest['segments'][0]
            video=root/'fake.mp4';video.write_bytes(b'fake')
            sidecar=root/'w.json';sidecar.write_text(json.dumps(dict(frames=[dict(gap=False,sync_uncertain=i==2) for i in range(5)])))
            proxy=dict(path=str(video),sha256=hash_file(video),sidecar_path=str(sidecar),sidecar_sha256=hash_file(sidecar))
            row.update(start_frame=0,end_frame_exclusive=5,proxy_t0=100.,pilot=False,
                proxies={c:proxy for c in ('cam_a','cam_b','cam_e')},auxiliary_proxies={'cam_w':proxy})
            manifest.update(seed=20261015,method='stratified-uniform-grid')
            (root/'classes.json').write_text(json.dumps(classes));manifest['classes_sha256']=hash_file(root/'classes.json')
            (root/'manifest.json').write_text(json.dumps(manifest))
            with patch('tools.validation.extract_frames.cv2.VideoCapture',side_effect=Capture):
                result=extract(root)
            self.assertTrue(result['valid'])
            saved=json.loads((root/'manifest.json').read_text())['segments'][0]['frames']
            self.assertEqual(saved[2]['webcam']['path'],'webcam/s1/0002.jpg')
            self.assertTrue(saved[2]['webcam']['sync_uncertain'])
            self.assertFalse((root/'labels.json').exists())
            (root/saved[0]['webcam']['path']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Webcam JPEG changed'):validate_dataset(root)

    def test_montage_keeps_physical_roles_in_required_positions(self):
        images={'cam_b':np.full((60,100,3),(255,0,0),dtype='uint8'),
                'cam_a':np.full((60,100,3),(0,255,0),dtype='uint8'),
                'cam_e':np.full((60,100,3),(0,0,255),dtype='uint8')}
        result=montage(images)
        self.assertEqual(result.shape,(720,1920,3))
        self.assertEqual(result[200,300].tolist(),[255,0,0])
        self.assertEqual(result[550,300].tolist(),[0,255,0])
        self.assertEqual(result[400,1500].tolist(),[0,0,255])

    def test_jpeg_write_is_atomic_and_uses_quality_85(self):
        image=np.zeros((720,1920,3),dtype='uint8')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'frame.jpg'
            digest=write_jpeg(path,image)
            self.assertEqual(len(digest),64)
            self.assertTrue(path.exists())
            self.assertEqual(list(Path(directory).iterdir()),[path])
            with patch('tools.validation.extract_frames.cv2.imencode',return_value=(False,None)):
                with self.assertRaises(ValueError):write_jpeg(path,image)
            from tools.workdata.common import hash_file
            self.assertEqual(hash_file(path),digest)
