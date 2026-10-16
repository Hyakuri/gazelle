from datetime import datetime, timezone
import unittest

import numpy as np

from tools.workdata.osd_clock import ClockReader, second_transitions


def synthesize(camera, text, weekday=None, scale=1, dark=False, noise=0):
    reader = ClockReader()
    layout = reader.settings['layouts'][camera]
    image = np.full((2160, 3840), 130, dtype=np.uint8)
    for slot, digit in zip(layout['digit_slots'], text):
        bitmap = reader.digits[int(digit)]
        x, y = layout['origin']
        x += slot * layout['advance']
        mask = np.repeat(np.repeat(bitmap, 4, axis=0), 4, axis=1).astype(bool)
        image[y:y+40, x:x+28][mask] = 0 if dark else 255
    if weekday:
        for slot, char in zip(layout['weekday_slots'], weekday):
            x = layout['origin'][0] + slot * layout['advance']
            y = layout['origin'][1]
            mask = np.repeat(np.repeat(reader.letters[char], 4, axis=0), 4, axis=1).astype(bool)
            image[y:y+40, x:x+28][mask] = 0 if dark else 255
    if noise:
        image = np.clip(image.astype(float) + np.random.default_rng(11).normal(0, noise, image.shape), 0, 255).astype('uint8')
    if scale != 1:
        import cv2
        image = cv2.resize(image, (round(3840*scale), round(2160*scale)), interpolation=cv2.INTER_AREA)
    return image


class ClockTest(unittest.TestCase):
    def test_synthetic_digits_noise_scale_polarity_and_camera_identity(self):
        reader = ClockReader()
        for camera in ('cam_a', 'cam_b', 'cam_e'):
            for scale in (1, .5):
                for dark in ((False, True) if camera == 'cam_e' else (False,)):
                    with self.subTest(camera=camera, scale=scale, dark=dark):
                        image = synthesize(camera, '20260907220503', 'Mon' if camera == 'cam_e' else None,
                                           scale=scale, dark=dark, noise=6)
                        found = reader.identify(image)
                        self.assertEqual(found['camera'], camera)
                        self.assertEqual(found['text'], '2026-09-07T22:05:03')
        self.assertIsNone(reader.identify(np.full((2160,3840), 128, dtype='uint8')))

    def test_invalid_date_seconds_weekday_and_ambiguous_pixels_are_missing(self):
        reader = ClockReader()
        for digits, day in [('20260230220503','Mon'), ('20260907220560','Mon'), ('20260907220503','Tue')]:
            self.assertIsNone(reader.read(synthesize('cam_e',digits,day), 'cam_e'))
        image=synthesize('cam_a','20260907220503')
        image[24:64,10:38]=255
        self.assertIsNone(reader.read(image,'cam_a'))

    def test_second_transition_requires_consecutive_valid_frames(self):
        rows=[dict(pts=i*.05, wall_time=100+(i>=3)) for i in range(6)]
        anchors=second_transitions(rows)
        self.assertEqual(len(anchors),1)
        self.assertAlmostEqual(anchors[0]['pts'],.15)
        self.assertEqual(anchors[0]['wall_time'],101)
        self.assertAlmostEqual(anchors[0]['bracket_seconds'],.05)
        rows[2]['wall_time']=None
        self.assertEqual(second_transitions(rows), [])
        rows=[dict(pts=0,wall_time=100),dict(pts=.2,wall_time=102)]
        self.assertEqual(second_transitions(rows), [])

    def test_scaled_clock_keeps_conservative_scores_after_reduced_contrast(self):
        reader=ClockReader()
        for dark in (False,True):
            image=synthesize('cam_e','20260824193510','Mon',scale=.5,dark=dark)
            image[image==0 if dark else image==255]=60 if dark else 195
            found=reader.read(image,'cam_e')
            self.assertIsNotNone(found)
            self.assertEqual(found['text'],'2026-08-24T19:35:10')
            self.assertLessEqual(found['max_error'],reader.settings['max_error'])
            self.assertGreaterEqual(found['min_margin'],reader.settings['min_margin'])
