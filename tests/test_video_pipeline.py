import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np
import torch

from gazelle.runtime.config import RuntimeConfig
from gazelle.runtime.contracts import GazePrediction
from gazelle.runtime.media import VideoFrameReader
from gazelle.runtime.pipeline import run_video_pipeline


class FakePredictor:
    def __init__(self):
        self.calls = []

    def predict_frame(self, image, heads):
        heads = tuple(heads)
        self.calls.append((image, heads))
        predictions = []
        for index, head in enumerate(heads):
            predictions.append(
                GazePrediction(
                    person_id=head.person_id,
                    bbox=head.bbox,
                    heatmap=torch.tensor([[0.1, 0.2], [0.8 + index, 0.3]]),
                    gaze_peak=(0.25, 0.75),
                    heatmap_peak_value=float(0.8 + index),
                    inout_score=0.9,
                )
            )
        return predictions


def write_tiny_video(path, width=32, height=24, fps=5.0, frame_count=3):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Failed to create test video: {}".format(path))
    try:
        for index in range(frame_count):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :, 0] = 20 + index
            frame[:, :, 1] = 40 + index
            frame[:, :, 2] = 60 + index
            writer.write(frame)
    finally:
        writer.release()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def make_config(**overrides):
    values = {
        "input_path": "clip.mp4",
        "output_dir": "outputs",
        "head_source": "none",
    }
    values.update(overrides)
    return RuntimeConfig(**values).validate()


class VideoPipelineTest(unittest.TestCase):
    def test_run_video_pipeline_none_head_source_writes_jsonl(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=3)
            fake = FakePredictor()
            config = make_config(input_path=str(video_path), output_dir=str(Path(tmpdir) / "outputs"))

            result = run_video_pipeline(config, predictor_factory=lambda config: fake)
            rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual(len(rows), 3)
        self.assertEqual([row["status"] for row in rows], ["ok", "ok", "ok"])
        self.assertEqual(len(fake.calls), 3)

    def test_run_video_pipeline_static_head_source(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            fake = FakePredictor()
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                head_source="static",
                bboxes=((0.1, 0.2, 0.3, 0.4),),
                person_ids=(7,),
            )

            run_video_pipeline(config, predictor_factory=lambda config: fake)

        self.assertEqual(fake.calls[0][1][0].person_id, 7)
        self.assertEqual(fake.calls[0][1][0].bbox, (0.1, 0.2, 0.3, 0.4))

    def test_run_video_pipeline_json_head_source_missing_frame_no_head(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=2)
            head_data = Path(tmpdir) / "heads.json"
            head_data.write_text(
                json.dumps(
                    [
                        {
                            "frame_index": 0,
                            "bbox_format": "normalized",
                            "heads": [{"person_id": 3, "bbox": [0.1, 0.2, 0.3, 0.4]}],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            fake = FakePredictor()
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                head_source="json",
                head_data=str(head_data),
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: fake)
            rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual([row["status"] for row in rows], ["ok", "no_head"])
        self.assertEqual(len(fake.calls), 1)

    def test_run_video_pipeline_max_frames(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=5)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                max_frames=2,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())
            rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual(result.frames_written, 2)
        self.assertEqual(len(rows), 2)

    def test_run_video_pipeline_frame_step(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=4)
            fake = FakePredictor()
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                frame_step=2,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: fake)
            rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual([row["status"] for row in rows], ["ok", "skipped", "ok", "skipped"])
        self.assertEqual(len(fake.calls), 2)

    def test_run_video_pipeline_saves_rendered_video_when_enabled(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=3)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                save_rendered=True,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())
            rendered_exists = result.rendered_video_path.exists()
            with VideoFrameReader(result.rendered_video_path) as reader:
                rendered_frames = list(reader)

        self.assertIsNotNone(result.rendered_video_path)
        self.assertTrue(rendered_exists)
        self.assertEqual(len(rendered_frames), result.frames_written)

    def test_run_video_pipeline_passes_enhanced_render_options(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=2)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                head_source="static",
                bboxes=((0.1, 0.2, 0.4, 0.6),),
                save_rendered=True,
                draw_heatmap=False,
                draw_gaze_arrow=False,
                draw_heatmap_contour=True,
                draw_labels=False,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())

            self.assertIsNotNone(result.rendered_video_path)
            self.assertTrue(result.rendered_video_path.exists())

    def test_run_video_pipeline_does_not_save_rendered_by_default(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            config = make_config(input_path=str(video_path), output_dir=str(Path(tmpdir) / "outputs"))

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())

        self.assertIsNone(result.rendered_video_path)

    def test_run_video_pipeline_rejects_save_heatmaps(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            factory_calls = []

            def fail_if_called(config):
                factory_calls.append(config)
                raise AssertionError("predictor should not be constructed")

            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                save_heatmaps=True,
            )

            with self.assertRaisesRegex(ValueError, "video heatmap export"):
                run_video_pipeline(config, predictor_factory=fail_if_called)

        self.assertEqual(factory_calls, [])

    def test_run_video_pipeline_existing_output_dir_rejects_before_predictor(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            output_dir = Path(tmpdir) / "outputs"
            existing_output = output_dir / "clip_gazelle"
            existing_output.mkdir(parents=True)
            factory_calls = []

            def fail_if_called(config):
                factory_calls.append(config)
                raise AssertionError("predictor should not be constructed")

            config = make_config(input_path=str(video_path), output_dir=str(output_dir))

            with self.assertRaises(FileExistsError):
                run_video_pipeline(config, predictor_factory=fail_if_called)

        self.assertEqual(factory_calls, [])
        self.assertFalse((existing_output / "predictions.jsonl").exists())
        self.assertFalse((existing_output / "run_config.json").exists())

    def test_run_video_pipeline_builds_predictor_once(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=3)
            factory_calls = []
            fake = FakePredictor()

            def factory(config):
                factory_calls.append(config)
                return fake

            config = make_config(input_path=str(video_path), output_dir=str(Path(tmpdir) / "outputs"))

            run_video_pipeline(config, predictor_factory=factory)

        self.assertEqual(len(factory_calls), 1)
        self.assertEqual(len(fake.calls), 3)

    def test_run_video_pipeline_jsonl_rows_match_frames_written(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=4)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                frame_step=2,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())
            rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual(len(rows), result.frames_written)


if __name__ == "__main__":
    unittest.main()
