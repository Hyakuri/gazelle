import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from tools.workdata import inventory, remux
from tools.workdata.common import packet_summary
from tools.workdata import common


class WorkdataToolsTest(unittest.TestCase):
    def test_webcam_names_are_strict_and_do_not_accept_unknown_variants(self):
        roles=inventory.load_roles()
        self.assertEqual(inventory.identify('20261016','WIN_20261014_12_05_36_Pro.mp4',roles),
                         ('cam_w','filename_clock',None))
        for name in ('WIN_bad_Pro.mp4','WIN_20260230_12_05_36_Pro.mp4',
                     'WIN_20261014_25_05_36_Pro.mp4','other_20261014_12_05_36_Pro.mp4'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                inventory.identify('20261016',name,roles)

    def test_selected_inventory_preserves_old_rows_across_root_relocation(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/'new';(root/'20261016').mkdir(parents=True)
            (root/'20261030').mkdir()
            (root/'20261016/WIN_20261014_12_05_36_Pro.mp4').write_bytes(b'webcam')
            (root/'20261030/unknown.mp4').write_bytes(b'not selected')
            output=Path(tmp)/'inventory.json'
            old=dict(session='20260821',relative_path='20260821/old.avi',private_marker='unchanged')
            output.write_text(json.dumps(dict(root=str(Path(tmp)/'old'),files=[old])))
            with patch.object(inventory,'probe_metadata',return_value=dict(duration=100,has_audio=True)),patch.object(
                    inventory,'probe_packets',return_value=dict(count=10,small_count=0)):
                result=inventory.create_inventory(root,output,sessions=['20261016'])
            self.assertEqual(result['files'][0],old)
            self.assertEqual(result['root'],str(root.resolve()))
            self.assertEqual(len(result['files']),2)
            self.assertTrue(result['files'][1]['video']['has_audio'])
            self.assertFalse(result['files'][1]['needs_remux'])

    def test_selected_remux_preserves_old_report_rows(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/'raw';(root/'20261016').mkdir(parents=True)
            source=root/'20261016/new.avi';source.write_bytes(b'source')
            out=Path(tmp)/'remux';out.mkdir()
            old=dict(input='/old/20260821/old.avi',output='/old/out.mp4',status='completed',marker=[1,2])
            common.atomic_json(out/'remux_report.json',dict(version=1,files=[old]))
            inv=Path(tmp)/'inventory.json'
            common.atomic_json(inv,dict(root=str(root),files=[
                dict(session='20260821',relative_path='20260821/old.avi',needs_remux=True),
                dict(session='20261016',relative_path='20261016/new.avi',needs_remux=True)]))
            def fake_remux(source,target,*args):
                return dict(input=str(source),output=str(target),status='completed')
            with patch.object(remux,'remux_one',side_effect=fake_remux) as run:
                result=remux.run_inventory(inv,out,sessions=['20261016'])
            self.assertEqual(run.call_count,1)
            self.assertEqual(len(result),1)
            rows=json.loads((out/'remux_report.json').read_text())['files']
            self.assertEqual(rows[0],old)
            self.assertEqual(len(rows),2)

    def test_remux_provenance_survives_relocation_but_rejects_mismatches(self):
        from tools.workdata.video_source import media_path
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/'relocated';(root/'20261016').mkdir(parents=True)
            original=root/'20261016/e.avi';original.write_bytes(b'source')
            out=Path(tmp)/'remux';(out/'20261016').mkdir(parents=True)
            target=out/'20261016/e.mp4';target.write_bytes(b'video')
            entry=dict(needs_remux=True,relative_path='20261016/e.avi',size_bytes=6,sha256=common.hash_file(original))
            report=dict(input=str(Path(tmp)/'old/20261016/e.avi'),output=str(target),input_size_bytes=6,
                        output_size_bytes=5,status='completed',validation=dict(valid=True))
            common.atomic_json(out/'remux_report.json',dict(files=[report]))
            self.assertEqual(media_path(entry,dict(root=str(root)),out),target.resolve())
            for update in (dict(input_size_bytes=7),dict(input=str(Path(tmp)/'old/20261023/e.avi'))):
                common.atomic_json(out/'remux_report.json',dict(files=[{**report,**update}]))
                with self.assertRaisesRegex(ValueError,'provenance'):
                    media_path(entry,dict(root=str(root)),out)
            common.atomic_json(out/'remux_report.json',dict(files=[report]))
            original.write_bytes(b'tamper')
            with self.assertRaisesRegex(ValueError,'checksum'):
                media_path(entry,dict(root=str(root)),out)

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
        self.assertEqual(value['last_pts'], .2)
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
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
            with patch.object(inventory, 'hash_file', wraps=common.hash_file) as hashed:
                third = inventory.fingerprint(path, second)
            hashed.assert_called_once_with(path)
            self.assertEqual(second['sha256'], third['sha256'])
            self.assertEqual(second['size_bytes'], third['size_bytes'])
            self.assertNotEqual(second['mtime_ns'], third['mtime_ns'])

    def test_remux_command_copies_only_video(self):
        self.assertEqual(remux.build_command('ffmpeg-custom', Path('in.avi'), Path('tmp.mp4')), [
            'ffmpeg-custom', '-nostdin', '-v', 'error', '-n', '-fflags', '+genpts', '-i', 'in.avi',
            '-map', '0:v:0', '-c:v', 'copy', '-bsf:v', r'noise=drop=lt(size\,64)', 'tmp.mp4'])

    def test_validation_rejects_packet_duration_pts_and_decode_failures(self):
        source = {'count': 100, 'small_count': 40}
        target = {'count': 60, 'small_count': 0, 'pts_strict': True, 'last_pts': 99.95}
        decoded = dict(windows=[30, 30, 59], tail_eof=True, last_timestamp_ms=99950, frame_interval_ms=50)
        with patch.object(remux, 'probe_metadata', return_value={'duration': 100, 'r_frame_rate': '30/1'}), patch.object(
            remux, 'probe_packets', return_value=target
        ), patch.object(remux, 'check_decode', return_value=decoded):
            good = remux.validate_output(Path('fake.mp4'), source, 100, 'ffprobe')
            self.assertTrue(good['valid'])
            for bad in ({**target, 'count': 59}, {**target, 'pts_strict': False}):
                with patch.object(remux, 'probe_packets', return_value=bad):
                    self.assertFalse(remux.validate_output(Path('fake.mp4'), source, 100, 'ffprobe')['valid'])

            self.assertFalse(remux.validate_output(Path('fake.mp4'), source, 99, 'ffprobe')['valid'])
            for changes in (dict(windows=[30, 30, 29]), dict(tail_eof=False),
                            dict(last_timestamp_ms=98000), dict(last_timestamp_ms=99910)):
                with patch.object(remux, 'check_decode', return_value={**decoded, **changes}):
                    self.assertFalse(remux.validate_output(Path('fake.mp4'), source, 100, 'ffprobe')['valid'])

    def test_tail_pts_removes_stream_start_time(self):
        for start in (.033,.25):
            with self.subTest(start=start), patch.object(remux,'probe_metadata',return_value=dict(duration=100,r_frame_rate='30/1',start_time=str(start))), patch.object(remux,'probe_packets',return_value=dict(count=100,pts_strict=True,last_pts=99.95+start)), patch.object(remux,'check_decode',return_value=dict(windows=[30,30,60],tail_eof=True,last_timestamp_ms=99950,frame_interval_ms=1000/30)):
                result=remux.validate_output(Path('fake'),dict(count=100,small_count=0),100,'ffprobe')
                self.assertTrue(result['valid'])
                self.assertAlmostEqual(result['decode_details']['tail_pts_delta_ms'],0)

    def test_missing_or_none_start_time_is_explicitly_assumed_zero(self):
        for extra in ({},{'start_time':None}):
            with self.subTest(extra=extra), patch.object(remux,'probe_metadata',return_value=dict(duration=100,r_frame_rate='30/1',**extra)), patch.object(remux,'probe_packets',return_value=dict(count=100,pts_strict=True,last_pts=99.95)), patch.object(remux,'check_decode',return_value=dict(windows=[30,30,60],tail_eof=True,last_timestamp_ms=99950,frame_interval_ms=1000/30)):
                result=remux.validate_output(Path('fake'),dict(count=100,small_count=0),100,'ffprobe')
                self.assertTrue(result['valid'])
                self.assertTrue(result['decode_details']['start_time_assumed_zero'])
                self.assertEqual(result['decode_details']['start_time'],0.)

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

    def test_first_minute_small_avi_packet_requires_remux(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / 'raw'
            session = root / '20260903'
            session.mkdir(parents=True)
            (session / (inventory.load_roles()['filename_patterns']['overview'] + '.avi')).write_bytes(b'input')
            with patch.object(inventory, 'probe_metadata', return_value={'duration': 100}), patch.object(
                inventory, 'probe_packets', return_value={'count': 100, 'small_count': 1, 'small_fraction': .01}
            ) as probe:
                row = inventory.create_inventory(root, Path(tmp) / 'inventory.json')['files'][0]
            self.assertTrue(row['needs_remux'])
            self.assertEqual(probe.call_args.kwargs, {'seconds': 60})

    def test_tail_check_reaches_eof_and_rejects_missing_last_thirty_frames(self):
        import cv2
        from tests.test_media import FakeCapture
        class SeekCapture(FakeCapture):
            def set(self, prop, start):
                self.index = start  # VFR seek starts one frame late.
                return True
        for readable, valid in ((200, True), (170, False), (400, False)):
            capture = SeekCapture(fps=20, frame_count=200, readable_count=readable)
            with patch.object(cv2, 'VideoCapture', return_value=capture), patch.object(
                remux, 'probe_metadata', return_value=dict(duration=10, r_frame_rate='20/1')
            ), patch.object(remux, 'probe_packets', return_value=dict(count=200, small_count=0, pts_strict=True, last_pts=9.95)):
                result = remux.validate_output('fake.mp4', dict(count=200, small_count=0), 10, 'ffprobe')
            self.assertEqual(result['valid'], valid)
            self.assertEqual(capture.release_calls, 1)
            if valid:
                self.assertEqual(result['decoded'], [30, 30, 59])
                self.assertTrue(result['decode_details']['tail_eof'])
            elif readable == 170:
                self.assertFalse(result['checks']['tail_pts'])
            else:
                self.assertFalse(result['checks']['decode'])


if __name__ == '__main__':
    unittest.main()
