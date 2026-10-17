import argparse
import json
import math
from pathlib import Path
import uuid

from PIL import Image
from tools.workdata.common import atomic_json, hash_file, outside_source, source_path


class OpenCVSource:
    def __init__(self, path):
        import cv2
        self.cv2 = cv2
        self.capture = cv2.VideoCapture(str(path))
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        count = self.capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not self.capture.isOpened() or not math.isfinite(fps) or fps <= 0 or count <= 0:
            self.close()
            raise ValueError('Cannot determine candidate video duration: {}'.format(path))
        self.duration = count / fps
        self.frame_interval_ms = 1000 / fps

    def read_at(self, seconds):
        if not self.capture.set(self.cv2.CAP_PROP_POS_MSEC, seconds * 1000):
            raise ValueError('Cannot seek candidate time')
        ok, frame = self.capture.read()
        if not ok:
            raise ValueError('Cannot decode candidate frame')
        image = Image.fromarray(self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB))
        return image, self.capture.get(self.cv2.CAP_PROP_POS_MSEC)

    def close(self):
        self.capture.release()


def validate_candidates(path, verify_images=True):
    path = Path(path)
    payload = json.loads(path.read_text(encoding='utf-8'))
    return _validate_manifest(payload, path.parent, verify_images)


def _validate_manifest(payload, root, verify_images=True):
    if payload.get('version') != 1 or payload.get('camera') != 'cam_e' or not payload.get('candidates'):
        raise ValueError('Invalid candidates manifest')
    seen = set()
    for row in payload['candidates']:
        if not isinstance(row.get('id'), str) or row['id'] in seen:
            raise ValueError('Candidate IDs must be unique strings')
        seen.add(row['id'])
        if row.get('width') != 1920 or row.get('height') != 1080:
            raise ValueError('Candidate dimensions must be 1920x1080')
        if not isinstance(row.get('session'), str) or not isinstance(row.get('source'), str):
            raise ValueError('Candidate source/session are required')
        time_ms = row.get('container_time_ms')
        if isinstance(time_ms, bool) or not isinstance(time_ms, (int, float)) or not math.isfinite(time_ms) or time_ms < 0:
            raise ValueError('Invalid candidate timestamp')
        image_path = source_path(root, row['image'])
        if verify_images:
            if hash_file(image_path) != row['image_sha256']:
                raise ValueError('Candidate image hash mismatch: {}'.format(image_path))
            with Image.open(image_path) as image:
                if image.size != (1920, 1080) or image.format != 'JPEG':
                    raise ValueError('Invalid candidate image format or size')
    return payload


def extract_candidates(inventory_path, remux_root, out_root, source_factory=OpenCVSource):
    inventory = json.loads(Path(inventory_path).read_text(encoding='utf-8'))
    out_root = outside_source(out_root, inventory['root'])
    generation = uuid.uuid4().hex[:12]
    candidates = []
    sessions = set()
    for row in inventory['files']:
        if row['physical_camera'] != 'cam_e':
            continue
        session = row['session']
        if session in sessions:
            raise ValueError('Expected one overview video per session: {}'.format(session))
        sessions.add(session)
        source = source_path(remux_root, str(Path(row['relative_path']).with_suffix('.mp4'))) if row['needs_remux'] else source_path(inventory['root'], row['relative_path'])
        if not source.is_file():
            raise ValueError('Missing validated overview remux: {}'.format(source))
        if row['needs_remux']:
            report_path = Path(remux_root) / 'remux_report.json'
            if not report_path.is_file():
                raise ValueError('Missing validated remux report')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            original = source_path(inventory['root'], row['relative_path'])
            matches = [item for item in report.get('files', [])
                       if Path(item['output']).resolve() == source.resolve()
                       and Path(item['input']).resolve() == original.resolve()]
            if (len(matches) != 1 or matches[0].get('validation', {}).get('valid') is not True
                    or matches[0].get('status') not in ('completed', 'skipped')
                    or matches[0].get('output_size_bytes') != source.stat().st_size):
                raise ValueError('Overview remux has no matching validated report: {}'.format(source))
        reader = source_factory(source)
        try:
            previous_time = -1
            for index in range(12):
                seconds = reader.duration * (index + 0.5) / 12
                image, timestamp = reader.read_at(seconds)
                if (not math.isfinite(timestamp) or timestamp <= previous_time
                        or abs(timestamp - seconds * 1000) > max(1, 2 * reader.frame_interval_ms)):
                    image.close()
                    raise ValueError('Invalid decoded candidate timestamp')
                previous_time = timestamp
                candidate_id = '{}-{}-{:02}'.format(session, generation, index)
                relative = Path('candidates') / session / (candidate_id + '.jpg')
                destination = source_path(out_root, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix('.tmp')
                try:
                    image.convert('RGB').resize((1920, 1080), Image.Resampling.LANCZOS).save(temporary, format='JPEG', quality=90)
                    temporary.replace(destination)
                finally:
                    temporary.unlink(missing_ok=True)
                    image.close()
                candidates.append(dict(id=candidate_id, session=session, source=str(source),
                                       container_time_ms=timestamp, requested_time_ms=seconds * 1000,
                                       image=relative.as_posix(), image_sha256=hash_file(destination),
                                       width=1920, height=1080))
            print('Candidates: {} (12)'.format(session), flush=True)
        finally:
            reader.close()
    if not candidates:
        raise ValueError('Inventory contains no overview videos')
    payload = dict(version=1, camera='cam_e', candidates=candidates)
    _validate_manifest(payload, out_root)
    if (out_root / 'candidates.json').exists():
        previous = validate_candidates(out_root / 'candidates.json')
        atomic_json(out_root / 'candidates.json.bak', previous)
    atomic_json(out_root / 'candidates.json', payload)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description='Extract 12 overview candidates per session, without inference.')
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--remux-root', type=Path, required=True)
    parser.add_argument('--out-root', type=Path, required=True)
    args = parser.parse_args(argv)
    extract_candidates(args.inventory, args.remux_root, args.out_root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
