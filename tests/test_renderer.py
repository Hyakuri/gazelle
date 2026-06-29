from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import torch
from PIL import Image

from gazelle.runtime.contracts import GazePrediction
from gazelle.runtime.renderer import (
    PEAK_MARKER_COLOR,
    PredictionRenderer,
    RenderOptions,
    build_prediction_label,
    heatmap_mask_to_contour_overlay,
    heatmap_to_topk_mask,
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
    def test_render_options_defaults(self):
        options = RenderOptions()

        self.assertEqual(options.heatmap_alpha, 0.45)
        self.assertTrue(options.draw_heatmap)
        self.assertFalse(options.draw_head_box)
        self.assertTrue(options.draw_gaze_peak)
        self.assertTrue(options.draw_gaze_arrow)
        self.assertFalse(options.draw_heatmap_contour)
        self.assertTrue(options.draw_labels)
        self.assertEqual(options.heatmap_contour_quantile, 0.90)
        self.assertIsNone(options.heatmap_contour_width)

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

    def test_prediction_renderer_can_be_reused(self):
        renderer = PredictionRenderer(RenderOptions(heatmap_alpha=0.25))
        first = Image.new("RGB", (12, 10), color=(20, 20, 20))
        second = Image.new("RGB", (14, 8), color=(30, 30, 30))
        first_before = first.tobytes()
        second_before = second.tobytes()

        first_rendered = renderer.render(first, [make_prediction(person_id=1)])
        second_rendered = renderer.render(second, [make_prediction(person_id=2)])

        self.assertEqual(first_rendered.size, first.size)
        self.assertEqual(second_rendered.size, second.size)
        self.assertEqual(first.tobytes(), first_before)
        self.assertEqual(second.tobytes(), second_before)

    def test_render_predictions_preserves_function_api(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction()],
            heatmap_alpha=0.25,
            draw_heatmap=False,
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_gaze_arrow=False,
            draw_labels=False,
        )

        self.assertEqual(rendered.mode, "RGB")
        self.assertEqual(rendered.size, image.size)

    def test_render_predictions_accepts_new_flags(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction()],
            draw_heatmap=False,
            draw_head_box=True,
            draw_gaze_arrow=False,
            draw_heatmap_contour=True,
            heatmap_contour_quantile=0.85,
            heatmap_contour_width=3,
        )

        self.assertEqual(rendered.mode, "RGB")
        self.assertEqual(rendered.size, image.size)

    def test_prediction_renderer_uses_cached_font_indirectly(self):
        renderer = PredictionRenderer()
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))

        rendered = renderer.render(image, [make_prediction(heatmap=None)])

        self.assertEqual(rendered.mode, "RGB")
        self.assertNotEqual(rendered.tobytes(), image.tobytes())

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

    def test_no_heatmap_disables_heatmap_overlay(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction()],
            draw_heatmap=False,
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_gaze_arrow=False,
            draw_labels=False,
        )

        self.assertEqual(rendered.tobytes(), image.tobytes())

    def test_heatmap_only_mode(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction()],
            draw_heatmap=True,
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_gaze_arrow=False,
            draw_labels=False,
        )

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_bbox_only_mode(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction()],
            draw_heatmap=False,
            draw_head_box=True,
            draw_gaze_peak=False,
            draw_gaze_arrow=False,
            draw_labels=False,
        )

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_head_box_default_not_drawn(self):
        image = Image.new("RGB", (20, 20), color=(20, 20, 20))
        rendered = PredictionRenderer(
            RenderOptions(
                draw_heatmap=False,
                draw_gaze_arrow=False,
                draw_gaze_peak=False,
                draw_labels=False,
            )
        ).render(image, [make_prediction(heatmap=None, gaze_peak=None)])

        self.assertEqual(rendered.tobytes(), image.tobytes())

    def test_head_box_drawn_when_enabled(self):
        image = Image.new("RGB", (20, 20), color=(20, 20, 20))
        rendered = PredictionRenderer(
            RenderOptions(
                draw_heatmap=False,
                draw_head_box=True,
                draw_gaze_arrow=False,
                draw_gaze_peak=False,
                draw_labels=False,
            )
        ).render(image, [make_prediction(heatmap=None, gaze_peak=None)])

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_label_anchor_uses_bbox_even_when_box_is_not_drawn(self):
        image = Image.new("RGB", (80, 80), color=(20, 20, 20))
        rendered = PredictionRenderer(
            RenderOptions(
                draw_heatmap=False,
                draw_head_box=False,
                draw_gaze_arrow=False,
                draw_gaze_peak=False,
                draw_labels=True,
            )
        ).render(
            image,
            [make_prediction(bbox=(0.5, 0.5, 0.7, 0.7), heatmap=None, gaze_peak=None)],
        )
        diff = np.any(np.asarray(rendered) != np.asarray(image), axis=2)
        ys, xs = np.nonzero(diff)

        self.assertGreater(len(xs), 0)
        self.assertGreaterEqual(int(xs.min()), 30)
        self.assertGreaterEqual(int(ys.min()), 20)

    def test_gaze_peak_draws_red_x(self):
        image = Image.new("RGB", (21, 21), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction(bbox=None, heatmap=None, gaze_peak=(0.5, 0.5))],
            draw_heatmap=False,
            draw_head_box=False,
            draw_gaze_arrow=False,
            draw_labels=False,
        )
        pixels = rendered.load()
        red_pixels = 0
        for y in range(21):
            for x in range(21):
                if pixels[x, y] == PEAK_MARKER_COLOR:
                    red_pixels += 1

        self.assertGreater(red_pixels, 0)

    def test_gaze_arrow_draws_from_bbox_center_to_peak(self):
        image = Image.new("RGB", (40, 40), color=(20, 20, 20))
        prediction = make_prediction(
            bbox=(0.1, 0.1, 0.3, 0.3),
            heatmap=None,
            gaze_peak=(0.8, 0.8),
        )
        color = stable_color_for_person(prediction.person_id)
        rendered = render_predictions(
            image,
            [prediction],
            draw_heatmap=False,
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_gaze_arrow=True,
            draw_labels=False,
        )
        pixels = rendered.load()

        self.assertEqual(pixels[8, 8], color)
        self.assertEqual(pixels[20, 20], color)

    def test_gaze_arrow_not_drawn_without_bbox(self):
        image = Image.new("RGB", (20, 20), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction(bbox=None, heatmap=None, gaze_peak=(0.8, 0.8))],
            draw_heatmap=False,
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_gaze_arrow=True,
            draw_labels=False,
        )

        self.assertEqual(rendered.tobytes(), image.tobytes())

    def test_label_contains_peak_value(self):
        label = build_prediction_label(
            make_prediction(person_id=3, inout_score=0.94, heatmap=None)
        )

        self.assertIn("id=3", label)
        self.assertIn("inout=0.94", label)
        self.assertIn("peak=1.00", label)

    def test_heatmap_topk_mask(self):
        mask = heatmap_to_topk_mask(
            torch.tensor([[0.1, 0.2], [0.3, 10.0]]),
            quantile=0.90,
        )

        self.assertFalse(mask[0, 0])
        self.assertFalse(mask[0, 1])
        self.assertTrue(mask[1, 1])

    def test_heatmap_topk_mask_constant_returns_empty(self):
        mask = heatmap_to_topk_mask(torch.ones(3, 3), quantile=0.90)

        self.assertFalse(mask.any())

    def test_heatmap_contour_draws_boundary_for_full_edge_region(self):
        overlay = heatmap_mask_to_contour_overlay(
            np.ones((3, 3), dtype=bool),
            image_width=12,
            image_height=12,
            color=(255, 255, 0),
            width=1,
        )
        alpha = np.asarray(overlay)[:, :, 3]

        self.assertGreater(int((alpha > 0).sum()), 0)

    def test_heatmap_contour_width_increases_visible_pixels(self):
        mask = np.zeros((5, 5), dtype=bool)
        mask[1:4, 1:4] = True
        narrow = heatmap_mask_to_contour_overlay(mask, 25, 25, (255, 255, 0), width=1)
        wide = heatmap_mask_to_contour_overlay(mask, 25, 25, (255, 255, 0), width=5)
        narrow_pixels = int((np.asarray(narrow)[:, :, 3] > 0).sum())
        wide_pixels = int((np.asarray(wide)[:, :, 3] > 0).sum())

        self.assertGreater(wide_pixels, narrow_pixels)

    def test_heatmap_contour_changes_output(self):
        image = Image.new("RGB", (20, 20), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction(bbox=None, gaze_peak=None)],
            draw_heatmap=False,
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_gaze_arrow=False,
            draw_heatmap_contour=True,
            draw_labels=False,
        )

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_heatmap_contour_changes_output_with_heatmap_off(self):
        image = Image.new("RGB", (20, 20), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction(bbox=None, gaze_peak=None)],
            draw_heatmap=False,
            draw_head_box=False,
            draw_gaze_peak=False,
            draw_gaze_arrow=False,
            draw_heatmap_contour=True,
            draw_labels=False,
        )

        self.assertNotEqual(rendered.tobytes(), image.tobytes())

    def test_invalid_heatmap_contour_quantile_raises(self):
        for quantile in (-0.1, 1.1, float("nan")):
            with self.subTest(quantile=quantile):
                with self.assertRaisesRegex(ValueError, "quantile"):
                    heatmap_to_topk_mask(torch.ones(2, 2), quantile=quantile)

    def test_prediction_with_bbox_draws_something(self):
        image = Image.new("RGB", (12, 10), color=(20, 20, 20))
        rendered = render_predictions(
            image,
            [make_prediction(heatmap=None, gaze_peak=None)],
            draw_head_box=True,
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
