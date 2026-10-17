import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .common import atomic_json, hash_file, outside_source, probe_metadata, probe_packets, source_path


def load_roles():
    return json.loads(Path(__file__).with_name('camera_roles.json').read_text(encoding='utf-8'))


def identify(session, filename, roles):
    matches = [key for key, pattern in roles['filename_patterns'].items() if pattern in filename]
    if len(matches) != 1:
        raise ValueError('Ambiguous or unknown camera filename: {}'.format(filename))
    key = matches[0]
    overrides = roles['overrides'].get(session, {})
    camera = overrides.get(key, roles['default'][key])
    part = re.search(r'-(\d+)$', Path(filename).stem)
    return camera, 'override' if key in overrides else 'filename', int(part[1]) if part else None


def fingerprint(path, cached=None):
    stat = path.stat()
    values = dict(size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
    if cached and all(cached.get(key) == value for key, value in values.items()) and cached.get('sha256'):
        return {**values, 'sha256': cached['sha256']}
    digest = hash_file(path)
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
        raise ValueError('Input changed while hashing: {}'.format(path))
    return {**values, 'sha256': digest}


def create_inventory(root, out, ffprobe='ffprobe'):
    root = Path(root).resolve(strict=True)
    out = outside_source(out, root)
    old = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    cache = {row['relative_path']: row for row in old.get('files', [])} if old.get('root') == str(root) else {}
    roles = load_roles()
    records = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in ('.avi', '.mp4'):
            continue
        relative = path.relative_to(root).as_posix()
        session = path.relative_to(root).parts[0]
        path = source_path(root, relative)
        camera, source, part = identify(session, path.name, roles)
        info = fingerprint(path, cache.get(relative))
        metadata = probe_metadata(path, ffprobe)
        packets = probe_packets(path, ffprobe, seconds=60)
        records.append(dict(session=session, relative_path=relative, **info, video=metadata,
                            first_60s_packets=packets, physical_camera=camera,
                            role=roles['cameras'][camera]['role'], camera_source=source, part_index=part,
                            needs_remux=path.suffix.lower() == '.avi' and packets['small_count'] > 0))
        print('Inventoried {}'.format(relative), flush=True)
    result = dict(version=1, root=str(root), created_at=datetime.now(timezone.utc).isoformat(), files=records)
    atomic_json(out, result)
    return result


def build_parser():
    parser = argparse.ArgumentParser(description='Inventory local videos without modifying the source root.')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--ffprobe', default='ffprobe')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = create_inventory(args.root, args.out, args.ffprobe)
    print('Files: {}'.format(len(result['files'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
