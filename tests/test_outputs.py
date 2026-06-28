import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import torch

from gazelle.runtime.contracts import GazePrediction, HeadObservation
from gazelle.runtime.outputs import (
    prediction_to_json_dict,
    save_prediction_heatmaps,
    write_predictions_json,
    write_run_config_json,
)


def make_prediction(person_id=1, bbox=(0.1, 0.2, 0.3, 0.4), inout_score=0.88):
    return GazePrediction(
        person_id=person_id,
        bbox=bbox,
        heatmap=torch.tensor([[0.1, 0.2], [0.9, 0.3]]),
        gaze_peak=(0.5, 0.5),
        heatmap_peak_value=0.9,
        inout_score=inout_score,
    )


class OutputsTest(unittest.TestCase):
    def test_prediction_to_json_dict(self):
        record = prediction_to_json_dict(make_prediction(), heatmap_path="heatmaps/person_1.pt")

        self.assertEqual(record["person_id"], 1)
        self.assertEqual(record["bbox_normalized"], [0.1, 0.2, 0.3, 0.4])
        self.assertEqual(record["gaze_peak_normalized"], [0.5, 0.5])
        self.assertEqual(record["heatmap_peak_value"], 0.9)
        self.assertEqual(record["inout_score"], 0.88)
        self.assertEqual(record["heatmap_path"], "heatmaps/person_1.pt")

    def test_write_predictions_json(self):
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "predictions.json"
            write_predictions_json(
                output_path,
                input_path="samples/frame.jpg",
                image_width=640,
                image_height=480,
                model_name="gazelle_dinov2_vitb14_inout",
                heads=(HeadObservation(person_id=1, bbox=(0.1, 0.2, 0.3, 0.4)),),
                predictions=(make_prediction(),),
                heatmap_paths=("heatmaps/person_1.pt",),
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["input"], "samples/frame.jpg")
        self.assertEqual(payload["width"], 640)
        self.assertEqual(payload["height"], 480)
        self.assertEqual(payload["model"], "gazelle_dinov2_vitb14_inout")
        self.assertEqual(payload["people"][0]["heatmap_path"], "heatmaps/person_1.pt")

    def test_write_predictions_json_handles_none_bbox_and_none_inout(self):
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "predictions.json"
            prediction = make_prediction(bbox=None, inout_score=None)
            write_predictions_json(
                output_path,
                input_path="samples/frame.jpg",
                image_width=12,
                image_height=10,
                model_name="gazelle_dinov2_vitb14",
                heads=(HeadObservation(person_id=1, bbox=None),),
                predictions=(prediction,),
            )
            person = json.loads(output_path.read_text(encoding="utf-8"))["people"][0]

        self.assertIsNone(person["bbox_normalized"])
        self.assertIsNone(person["inout_score"])
        self.assertNotIn("heatmap_path", person)

    def test_write_predictions_json_rejects_head_prediction_mismatch(self):
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "predictions.json"
            with self.assertRaisesRegex(ValueError, "predictions length"):
                write_predictions_json(
                    output_path,
                    input_path="samples/frame.jpg",
                    image_width=12,
                    image_height=10,
                    model_name="gazelle_dinov2_vitb14",
                    heads=(),
                    predictions=(make_prediction(),),
                )

    def test_save_prediction_heatmaps(self):
        with TemporaryDirectory() as tmpdir:
            heatmaps_dir = Path(tmpdir) / "heatmaps"
            paths = save_prediction_heatmaps(heatmaps_dir, (make_prediction(),))
            saved_path = heatmaps_dir / "person_1.pt"
            try:
                loaded = torch.load(saved_path, map_location="cpu", weights_only=True)
            except TypeError:
                loaded = torch.load(saved_path, map_location="cpu")

        self.assertEqual(paths, ["heatmaps/person_1.pt"])
        self.assertTrue(torch.equal(loaded, make_prediction().heatmap))

    def test_write_run_config_json(self):
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "run_config.json"
            write_run_config_json(
                output_path,
                {
                    "input_path": Path("samples/frame.jpg"),
                    "bboxes": ((0.1, 0.2, 0.3, 0.4),),
                },
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["input_path"], str(Path("samples") / "frame.jpg"))
        self.assertEqual(payload["bboxes"], [[0.1, 0.2, 0.3, 0.4]])


if __name__ == "__main__":
    unittest.main()
