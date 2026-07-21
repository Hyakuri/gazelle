import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import torch

from gazelle.runtime.contracts import GazePrediction, HeadObservation
from gazelle.runtime.perception.contracts import (
    HeadFrameResult,
    HeadPerception,
    HeadPerceptionState,
    HeadPoseAngles,
    HeadViewState,
    NormalizedLandmark,
)
from gazelle.runtime.perception.outputs import (
    head_frame_to_json_dict,
    write_head_observations_json,
)
from gazelle.runtime.outputs import (
    JsonlWriter,
    append_jsonl,
    prediction_frame_to_json_dict,
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


def make_rich_head_result():
    face_landmarks = tuple(
        NormalizedLandmark(x=index / 1000.0, y=index / 2000.0, z=-index / 3000.0)
        for index in range(478)
    )
    perception = HeadPerception(
        person_id=7,
        head_bbox=(0.1, 0.2, 0.3, 0.4),
        face_bbox=(0.11, 0.21, 0.29, 0.39),
        confidence=0.91,
        state=HeadPerceptionState.FACE_POSE,
        view_state=HeadViewState.FRONTAL,
        observed=True,
        track_age_frames=12,
        missed_frames=1,
        missed_ms=33.3,
        face_keypoints=(
            NormalizedLandmark(x=0.2, y=0.3),
            NormalizedLandmark(x=0.4, y=0.5, visibility=0.6),
        ),
        pose_head_landmarks=(
            NormalizedLandmark(x=0.6, y=0.7, presence=0.8),
            NormalizedLandmark(x=0.8, y=0.9, z=0.1),
        ),
        facial_transformation_matrix=((1.0, 2.0), (3.0, 4.0)),
        head_pose=HeadPoseAngles(yaw_deg=1.5, pitch_deg=-2.5, roll_deg=3.5),
        face_landmarks=face_landmarks,
    )
    return HeadFrameResult(
        heads=(HeadObservation(person_id=7, bbox=(0.1, 0.2, 0.3, 0.4), confidence=0.91),),
        perceptions=(perception,),
        timings_ms={"face": 1.25, "pose": 2.5},
    )


class OutputsTest(unittest.TestCase):
    def test_head_frame_serializes_minimal_provider_heads(self):
        record = head_frame_to_json_dict(
            frame_index=1,
            timestamp_ms=33.3,
            image_width=640,
            image_height=480,
            provider="static",
            result=HeadFrameResult(
                heads=(HeadObservation(person_id=4, bbox=(0.1, 0.2, 0.3, 0.4), confidence=0.8),),
                timings_ms={"provider": 1.0},
            ),
        )

        self.assertEqual(record["frame_index"], 1)
        self.assertEqual(record["timestamp_ms"], 33.3)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["width"], 640)
        self.assertEqual(record["height"], 480)
        self.assertEqual(record["provider"], "static")
        self.assertEqual(record["timings_ms"], {"provider": 1.0})
        self.assertEqual(
            record["people"],
            [{"person_id": 4, "head_bbox_normalized": [0.1, 0.2, 0.3, 0.4], "confidence": 0.8}],
        )

    def test_head_frame_serializes_rich_perception_without_face_landmarks_by_default(self):
        rich_result = make_rich_head_result()

        record = head_frame_to_json_dict(
            frame_index=2,
            timestamp_ms=66.6,
            image_width=640,
            image_height=480,
            provider="mediapipe",
            result=rich_result,
            save_face_landmarks=False,
        )

        person = record["people"][0]
        self.assertEqual(person["person_id"], 7)
        self.assertEqual(person["head_bbox_normalized"], [0.1, 0.2, 0.3, 0.4])
        self.assertEqual(person["face_bbox_normalized"], [0.11, 0.21, 0.29, 0.39])
        self.assertEqual(person["state"], "face_pose")
        self.assertEqual(person["view_state"], "frontal")
        self.assertTrue(person["observed"])
        self.assertEqual(person["tracking"], {"track_age_frames": 12, "missed_frames": 1, "missed_ms": 33.3})
        self.assertEqual(person["face_keypoints"][1], {"x": 0.4, "y": 0.5, "visibility": 0.6})
        self.assertEqual(person["pose_head_landmarks"][0], {"x": 0.6, "y": 0.7, "presence": 0.8})
        self.assertEqual(person["facial_transformation_matrix"], [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(person["head_pose"], {"yaw_deg": 1.5, "pitch_deg": -2.5, "roll_deg": 3.5})
        self.assertNotIn("face_landmarks", person)

    def test_head_frame_includes_all_face_landmarks_only_when_enabled(self):
        record = head_frame_to_json_dict(
            frame_index=2,
            timestamp_ms=66.6,
            image_width=640,
            image_height=480,
            provider="mediapipe",
            result=make_rich_head_result(),
            save_face_landmarks=True,
        )

        landmarks = record["people"][0]["face_landmarks"]
        self.assertEqual(len(landmarks), 478)
        self.assertEqual(landmarks[0], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(landmarks[-1], {"x": 0.477, "y": 0.2385, "z": -0.159})

    def test_head_frame_serializes_no_head_and_reuses_jsonl_writer(self):
        result = HeadFrameResult(heads=(), timings_ms={"provider": 0.5})
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "heads.jsonl"
            with JsonlWriter(output_path) as writer:
                record = write_head_observations_json(
                    writer,
                    frame_index=3,
                    timestamp_ms=100.0,
                    image_width=320,
                    image_height=240,
                    provider="mediapipe",
                    result=result,
                )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(record, payload)
        self.assertEqual(payload["status"], "no_head")
        self.assertEqual(payload["people"], [])
        self.assertEqual(payload["timings_ms"], {"provider": 0.5})

    def test_head_frame_rejects_non_finite_serialized_values(self):
        result = HeadFrameResult(
            heads=(HeadObservation(person_id=1, bbox=(0.1, float("nan"), 0.3, 0.4), confidence=0.8),),
        )

        with self.assertRaisesRegex(ValueError, "finite"):
            head_frame_to_json_dict(
                frame_index=0,
                timestamp_ms=0.0,
                image_width=10,
                image_height=8,
                provider="static",
                result=result,
            )

    def test_prediction_to_json_dict(self):
        record = prediction_to_json_dict(make_prediction(), heatmap_path="heatmaps/person_1.pt")

        self.assertEqual(record["person_id"], 1)
        self.assertEqual(record["bbox_normalized"], [0.1, 0.2, 0.3, 0.4])
        self.assertEqual(record["gaze_peak_normalized"], [0.5, 0.5])
        self.assertEqual(record["heatmap_peak_value"], 0.9)
        self.assertEqual(record["inout_score"], 0.88)
        self.assertEqual(record["heatmap_path"], "heatmaps/person_1.pt")

    def test_prediction_frame_to_json_dict_ok(self):
        record = prediction_frame_to_json_dict(
            frame_index=12,
            timestamp_ms=400.0,
            status="ok",
            image_width=640,
            image_height=480,
            predictions=(make_prediction(person_id=3),),
            inference_ms=34.2,
        )

        self.assertEqual(record["frame_index"], 12)
        self.assertEqual(record["timestamp_ms"], 400.0)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["width"], 640)
        self.assertEqual(record["height"], 480)
        self.assertEqual(record["inference_ms"], 34.2)
        self.assertEqual(record["people"][0]["person_id"], 3)
        self.assertNotIn("heatmap_path", record["people"][0])

    def test_prediction_frame_to_json_dict_no_head(self):
        record = prediction_frame_to_json_dict(
            frame_index=1,
            timestamp_ms=33.3,
            status="no_head",
            image_width=10,
            image_height=8,
            predictions=(),
        )

        self.assertEqual(record["status"], "no_head")
        self.assertEqual(record["people"], [])
        self.assertNotIn("inference_ms", record)

    def test_prediction_frame_to_json_dict_skipped(self):
        record = prediction_frame_to_json_dict(
            frame_index=2,
            timestamp_ms=66.6,
            status="skipped",
            image_width=10,
            image_height=8,
            predictions=(),
        )

        self.assertEqual(record["status"], "skipped")
        self.assertEqual(record["people"], [])

    def test_append_jsonl_writes_one_line(self):
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "predictions.jsonl"
            append_jsonl(output_path, {"frame_index": 0, "status": "ok"})
            lines = output_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["status"], "ok")

    def test_jsonl_writer_context_manager(self):
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "predictions.jsonl"
            with JsonlWriter(output_path) as writer:
                writer.write({"frame_index": 0, "status": "ok"})
                writer.write({"frame_index": 1, "status": "skipped"})
            lines = output_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual([json.loads(line)["status"] for line in lines], ["ok", "skipped"])

    def test_jsonl_people_records_reuse_prediction_schema(self):
        record = prediction_frame_to_json_dict(
            frame_index=0,
            timestamp_ms=0.0,
            status="ok",
            image_width=10,
            image_height=8,
            predictions=(make_prediction(person_id=5, bbox=None, inout_score=None),),
        )
        person = record["people"][0]

        self.assertEqual(person["person_id"], 5)
        self.assertIsNone(person["bbox_normalized"])
        self.assertIsNone(person["inout_score"])

    def test_prediction_frame_to_json_dict_serializes_error(self):
        record = prediction_frame_to_json_dict(
            frame_index=0,
            timestamp_ms=0.0,
            status="error",
            image_width=10,
            image_height=8,
            predictions=(),
            inference_ms=12.5,
            error="failed",
        )

        self.assertEqual(record["status"], "error")
        self.assertEqual(record["inference_ms"], 12.5)
        self.assertEqual(record["error"], "failed")

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
