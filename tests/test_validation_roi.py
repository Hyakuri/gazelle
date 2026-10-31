import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageFont
from tools.workdata.common import hash_file
from tools.validation import roi_regions as regions
from tools.validation.extract_roi_candidates import extract_candidates, validate_candidates
from tools.validation.roi_server import RoiApplication, make_handler
from tools.validation.render_roi_reference import draw_regions


def document():
    return dict(version=1, camera='cam_e', reference=dict(session='session', source='video.mp4',
                container_time_ms=10, image_sha256='a' * 64, width=1920, height=1080),
                regions=[dict(key='desk', name_zh='Desk', kind='target', color='#11aa33',
                              polygon=[[0.1, 0.1], [0.9, 0.1], [0.5, 0.8]])],
                annotator='test', created_at='2026-10-16T00:00:00+00:00', updated_at='2026-10-16T00:00:00+00:00')


class RoiRegionsTest(unittest.TestCase):
    def test_overlapping_cell_does_not_erase_target_outlines(self):
        rows = [dict(key='target', name_zh='Target', kind='target', color='#e67e22',
                     polygon=[[.2, .2], [.6, .2], [.6, .6], [.2, .6]]),
                dict(key='cell', name_zh='Cell', kind='cell', color='#9b59b6',
                     polygon=[[.05, .05], [.95, .05], [.95, .95], [.05, .95]])]
        with Image.new('RGB', (400, 400), 'white') as base:
            for order in (rows, list(reversed(rows))):
                with draw_regions(base, order, ImageFont.load_default()) as rendered:
                    self.assertEqual(rendered.getpixel((80, 180)), (230, 126, 34))
                    self.assertEqual(rendered.getpixel((20, 180)), (155, 89, 182))

    def test_class_keys_and_colors_are_bounded(self):
        doc = document()
        doc['regions'] = []
        with self.assertRaises(ValueError):
            regions.make_classes(doc)
        palette = ['#010101', '#020202', '#030303', '#040404', '#050505', '#060606', '#070707']
        doc['regions'] = [{**document()['regions'][0], 'key': 'desk' + str(i), 'color': color}
                          for i, color in enumerate(palette)]
        with self.assertRaises(ValueError):
            regions.make_classes(doc)
        doc['regions'].pop()
        with self.assertRaises(ValueError):
            regions.make_classes(doc)
        doc['regions'].pop()
        self.assertEqual([r['key'] for r in regions.make_classes(doc)['classes']], list(range(1, 10)) + [0])
        for color in ('#c0392b', '#9B59B6', '#010101'):
            doc['regions'][1]['color'] = color
            with self.subTest(color=color), self.assertRaises(ValueError):
                regions.validate(doc)

    def test_completion_is_tied_to_valid_exported_file(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trial.json'
            doc = document()
            regions.save(path, doc)
            self.assertIsNone(regions.completed_document(path))
            with self.assertRaises(ValueError):
                regions.mark_complete(path)
            cell = {**doc['regions'][0], 'key': 'work_cell', 'kind': 'cell', 'color': '#9b59b6'}
            doc['regions'].append(cell)
            regions.save(path, doc)
            exported=Path(tmp)/'custom-export';exported.mkdir()
            (exported/'roi_reference.png').write_bytes(b'fake reference')
            (exported/'classes.json').write_text(json.dumps(regions.make_classes(doc)))
            regions.mark_complete(path,out_root=exported)
            self.assertEqual(regions.completed_document(path), doc)
            marker = json.loads(regions.completion_path(path).read_text(encoding='utf-8'))
            self.assertIn('completed_at', marker)
            self.assertEqual(len(marker['regions_sha256']), 64)
            self.assertEqual(marker['export_root'],str(exported.resolve()))
            (exported/'roi_reference.png').write_bytes(b'changed')
            self.assertIsNone(regions.completed_document(path))
            (exported/'roi_reference.png').write_bytes(b'fake reference')
            original=(exported/'classes.json').read_bytes()
            (exported/'classes.json').write_bytes(b'changed')
            self.assertIsNone(regions.completed_document(path))
            (exported/'classes.json').write_bytes(original)
            path.with_suffix('.draft.json').write_text('{"points": [[0, 0]], "region": null}', encoding='utf-8')
            self.assertIsNone(regions.completed_document(path))
            path.with_suffix('.draft.json').write_text('{"points": [], "region": null}', encoding='utf-8')
            self.assertEqual(regions.completed_document(path), doc)
            doc['regions'][0]['name_zh'] = 'Changed'
            regions.save(path, doc)
            self.assertIsNone(regions.completed_document(path))

    def test_identical_saves_do_not_rotate_backups(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trial.json'
            doc = document()
            regions.save(path, doc)
            doc['regions'][0]['name_zh'] = 'Updated'
            regions.save(path, doc)
            previous = path.with_suffix('.json.bak').read_bytes()
            regions.save(path, doc)
            self.assertEqual(path.with_suffix('.json.bak').read_bytes(), previous)

    def test_overflow_and_touching_polygon_edges_are_rejected_cleanly(self):
        doc = document()
        doc['regions'][0]['polygon'][0][0] = 10 ** 1000
        with self.assertRaises(ValueError):
            regions.validate(doc)
        for polygon in ([[0, 0], [1, 0], [.5, 0], [.5, 1]],
                        [[0, 0], [1, 0], [1, 1], [.5, 0], [0, 1]]):
            with self.subTest(polygon=polygon), self.assertRaises(ValueError):
                regions.validate_polygon(polygon)

    def test_http_boundary_without_opening_a_port(self):
        app = Mock(token='token')
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

    def test_http_rejects_bad_token_before_body_and_bounds_json(self):
        app = Mock(token='token')
        handler = object.__new__(make_handler(app))
        handler.server = Mock(server_port=8765)
        handler._send = Mock()
        handler.path = '/api/save'
        handler.headers = {'Host': '127.0.0.1:8765', 'Content-Type': 'application/json',
                           'Content-Length': '2', 'X-Editor-Token': 'wrong'}
        handler.rfile = Mock()
        handler.do_POST()
        self.assertEqual(handler._send.call_args.args[0], 403)
        handler.rfile.read.assert_not_called()
        for length, content, body in [('1048577', 'application/json', b'{}'),
                                      ('2', 'text/plain', b'{}'),
                                      ('4000', 'application/json', b'[' * 2000 + b']' * 2000)]:
            handler.headers.update({'X-Editor-Token': 'token', 'Content-Length': length,
                                    'Content-Type': content})
            handler.rfile = io.BytesIO(body)
            handler.do_POST()
            self.assertEqual(handler._send.call_args.args[0], 400)
        app.update.assert_not_called()

    def test_valid_schema_and_class_order(self):
        doc = document()
        self.assertEqual(regions.validate(doc), doc)
        classes = regions.make_classes(doc)['classes']
        self.assertEqual([row['label'] for row in classes], ['desk', 'hands_object', 'cell_other', 'away', 'absent', 'unknown'])
        self.assertEqual([row['key'] for row in classes], [1, 2, 3, 4, 5, 0])
        self.assertEqual(classes[0]['color'], '#11aa33')
        self.assertTrue(all(row['color'].startswith('#') for row in classes))

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
            frame_interval_ms = 50
            def __init__(self, path):
                pass
            def read_at(self, seconds):
                return Image.new('RGB', (4, 4), 'white'), seconds * 1000
            def close(self):
                pass
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / 'inventory.json'
            original=root/'raw/session/e.avi';original.parent.mkdir(parents=True);original.write_bytes(b'original')
            inventory.write_text(json.dumps(dict(root=str(root / 'raw'), files=[
                dict(session='session', physical_camera='cam_e', needs_remux=True, relative_path='session/e.avi',
                     size_bytes=original.stat().st_size,sha256=hash_file(original))
            ])), encoding='utf-8')
            (root / 'remux/session').mkdir(parents=True)
            (root / 'remux/session/e.mp4').touch()
            with self.assertRaisesRegex(ValueError, 'validated'):
                extract_candidates(inventory, root / 'remux', root / 'roi', source_factory=FakeSource)
            (root / 'remux/remux_report.json').write_text(json.dumps(dict(version=1, files=[dict(
                input=str(root / 'previous-root/session/e.avi'), output=str(root / 'remux/session/e.mp4'),
                input_size_bytes=original.stat().st_size,output_size_bytes=0, status='completed', validation=dict(valid=True))])), encoding='utf-8')
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
            self.assertIsNone(regions.completed_document(path))
            with self.assertRaises(ValueError):
                app.export(app.token)
            payload['regions'].append({**document()['regions'][0], 'key': 'work_cell',
                                       'kind': 'cell', 'color': '#9b59b6'})
            app.update(payload, app.token)
            backup = path.with_suffix('.json.bak').read_bytes()
            original = path.read_bytes()
            app.update(payload, app.token)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.with_suffix('.json.bak').read_bytes(), backup)
            for draft in ({'points': [], 'region': {'key': 'bad'}},
                          {'points': [], 'region': None, 'extra': 'unexpected'},
                          {'points': [[.2, .2]], 'region': None}):
                with self.subTest(draft=draft), self.assertRaises(ValueError):
                    app.update({**payload, 'draft': draft}, app.token)
            with patch('tools.validation.render_roi_reference.find_font', side_effect=ValueError('font missing')):
                with self.assertRaises(ValueError):
                    app.export(app.token)
            self.assertIsNone(regions.completed_document(path))
            with patch('tools.validation.render_roi_reference.find_font', return_value=ImageFont.load_default()):
                self.assertEqual(app.export(app.token)['images'], 2)
            self.assertIsNotNone(regions.completed_document(path))
            self.assertTrue((root / 'roi/trial_export/roi_reference.png').is_file())
            with Image.open(root / 'roi/trial_export/roi_reference.png') as image:
                self.assertNotEqual(image.getpixel((960, 324)), (255, 255, 255))
            self.assertTrue((root / 'roi/trial_export/classes.json').is_file())
            payload['regions'][0]['unexpected']='discard me'
            saved=app.update(payload,app.token)
            self.assertNotIn('unexpected',saved['regions'][0])
            self.assertTrue(saved['complete'],'no-op save retains server export completion')
            self.assertTrue(saved['has_export'])
            payload['regions'][0]['polygon']=[[.1,.1],[.11,.1],[.1,.11]]
            app.update(payload,app.token)
            warning=app.export(app.token)
            self.assertTrue(warning['confirmation_required'])
            self.assertEqual(warning['small_regions'][0]['key'],'desk')
            with patch('tools.validation.render_roi_reference.find_font',return_value=ImageFont.load_default()):
                self.assertEqual(app.export(app.token,confirm_small=True)['images'],2)
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
            class StaleTimeSource(FakeSource):
                def read_at(self, seconds):
                    return Image.new('RGB', (4, 4)), 0
            class DistantTimeSource(FakeSource):
                def read_at(self, seconds):
                    return Image.new('RGB', (4, 4)), (seconds + 5) * 1000
            for factory in (StaleTimeSource, DistantTimeSource):
                with self.assertRaisesRegex(ValueError, 'timestamp'):
                    extract_candidates(inventory, root / 'remux', root / 'roi', source_factory=factory)
                self.assertEqual(candidate_file.read_bytes(), previous)
            extract_candidates(inventory, root / 'remux', root / 'roi', source_factory=FakeSource)
            self.assertEqual(candidate_file.with_suffix('.json.bak').read_bytes(), previous)
