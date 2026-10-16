import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools.workdata.proxies import make_grid, encoder_command, validate_sidecar, publish_proxy, full_mapped_frames, validate_video, run


class ProxyTest(unittest.TestCase):
    def test_existing_unverified_output_requires_explicit_force(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.mp4';source.write_bytes(b'synthetic')
            stat=source.stat();output=root/'proxies'/'test';output.mkdir(parents=True)
            target=output/'proxy_front.mp4';target.write_bytes(b'preserve existing output')
            mapping=dict(session='test',overlap=[[0,1]],version=1,files=[dict(
                camera=camera,status='valid',source='source.mp4',media_path=str(source),
                fingerprint=dict(media_size=stat.st_size,media_mtime_ns=stat.st_mtime_ns))
                for camera in ('cam_a','cam_b','cam_e')])
            path=root/'map.json';path.write_text(json.dumps(mapping))
            with patch('tools.workdata.proxies.subprocess.run') as command, \
                    patch('tools.workdata.proxies.generate_camera') as generate:
                command.return_value.stdout='synthetic-commit'
                generate.side_effect=AssertionError('Existing output was regenerated without --force')
                with self.assertRaisesRegex(FileExistsError,'--force'):
                    run(path,root/'proxies')
                generate.assert_not_called()
            self.assertEqual(target.read_bytes(),b'preserve existing output')

    def test_grid_is_on_clock_multiples_and_inside_overlap(self):
        grid=make_grid([[100.03,101.01]],5)
        self.assertAlmostEqual(grid['t0'],100.2)
        self.assertEqual(grid['N'],5)
        self.assertAlmostEqual(grid['t0']+(grid['N']-1)*grid['step'],101.)
        with self.assertRaises(ValueError): make_grid([[1,2],[3,4]],5)
        provisional=make_grid([[1,2],[3,4]],5,allow_internal_gaps=True)
        self.assertEqual(provisional['N'],16)
        self.assertEqual(provisional['coverage_gaps'],[dict(start=2,end=3,seconds=1)])
        self.assertEqual(provisional['gap_policy'],'nearest_with_gap_flag_provisional')
        for hz in (0,-1,float('nan')):
            with self.assertRaises(ValueError):make_grid([[1,2]],hz)

    def test_encoder_is_cpu_cfr_no_audio_and_uses_requested_size(self):
        command=encoder_command('ffmpeg','temporary.mp4',5,(1920,1080))
        for token in ('libx264','20','yuv420p','-an','-framerate','5','1920x1080'):
            self.assertIn(token,command)
        self.assertNotIn('h264_nvenc',command)
        self.assertEqual(command[-1],'temporary.mp4')

    def test_sidecar_requires_complete_aligned_grid_and_gap_flags(self):
        grid=make_grid([[10,10.4]],5)
        rows=[dict(k=i,t_k=10+i*.2,source='one.mp4',pts=i*.2,
                   delta_seconds=0.,gap=False) for i in range(3)]
        validate_sidecar(rows,grid)
        with self.assertRaises(ValueError):validate_sidecar(rows[:-1],grid)
        rows[1]['gap']=True
        with self.assertRaises(ValueError):validate_sidecar(rows,grid)
        rows[1]['gap']=False
        rows[1]['t_k']=float('nan')
        with self.assertRaises(ValueError):validate_sidecar(rows,grid)
        epoch=1788307200.
        large_grid=dict(t0=epoch+.2,N=1,step=.2,step_hz=5.)
        validate_sidecar([dict(k=0,t_k=epoch+.2,source='epoch.mp4',pts=.1,
                              delta_seconds=(epoch+.1)-(epoch+.2),gap=False)],large_grid)

    def test_failed_validation_preserves_existing_output_and_removes_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            target=root/'proxy_front.mp4'
            target.write_bytes(b'old')
            temporary=root/'fresh.mp4'
            temporary.write_bytes(b'new')
            with patch('tools.workdata.proxies.validate_video',side_effect=ValueError('bad output')):
                with self.assertRaises(ValueError):
                    publish_proxy(temporary,target,root/'proxy_front.frames.json',{}, {},(1920,1080))
            self.assertEqual(target.read_bytes(),b'old')
            self.assertFalse(temporary.exists())

    def test_successful_publication_binds_sidecar_to_video_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            temporary=root/'fresh.mp4'
            temporary.write_bytes(b'new')
            target=root/'proxy_front.mp4'; sidecar=root/'proxy_front.frames.json'
            with patch('tools.workdata.proxies.validate_video',return_value={'valid':True}):
                publish_proxy(temporary,target,sidecar,{'frames':[]},{},(1920,1080))
            self.assertEqual(target.read_bytes(),b'new')
            self.assertEqual(len(json.loads(sidecar.read_text())['video_sha256']),64)

    def test_full_decode_counts_frames_outside_sampling_interval(self):
        class Source:
            def __init__(self,path):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def frames(self):
                for i in range(5):yield i*.2,object()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fake.mp4';path.write_bytes(b'not media')
            stat=path.stat()
            row=dict(source='fake.mp4',media_path=str(path),
                     fingerprint=dict(media_size=stat.st_size,media_mtime_ns=stat.st_mtime_ns),
                     segments=[dict(a=100,b=1,pts_start=0,pts_end=1)])
            capture=Mock();capture.get.return_value=6
            counts=[]
            with patch('tools.workdata.proxies.cv2.VideoCapture',return_value=capture):
                frames=list(full_mapped_frames([row],counts,Source))
            self.assertEqual(len(frames),5)
            self.assertTrue(counts[0]['reached_eof'])
            self.assertTrue(counts[0]['review_required'])
            self.assertAlmostEqual(counts[0]['relative_difference'],1/6)
            capture.release.assert_called_once()

    def test_video_validation_decodes_count_and_rejects_audio_and_wrong_rate(self):
        video=dict(codec_type='video',nb_read_frames='3',width=1920,height=1080,
                   codec_name='h264',pix_fmt='yuv420p',avg_frame_rate='5/1',duration='.6')
        data=dict(streams=[video],format=dict(duration='.6'))
        grid=make_grid([[10,10.4]],5)
        with patch('tools.workdata.proxies.subprocess.run') as run:
            run.return_value.stdout=json.dumps(data)
            self.assertTrue(validate_video('fake',grid,(1920,1080))['valid'])
            self.assertIn('-count_frames',run.call_args.args[0])
            video['avg_frame_rate']='25/1'
            run.return_value.stdout=json.dumps(data)
            with self.assertRaises(ValueError):validate_video('fake',grid,(1920,1080))
            video['avg_frame_rate']='5/1';data['streams'].append(dict(codec_type='audio'))
            run.return_value.stdout=json.dumps(data)
            with self.assertRaises(ValueError):validate_video('fake',grid,(1920,1080))
