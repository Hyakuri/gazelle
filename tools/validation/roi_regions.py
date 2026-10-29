import argparse
from datetime import datetime, timezone
import json
import math
from numbers import Real
from pathlib import Path
import re

from tools.workdata.common import atomic_json, hash_file


def defaults():
    return json.loads(Path(__file__).with_name('default_regions.json').read_text(encoding='utf-8'))


def finite(value):
    try:
        return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def normalize_point(x, y, width, height):
    if width <= 0 or height <= 0:
        raise ValueError('Image dimensions must be positive')
    return [x / width, y / height]


def pixel_point(point, width, height):
    return (round(point[0] * width), round(point[1] * height))


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, c):
    return abs(_cross(a, b, c)) < 1e-12 and all(min(a[i], b[i]) <= c[i] <= max(a[i], b[i]) for i in (0, 1))


def _intersects(a, b, c, d):
    if _cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0:
        return True
    return _on_segment(a, b, c) or _on_segment(a, b, d) or _on_segment(c, d, a) or _on_segment(c, d, b)


def validate_polygon(points):
    if not isinstance(points, list) or not 3 <= len(points) <= 500:
        raise ValueError('A polygon needs 3 to 500 vertices')
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2 or any(not finite(v) or not 0 <= v <= 1 for v in point):
            raise ValueError('Polygon coordinates must be finite and normalized to [0, 1]')
    if len({tuple(point) for point in points}) != len(points):
        raise ValueError('Polygon vertices must be distinct')
    edges = list(zip(points, points[1:] + points[:1]))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if _intersects(a, b, c, d):
                raise ValueError('Polygon must not self-intersect')
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)
    if abs(area) < 1e-12:
        raise ValueError('Polygon must have nonzero area')


