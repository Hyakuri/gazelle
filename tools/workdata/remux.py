import argparse
import json
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
        if not capture.isOpened():
            return [0, 0, 0]
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        results = []
        # VFR frame-number seeks can land one frame late. Decode a wider tail
        # window to EOF, then require its final 30 frames to be continuous.
        for start, window in ((0, 30), (max(0, count // 2 - 15), 30), (max(0, count - 60), 60)):
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, start):
                results.append(0)
                continue
            decoded = 0
            for _ in range(window):
                ok, _ = capture.read()
                if not ok:
                    break
                decoded += 1
            results.append(min(30, decoded))
        return results
    finally:
        capture.release()


def validate_output(path, input_packets, input_duration, ffprobe):
    metadata = probe_metadata(path, ffprobe)
    packets = probe_packets(path, ffprobe)
    decoded = check_decode(path)
    checks = dict(packet_count=packets['count'] == input_packets['count'] - input_packets['small_count'],
                  duration=abs(metadata['duration'] - input_duration) <= input_duration * 0.005,
                  pts_strict=packets['pts_strict'], decode=decoded == [30, 30, 30])
    return dict(valid=all(checks.values()), checks=checks, packets=packets,
                duration=metadata['duration'], decoded=decoded)


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


def run_inventory(inventory_path, out_root, ffmpeg='ffmpeg', ffprobe='ffprobe', force=False):
    inventory = json.loads(Path(inventory_path).read_text(encoding='utf-8'))
    root = Path(inventory['root'])
    out_root = outside_source(out_root, root)
    results = []
    for row in inventory['files']:
        if not row['needs_remux']:
            continue
        source = source_path(root, row['relative_path'])
        if source.suffix.lower() != '.avi':
            raise ValueError('Only AVI entries may require remux')
        output = source_path(out_root, str(Path(row['relative_path']).with_suffix('.mp4')))
        result = remux_one(source, output, ffmpeg, ffprobe, force)
        results.append(result)
        atomic_json(out_root / 'remux_report.json', dict(version=1, files=results))
        print('{}: {}'.format(result['status'], row['relative_path']), flush=True)
    return results


def build_parser():
    parser = argparse.ArgumentParser(description='Copy AVI video packets to validated MP4 files.')
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--out-root', type=Path, required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    parser.add_argument('--force', action='store_true')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    results = run_inventory(args.inventory, args.out_root, args.ffmpeg, args.ffprobe, args.force)
    return int(any(row['status'] == 'failed' for row in results))


if __name__ == '__main__':
    raise SystemExit(main())
