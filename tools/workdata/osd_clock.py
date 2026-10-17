"""Conservative fixed-grid clock recognition; no model, network, or OCR service."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import cv2
import numpy as np


WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def _bitmap(rows):
    return np.array([[int(value) for value in row] for row in rows], dtype=float)


class ClockReader:
    def __init__(self, layouts=None, glyphs=None):
        root = Path(__file__).parent
        self.settings = json.loads(Path(layouts or root / 'osd_layouts.json').read_text(encoding='utf-8'))
        values = json.loads(Path(glyphs or root / 'osd_glyphs.json').read_text(encoding='utf-8'))
        self.digits = np.array([_bitmap(values[str(i)]) for i in range(10)])
        self.letters = {key: _bitmap(value) for key, value in self.settings['weekday_cues'].items()}

    def _samples(self, image, camera, slot, source_size):
        layout = self.settings['layouts'][camera]
        sx, sy = source_size[0] / 3840, source_size[1] / 2160
        x, y = layout['origin']
        x += slot * layout['advance']
        left, top, right, bottom = round(x*sx), round(y*sy), round((x+28)*sx), round((y+40)*sy)
        if not (0 <= left < right <= image.shape[1] and 0 <= top < bottom <= image.shape[0]):
            raise ValueError('Clock grid outside image')
        cell = cv2.resize(image[top:bottom, left:right], (28,40), interpolation=cv2.INTER_NEAREST)
        minimum = cell.min(axis=2) if cell.ndim == 3 else cell
        maximum = cell.max(axis=2) if cell.ndim == 3 else cell
        samples = []
        # Downscaling and H.264 soften black/white glyphs; retain the same
        # template-error and winner-margin requirements at every resolution.
        key='scaled_thresholds' if sx<1 or sy<1 else 'thresholds'
        for cutoff in self.settings[key]:
            light = minimum > 255-cutoff
            masks = [light]
            if layout['polarity'] == 'both':
                dark = maximum < cutoff
                masks += [dark, light | dark]
            samples.extend(mask.reshape(10,4,7,4).mean(axis=(1,3)) for mask in masks)
        return np.array(samples)

    def _scores(self, samples, templates):
        return np.abs(templates[:,None] - samples).mean(axis=(2,3)).min(axis=1)

    def read(self, image, camera, source_size=None):
        """Read RGB/gray pixels; optional source_size permits a cropped top band."""
        image = np.asarray(image)
        source_size = source_size or (image.shape[1], image.shape[0])
        layout = self.settings['layouts'][camera]
        values, errors, margins = [], [], []
        try:
            for slot in layout['digit_slots']:
                scores = self._scores(self._samples(image,camera,slot,source_size), self.digits)
                order = np.argsort(scores)
                error, margin = float(scores[order[0]]), float(scores[order[1]]-scores[order[0]])
                if error > self.settings['max_error'] or margin < self.settings['min_margin']:
                    return None
                values.append(str(order[0]))
                errors.append(error)
                margins.append(margin)
            text = ''.join(values)
            # Treat the displayed wall clock as a timezone-free numeric axis.
            # UTC is only an encoding convention; these clocks are not calibrated UTC.
            date = datetime.strptime(text, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            if camera == 'cam_e':
                words = [word for word in WEEKDAYS if all(c in self.letters for c in word)]
                samples = [self._samples(image,camera,s,source_size) for s in layout['weekday_slots']]
                word_scores = [np.mean([self._scores(sample,np.array([self.letters[c]]))[0]
                                        for sample,c in zip(samples,word)]) for word in words]
                order = np.argsort(word_scores)
                if (word_scores[order[0]] > self.settings['max_error']
                        or word_scores[order[1]]-word_scores[order[0]] < self.settings['min_margin']
                        or words[order[0]] != WEEKDAYS[date.weekday()]):
                    return None
            return dict(camera=camera, text=date.strftime('%Y-%m-%dT%H:%M:%S'),
                        wall_time=date.timestamp(), max_error=max(errors), min_margin=min(margins))
        except (ValueError, OverflowError):
            return None

    def identify(self, image, source_size=None):
        found = [value for camera in self.settings['layouts']
                 if (value := self.read(image,camera,source_size)) is not None]
        return found[0] if len(found) == 1 else None


def second_transitions(readings, max_gap=.25):
    """Only adjacent, reliable decoded frames can bracket a one-second jump."""
    anchors = []
    previous = None
    for row in readings:
        if (previous is not None and previous.get('wall_time') is not None and row.get('wall_time') is not None
                and row['wall_time'] - previous['wall_time'] == 1
                and 0 < row['pts'] - previous['pts'] <= max_gap):
            anchors.append(dict(pts=row['pts'], wall_time=row['wall_time'],
                                bracket_seconds=row['pts']-previous['pts']))
        previous = row
    return anchors


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read a fixed-layout clock from a local image; no inference.')
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--camera', choices=('cam_a','cam_b','cam_e'))
    args = parser.parse_args(argv)
    image = cv2.imread(str(args.image))
    if image is None:
        parser.error('Cannot read image')
    reader = ClockReader()
    result = reader.read(image,args.camera) if args.camera else reader.identify(image)
    print(json.dumps(result))
    return int(result is None)


if __name__ == '__main__':
    raise SystemExit(main())
