import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np
import torch

from gazelle.runtime.config import RuntimeConfig
from gazelle.runtime.contracts import GazePrediction
from gazelle.runtime.media import VideoFrameReader
from gazelle.runtime.pipeline import build_head_provider_from_config, run_video_pipeline
from gazelle.runtime.perception.provider import MediaPipeHeadProvider


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


class FakeHeadProvider:
    def __init__(self, close_error=None):
        self.close_calls = 0
        self.close_error = close_error

    def get_heads(self, frame, frame_index, timestamp_ms, image_width, image_height):
        return ()

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class FakeVideoWriter:
    def __init__(self, close_error=None):
        self.close_calls = 0
        self.close_error = close_error

    def write(self, image):
        return None

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class FakeVideoReader:
    def __init__(self, fps):
        self.metadata = SimpleNamespace(width=32, height=24, fps=fps, frame_count=0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def __iter__(self):
        return iter(())


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
    def test_build_head_provider_mediapipe_video_uses_source_fps_for_tracker(self):
        backend = SimpleNamespace(close=lambda: None)
        tracker = SimpleNamespace(close=lambda: None)

        class FakeTrackerFactory:
            source_fps = None

            def __call__(self, source_fps):
                self.source_fps = source_fps
                return tracker

        tracker_factory = FakeTrackerFactory()
        provider = build_head_provider_from_config(
            make_config(head_source="mediapipe"),
            media_type="video",
            source_fps=25.0,
            backend_factory=lambda config, *, media_type: backend,
            tracker_factory=tracker_factory,
        )

        self.assertIsInstance(provider, MediaPipeHeadProvider)
        self.assertEqual(tracker_factory.source_fps, 25.0)

    def test_run_video_pipeline_closes_provider_when_predictor_factory_fails(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            provider = FakeHeadProvider(close_error=RuntimeError("provider cleanup failed"))
            primary_error = RuntimeError("predictor construction failed")
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
            )

            def fail_predictor(config):
                raise primary_error

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                with self.assertRaises(RuntimeError) as caught:
                    run_video_pipeline(config, predictor_factory=fail_predictor)

        self.assertIs(caught.exception, primary_error)
        self.assertEqual(provider.close_calls, 1)
        self.assertTrue(
            any("provider cleanup failed" in note for note in caught.exception.__notes__)
        )

    def test_run_video_pipeline_closes_provider_when_writer_setup_fails(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            provider = FakeHeadProvider()
            primary_error = RuntimeError("writer construction failed")
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                save_rendered=True,
            )

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                with patch(
                    "gazelle.runtime.pipeline.VideoFrameWriter",
                    side_effect=primary_error,
                ):
                    with self.assertRaises(RuntimeError) as caught:
                        run_video_pipeline(
                            config,
                            predictor_factory=lambda config: FakePredictor(),
                        )

        self.assertIs(caught.exception, primary_error)
        self.assertEqual(provider.close_calls, 1)

    def test_run_video_pipeline_attempts_writer_and_provider_cleanup(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            provider = FakeHeadProvider(close_error=RuntimeError("provider cleanup failed"))
            writer = FakeVideoWriter(close_error=RuntimeError("writer cleanup failed"))
            primary_error = RuntimeError("renderer construction failed")
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                save_rendered=True,
            )

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                with patch("gazelle.runtime.pipeline.VideoFrameWriter", return_value=writer):
                    with patch(
                        "gazelle.runtime.pipeline.PredictionRenderer",
                        side_effect=primary_error,
                    ):
                        with self.assertRaises(RuntimeError) as caught:
                            run_video_pipeline(
                                config,
                                predictor_factory=lambda config: FakePredictor(),
                            )

        self.assertIs(caught.exception, primary_error)
        self.assertEqual(writer.close_calls, 1)
        self.assertEqual(provider.close_calls, 1)
        notes = caught.exception.__notes__
        self.assertTrue(any("writer cleanup failed" in note for note in notes))
        self.assertTrue(any("provider cleanup failed" in note for note in notes))

    def test_run_video_pipeline_resolves_tracker_fps_fallbacks(self):
        for output_fps, expected_fps in ((12.0, 12.0), (None, 30.0)):
            with self.subTest(output_fps=output_fps):
                with TemporaryDirectory() as tmpdir:
                    provider = FakeHeadProvider()
                    config = make_config(
                        input_path=str(Path(tmpdir) / "clip.mp4"),
                        output_dir=str(Path(tmpdir) / "outputs"),
                        output_fps=output_fps,
                    )
                    with patch(
                        "gazelle.runtime.pipeline.VideoFrameReader",
                        return_value=FakeVideoReader(fps=0.0),
                    ):
                        with patch(
                            "gazelle.runtime.pipeline.build_head_provider_from_config",
                            return_value=provider,
                        ) as build_provider:
                            run_video_pipeline(
                                config,
                                predictor_factory=lambda config: FakePredictor(),
                            )

                self.assertEqual(
                    build_provider.call_args.kwargs["source_fps"],
                    expected_fps,
                )

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
                draw_head_box=True,
                draw_gaze_arrow=False,
                draw_heatmap_contour=True,
                heatmap_contour_width=3,
                draw_labels=False,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())

            self.assertIsNotNone(result.rendered_video_path)
            self.assertTrue(result.rendered_video_path.exists())

    def test_run_video_pipeline_head_box_flag_parsed_and_runs(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                head_source="static",
                bboxes=((0.1, 0.2, 0.4, 0.6),),
                save_rendered=True,
                draw_head_box=True,
                draw_heatmap=False,
                draw_gaze_arrow=False,
                draw_gaze_peak=False,
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
