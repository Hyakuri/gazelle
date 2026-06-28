import json
import tempfile
import unittest
from pathlib import Path

from gazelle.runtime.contracts import HeadObservation
from gazelle.runtime.heads import (
    JsonHeadProvider,
    NoneHeadProvider,
    StaticHeadProvider,
    load_json_head_provider,
)


class HeadProvidersTest(unittest.TestCase):
    def test_none_head_provider_returns_single_none_bbox(self):
        heads = NoneHeadProvider().get_heads(None, 0, 0.0, 640, 480)

        self.assertEqual(heads, (HeadObservation(person_id=0, bbox=None, confidence=None),))

    def test_none_head_provider_uses_custom_person_id(self):
        heads = NoneHeadProvider(person_id=42).get_heads(None, 0, 0.0, 640, 480)

        self.assertEqual(heads[0].person_id, 42)
        self.assertIsNone(heads[0].bbox)

    def test_static_normalized_single_bbox(self):
        heads = StaticHeadProvider((0.1, 0.2, 0.3, 0.4)).get_heads(None, 0, 0.0, 640, 480)

        self.assertEqual(heads, (HeadObservation(person_id=0, bbox=(0.1, 0.2, 0.3, 0.4)),))

    def test_static_normalized_multiple_bboxes(self):
        heads = StaticHeadProvider([(0.1, 0.2, 0.3, 0.4), (0.5, 0.6, 0.7, 0.8)]).get_heads(
            None,
            0,
            0.0,
            640,
            480,
        )

        self.assertEqual([head.bbox for head in heads], [(0.1, 0.2, 0.3, 0.4), (0.5, 0.6, 0.7, 0.8)])

    def test_static_pixel_bbox_to_normalized(self):
        heads = StaticHeadProvider((100, 80, 220, 230), bbox_format="pixel").get_heads(
            None,
            0,
            0.0,
            400,
            300,
        )

        self.assertEqual(heads[0].bbox, (0.25, 80 / 300.0, 0.55, 230 / 300.0))

    def test_static_assigns_default_person_ids(self):
        heads = StaticHeadProvider([(0.1, 0.2, 0.3, 0.4), (0.5, 0.6, 0.7, 0.8)]).get_heads(
            None,
            0,
            0.0,
            640,
            480,
        )

        self.assertEqual([head.person_id for head in heads], [0, 1])

    def test_static_uses_provided_person_ids(self):
        heads = StaticHeadProvider([(0.1, 0.2, 0.3, 0.4)], person_ids=[9]).get_heads(None, 0, 0.0, 640, 480)

        self.assertEqual(heads[0].person_id, 9)

    def test_static_uses_confidences(self):
        heads = StaticHeadProvider([(0.1, 0.2, 0.3, 0.4)], confidences=[0.75]).get_heads(None, 0, 0.0, 640, 480)

        self.assertEqual(heads[0].confidence, 0.75)

    def test_static_rejects_empty_bboxes(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            StaticHeadProvider([])

    def test_static_rejects_invalid_bbox_format(self):
        with self.assertRaisesRegex(ValueError, "bbox_format"):
            StaticHeadProvider((0.1, 0.2, 0.3, 0.4), bbox_format="xywh")

    def test_static_rejects_person_id_length_mismatch(self):
        with self.assertRaisesRegex(ValueError, "person_ids length"):
            StaticHeadProvider([(0.1, 0.2, 0.3, 0.4)], person_ids=[1, 2])

    def test_static_rejects_confidence_length_mismatch(self):
        with self.assertRaisesRegex(ValueError, "confidences length"):
            StaticHeadProvider([(0.1, 0.2, 0.3, 0.4)], confidences=[0.5, 0.6])

    def test_static_rejects_invalid_person_id(self):
        with self.assertRaisesRegex(ValueError, "person_id"):
            StaticHeadProvider([(0.1, 0.2, 0.3, 0.4)], person_ids=[True])

    def test_static_rejects_invalid_confidence(self):
        for confidence in (True, float("nan"), float("inf"), "0.5"):
            with self.subTest(confidence=confidence):
                with self.assertRaisesRegex(ValueError, "confidence"):
                    StaticHeadProvider([(0.1, 0.2, 0.3, 0.4)], confidences=[confidence])

    def test_static_rejects_invalid_bbox_with_index(self):
        provider = StaticHeadProvider((2.0, 0.2, 3.0, 0.4))

        with self.assertRaisesRegex(ValueError, "index 0"):
            provider.get_heads(None, 0, 0.0, 640, 480)

    def test_json_image_record_defaults_to_frame_zero(self):
        provider = JsonHeadProvider(
            {
                "bbox_format": "pixel",
                "heads": [{"person_id": 3, "bbox": [100, 80, 220, 230], "confidence": 0.97}],
            }
        )

        heads = provider.get_heads(None, 0, 0.0, 400, 300)

        self.assertEqual(len(heads), 1)
        self.assertEqual(heads[0].person_id, 3)
        self.assertEqual(heads[0].bbox, (0.25, 80 / 300.0, 0.55, 230 / 300.0))
        self.assertEqual(heads[0].confidence, 0.97)

    def test_jsonl_video_records_by_frame_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "heads.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "frame_index": 0,
                                "timestamp_ms": 0.0,
                                "bbox_format": "pixel",
                                "heads": [{"person_id": 3, "bbox": [100, 80, 220, 230]}],
                            }
                        ),
                        "",
                        json.dumps(
                            {
                                "frame_index": 1,
                                "timestamp_ms": 33.33,
                                "bbox_format": "pixel",
                                "heads": [{"person_id": 4, "bbox": [102, 81, 222, 231]}],
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            provider = load_json_head_provider(path)
            heads = provider.get_heads(None, 1, 33.33, 400, 300)

        self.assertEqual(heads[0].person_id, 4)
        self.assertEqual(heads[0].bbox, (102 / 400.0, 81 / 300.0, 222 / 400.0, 231 / 300.0))

    def test_json_list_records(self):
        provider = JsonHeadProvider(
            [
                {
                    "frame_index": 0,
                    "bbox_format": "normalized",
                    "heads": [{"person_id": 1, "bbox": [0.1, 0.1, 0.2, 0.3]}],
                },
                {"frame_index": 1, "bbox_format": "normalized", "heads": []},
            ]
        )

        self.assertEqual(provider.get_heads(None, 0, 0.0, 640, 480)[0].person_id, 1)
        self.assertEqual(provider.get_heads(None, 1, 33.33, 640, 480), ())

    def test_json_missing_frame_returns_empty_tuple(self):
        provider = JsonHeadProvider({"heads": []})

        self.assertEqual(provider.get_heads(None, 5, 0.0, 640, 480), ())

    def test_json_duplicate_frame_index_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate frame_index 0"):
            JsonHeadProvider([{"frame_index": 0, "heads": []}, {"frame_index": 0, "heads": []}])

    def test_json_malformed_line_reports_line_number(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "heads.jsonl"
            path.write_text('{"frame_index": 0, "heads": []}\n{"frame_index":', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "line 2"):
                load_json_head_provider(path)

    def test_json_head_missing_person_id_uses_index(self):
        provider = JsonHeadProvider({"heads": [{"bbox": [0.1, 0.1, 0.2, 0.2]}, {"bbox": [0.3, 0.3, 0.4, 0.4]}]})

        heads = provider.get_heads(None, 0, 0.0, 640, 480)

        self.assertEqual([head.person_id for head in heads], [0, 1])

    def test_json_head_level_bbox_format_override(self):
        provider = JsonHeadProvider(
            {
                "bbox_format": "pixel",
                "heads": [{"bbox_format": "normalized", "bbox": [0.1, 0.2, 0.3, 0.4]}],
            }
        )

        heads = provider.get_heads(None, 0, 0.0, 640, 480)

        self.assertEqual(heads[0].bbox, (0.1, 0.2, 0.3, 0.4))

    def test_json_pixel_bbox_converted_using_image_size(self):
        provider = JsonHeadProvider({"bbox_format": "pixel", "heads": [{"bbox": [10, 20, 30, 40]}]})

        heads = provider.get_heads(None, 0, 0.0, 100, 200)

        self.assertEqual(heads[0].bbox, (0.1, 0.1, 0.3, 0.2))

    def test_json_normalized_bbox_sanitized(self):
        provider = JsonHeadProvider({"heads": [{"bbox": [-0.1, 0.2, 1.2, 0.4]}]})

        heads = provider.get_heads(None, 0, 0.0, 100, 200)

        self.assertEqual(heads[0].bbox, (0.0, 0.2, 1.0, 0.4))

    def test_json_rejects_invalid_frame_index(self):
        with self.assertRaisesRegex(ValueError, "frame_index"):
            JsonHeadProvider([{"frame_index": True, "heads": []}])
        with self.assertRaisesRegex(ValueError, "frame_index"):
            JsonHeadProvider([{"frame_index": -1, "heads": []}])

    def test_json_rejects_invalid_heads_field(self):
        with self.assertRaisesRegex(ValueError, "heads"):
            JsonHeadProvider({"heads": {}})
        with self.assertRaisesRegex(ValueError, "heads"):
            JsonHeadProvider({"bbox_format": "normalized"})

    def test_json_rejects_invalid_confidence(self):
        provider = JsonHeadProvider({"heads": [{"bbox": [0.1, 0.1, 0.2, 0.2], "confidence": float("inf")}]})

        with self.assertRaisesRegex(ValueError, "head 0 invalid confidence"):
            provider.get_heads(None, 0, 0.0, 100, 100)

    def test_json_allows_empty_heads(self):
        provider = JsonHeadProvider({"heads": []})

        self.assertEqual(provider.get_heads(None, 0, 0.0, 100, 100), ())

    def test_json_allows_none_bbox(self):
        provider = JsonHeadProvider({"heads": [{"person_id": 2, "bbox": None}]})

        heads = provider.get_heads(None, 0, 0.0, 100, 100)

        self.assertEqual(heads, (HeadObservation(person_id=2, bbox=None, confidence=None),))


if __name__ == "__main__":
    unittest.main()
