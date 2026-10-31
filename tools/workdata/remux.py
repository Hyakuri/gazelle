import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import time
import uuid

from .common import atomic_json, outside_source, probe_metadata, probe_packets, source_path


def build_command(ffmpeg, source, temporary):
    return [ffmpeg, '-nostdin', '-v', 'error', '-n', '-fflags', '+genpts', '-i', str(source),
            '-map', '0:v:0', '-c:v', 'copy', '-bsf:v', r'noise=drop=lt(size\,64)', str(temporary)]


def check_decode(path):
    import cv2
    capture = cv2.VideoCapture(str(path))
    try:
        details = dict(windows=[0, 0, 0], tail_eof=False, last_timestamp_ms=None, frame_interval_ms=None)
        if not capture.isOpened():
            return details
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            return details
        details['frame_interval_ms'] = 1000 / fps
        # VFR frame-number seeks can land one frame late. Decode a wider tail
        # window to EOF, then require its final 30 frames to be continuous.
        for index, (start, window) in enumerate(((0, 30), (max(0, count // 2 - 15), 30), (max(0, count - 60), 120))):
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, start):
                continue
            decoded = 0
            for _ in range(window):
                ok, _ = capture.read()
                if not ok:
                    if index == 2:
                        details['tail_eof'] = True
                    break
                decoded += 1
                if index == 2:
                    timestamp = capture.get(cv2.CAP_PROP_POS_MSEC)
                    details['last_timestamp_ms'] = timestamp if math.isfinite(timestamp) else None
            details['windows'][index] = decoded
        return details
    finally:
        capture.release()


def validate_output(path, input_packets, input_duration, ffprobe):
    metadata = probe_metadata(path, ffprobe)
    packets = probe_packets(path, ffprobe)
    decoded = check_decode(path)
    last_ms = decoded['last_timestamp_ms']
    try:
        rate = float(Fraction(metadata['r_frame_rate']))
        interval = 1000 / rate if math.isfinite(rate) and rate > 0 else None
    except (KeyError, ValueError, ZeroDivisionError, TypeError, OverflowError):
        interval = None
    decoded['nominal_frame_interval_ms'] = interval
    last_pts = packets['last_pts']
    assumed_zero=metadata.get('start_time') is None
    try:
        start_time = 0. if assumed_zero else float(metadata['start_time'])
        if not math.isfinite(start_time):start_time=None
    except (TypeError,ValueError,OverflowError):
        start_time=None
    delta = last_ms - 1000 * (last_pts - start_time) if last_ms is not None and last_pts is not None and start_time is not None else None
    decoded.update(start_time=start_time, start_time_assumed_zero=assumed_zero, tail_pts_delta_ms=delta)
    tail_pts = (last_ms is not None and interval is not None and last_pts is not None
                and delta is not None and abs(delta) <= interval)
    checks = dict(packet_count=packets['count'] == input_packets['count'] - input_packets['small_count'],
                  duration=abs(metadata['duration'] - input_duration) <= input_duration * 0.005,
                  pts_strict=packets['pts_strict'],
                  decode=decoded['windows'][:2] == [30, 30] and decoded['windows'][2] >= 30 and decoded['tail_eof'],
                  tail_pts=tail_pts)
    return dict(valid=all(checks.values()), checks=checks, packets=packets,
                duration=metadata['duration'], decoded=decoded['windows'], decode_details=decoded)


def remux_one(source, output, ffmpeg='ffmpeg', ffprobe='ffprobe', force=False):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Remux output must differ from source')
    started = time.monotonic()
    result = dict(input=str(source), output=str(output), input_size_bytes=source.stat().st_size)
    temporary = output.with_name('.' + output.stem + '.' + uuid.uuid4().hex + '.mp4')
    try:
        source_stat = source.stat()
        packets = probe_packets(source, ffprobe)
        duration = probe_metadata(source, ffprobe)['duration']
        result.update(input_packets=packets, input_duration=duration)
        if output.exists() and not force:
            try:
                existing = validate_output(output, packets, duration, ffprobe)
            except (ValueError, RuntimeError, subprocess.SubprocessError):
                existing = {'valid': False}
            if existing['valid']:
                result.update(status='skipped', validation=existing)
                return result
        output.parent.mkdir(parents=True, exist_ok=True)
        command = build_command(ffmpeg, source, temporary)
        result['command'] = command
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        validation = validate_output(temporary, packets, duration, ffprobe)
        result['validation'] = validation
        if not validation['valid']:
            raise ValueError('Remux validation failed')
        after = source.stat()
        if (after.st_size, after.st_mtime_ns) != (source_stat.st_size, source_stat.st_mtime_ns):
            raise ValueError('Source changed during remux')
        temporary.replace(output)
        result['status'] = 'completed'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(status='failed', error=str(error))
        if isinstance(error, subprocess.CalledProcessError):
            result['stderr'] = error.stderr
    finally:
        temporary.unlink(missing_ok=True)
        result['output_size_bytes'] = output.stat().st_size if output.exists() else None
        result['elapsed_seconds'] = time.monotonic() - started
    return result


def run_inventory(inventory_path, out_root, ffmpeg='ffmpeg', ffprobe='ffprobe', force=False, sessions=None):
    inventory = json.loads(Path(inventory_path).read_text(encoding='utf-8'))
    root = Path(inventory['root'])
    out_root = outside_source(out_root, root)
    selected = None if sessions is None else set(sessions)
    if selected is not None and (not selected or not selected.issubset({r['session'] for r in inventory['files']})):
        raise ValueError('No matching selected session in inventory')
    report_path = out_root / 'remux_report.json'
    saved = json.loads(report_path.read_text(encoding='utf-8')).get('files', []) if report_path.exists() else []
    results = []
    for row in inventory['files']:
        if not row['needs_remux'] or (selected is not None and row['session'] not in selected):
            continue
        source = source_path(root, row['relative_path'])
        if source.suffix.lower() != '.avi':
            raise ValueError('Only AVI entries may require remux')
        output = source_path(out_root, str(Path(row['relative_path']).with_suffix('.mp4')))
        result = remux_one(source, output, ffmpeg, ffprobe, force)
        results.append(result)
        existing=next((i for i,record in enumerate(saved) if Path(record['output']).resolve()==output.resolve()),None)
        if existing is None:
            saved.append(result)
        elif not (result['status']=='failed' and saved[existing].get('status') in ('completed','skipped')
                  and saved[existing].get('validation',{}).get('valid')):
            saved[existing]=result
        atomic_json(report_path, dict(version=1, files=saved))
        print('{}: {}'.format(result['status'], row['relative_path']), flush=True)
    return results


def build_parser():
    parser = argparse.ArgumentParser(description='Copy AVI video packets to validated MP4 files.')
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--out-root', type=Path, required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--session', action='append', help='Remux only selected recordings; preserve other report rows')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    results = run_inventory(args.inventory, args.out_root, args.ffmpeg, args.ffprobe, args.force, args.session)
    return int(any(row['status'] == 'failed' for row in results))


if __name__ == '__main__':
    raise SystemExit(main())