def validate(payload):
    if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload.get('version') != 1 or payload.get('camera') != 'cam_e':
        raise ValueError('Expected version 1 and camera cam_e')
    reference = payload.get('reference', {})
    if not isinstance(reference, dict):
        raise ValueError('Reference must be an object')
    for key in ('session', 'source', 'image_sha256'):
        if not isinstance(reference.get(key), str) or not reference[key]:
            raise ValueError('Missing reference ' + key)
    if not re.fullmatch(r'[a-f0-9]{64}', reference['image_sha256']):
        raise ValueError('Invalid reference image SHA-256')
    if not finite(reference.get('container_time_ms')) or reference['container_time_ms'] < 0:
        raise ValueError('Invalid reference container time')
    for key in ('width', 'height'):
        if type(reference.get(key)) is not int or reference[key] <= 0:
            raise ValueError('Invalid reference dimensions')
    if not isinstance(payload.get('annotator'), str) or not payload['annotator'].strip():
        raise ValueError('Annotator is required')
    for key in ('created_at', 'updated_at'):
        try:
            datetime.fromisoformat(payload[key])
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid ' + key) from None
    items = payload.get('regions')
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError('Expected at most 100 regions')
    seen = set()
    fixed = defaults()['fixed_classes']
    reserved = {row['label'] for row in fixed}
    colors = {row['color'].lower() for row in fixed}
    targets = 0
    cells = 0
    for row in items:
        if not isinstance(row, dict):
            raise ValueError('Region must be an object')
        key = row.get('key')
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', key) or key in reserved:
            raise ValueError('Region key must be a non-reserved ASCII identifier')
        if key in seen:
            raise ValueError('Region keys must be unique')
        seen.add(key)
        if not isinstance(row.get('name_zh'), str) or not row['name_zh'].strip():
            raise ValueError('Region name is required')
        if row.get('kind') not in ('target', 'cell'):
            raise ValueError('Region kind must be target or cell')
        cells += row['kind'] == 'cell'
        if cells > 1:
            raise ValueError('At most one cell is allowed')
        if not isinstance(row.get('color'), str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', row['color']):
            raise ValueError('Region color must be #rrggbb')
        if row['kind'] == 'target':
            targets += 1
            if targets + sum(row['label'] != 'unknown' for row in fixed) > 9:
                raise ValueError('At most five target regions fit the digit keys 1 to 9')
            if row['color'].lower() in colors:
                raise ValueError('Target colors must be distinct from other targets and fixed classes')
            colors.add(row['color'].lower())
        validate_polygon(row.get('polygon'))
    return payload


def reference_matches(reference, candidate):
    return all(reference.get(key) == candidate.get(key) for key in (
        'session', 'source', 'container_time_ms', 'image_sha256', 'width', 'height'))


def validate_draft(draft, document):
    if not isinstance(draft, dict) or set(draft) != {'points', 'region'}:
        raise ValueError('Invalid draft schema')
    points, region = draft['points'], draft['region']
    if not isinstance(points, list) or len(points) > 500:
        raise ValueError('Invalid draft points')
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or any(not finite(v) or not 0 <= v <= 1 for v in point):
            raise ValueError('Invalid draft coordinate')
    if region is None:
        if points:
            raise ValueError('Draft points need a region')
    else:
        if not isinstance(region, dict) or set(region) != {'key', 'name_zh', 'kind', 'color'}:
            raise ValueError('Invalid draft region')
        validate({**document, 'regions': document['regions'] + [
            {**region, 'polygon': [[0, 0], [1, 0], [0, 1]]}]})
    return draft


def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def save(path, payload):
    validate(payload)
    path = Path(path)
    if path.exists():
        previous = load(path)
        if previous == payload:
            return
        atomic_json(path.with_suffix(path.suffix + '.bak'), previous)
    atomic_json(path, payload)


def make_classes(payload):
    validate(payload)
    classes = [dict(label=row['key'], name_zh=row['name_zh'], color=row['color']) for row in payload['regions'] if row['kind'] == 'target']
    if not classes:
        raise ValueError('At least one target region is required')
    classes += defaults()['fixed_classes']
    return dict(version=1, classes=[dict(key=0 if row['label'] == 'unknown' else i + 1, **row)
                                    for i, row in enumerate(classes)])


def validate_complete(payload):
    make_classes(payload)
    if sum(row['kind'] == 'cell' for row in payload['regions']) != 1:
        raise ValueError('Exactly one cell is required before export')
    return payload


def completion_path(path):
    return Path(path).with_suffix('.complete.json')


def default_export_root(path):
    path=Path(path)
    return path.parent if path.name=='roi_regions.json' else path.parent/(path.stem+'_export')


def small_regions(payload):
    result=[]
    for row in payload['regions']:
        points=row['polygon']
        area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2
        if area<.005:result.append(dict(key=row['key'],name_zh=row['name_zh'],area_fraction=area))
    return result


def mark_complete(path, expected_sha256=None, out_root=None):
    validate_complete(load(path))
    digest = hash_file(path)
    if expected_sha256 is not None and expected_sha256 != digest:
        raise ValueError('Regions changed during export; export again')
    root=Path(out_root if out_root is not None else default_export_root(path)).resolve()
    exports={name:hash_file(root/name) for name in ('roi_reference.png','classes.json')}
    if json.loads((root/'classes.json').read_text(encoding='utf-8'))!=make_classes(load(path)):
        raise ValueError('Exported classes differ from regions')
    atomic_json(completion_path(path), dict(version=2,export_root=str(root),exports=exports,
                completed_at=datetime.now(timezone.utc).isoformat(), regions_sha256=digest))


def completed_exports(path):
    marker=json.loads(completion_path(path).read_text(encoding='utf-8'))
    if type(marker.get('version')) is not int or marker['version']!=2:
        raise ValueError('Export completion marker version 2 required; export again')
    root=Path(marker['export_root'])
    if not root.is_absolute() or set(marker['exports'])!={'roi_reference.png','classes.json'}:
        raise ValueError('Invalid export completion marker')
    for name,digest in marker['exports'].items():
        if hash_file(root/name)!=digest:raise ValueError('Export hash mismatch: '+name)
    return marker


def completed_document(path):
    """Return only the unchanged document recorded by a successful export."""
    try:
        marker = completed_exports(path)
        datetime.fromisoformat(marker['completed_at'])
        if marker['regions_sha256'] != hash_file(path):
            return None
        document = validate_complete(load(path))
        draft_path = Path(path).with_suffix('.draft.json')
        if draft_path.exists():
            draft = validate_draft(json.loads(draft_path.read_text(encoding='utf-8')), document)
            if draft['region'] is not None:
                return None
        return document
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate region definitions or derive annotation classes.')
    parser.add_argument('action', choices=('validate', 'classes'))
    parser.add_argument('path', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    payload = load(args.path)
    if args.action == 'classes':
        if args.out is None:
            parser.error('classes requires --out')
        atomic_json(args.out, make_classes(payload))
    print('Valid regions: {}'.format(len(payload['regions'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
