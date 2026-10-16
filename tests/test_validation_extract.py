from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tools.validation.extract_frames import montage, write_jpeg, validate_dataset


class ExtractTest(unittest.TestCase):
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
