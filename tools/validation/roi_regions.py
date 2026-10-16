import argparse
from datetime import datetime
import json
import math
from numbers import Real
from pathlib import Path
import re

from tools.workdata.common import atomic_json


def defaults():
    return json.loads(Path(__file__).with_name('default_regions.json').read_text(encoding='utf-8'))


def finite(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


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
    reserved = {row['label'] for row in defaults()['fixed_classes']}
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
        validate_polygon(row.get('polygon'))
    return payload


def reference_matches(reference, candidate):
    return all(reference.get(key) == candidate.get(key) for key in (
        'session', 'source', 'container_time_ms', 'image_sha256', 'width', 'height'))


def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def save(path, payload):
    validate(payload)
    path = Path(path)
    if path.exists():
        atomic_json(path.with_suffix(path.suffix + '.bak'), load(path))
    atomic_json(path, payload)


def make_classes(payload):
    validate(payload)
    classes = [dict(label=row['key'], name_zh=row['name_zh'], color=row['color']) for row in payload['regions'] if row['kind'] == 'target']
    classes += defaults()['fixed_classes']
    return dict(version=1, classes=[dict(key=0 if row['label'] == 'unknown' else i + 1, **row)
                                    for i, row in enumerate(classes)])


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
