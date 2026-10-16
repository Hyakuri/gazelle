import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name, suffix='.tmp', delete=False) as handle:
            name = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        name.replace(path)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def outside_source(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if path == root or root in path.parents:
        raise ValueError('Output must be outside the read-only source root: {}'.format(path))
    return path


def source_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError('Source path escapes inventory root: {}'.format(relative))
    return path


def probe_metadata(path, ffprobe='ffprobe'):
    result = subprocess.run([ffprobe, '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', check=True)
    payload = json.loads(result.stdout)
    videos = [stream for stream in payload.get('streams', []) if stream.get('codec_type') == 'video']
    if not videos:
        raise ValueError('No video stream: {}'.format(path))
    video = videos[0]
    duration = video.get('duration', payload.get('format', {}).get('duration'))
    try:
        duration = float(duration)
    except (ValueError, TypeError):
        raise ValueError('Missing video duration: {}'.format(path)) from None
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid video duration: {}'.format(path))
    return {**{key: video.get(key) for key in (
        'codec_name', 'width', 'height', 'r_frame_rate', 'avg_frame_rate', 'nb_frames', 'start_time'
    )}, 'duration': duration,
        'has_audio': any(stream.get('codec_type') == 'audio' for stream in payload.get('streams', []))}


def packet_summary(lines):
    count = small = 0
    previous = None
    strict = True
    for line in lines:
        fields = dict(item.split('=', 1) for item in line.strip().split('|') if '=' in item)
        if 'size' not in fields:
            continue
        size = int(fields['size'])
        count += 1
        small += size < 64
        try:
            pts = float(fields.get('pts_time', 'nan'))
        except ValueError:
            pts = float('nan')
        if not math.isfinite(pts):
            strict = False
        else:
            if previous is not None and pts <= previous:
                strict = False
            previous = pts
    return dict(count=count, small_count=small, small_fraction=small / count if count else 0.0,
                pts_strict=strict and count > 0)


def probe_packets(path, ffprobe='ffprobe', seconds=None):
    command = [ffprobe, '-v', 'error', '-select_streams', 'v:0']
    if seconds is not None:
        command += ['-read_intervals', '%+{}'.format(seconds)]
    command += ['-show_entries', 'packet=pts_time,size', '-of', 'compact=p=0:nk=0', str(path)]
    with tempfile.TemporaryFile() as errors:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True,
                              encoding='utf-8', errors='replace') as process:
            try:
                summary = packet_summary(process.stdout)
            except BaseException:
                process.kill()
                raise
            finally:
                process.stdout.close()
            if process.wait() != 0:
                errors.seek(0)
                raise RuntimeError('ffprobe failed: ' + errors.read(8192).decode('utf-8', errors='replace'))
    return summary
