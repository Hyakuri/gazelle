import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageFont
from tools.validation import roi_regions as regions
from tools.validation.extract_roi_candidates import extract_candidates, validate_candidates
from tools.validation.roi_server import RoiApplication, make_handler


def document():
    return dict(version=1, camera='cam_e', reference=dict(session='session', source='video.mp4',
                container_time_ms=10, image_sha256='a' * 64, width=1920, height=1080),
                regions=[dict(key='desk', name_zh='Desk', kind='target', color='#11aa33',
                              polygon=[[0.1, 0.1], [0.9, 0.1], [0.5, 0.8]])],
                annotator='test', created_at='2026-10-16T00:00:00+00:00', updated_at='2026-10-16T00:00:00+00:00')


class RoiRegionsTest(unittest.TestCase):
    def test_http_boundary_without_opening_a_port(self):
        app = Mock()
        handler = object.__new__(make_handler(app))
        handler.server = Mock(server_port=8765)
        handler._send = Mock()
        handler.path = '/api/state'
        handler.headers = {'Host': 'attacker.example:8765'}
        handler.do_GET()
        self.assertEqual(handler._send.call_args.args[0], 403)
        app.state.assert_not_called()
        handler.path = '/api/save'
        handler.headers = {'Host': '127.0.0.1:8765', 'Origin': 'https://attacker.example'}
        handler.do_POST()
        self.assertEqual(handler._send.call_args.args[0], 403)
        app.update.assert_not_called()
        handler.headers = {'Host': '127.0.0.1:8765', 'Content-Type': 'application/json',
                           'Content-Length': '2', 'X-Editor-Token': 'token'}
        handler.rfile = io.BytesIO(b'{}')
        app.update.return_value = {'saved': True}
        handler.do_POST()
        app.update.assert_called_once_with({}, 'token')
        self.assertEqual(handler._send.call_args.args[0], 200)

    def test_valid_schema_and_class_order(self):
        doc = document()
        self.assertEqual(regions.validate(doc), doc)
        classes = regions.make_classes(doc)['classes']
        self.assertEqual([row['label'] for row in classes], ['desk', 'cell_other', 'away', 'absent', 'unknown'])
        self.assertEqual([row['key'] for row in classes], [1, 2, 3, 4, 0])

    def test_invalid_polygon_and_region_boundaries(self):
        for polygon in ([[0, 0], [1, 1]], [[0, 0], [2, 0], [0, 1]],
                        [[0, 0], [1, 1], [0, 1], [1, 0]], [[0, 0], [0.5, 0], [1, 0]],
                        [[0, 0], [float('nan'), 0], [0, 1]], [[0, 0], [True, 0], [0, 1]]):
            doc = document()
            doc['regions'][0]['polygon'] = polygon
            with self.subTest(polygon=polygon), self.assertRaises(ValueError):
                regions.validate(doc)
        doc = document()
        doc['regions'] *= 2
        with self.assertRaisesRegex(ValueError, 'unique'):
            regions.validate(doc)
        doc = document()
        doc['regions'][0]['kind'] = 'cell'
        doc['regions'].append({**doc['regions'][0], 'key': 'other'})
        with self.assertRaisesRegex(ValueError, 'cell'):
            regions.validate(doc)
        for key in ('unknown', 'cell_other', 'not valid'):
            doc = document()
            doc['regions'][0]['key'] = key
            with self.assertRaises(ValueError):
                regions.validate(doc)

    def test_normalization_roundtrip(self):
        self.assertEqual(regions.normalize_point(100, 50, 200, 100), [0.5, 0.5])
        self.assertEqual(regions.pixel_point([0.5, 0.5], 200, 100), (100, 50))

    def test_atomic_save_backup_resume_and_invalid_preservation(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trial.json'
            first = document()
            regions.save(path, first)
            second = copy.deepcopy(first)
            second['regions'][0]['name_zh'] = 'Updated'
            regions.save(path, second)
            self.assertEqual(regions.load(path), second)
            self.assertEqual(regions.load(path.with_suffix('.json.bak')), first)
            second['regions'][0]['polygon'] = []
            with self.assertRaises(ValueError):
                regions.save(path, second)
            self.assertEqual(regions.load(path)['regions'][0]['name_zh'], 'Updated')

    def test_candidate_extraction_and_application_without_ports(self):
        class FakeSource:
            duration = 120
            def __init__(self, path):
                pass
            def read_at(self, seconds):
                return Image.new('RGB', (4, 4), 'white'), seconds * 1000
            def close(self):
                pass
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps(dict(root=str(root / 'raw'), files=[
                dict(session='session', physical_camera='cam_e', needs_remux=True, relative_path='session/e.avi')
            ])), encoding='utf-8')
            (root / 'remux/session').mkdir(parents=True)
            (root / 'remux/session/e.mp4').touch()
            manifest = extract_candidates(inventory, root / 'remux', root / 'roi', source_factory=FakeSource)
            self.assertEqual(len(manifest['candidates']), 12)
            self.assertEqual([row['container_time_ms'] for row in manifest['candidates']], list(range(5000, 120000, 10000)))
            candidate_file = root / 'roi/candidates.json'
            validate_candidates(candidate_file)
            path = root / 'roi/trial.json'
            app = RoiApplication(candidate_file, path, 'tester')
            self.assertFalse(path.exists())
            state = app.state()
            self.assertEqual(len(state['candidates']), 12)
            first = manifest['candidates'][0]
            self.assertTrue(app.image(first['id']).startswith(b'\xff\xd8'))
            with self.assertRaises(ValueError):
                app.image('../secret')
            payload = dict(reference_id=first['id'], regions=document()['regions'], draft=dict(points=[], region=None))
            with self.assertRaises(PermissionError):
                app.update(payload, 'wrong-token')
            app.update(payload, app.token)
            self.assertEqual(regions.load(path)['annotator'], 'tester')
            resumed = RoiApplication(candidate_file, path, 'tester').state()
            self.assertEqual(resumed['document']['regions'], document()['regions'])
            with patch('tools.validation.render_roi_reference.find_font', return_value=ImageFont.load_default()):
                self.assertEqual(app.export(app.token)['images'], 2)
            self.assertTrue((root / 'roi/trial_export/roi_reference.png').is_file())
            with Image.open(root / 'roi/trial_export/roi_reference.png') as image:
                self.assertNotEqual(image.getpixel((960, 324)), (255, 255, 255))
            self.assertTrue((root / 'roi/trial_export/classes.json').is_file())
            self.assertFalse((root / 'roi/roi_regions.json').exists())
            html = app.page().decode('utf-8')
            self.assertNotIn('https://', html)
            self.assertIn('/api/save', html)
            previous = candidate_file.read_bytes()
            class InvalidTimeSource(FakeSource):
                def read_at(self, seconds):
                    return Image.new('RGB', (4, 4)), -1
            with self.assertRaisesRegex(ValueError, 'timestamp'):
                extract_candidates(inventory, root / 'remux', root / 'roi', source_factory=InvalidTimeSource)
            self.assertEqual(candidate_file.read_bytes(), previous)
