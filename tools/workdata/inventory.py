import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .common import atomic_json, hash_file, outside_source, probe_metadata, probe_packets, source_path


def load_roles():
    return json.loads(Path(__file__).with_name('camera_roles.json').read_text(encoding='utf-8'))


def filename_clock(filename,roles):
    for rule in roles['filename_clock_patterns']:
        if re.fullmatch(rule['regex'],filename):
            return datetime.strptime(filename,rule['format'])
    return None


def identify(session, filename, roles):
    if filename_clock(filename,roles) is not None:
        return 'cam_w', 'filename_clock', None
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


def create_inventory(root, out, ffprobe='ffprobe', sessions=None):
    root = Path(root).resolve(strict=True)
    out = outside_source(out, root)
    old = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    cache = {row['relative_path']: row for row in old.get('files', [])} if old.get('root') == str(root) else {}
    roles = load_roles()
    selected = None if sessions is None else set(sessions)
    if selected is not None and (not selected or any(not re.fullmatch(r'\d{8}', s) for s in selected)):
        raise ValueError('Sessions must be eight-digit recording names')
    directories = [root] if selected is None else [source_path(root, s) for s in sorted(selected)]
    if any(not path.is_dir() for path in directories):
        raise ValueError('Selected session directory is missing')
    if selected is not None and old.get('root') not in (None,str(root)):
        for row in old.get('files',[]):
            path=source_path(root,row['relative_path'])
            if (not path.is_file() or path.stat().st_size!=row['size_bytes']
                    or path.stat().st_mtime_ns!=row['mtime_ns']):
                raise ValueError('Selected root does not contain the existing inventory: '+row['relative_path'])
    records = [] if selected is None else [row for row in old.get('files', []) if row['session'] not in selected]
    for path in sorted(p for directory in directories for p in directory.rglob('*')):
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
    if selected is not None:
        updated={row['relative_path']:row for row in records}
        ordered=[updated.pop(row['relative_path']) for row in old.get('files',[])
                 if row['relative_path'] in updated]
        records=ordered+list(updated.values())
    result = dict(version=1, root=str(root), created_at=datetime.now(timezone.utc).isoformat(), files=records)
    atomic_json(out, result)
    return result


def build_parser():
    parser = argparse.ArgumentParser(description='Inventory local videos without modifying the source root.')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--ffprobe', default='ffprobe')
    parser.add_argument('--session', action='append', help='Scan only this recording; repeat to select several, preserving other rows')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = create_inventory(args.root, args.out, args.ffprobe, args.session)
    print('Files: {}'.format(len(result['files'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
