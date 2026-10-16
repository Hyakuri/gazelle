import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from tools.workdata import inventory, remux
from tools.workdata.common import packet_summary
from tools.workdata import common


class WorkdataToolsTest(unittest.TestCase):
    def test_roles_and_override_and_parts(self):
        roles = inventory.load_roles()
        for session in ('20260821', '20260903', '20261009'):
            for number in (1, 2):
                name = '{}{}-2.mp4'.format(session, roles['filename_patterns'][str(number)])
                camera, source, part = inventory.identify(session, name, roles)
                expected = 'cam_{}'.format('ab'[number - 1] if session != '20260903' else 'ba'[number - 1])
                self.assertEqual((camera, source, part), (expected, 'override' if session == '20260903' else 'filename', 2))
        self.assertEqual(inventory.identify('20260821', roles['filename_patterns']['overview'] + '.avi', roles), ('cam_e', 'filename', None))
        with self.assertRaises(ValueError):
            inventory.identify('20260821', 'unknown.mp4', roles)

    def test_packet_summary_counts_and_strict_pts(self):
        value = packet_summary(iter(['size=0|pts_time=0', 'pts_time=0.1|size=63', 'size=64|pts_time=0.2']))
        self.assertEqual(value['count'], 3)
        self.assertEqual(value['small_count'], 2)
        self.assertAlmostEqual(value['small_fraction'], 2 / 3)
        self.assertTrue(value['pts_strict'])
        for values in (['size=64|pts_time=1', 'size=70|pts_time=1'], ['size=64|pts_time=N/A'], []):
            self.assertFalse(packet_summary(iter(values))['pts_strict'])

    def test_hash_cache_uses_size_mtime_and_invalidates(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.avi'
            path.write_bytes(b'old')
            first = inventory.fingerprint(path)
            with patch('tools.workdata.inventory.hash_file', side_effect=AssertionError('cache missed')):
                self.assertEqual(inventory.fingerprint(path, first), first)
            path.write_bytes(b'longer')
            second = inventory.fingerprint(path, first)
            self.assertNotEqual(first['sha256'], second['sha256'])

    def test_remux_command_copies_only_video(self):
        self.assertEqual(remux.build_command('ffmpeg-custom', Path('in.avi'), Path('tmp.mp4')), [
            'ffmpeg-custom', '-nostdin', '-v', 'error', '-n', '-fflags', '+genpts', '-i', 'in.avi',
            '-map', '0:v:0', '-c:v', 'copy', '-bsf:v', r'noise=drop=lt(size\,64)', 'tmp.mp4'])

    def test_validation_rejects_packet_duration_pts_and_decode_failures(self):
        source = {'count': 100, 'small_count': 40}
        target = {'count': 60, 'small_count': 0, 'pts_strict': True}
        with patch.object(remux, 'probe_metadata', return_value={'duration': 100}), patch.object(
            remux, 'probe_packets', return_value=target
        ), patch.object(remux, 'check_decode', return_value=[30, 30, 30]):
            good = remux.validate_output(Path('fake.mp4'), source, 100, 'ffprobe')
            self.assertTrue(good['valid'])
            for bad in ({**target, 'count': 59}, {**target, 'pts_strict': False}):
                with patch.object(remux, 'probe_packets', return_value=bad):
                    self.assertFalse(remux.validate_output(Path('fake.mp4'), source, 100, 'ffprobe')['valid'])
            self.assertFalse(remux.validate_output(Path('fake.mp4'), source, 99, 'ffprobe')['valid'])
            with patch.object(remux, 'check_decode', return_value=[30, 30, 29]):
                self.assertFalse(remux.validate_output(Path('fake.mp4'), source, 100, 'ffprobe')['valid'])

    def test_atomic_publication_and_failed_force_preserve_existing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src, out = root / 'in.avi', root / 'out.mp4'
            src.write_bytes(b'original')
            def run(command, **kwargs):
                Path(command[-1]).write_bytes(b'remuxed')
                return Mock(returncode=0, stderr='')
            with patch.object(remux, 'probe_packets', return_value={'count': 100, 'small_count': 40}), patch.object(
                remux, 'probe_metadata', return_value={'duration': 100}
            ), patch.object(remux.subprocess, 'run', side_effect=run), patch.object(
                remux, 'validate_output', return_value={'valid': False}
            ):
                result = remux.remux_one(src, out)
                self.assertEqual(result['status'], 'failed')
                self.assertFalse(out.exists())
                out.write_bytes(b'valid-old')
                self.assertEqual(remux.remux_one(src, out, force=True)['status'], 'failed')
                self.assertEqual(out.read_bytes(), b'valid-old')
                self.assertFalse(list(root.glob('.*.mp4')))
                with patch.object(remux, 'validate_output', return_value={'valid': True}):
                    self.assertEqual(remux.remux_one(src, out)['status'], 'skipped')
                    self.assertEqual(remux.remux_one(src, out, force=True)['status'], 'completed')
                    self.assertEqual(out.read_bytes(), b'remuxed')
            self.assertEqual(src.read_bytes(), b'original')

    def test_cli_overrides(self):
        args = inventory.build_parser().parse_args(['--root', 'raw', '--out', 'inventory.json', '--ffprobe', 'probe'])
        self.assertEqual(args.ffprobe, 'probe')
        args = remux.build_parser().parse_args(['--inventory', 'inventory.json', '--out-root', 'out', '--ffmpeg', 'mpeg', '--force'])
        self.assertTrue(args.force)
        self.assertEqual(args.ffmpeg, 'mpeg')

    def test_inventory_roundtrip_and_source_write_guard(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / 'raw'
            session = root / '20260903'
            session.mkdir(parents=True)
            name = inventory.load_roles()['filename_patterns']['1'] + '-2.mp4'
            (session / name).write_bytes(b'input')
            output = Path(tmp) / 'derived/inventory.json'
            with patch.object(inventory, 'probe_metadata', return_value={'duration': 100}), patch.object(
                inventory, 'probe_packets', return_value={'count': 10, 'small_count': 0, 'small_fraction': 0}
            ):
                rows = inventory.create_inventory(root, output)['files']
                self.assertEqual(rows[0]['physical_camera'], 'cam_b')
                self.assertEqual(rows[0]['camera_source'], 'override')
                self.assertFalse(rows[0]['needs_remux'])
                with patch.object(inventory, 'hash_file', side_effect=AssertionError('unexpected rehash')):
                    self.assertEqual(inventory.create_inventory(root, output)['files'], rows)
                with self.assertRaisesRegex(ValueError, 'outside'):
                    inventory.create_inventory(root, root / 'inventory.json')
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['files'], rows)
            with self.assertRaisesRegex(ValueError, 'escapes'):
                common.source_path(root, '../other.avi')

    def test_metadata_selects_first_video_and_detects_audio(self):
        payload = {'streams': [dict(codec_type='audio'), dict(codec_type='video', codec_name='hevc',
                   duration='100', width=3840, height=2160, start_time='0', nb_frames='3000',
                   r_frame_rate='30/1', avg_frame_rate='20/1')], 'format': {'duration': '101'}}
        with patch.object(common.subprocess, 'run', return_value=Mock(stdout=json.dumps(payload))) as run:
            result = common.probe_metadata('fake.avi', 'probe-custom')
        self.assertEqual(result['duration'], 100)
        self.assertEqual(result['codec_name'], 'hevc')
        self.assertTrue(result['has_audio'])
        self.assertEqual(run.call_args.args[0][0], 'probe-custom')

    def test_tail_check_uses_preroll_to_avoid_vfr_seek_rounding(self):
        import cv2
        capture = Mock()
        capture.get.return_value = 100
        capture.read.return_value = (True, object())
        with patch.object(cv2, 'VideoCapture', return_value=capture):
            self.assertEqual(remux.check_decode('fake.mp4'), [30, 30, 30])
        self.assertEqual([call.args[1] for call in capture.set.call_args_list], [0, 35, 40])
        self.assertEqual(capture.read.call_count, 120)
        capture.release.assert_called_once()


if __name__ == '__main__':
    unittest.main()
