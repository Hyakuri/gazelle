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
from gazelle.runtime.contracts import GazePrediction, HeadObservation
from gazelle.runtime.media import VideoFrameReader
from gazelle.runtime.pipeline import build_head_provider_from_config, run_video_pipeline
from gazelle.runtime.perception.contracts import (
    HeadFrameResult,
    HeadPerception,
    HeadPerceptionState,
    HeadViewState,
)
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
    def __init__(self, result_factory=None, close_error=None):
        self.close_calls = 0
        self.close_error = close_error
        self.calls = []
        self.result_factory = result_factory or (
            lambda frame_index: HeadFrameResult(
                heads=(
                    HeadObservation(
                        person_id=frame_index,
                        bbox=(0.1, 0.2, 0.4, 0.6),
                        confidence=0.9,
                    ),
                )
            )
        )

    def get_frame_result(self, frame, frame_index, timestamp_ms, image_width, image_height):
        self.calls.append(frame_index)
        return self.result_factory(frame_index)

    def get_heads(self, frame, frame_index, timestamp_ms, image_width, image_height):
        return self.get_frame_result(
            frame,
            frame_index,
            timestamp_ms,
            image_width,
            image_height,
        ).heads

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class FakeVideoWriter:
    def __init__(self, close_error=None):
        self.close_calls = 0
        self.close_error = close_error
        self.images = []

    def write(self, image):
        self.images.append(image)

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class FakeVideoReader:
    def __init__(self, fps, frames=(), iteration_error=None, close_error=None):
        self.metadata = SimpleNamespace(width=32, height=24, fps=fps, frame_count=0)
        self.frames = tuple(frames)
        self.iteration_error = iteration_error
        self.close_error = close_error
        self.close_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def __iter__(self):
        if self.iteration_error is not None:
            raise self.iteration_error
        return iter(self.frames)

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class FakeJsonlWriter:
    def __init__(self, name, events=None, close_error=None):
        self.name = name
        self.events = events if events is not None else []
        self.close_error = close_error
        self.close_calls = 0

    def write(self, record):
        self.events.append(self.name)

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


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
    def test_video_renderer_receives_perceptions_only_for_ok_frames(self):
        perceptions = tuple(
            HeadPerception(
                person_id=index,
                head_bbox=(0.1, 0.2, 0.4, 0.6),
                face_bbox=None,
                confidence=0.9,
                state=HeadPerceptionState.FACE_ONLY,
                view_state=HeadViewState.FRONTAL,
                observed=True,
            )
            for index in range(2)
        )

        def result_for_frame(frame_index):
            if frame_index == 2:
                return HeadFrameResult(heads=())
            head = HeadObservation(frame_index, (0.1, 0.2, 0.4, 0.6), 0.9)
            return HeadFrameResult(heads=(head,), perceptions=(perceptions[frame_index],))

        frames = tuple(
            SimpleNamespace(index=index, timestamp_ms=index * 200.0, image=object())
            for index in range(3)
        )
        reader = FakeVideoReader(fps=5.0, frames=frames)
        provider = FakeHeadProvider(result_for_frame)
        writer = FakeVideoWriter()
        rendered_marker = object()
        render_calls = []

        class FakeRenderer:
            def __init__(self, options):
                self.options = options

            def render(self, image, predictions, perceptions=()):
                render_calls.append((image, tuple(predictions), tuple(perceptions)))
                return rendered_marker

        with TemporaryDirectory() as tmpdir:
            config = make_config(
                input_path=str(Path(tmpdir) / "clip.mp4"),
                output_dir=str(Path(tmpdir) / "outputs"),
                frame_step=2,
                save_rendered=True,
            )
            with patch("gazelle.runtime.pipeline.VideoFrameReader", return_value=reader):
                with patch(
                    "gazelle.runtime.pipeline.build_head_provider_from_config",
                    return_value=provider,
                ):
                    with patch(
                        "gazelle.runtime.pipeline.VideoFrameWriter",
                        return_value=writer,
                    ):
                        with patch(
                            "gazelle.runtime.pipeline.PredictionRenderer",
                            FakeRenderer,
                        ):
                            run_video_pipeline(
                                config,
                                predictor_factory=lambda config: FakePredictor(),
                            )

        self.assertEqual(len(render_calls), 1)
        self.assertEqual(render_calls[0][2], (perceptions[0],))
        self.assertIs(writer.images[0], rendered_marker)
        self.assertIs(writer.images[1], frames[1].image)
        self.assertIs(writer.images[2], frames[2].image)

    def test_perception_runs_on_every_frame_when_frame_step_is_two(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=4)
            provider = FakeHeadProvider()
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                frame_step=2,
            )

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())

        self.assertEqual(provider.calls, [0, 1, 2, 3])

    def test_frame_step_skips_gazelle_after_perception(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=4)
            provider = FakeHeadProvider()
            predictor = FakePredictor()
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                frame_step=2,
            )

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                result = run_video_pipeline(config, predictor_factory=lambda config: predictor)
            gaze_rows = read_jsonl(result.predictions_jsonl_path)

        predictor_frame_ids = [call[1][0].person_id for call in predictor.calls]
        self.assertEqual(provider.calls, [0, 1, 2, 3])
        self.assertEqual(predictor_frame_ids, [0, 2])
        self.assertEqual(
            [row["status"] for row in gaze_rows],
            ["ok", "skipped", "ok", "skipped"],
        )

    def test_missing_head_writes_no_head_without_predictor(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=3)
            provider = FakeHeadProvider(lambda frame_index: HeadFrameResult(heads=()))
            factory_calls = []
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
            )

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                result = run_video_pipeline(
                    config,
                    predictor_factory=lambda config: factory_calls.append(config),
                )
            gaze_rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual([row["status"] for row in gaze_rows], ["no_head"] * 3)
        self.assertEqual(factory_calls, [])

    def test_predictor_is_built_once_on_first_usable_frame(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=4)
            provider = FakeHeadProvider(
                lambda frame_index: HeadFrameResult(heads=())
                if frame_index == 0
                else HeadFrameResult(
                    heads=(HeadObservation(frame_index, (0.1, 0.2, 0.4, 0.6), 0.9),)
                )
            )
            predictor = FakePredictor()
            factory_calls = []
            provider_calls_at_construction = []
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
            )

            def factory(config):
                factory_calls.append(config)
                provider_calls_at_construction.append(tuple(provider.calls))
                return predictor

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                result = run_video_pipeline(config, predictor_factory=factory)
            gaze_rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual(len(factory_calls), 1)
        self.assertEqual(provider_calls_at_construction, [(0, 1)])
        self.assertEqual([call[1][0].person_id for call in predictor.calls], [1, 2, 3])
        self.assertEqual([row["status"] for row in gaze_rows], ["no_head", "ok", "ok", "ok"])

    def test_all_skipped_video_does_not_build_predictor(self):
        frame = SimpleNamespace(index=1, timestamp_ms=200.0, image=object())
        reader = FakeVideoReader(fps=5.0, frames=(frame,))
        provider = FakeHeadProvider()
        factory_calls = []

        with TemporaryDirectory() as tmpdir:
            config = make_config(
                input_path=str(Path(tmpdir) / "clip.mp4"),
                output_dir=str(Path(tmpdir) / "outputs"),
                frame_step=2,
            )
            with patch("gazelle.runtime.pipeline.VideoFrameReader", return_value=reader):
                with patch(
                    "gazelle.runtime.pipeline.build_head_provider_from_config",
                    return_value=provider,
                ):
                    result = run_video_pipeline(
                        config,
                        predictor_factory=lambda config: factory_calls.append(config),
                    )
            gaze_rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual(provider.calls, [1])
        self.assertEqual(factory_calls, [])
        self.assertEqual([row["status"] for row in gaze_rows], ["skipped"])

    def test_head_observation_row_is_written_before_gaze_row(self):
        frame = SimpleNamespace(index=0, timestamp_ms=0.0, image=object())
        reader = FakeVideoReader(fps=5.0, frames=(frame,))
        provider = FakeHeadProvider()
        events = []
        head_writer = FakeJsonlWriter("head", events)
        gaze_writer = FakeJsonlWriter("gaze", events)

        with TemporaryDirectory() as tmpdir:
            config = make_config(
                input_path=str(Path(tmpdir) / "clip.mp4"),
                output_dir=str(Path(tmpdir) / "outputs"),
            )
            with patch("gazelle.runtime.pipeline.VideoFrameReader", return_value=reader):
                with patch(
                    "gazelle.runtime.pipeline.build_head_provider_from_config",
                    return_value=provider,
                ):
                    with patch(
                        "gazelle.runtime.pipeline.JsonlWriter",
                        side_effect=(head_writer, gaze_writer),
                    ):
                        run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())

        self.assertEqual(events, ["head", "gaze"])

    def test_pipeline_attempts_all_resource_cleanup_on_processing_failure(self):
        primary_error = RuntimeError("processing failed")
        frame = SimpleNamespace(index=0, timestamp_ms=0.0, image=object())
        reader = FakeVideoReader(
            fps=5.0,
            frames=(frame,),
            close_error=RuntimeError("reader cleanup failed"),
        )

        def fail_result(frame_index):
            raise primary_error

        provider = FakeHeadProvider(
            fail_result,
            close_error=RuntimeError("provider cleanup failed"),
        )
        video_writer = FakeVideoWriter(close_error=RuntimeError("video cleanup failed"))
        head_writer = FakeJsonlWriter(
            "head",
            close_error=RuntimeError("head JSONL cleanup failed"),
        )
        gaze_writer = FakeJsonlWriter(
            "gaze",
            close_error=RuntimeError("gaze JSONL cleanup failed"),
        )

        with TemporaryDirectory() as tmpdir:
            config = make_config(
                input_path=str(Path(tmpdir) / "clip.mp4"),
                output_dir=str(Path(tmpdir) / "outputs"),
                save_rendered=True,
            )
            with patch("gazelle.runtime.pipeline.VideoFrameReader", return_value=reader):
                with patch(
                    "gazelle.runtime.pipeline.build_head_provider_from_config",
                    return_value=provider,
                ):
                    with patch(
                        "gazelle.runtime.pipeline.VideoFrameWriter",
                        return_value=video_writer,
                    ):
                        with patch(
                            "gazelle.runtime.pipeline.JsonlWriter",
                            side_effect=(head_writer, gaze_writer),
                        ):
                            with self.assertRaises(RuntimeError) as caught:
                                run_video_pipeline(
                                    config,
                                    predictor_factory=lambda config: FakePredictor(),
                                )

        self.assertIs(caught.exception, primary_error)
        self.assertEqual(head_writer.close_calls, 1)
        self.assertEqual(gaze_writer.close_calls, 1)
        self.assertEqual(video_writer.close_calls, 1)
        self.assertEqual(provider.close_calls, 1)
        self.assertEqual(reader.close_calls, 1)
        notes = caught.exception.__notes__
        for message in (
            "head JSONL cleanup failed",
            "gaze JSONL cleanup failed",
            "video cleanup failed",
            "provider cleanup failed",
            "reader cleanup failed",
        ):
            self.assertTrue(any(message in note for note in notes))

    def test_head_observation_rows_match_frames_written(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=4)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                frame_step=2,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())
            rows = read_jsonl(result.head_observations_jsonl_path)

        self.assertEqual(len(rows), result.frames_written)

    def test_gaze_rows_match_frames_written(self):
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

    def test_provider_receives_source_fps(self):
        with TemporaryDirectory() as tmpdir:
            config = make_config(
                input_path=str(Path(tmpdir) / "clip.mp4"),
                output_dir=str(Path(tmpdir) / "outputs"),
                output_fps=12.0,
            )
            reader = FakeVideoReader(fps=0.0)
            provider = FakeHeadProvider()

            with patch("gazelle.runtime.pipeline.VideoFrameReader", return_value=reader):
                with patch(
                    "gazelle.runtime.pipeline.build_head_provider_from_config",
                    return_value=provider,
                ) as build_provider:
                    run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())

        self.assertEqual(build_provider.call_args.kwargs["source_fps"], 12.0)

    def test_provider_closes_on_reader_or_predictor_failure(self):
        for failure_kind in ("reader", "predictor"):
            with self.subTest(failure_kind=failure_kind), TemporaryDirectory() as tmpdir:
                video_path = Path(tmpdir) / "clip.mp4"
                write_tiny_video(video_path, frame_count=1)
                provider = FakeHeadProvider()
                primary_error = RuntimeError("{} failed".format(failure_kind))
                config = make_config(
                    input_path=str(video_path),
                    output_dir=str(Path(tmpdir) / "outputs"),
                )

                if failure_kind == "reader":
                    reader = FakeVideoReader(fps=5.0, iteration_error=primary_error)
                    reader_patch = patch(
                        "gazelle.runtime.pipeline.VideoFrameReader",
                        return_value=reader,
                    )
                    predictor_factory = lambda config: FakePredictor()
                else:
                    reader_patch = patch("gazelle.runtime.pipeline.VideoFrameReader", wraps=VideoFrameReader)

                    def predictor_factory(config):
                        raise primary_error

                with reader_patch:
                    with patch(
                        "gazelle.runtime.pipeline.build_head_provider_from_config",
                        return_value=provider,
                    ):
                        with self.assertRaises(RuntimeError) as caught:
                            run_video_pipeline(config, predictor_factory=predictor_factory)

                self.assertIs(caught.exception, primary_error)
                self.assertEqual(provider.close_calls, 1)

    def test_existing_output_dir_rejects_before_provider(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            output_dir = Path(tmpdir) / "outputs"
            (output_dir / "clip_gazelle").mkdir(parents=True)
            config = make_config(input_path=str(video_path), output_dir=str(output_dir))

            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config"
            ) as build_provider:
                with self.assertRaises(FileExistsError):
                    run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())

        build_provider.assert_not_called()

    def test_max_frames_limits_both_output_files(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=5)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                max_frames=2,
            )

            result = run_video_pipeline(config, predictor_factory=lambda config: FakePredictor())
            head_rows = read_jsonl(result.head_observations_jsonl_path)
            gaze_rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual(result.frames_written, 2)
        self.assertEqual(len(head_rows), 2)
        self.assertEqual(len(gaze_rows), 2)

    def test_tracked_only_head_can_run_gazelle(self):
        head = HeadObservation(9, (0.2, 0.2, 0.5, 0.6), 0.8)
        perception = HeadPerception(
            person_id=9,
            head_bbox=head.bbox,
            face_bbox=None,
            confidence=0.8,
            state=HeadPerceptionState.TRACKED_ONLY,
            view_state=HeadViewState.UNKNOWN,
            observed=False,
            missed_frames=1,
            missed_ms=200.0,
        )
        provider = FakeHeadProvider(
            lambda frame_index: HeadFrameResult(heads=(head,), perceptions=(perception,))
        )
        predictor = FakePredictor()

        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=1)
            config = make_config(
                input_path=str(video_path),
                output_dir=str(Path(tmpdir) / "outputs"),
            )
            with patch(
                "gazelle.runtime.pipeline.build_head_provider_from_config",
                return_value=provider,
            ):
                result = run_video_pipeline(config, predictor_factory=lambda config: predictor)
            head_rows = read_jsonl(result.head_observations_jsonl_path)
            gaze_rows = read_jsonl(result.predictions_jsonl_path)

        self.assertEqual(len(predictor.calls), 1)
        self.assertEqual(head_rows[0]["people"][0]["state"], "tracked_only")
        self.assertEqual(gaze_rows[0]["status"], "ok")

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
