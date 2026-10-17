import argparse
import json
import os
from pathlib import Path
import uuid

from PIL import Image, ImageDraw, ImageFont
from tools.workdata.common import atomic_json, hash_file, source_path
from .extract_roi_candidates import validate_candidates
from .roi_regions import load, make_classes, mark_complete, pixel_point, reference_matches, validate_complete, validate_draft, default_export_root, small_regions


def find_font(path=None):
    if path:
        return ImageFont.truetype(str(path), 28)
    candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc',
                  Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), 28)
    raise ValueError('No Chinese font found; provide --font pointing to an existing CJK font')


def draw_regions(image, regions, font):
    result = image.convert('RGBA')
    ordered = sorted(regions, key=lambda row: row['kind'] != 'cell')
    for region in ordered:
        overlay = Image.new('RGBA', result.size)
        draw = ImageDraw.Draw(overlay)
        points = [pixel_point(point, *result.size) for point in region['polygon']]
        color = region['color']
        rgba = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        draw.polygon(points, fill=(*rgba, 45))
        result = Image.alpha_composite(result, overlay)
    draw = ImageDraw.Draw(result)
    for region in ordered:
        points = [pixel_point(point, *result.size) for point in region['polygon']]
        draw.polygon(points, outline=region['color'], width=4)
    for region in ordered:
        x, y = pixel_point(region['polygon'][0], *result.size)
        draw.text((min(x + 6, result.width - 160), min(y + 6, result.height - 40)), region['name_zh'],
                  font=font, fill=region['color'], stroke_width=2, stroke_fill='white')
    return result.convert('RGB')


def _save_png(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.stem + '.' + uuid.uuid4().hex + '.png')
    try:
        image.save(temporary, format='PNG')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def render(regions_path, candidates_path, out_root=None, font_path=None, confirm_small=False):
    digest = hash_file(regions_path)
    payload = validate_complete(load(regions_path))
    small=small_regions(payload)
    if small and not confirm_small:
        raise ValueError('Regions below 0.5% need confirmation (--confirm-small): '+', '.join(r['key'] for r in small))
    draft_path = Path(regions_path).with_suffix('.draft.json')
    if draft_path.exists():
        if validate_draft(json.loads(draft_path.read_text(encoding='utf-8')), payload)['region'] is not None:
            raise ValueError('Close or cancel the draft before export')
    manifest = validate_candidates(candidates_path)
    matches = [row for row in manifest['candidates'] if reference_matches(payload['reference'], row)]
    if len(matches) != 1:
        raise ValueError('Reference must match exactly one candidate image')
    out_root = Path(out_root) if out_root is not None else default_export_root(regions_path)
    font = find_font(font_path)
    selected = {'roi_reference.png': matches[0]}
    sessions = set()
    for row in manifest['candidates']:
        if row['session'] not in sessions:
            sessions.add(row['session'])
            selected['overlays/' + row['session'] + '.png'] = row
    outputs = []
    for relative, row in selected.items():
        path = source_path(out_root, relative)
        with Image.open(source_path(Path(candidates_path).parent, row['image'])) as image:
            rendered = draw_regions(image, payload['regions'], font)
            try:
                _save_png(rendered, path)
            finally:
                rendered.close()
        outputs.append(str(path))
    atomic_json(out_root / 'classes.json', make_classes(payload))
    mark_complete(regions_path, expected_sha256=digest, out_root=out_root)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description='Render the reference, session overlays and annotation classes.')
    parser.add_argument('--regions-path', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--out-root', type=Path)
    parser.add_argument('--confirm-small', action='store_true', help='Confirm regions below 0.5% of the image')
    parser.add_argument('--font', type=Path)
    args = parser.parse_args(argv)
    outputs = render(args.regions_path, args.candidates, args.out_root, args.font, args.confirm_small)
    print('Rendered {} references; wrote classes.json'.format(len(outputs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
