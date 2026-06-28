from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import torch
from PIL import Image

from gazelle.runtime.contracts import GazePrediction
from gazelle.runtime.renderer import (
    heatmap_to_overlay,
    render_predictions,
    save_rendered_image,
    stable_color_for_person,
)


_DEFAULT_HEATMAP = object()


def make_prediction(
    person_id=1,
    bbox=(0.2, 0.2, 0.7, 0.7),
    heatmap=_DEFAULT_HEATMAP,
    gaze_peak=(0.5, 0.5),
    inout_score=0.93,
):
    if heatmap is _DEFAULT_HEATMAP:
        heatmap = torch.tensor([[0.0, 1.0], [0.2, 0.4]])
    return GazePrediction(
        person_id=person_id,
        bbox=bbox,
        heatmap=heatmap,
        gaze_peak=gaze_peak,
        heatmap_peak_value=1.0,
        inout_score=inout_score,
    )


class RendererTest(unittest.TestCase):
    def test_stable_color_is_repeatable(self):
        self.assertEqual(stable_color_for_person(7), stable_color_for_person(7))

    def test_stable_color_differs_for_different_people(self):
        self.assertNotEqual(stable_color_for_person(1), stable_color_for_person(2))

    def test_stable_color_channels_are_bright_enough(self):
        for channel in stable_color_for_person(123):
            self.assertGreaterEqual(channel, 64)
            self.assertLessEqual(channel, 255)

    def test_heatmap_overlay_returns_rgba_image_with_input_size(self):
        overlay = heatmap_to_overlay(
            torch.tensor([[0.0, 1.0], [0.5, 0.2]]),
            image_width=8,
            image_height=6,
            color=(255, 0, 0),
            alpha=0.5,
        )

        self.assertEqual(overlay.mode, "RGBA")
        self.assertEqual(overlay.size, (8, 6))

    def test_heatmap_overlay_rejects_invalid_alpha(self):
        for alpha in (-0.1, 1.1):
            with self.subTest(alpha=alpha):
                with self.assertRaisesRegex(ValueError, "alpha"):
                    heatmap_to_overlay(np.ones((2, 2)), 8, 6, (255, 0, 0), alpha)

    def test_heatmap_overlay_rejects_non_2d_heatmap(self):
        with self.assertRaisesRegex(ValueError, "2D"):
            heatmap_to_overlay(np.ones((2, 2, 1)), 8, 6, (255, 0, 0), 0.5)

    def test_constant_heatmap_does_not_crash(self):
        overlay = heatmap_to_overlay(np.ones((2, 2)), 8, 6, (255, 0, 0), 0.5)

        self.assertEqual(overlay.mode, "RGBA")
        self.assertEqual(overlay.size, (8, 6))

    def test_render_predictions_output_size_and_mode_match_input(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(image, [make_prediction()])

        self.assertEqual(rendered.mode, "RGB")
        self.assertEqual(rendered.size, image.size)

    def test_render_predictions_does_not_mutate_original_image(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        before = image.tobytes()

        render_predictions(image, [make_prediction()])

        self.assertEqual(image.tobytes(), before)

    def test_prediction_with_heatmap_changes_rendered_image(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction(bbox=None, gaze_peak=None)],
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_labels=False,
        )

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_prediction_with_bbox_draws_something(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction(heatmap=None, gaze_peak=None)],
            draw_labels=False,
        )

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_prediction_with_none_bbox_does_not_crash(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(image, [make_prediction(bbox=None)])

        self.assertEqual(rendered.size, image.size)

    def test_prediction_with_none_gaze_peak_does_not_crash(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(image, [make_prediction(gaze_peak=None)])

        self.assertEqual(rendered.size, image.size)

    def test_prediction_with_none_heatmap_still_draws_bbox_or_label(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(image, [make_prediction(heatmap=None)])

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_save_rendered_image_saves_png(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rendered.png"
            save_rendered_image(path, Image.new("RGB", (8, 6)))

            self.assertTrue(path.exists())
            with Image.open(path) as image:
                self.assertEqual(image.size, (8, 6))

    def test_save_rendered_image_saves_jpg(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rendered.jpg"
            save_rendered_image(path, Image.new("RGB", (8, 6)))

            self.assertTrue(path.exists())
            with Image.open(path) as image:
                self.assertEqual(image.size, (8, 6))

    def test_save_rendered_image_rejects_unsupported_extension(self):
        with TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "Rendered image path"):
                save_rendered_image(Path(tmpdir) / "rendered.txt", Image.new("RGB", (8, 6)))


if __name__ == "__main__":
    unittest.main()
