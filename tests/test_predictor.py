import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from PIL import Image

from gazelle.runtime.contracts import HeadObservation
from gazelle.runtime.predictor import GazellePredictor, prepare_head_bboxes, validate_and_clip_bbox


class RecordingTransform:
    def __init__(self):
        self.calls = []

    def __call__(self, image):
        self.calls.append(image)
        return torch.zeros(3, 4, 4)


class FakeGazelleModel:
    def __init__(self, include_inout=True):
        self.include_inout = include_inout
        self.calls = []
        self.loaded_state = None
        self.strict_load = None
        self.to_device = None
        self.eval_called = False

    def to(self, device):
        self.to_device = str(device)
        return self

    def eval(self):
        self.eval_called = True
        return self

    def get_gazelle_state_dict(self, include_backbone=False):
        state = {"decoder.weight": torch.zeros(1)}
        if include_backbone:
            state["backbone.weight"] = torch.zeros(1)
        return state

    def state_dict(self):
        return {
            "backbone.weight": torch.ones(1),
            "decoder.weight": torch.ones(1),
        }

    def load_state_dict(self, state_dict, strict=False):
        if strict and set(state_dict) != set(self.state_dict()):
            raise AssertionError("strict load received wrong keys")
        self.loaded_state = dict(state_dict)
        self.strict_load = strict

    def __call__(self, model_input):
        self.calls.append(model_input)
        people_count = len(model_input["bboxes"][0])
        heatmaps = torch.zeros(people_count, 2, 3)
        for index in range(people_count):
            heatmaps[index, index % 2, (index + 1) % 3] = 0.5 + index
        output = {"heatmap": [heatmaps], "inout": None}
        if self.include_inout:
            output["inout"] = [torch.arange(people_count, dtype=torch.float32) / 10.0]
        return output


class GazellePredictorTest(unittest.TestCase):
    def make_predictor(self, include_inout=True):
        model = FakeGazelleModel(include_inout=include_inout)
        transform = RecordingTransform()
        predictor = GazellePredictor(
            model_name="gazelle_dinov2_vitb14_inout",
            model=model,
            transform=transform,
            device="cpu",
        )
        return predictor, model, transform

    def test_no_heads_returns_empty_without_transform_or_model_call(self):
        predictor, model, transform = self.make_predictor()
        frame = Image.new("RGB", (8, 6))

        self.assertEqual(predictor.predict_frame(frame, []), [])
        self.assertEqual(transform.calls, [])
        self.assertEqual(model.calls, [])

    def test_single_none_bbox_uses_gazelle_no_bbox_mode(self):
        predictor, model, _ = self.make_predictor()
        frame = Image.new("RGB", (8, 6))

        predictions = predictor.predict_frame(frame, [HeadObservation(person_id=7, bbox=None)])

        self.assertEqual(model.calls[0]["bboxes"], [[None]])
        self.assertEqual(len(predictions), 1)
        self.assertEqual(predictions[0].person_id, 7)
        self.assertIsNone(predictions[0].bbox)
        self.assertEqual(predictions[0].gaze_peak, (1 / 3.0, 0.0))
        self.assertEqual(predictions[0].heatmap_peak_value, 0.5)
        self.assertEqual(predictions[0].inout_score, 0.0)
        self.assertEqual(tuple(predictions[0].heatmap.shape), (2, 3))

    def test_multi_person_requires_bbox_for_every_head(self):
        predictor, model, transform = self.make_predictor()
        frame = Image.new("RGB", (8, 6))

        with self.assertRaisesRegex(ValueError, "requires a valid bbox"):
            predictor.predict_frame(
                frame,
                [
                    HeadObservation(person_id=1, bbox=(0.1, 0.1, 0.2, 0.2)),
                    HeadObservation(person_id=2, bbox=None),
                ],
            )

        self.assertEqual(model.calls, [])
        self.assertEqual(transform.calls, [])

    def test_bbox_is_clipped_before_model_call_and_output_order_is_preserved(self):
        predictor, model, _ = self.make_predictor()
        frame = Image.new("RGB", (8, 6))
        heads = [
            HeadObservation(person_id=10, bbox=(-0.2, 0.1, 0.3, 0.9)),
            HeadObservation(person_id=4, bbox=(0.4, -0.2, 1.3, 0.5)),
        ]

        predictions = predictor.predict_frame(frame, heads)

        self.assertEqual(
            model.calls[0]["bboxes"],
            [[(0.0, 0.1, 0.3, 0.9), (0.4, 0.0, 1.0, 0.5)]],
        )
        self.assertEqual([prediction.person_id for prediction in predictions], [10, 4])
        self.assertEqual([prediction.bbox for prediction in predictions], model.calls[0]["bboxes"][0])
        self.assertEqual(predictions[1].gaze_peak, (2 / 3.0, 1 / 2.0))
        self.assertEqual(predictions[1].heatmap_peak_value, 1.5)
        self.assertAlmostEqual(predictions[1].inout_score, 0.1)

    def test_bbox_validation_rejects_invalid_values(self):
        invalid_bboxes = [
            (0.5, 0.1, 0.2, 0.4),
            (0.1, 0.5, 0.4, 0.2),
            (2.0, 0.1, 3.0, 0.4),
            (0.0, 0.0, float("nan"), 1.0),
            (0.0, 0.0, True, 1.0),
        ]
        for bbox in invalid_bboxes:
            with self.subTest(bbox=bbox):
                with self.assertRaises(ValueError):
                    validate_and_clip_bbox(bbox)

    def test_prepare_head_bboxes_accepts_single_none_bbox(self):
        prepared_heads, model_bboxes = prepare_head_bboxes([HeadObservation(person_id=5, bbox=None)])

        self.assertEqual(prepared_heads[0].person_id, 5)
        self.assertEqual(model_bboxes, [None])

    def test_from_checkpoint_loads_prepared_checkpoint_with_mocked_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "model.pt"
            torch.save({"decoder.weight": torch.ones(1)}, checkpoint)
            fake_model = FakeGazelleModel()
            fake_transform = RecordingTransform()
            fake_module = types.ModuleType("gazelle.model")
            fake_module.get_gazelle_model = lambda model_name: (fake_model, fake_transform)

            with patch.dict(sys.modules, {"gazelle.model": fake_module}):
                predictor = GazellePredictor.from_checkpoint(
                    "gazelle_dinov2_vitb14_inout",
                    checkpoint,
                    device="cpu",
                    cache_dir=tmpdir,
                )

            self.assertIs(predictor.model, fake_model)
            self.assertIs(predictor.transform, fake_transform)
            self.assertTrue(fake_model.strict_load)
            self.assertTrue(fake_model.eval_called)
            self.assertEqual(fake_model.to_device, "cpu")
            self.assertIn("decoder.weight", fake_model.loaded_state)
            self.assertTrue((Path(tmpdir) / "torch_hub").exists())


if __name__ == "__main__":
    unittest.main()
