"""Generate CPU H.264 proxies on the common displayed-clock grid."""

import argparse
from fractions import Fraction
import heapq
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

import cv2

from .common import atomic_json, hash_file
from .sync_check import has_sampling_gap, nearest_frames
from .timemap import map_file_time
from .video_source import VideoSource


ROLES = {'cam_b': 'front', 'cam_a': 'right', 'cam_e': 'overview'}


def make_grid(overlap, hz=5., allow_internal_gaps=False):
    if not math.isfinite(hz) or hz <= 0 or not overlap or (len(overlap)!=1 and not allow_internal_gaps):
        raise ValueError('A positive frequency and one continuous common interval are required')
    if any(not math.isfinite(a) or not math.isfinite(b) or a>=b for a,b in overlap):
        raise ValueError('Invalid overlap interval')
    if any(b>=c for (_,b),(c,_) in zip(overlap,overlap[1:])):
        raise ValueError('Overlap intervals must be ordered and disjoint')
    start, end = overlap[0][0],overlap[-1][1]
    if not math.isfinite(start) or not math.isfinite(end) or end <= start:
        raise ValueError('Invalid overlap interval')
    first = math.ceil(start * hz - 1e-6)
    last = math.floor(end * hz + 1e-6)
    if last < first:
        raise ValueError('No common grid points')
    grid=dict(t0=first / hz, N=last-first+1, step=1/hz, step_hz=hz)
    if len(overlap)>1:
        grid.update(coverage_gaps=[dict(start=b,end=c,seconds=c-b) for (_,b),(c,_) in zip(overlap,overlap[1:])],
                    gap_policy='nearest_with_gap_flag_provisional')
    return grid


def encoder_command(ffmpeg, path, hz, size):
    rate = format(hz, '.12g')
    return [str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-video_size', '{}x{}'.format(*size),
            '-framerate', rate, '-i', 'pipe:0', '-an', '-c:v', 'libx264',
            '-threads', '2', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
            '-r', rate, '-fps_mode', 'cfr', '-movflags', '+faststart', str(path)]


def validate_sidecar(rows, grid):
    if len(rows) != grid['N']:
        raise ValueError('Sidecar frame count differs from grid')
    for k, row in enumerate(rows):
        if (row['k'] != k or not math.isfinite(row['t_k'])
                or abs(row['t_k']-(grid['t0']+k*grid['step'])) > 1e-6
                or not isinstance(row['source'], str) or not row['source']
                or not math.isfinite(row['pts']) or not math.isfinite(row['delta_seconds'])
                or type(row['gap']) is not bool
                or row['gap'] != has_sampling_gap(row['delta_seconds'],grid['step'],row['t_k'])):
            raise ValueError('Invalid sidecar row at index {}'.format(k))


