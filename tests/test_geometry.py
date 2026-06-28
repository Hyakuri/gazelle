import unittest

from gazelle.runtime.geometry import (
    normalized_bbox_to_pixel,
    pixel_bbox_to_normalized,
    sanitize_head_bbox_for_model,
    sanitize_normalized_bbox,
)


class GeometryTest(unittest.TestCase):
    def test_valid_normalized_bbox(self):
        self.assertEqual(
            sanitize_normalized_bbox((0.1, 0.2, 0.3, 0.4)),
            (0.1, 0.2, 0.3, 0.4),
        )

    def test_valid_pixel_bbox_to_normalized(self):
        self.assertEqual(
            pixel_bbox_to_normalized((10, 20, 30, 40), image_width=100, image_height=200),
            (0.1, 0.1, 0.3, 0.2),
        )

    def test_out_of_bounds_normalized_bbox_is_clipped(self):
        self.assertEqual(
            sanitize_normalized_bbox((-0.1, 0.2, 1.2, 0.8)),
            (0.0, 0.2, 1.0, 0.8),
        )

    def test_out_of_bounds_pixel_bbox_is_clipped(self):
        self.assertEqual(
            pixel_bbox_to_normalized((-10, 20, 120, 220), image_width=100, image_height=200),
            (0.0, 0.1, 1.0, 1.0),
        )

    def test_normalized_bbox_to_pixel_stays_inside_image_bounds(self):
        self.assertEqual(
            normalized_bbox_to_pixel((-0.1, 0.25, 1.2, 0.75), image_width=100, image_height=200),
            (0.0, 50.0, 100.0, 150.0),
        )

    def test_bbox_length_must_be_four(self):
        with self.assertRaisesRegex(ValueError, "four"):
            sanitize_normalized_bbox((0.1, 0.2, 0.3))

    def test_bbox_must_be_iterable(self):
        with self.assertRaisesRegex(ValueError, "iterable"):
            sanitize_normalized_bbox(3.14)

    def test_string_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite real"):
            sanitize_normalized_bbox(("0", 0.1, 0.2, 0.3))

    def test_nan_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite real"):
            sanitize_normalized_bbox((0.0, 0.1, float("nan"), 0.3))

    def test_inf_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite real"):
            sanitize_normalized_bbox((0.0, 0.1, float("inf"), 0.3))

    def test_bool_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite real"):
            sanitize_normalized_bbox((0.0, 0.1, True, 0.3))

    def test_xmin_must_be_less_than_xmax(self):
        with self.assertRaisesRegex(ValueError, "xmin < xmax"):
            sanitize_normalized_bbox((0.5, 0.1, 0.5, 0.3))

    def test_ymin_must_be_less_than_ymax(self):
        with self.assertRaisesRegex(ValueError, "ymin < ymax"):
            sanitize_normalized_bbox((0.1, 0.5, 0.3, 0.5))

    def test_empty_after_clipping_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty after clipping"):
            sanitize_normalized_bbox((1.1, 0.1, 1.2, 0.3))

    def test_tiny_bbox_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "min_size"):
            sanitize_normalized_bbox((0.1, 0.1, 0.1000001, 0.3), min_size=1e-4)

    def test_image_width_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "image_width"):
            pixel_bbox_to_normalized((0, 0, 1, 1), image_width=0, image_height=100)
        with self.assertRaisesRegex(ValueError, "image_width"):
            normalized_bbox_to_pixel((0, 0, 1, 1), image_width=0, image_height=100)

    def test_image_height_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "image_height"):
            pixel_bbox_to_normalized((0, 0, 1, 1), image_width=100, image_height=0)
        with self.assertRaisesRegex(ValueError, "image_height"):
            normalized_bbox_to_pixel((0, 0, 1, 1), image_width=100, image_height=0)

    def test_sanitize_head_bbox_for_model_allows_none(self):
        self.assertIsNone(sanitize_head_bbox_for_model(None))

    def test_sanitize_head_bbox_for_model_sanitizes_bbox(self):
        self.assertEqual(
            sanitize_head_bbox_for_model((-0.1, 0.2, 0.4, 1.2)),
            (0.0, 0.2, 0.4, 1.0),
        )


if __name__ == "__main__":
    unittest.main()