def validate_video(path, grid, size, ffprobe='ffprobe'):
    result = subprocess.run([str(ffprobe), '-v', 'error', '-count_frames',
                             '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, text=True, encoding='utf-8', check=True)
    info = json.loads(result.stdout)
    streams = info['streams']
    videos = [s for s in streams if s.get('codec_type') == 'video']
    if len(videos) != 1 or len(streams) != 1:
        raise ValueError('Proxy must contain exactly one video stream and no audio')
    video = videos[0]
    count = int(video['nb_read_frames'])
    rate = float(Fraction(video['avg_frame_rate']))
    duration = float(video.get('duration', info['format']['duration']))
    if (count != grid['N'] or (video['width'],video['height']) != tuple(size)
            or video['codec_name'] != 'h264' or video['pix_fmt'] != 'yuv420p'
            or abs(rate-grid['step_hz']) > 1e-6
            or abs(duration-grid['N']*grid['step']) > 1e-3):
        raise ValueError('Proxy encoding, count, dimensions, rate or duration failed validation')
    return dict(valid=True, decoded_frames=count, width=size[0], height=size[1],
                codec=video['codec_name'], pix_fmt=video['pix_fmt'], fps=rate, duration=duration)


def publish_proxy(temporary, target, sidecar, payload, grid, size, ffprobe='ffprobe'):
    temporary, target, sidecar = Path(temporary), Path(target), Path(sidecar)
    pending = sidecar.with_name('.'+sidecar.name+'.pending')
    try:
        validation = validate_video(temporary,grid,size,ffprobe)
        payload = dict(payload, validation=validation, video_sha256=hash_file(temporary),
                       video_size_bytes=temporary.stat().st_size)
        atomic_json(pending,payload)
        temporary.replace(target)
        pending.replace(sidecar)
        return payload
    finally:
        temporary.unlink(missing_ok=True)
        pending.unlink(missing_ok=True)


def full_mapped_frames(files, counts, source_factory=VideoSource):
    """One live frame per source; the caller must drain to EOF for full counts."""
    def one(row):
        path=Path(row['media_path'])
        stat=path.stat()
        if (stat.st_size,stat.st_mtime_ns) != (row['fingerprint']['media_size'],row['fingerprint']['media_mtime_ns']):
            raise ValueError('Source changed since mapping: '+row['source'])
        capture=cv2.VideoCapture(str(path))
        try:
            declared=float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        finally:
            capture.release()
        declared=int(declared) if math.isfinite(declared) and declared>0 else None
        record=dict(source=row['source'],container_frame_count=declared,decoded_frames=0,
                    reached_eof=False,relative_difference=None,review_required=True)
        counts.append(record)
        previous=-float('inf')
        with source_factory(path) as source:
            for frame_index,(pts,frame) in enumerate(source.frames()):
                record['decoded_frames']+=1
                wall=map_file_time(row,pts,frame_index)
                if wall<previous:
                    raise ValueError('Backward clock breakpoint requires review: '+row['source'])
                previous=wall
                yield dict(source=row['source'],pts=pts,wall_time=wall,frame=frame)
        record['reached_eof']=True
        if declared:
            difference=abs(record['decoded_frames']-declared)/declared
            record.update(relative_difference=difference,review_required=difference>.005)
    streams=[one(row) for row in files]
    try:
        yield from heapq.merge(*streams,key=lambda row:row['wall_time'])
    finally:
        for stream in streams:
            stream.close()


def generate_camera(files, grid, size, target, sidecar, fingerprint, camera, ffmpeg, ffprobe):
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    descriptor,name=tempfile.mkstemp(prefix='.'+target.stem+'-',suffix='.mp4',dir=target.parent)
    os.close(descriptor)
    temporary=Path(name)
    counts=[]; rows=[]; started=time.monotonic()
    frames=full_mapped_frames(files,counts)
    times=(grid['t0']+k*grid['step'] for k in range(grid['N']))
    try:
        with tempfile.TemporaryFile() as errors:
            process=subprocess.Popen(encoder_command(ffmpeg,temporary,grid['step_hz'],size),
                                     stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors)
            try:
                for row in nearest_frames(frames,times,grid['step']):
                    pixels=row['frame'].reformat(width=size[0],height=size[1],format='bgr24').to_ndarray()
                    process.stdin.write(pixels.tobytes())
                    rows.append({key:row[key] for key in ('k','t_k','source','pts','delta_seconds','gap')})
                    if len(rows)%1500==0:
                        print('{} {}/{} proxy frames'.format(camera,len(rows),grid['N']),flush=True)
                process.stdin.close()
                if process.wait()!=0:
                    errors.seek(0)
                    raise RuntimeError('FFmpeg encoding failed: '+errors.read(8192).decode('utf-8',errors='replace'))
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                if not process.stdin.closed:
                    process.stdin.close()
                raise
        # nearest_frames stops at the final grid point; audit the remaining source frames too.
        for _ in frames:
            pass
        validate_sidecar(rows,grid)
        payload=dict(version=1,camera=camera,role=ROLES[camera],grid=grid,
                     fingerprint=fingerprint,frames=rows,source_decode=counts,
                     gap_count=sum(row['gap'] for row in rows),elapsed_seconds=time.monotonic()-started)
        return publish_proxy(temporary,target,sidecar,payload,grid,size,ffprobe)
    finally:
        frames.close()
        temporary.unlink(missing_ok=True)


def resume_camera(target,sidecar,fingerprint,grid,size,ffprobe):
    if not target.exists() or not sidecar.exists():
        return None
    try:
        payload=json.loads(sidecar.read_text(encoding='utf-8'))
        if payload['fingerprint']!=fingerprint or payload['video_sha256']!=hash_file(target):
            return None
        validate_sidecar(payload['frames'],grid)
        validate_video(target,grid,size,ffprobe)
        if not all(row['reached_eof'] for row in payload['source_decode']):
            return None
        return payload
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        return None


def run(path,out_root,hz=5.,size=(1920,1080),force=False,ffmpeg='ffmpeg',ffprobe='ffprobe',allow_internal_gaps=False):
    if len(size)!=2 or any(type(v) is not int or v<=0 or v%2 for v in size):
        raise ValueError('Positive even output dimensions are required')
    mapping=json.loads(Path(path).read_text(encoding='utf-8'))
    if mapping['version']>=2 and mapping.get('calibrated') is not True:
        raise ValueError('v2 proxies require successful content calibration for both cameras')
    if any(row['status']!='valid' for row in mapping['files']):
        raise ValueError('Every source requires a valid time map')
    grid=make_grid(mapping['overlap'],hz,allow_internal_gaps)
    root=Path(out_root)/mapping['session']
    root.mkdir(parents=True,exist_ok=True)
    repository=Path(__file__).resolve().parents[2]
    git=['git','-c','safe.directory='+repository.as_posix()]
    commit=subprocess.run(git+['rev-parse','HEAD'],cwd=repository,
                          capture_output=True,text=True,check=True).stdout.strip()
    dirty=bool(subprocess.run(git+['status','--porcelain','--','tools/workdata'],cwd=repository,
                              capture_output=True,text=True,check=True).stdout.strip())
    implementation=hashlib.sha256(b''.join((Path(__file__).parent/name).read_bytes() for name in
                                 ('proxies.py','sync_check.py','sync_calibrate.py','video_source.py','timemap.py'))).hexdigest()
    version=dict(timemap_sha256=hash_file(path),implementation_sha256=implementation,grid=grid,size=list(size))
    cameras={}; started=time.monotonic()
    for camera,role in ROLES.items():
        files=[row for row in mapping['files'] if row['camera']==camera]
        if not files:
            raise ValueError('Missing physical camera '+camera)
        # Check input provenance even when an output can be resumed.
        for row in files:
            stat=Path(row['media_path']).stat()
            if (stat.st_size,stat.st_mtime_ns)!=(row['fingerprint']['media_size'],row['fingerprint']['media_mtime_ns']):
                raise ValueError('Source changed since mapping: '+row['source'])
        target=root/('proxy_'+role+'.mp4'); sidecar=root/('proxy_'+role+'.frames.json')
        fingerprint=dict(version,camera=camera)
        payload=None if force else resume_camera(target,sidecar,fingerprint,grid,size,ffprobe)
        skipped=payload is not None
        if payload is None:
            if not force and (target.exists() or sidecar.exists()):
                raise FileExistsError('Existing proxy cannot be resumed; inspect it and use --force to rebuild: '+str(target))
            payload=generate_camera(files,grid,size,target,sidecar,fingerprint,camera,ffmpeg,ffprobe)
        cameras[camera]=dict(role=role,video=target.name,frames=sidecar.name,
                             sha256=payload['video_sha256'],size_bytes=payload['video_size_bytes'],
                             gap_count=payload['gap_count'],gap_fraction=payload['gap_count']/grid['N'],
                             source_decode=payload['source_decode'],elapsed_seconds=payload['elapsed_seconds'],
                             status='skipped-valid' if skipped else 'completed')
        print('{} {}: {} N={} gaps={}'.format(mapping['session'],camera,cameras[camera]['status'],grid['N'],payload['gap_count']),flush=True)
    result=dict(version=1,session=mapping['session'],grid=grid,t0=grid['t0'],N=grid['N'],
                cameras=cameras,time_map_version=mapping['version'],time_map_sha256=version['timemap_sha256'],
                code_commit_sha=commit,code_worktree_dirty=dirty,implementation_sha256=version['implementation_sha256'],
                elapsed_seconds=time.monotonic()-started)
    atomic_json(root/'session.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='Encode CPU H.264 clock-aligned proxies; no inference or network.')
    parser.add_argument('--timemaps',type=Path,required=True)
    parser.add_argument('--out-root',type=Path,required=True)
    parser.add_argument('--session')
    parser.add_argument('--step-hz',type=float,default=5.)
    parser.add_argument('--size',type=int,nargs=2,default=(1920,1080),metavar=('WIDTH','HEIGHT'))
    parser.add_argument('--ffmpeg',default='ffmpeg')
    parser.add_argument('--ffprobe',default='ffprobe')
    parser.add_argument('--force',action='store_true')
    parser.add_argument('--allow-internal-gaps',action='store_true',
                        help='Provisional policy: retain one regular grid across documented internal coverage gaps.')
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    paths=[args.timemaps/(args.session+'.json')] if args.session else sorted(args.timemaps.glob('*.json'))
    if not paths:
        parser.error('No time maps found')
    for path in paths:
        run(path,args.out_root,args.step_hz,tuple(args.size),args.force,args.ffmpeg,args.ffprobe,args.allow_internal_gaps)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
