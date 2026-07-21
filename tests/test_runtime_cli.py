from contextlib import redirect_stderr
import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gazelle.runtime.cli import build_parser, main, parse_runtime_config
from gazelle.runtime.config import (
    RuntimeConfig,
    validate_device_name,
    validate_max_heads,
    validate_pose_model,
    validate_positive_finite_float,
)


class RuntimeCliTest(unittest.TestCase):
    def assert_no_model_modules_newly_imported(self, callback):
        before = set(sys.modules)
        callback()
        newly_imported = set(sys.modules) - before
        self.assertNotIn("gazelle.model", newly_imported)
        self.assertNotIn("gazelle.backbone", newly_imported)
        self.assertNotIn("mediapipe", newly_imported)

    def test_help_exits_without_model_construction_imports(self):
        def run_help():
            parser = build_parser()
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args(["--help"])
            self.assertEqual(cm.exception.code, 0)

        self.assert_no_model_modules_newly_imported(run_help)

    def test_list_models_returns_registered_models(self):
        def run_list_models():
            stdout = io.StringIO()
            exit_code = main(["--list-models"], stdout=stdout)
            self.assertEqual(exit_code, 0)
            self.assertIn("gazelle_dinov2_vitb14_inout", stdout.getvalue())

        self.assert_no_model_modules_newly_imported(run_list_models)

    def test_parse_config_accepts_default_model(self):
        config = parse_runtime_config(["--list-models"])
        self.assertTrue(config.list_models)
        self.assertEqual(config.model, "gazelle_dinov2_vitb14_inout")

    def test_parse_mediapipe_head_config(self):
        config = parse_runtime_config(
            [
                "--input",
                "worker.mp4",
                "--head-source",
                "mediapipe",
                "--max-heads",
                "3",
                "--pose-model",
                "lite",
                "--head-track-max-gap-ms",
                "750",
                "--save-face-landmarks",
            ]
        )

        self.assertEqual(config.head_source, "mediapipe")
        self.assertEqual(config.max_heads, 3)
        self.assertEqual(config.pose_model, "lite")
        self.assertEqual(config.head_track_max_gap_ms, 750.0)
        self.assertTrue(config.save_face_landmarks)

    def test_mediapipe_head_config_defaults(self):
        config = parse_runtime_config(["--input", "worker.mp4"])

        self.assertEqual(config.max_heads, 1)
        self.assertEqual(config.pose_model, "full")
        self.assertEqual(config.head_track_max_gap_ms, 500.0)
        self.assertFalse(config.save_face_landmarks)

    def test_mediapipe_runtime_config_validators_reject_invalid_values(self):
        for max_heads in (0, 11, True):
            with self.subTest(max_heads=max_heads):
                with self.assertRaises(ValueError):
                    validate_max_heads(max_heads)

        with self.assertRaises(ValueError):
            validate_pose_model("medium")

        for gap_ms in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(gap_ms=gap_ms):
                with self.assertRaises(ValueError):
                    validate_positive_finite_float(gap_ms, "head_track_max_gap_ms")

    def test_prepare_only_config_does_not_require_input(self):
        config = parse_runtime_config(["--prepare-only", "--cache-dir", "models"])
        self.assertTrue(config.prepare_only)
        self.assertIsNone(config.input_path)
        self.assertEqual(config.cache_dir, "models")

    def test_parse_image_static_config(self):
        config = parse_runtime_config(
            [
                "--input",
                "image.jpg",
                "--output-dir",
                "outputs",
                "--overwrite",
                "--head-source",
                "static",
                "--bbox",
                "0.1",
                "0.2",
                "0.3",
                "0.4",
                "--bbox",
                "0.5",
                "0.2",
                "0.7",
                "0.6",
                "--bbox-format",
                "normalized",
                "--person-id",
                "3",
                "--person-id",
                "4",
                "--save-heatmaps",
                "--save-rendered",
                "--rendered-name",
                "rendered.jpg",
                "--heatmap-alpha",
                "0.25",
                "--no-gaze-peak",
                "--no-labels",
            ]
        )
        self.assertEqual(config.input_path, "image.jpg")
        self.assertEqual(config.output_dir, "outputs")
        self.assertTrue(config.overwrite)
        self.assertEqual(config.head_source, "static")
        self.assertEqual(config.bboxes, ((0.1, 0.2, 0.3, 0.4), (0.5, 0.2, 0.7, 0.6)))
        self.assertEqual(config.person_ids, (3, 4))
        self.assertTrue(config.save_heatmaps)
        self.assertTrue(config.save_rendered)
        self.assertEqual(config.rendered_name, "rendered.jpg")
        self.assertEqual(config.heatmap_alpha, 0.25)
        self.assertTrue(config.draw_heatmap)
        self.assertFalse(config.draw_head_box)
        self.assertFalse(config.draw_gaze_peak)
        self.assertTrue(config.draw_gaze_arrow)
        self.assertFalse(config.draw_heatmap_contour)
        self.assertFalse(config.draw_labels)

    def test_parse_image_render_config(self):
        config = parse_runtime_config(
            [
                "--input",
                "image.jpg",
                "--save-rendered",
                "--rendered-name",
                "rendered.jpg",
                "--heatmap-alpha",
                "0.25",
                "--head-box",
                "--no-gaze-peak",
                "--no-labels",
            ]
        )

        self.assertTrue(config.save_rendered)
        self.assertEqual(config.rendered_name, "rendered.jpg")
        self.assertEqual(config.heatmap_alpha, 0.25)
        self.assertTrue(config.draw_head_box)
        self.assertFalse(config.draw_gaze_peak)
        self.assertFalse(config.draw_labels)

    def test_head_box_default_disabled(self):
        config = parse_runtime_config(["--input", "image.jpg", "--save-rendered"])

        self.assertFalse(config.draw_head_box)

    def test_parse_head_box_enabled(self):
        config = parse_runtime_config(["--input", "image.jpg", "--save-rendered", "--head-box"])

        self.assertTrue(config.draw_head_box)

    def test_parse_enhanced_render_config(self):
        config = parse_runtime_config(
            [
                "--input",
                "image.jpg",
                "--save-rendered",
                "--head-box",
                "--no-heatmap",
                "--no-gaze-arrow",
                "--draw-heatmap-contour",
                "--heatmap-contour-quantile",
                "0.85",
                "--heatmap-contour-width",
                "3",
            ]
        )

        self.assertTrue(config.save_rendered)
        self.assertTrue(config.draw_head_box)
        self.assertFalse(config.draw_heatmap)
        self.assertFalse(config.draw_gaze_arrow)
        self.assertTrue(config.draw_heatmap_contour)
        self.assertEqual(config.heatmap_contour_quantile, 0.85)
        self.assertEqual(config.heatmap_contour_width, 3)

    def test_parse_video_config(self):
        config = parse_runtime_config(
            [
                "--input",
                "sample.mp4",
                "--output-fps",
                "24",
                "--max-frames",
                "10",
                "--frame-step",
                "2",
                "--output-video-name",
                "rendered.mp4",
            ]
        )

        self.assertEqual(config.input_path, "sample.mp4")
        self.assertEqual(config.output_fps, 24.0)
        self.assertEqual(config.max_frames, 10)
        self.assertEqual(config.frame_step, 2)
        self.assertEqual(config.output_video_name, "rendered.mp4")

    def test_prepare_only_route_calls_resource_preparation(self):
        prepared = SimpleNamespace(
            model_name="gazelle_dinov2_vitb14_inout",
            checkpoint_path="models/checkpoints/example.pt",
            checkpoint_candidate=None,
            cache_paths=SimpleNamespace(root_dir="models", torch_hub_dir="models/torch_hub"),
            candidate_results=(),
        )
        with patch("gazelle.runtime.resources.prepare_runtime_resources", return_value=prepared) as mock_prepare:
            with patch(
                "gazelle.runtime.perception.resources.prepare_mediapipe_resources"
            ) as mock_prepare_mediapipe:
                stdout = io.StringIO()
                exit_code = main(["--prepare-only", "--cache-dir", "models"], stdout=stdout)
        self.assertEqual(exit_code, 0)
        mock_prepare.assert_called_once()
        mock_prepare_mediapipe.assert_not_called()
        self.assertIn("Prepared Gazelle resources", stdout.getvalue())
        self.assertIn("checkpoint_source: local", stdout.getvalue())

    def test_prepare_only_mediapipe_prepares_and_prints_selected_assets(self):
        prepared = SimpleNamespace(
            model_name="gazelle_dinov2_vitb14_inout",
            checkpoint_path="models/checkpoints/example.pt",
            checkpoint_candidate=None,
            cache_paths=SimpleNamespace(root_dir="models", torch_hub_dir="models/torch_hub"),
            candidate_results=(),
        )
        prepared_mediapipe = SimpleNamespace(
            face_detector_path="models/mediapipe/blaze_face_full_range.tflite",
            face_landmarker_path="models/mediapipe/face_landmarker.task",
            pose_landmarker_path="models/mediapipe/pose_landmarker_heavy.task",
            pose_model="heavy",
        )
        with patch(
            "gazelle.runtime.resources.prepare_runtime_resources",
            return_value=prepared,
        ) as mock_prepare:
            with patch(
                "gazelle.runtime.perception.resources.prepare_mediapipe_resources",
                return_value=prepared_mediapipe,
            ) as mock_prepare_mediapipe:
                stdout = io.StringIO()
                exit_code = main(
                    [
                        "--prepare-only",
                        "--head-source",
                        "mediapipe",
                        "--pose-model",
                        "heavy",
                    ],
                    stdout=stdout,
                )

        self.assertEqual(exit_code, 0)
        mock_prepare.assert_called_once()
        mock_prepare_mediapipe.assert_called_once()
        config = mock_prepare_mediapipe.call_args.args[0]
        self.assertEqual(config.pose_model, "heavy")
        output = stdout.getvalue()
        self.assertIn("face_detector: models/mediapipe/blaze_face_full_range.tflite", output)
        self.assertIn("face_landmarker: models/mediapipe/face_landmarker.task", output)
        self.assertIn("pose_landmarker: models/mediapipe/pose_landmarker_heavy.task", output)
        self.assertIn("pose_model: heavy", output)

    def test_image_input_route_calls_pipeline(self):
        result = SimpleNamespace(
            output_dir="outputs/frame_gazelle",
            predictions_path="outputs/frame_gazelle/predictions.json",
            head_observations_path="outputs/frame_gazelle/head_observations.json",
            run_config_path="outputs/frame_gazelle/run_config.json",
            rendered_path=None,
        )
        with patch("gazelle.runtime.pipeline.run_image_pipeline", return_value=result) as mock_pipeline:
            stdout = io.StringIO()
            exit_code = main(
                [
                    "--input",
                    "image.jpg",
                    "--output-dir",
                    "outputs",
                    "--head-source",
                    "none",
                ],
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        mock_pipeline.assert_called_once()
        config = mock_pipeline.call_args.args[0]
        self.assertEqual(config.input_path, "image.jpg")
        self.assertEqual(config.output_dir, "outputs")
        self.assertEqual(config.head_source, "none")
        self.assertIn("predictions:", stdout.getvalue())
        self.assertIn("head_observations: outputs/frame_gazelle/head_observations.json", stdout.getvalue())

    def test_video_input_route_calls_pipeline(self):
        result = SimpleNamespace(
            output_dir="outputs/clip_gazelle",
            predictions_jsonl_path="outputs/clip_gazelle/predictions.jsonl",
            head_observations_jsonl_path="outputs/clip_gazelle/head_observations.jsonl",
            run_config_path="outputs/clip_gazelle/run_config.json",
            rendered_video_path=None,
            frames_read=2,
            frames_written=2,
        )
        with patch("gazelle.runtime.media.detect_media_type", return_value="video") as mock_detect:
            with patch("gazelle.runtime.pipeline.run_image_pipeline") as mock_image_pipeline:
                with patch("gazelle.runtime.pipeline.run_video_pipeline", return_value=result) as mock_video_pipeline:
                    stdout = io.StringIO()
                    exit_code = main(
                        [
                            "--input",
                            "clip.mp4",
                            "--output-dir",
                            "outputs",
                            "--head-source",
                            "none",
                        ],
                        stdout=stdout,
                    )

        self.assertEqual(exit_code, 0)
        mock_detect.assert_called_once_with("clip.mp4")
        mock_image_pipeline.assert_not_called()
        mock_video_pipeline.assert_called_once()
        self.assertIn("predictions_jsonl:", stdout.getvalue())
        self.assertIn("frames_written: 2", stdout.getvalue())

    def test_cli_prints_head_observations_jsonl(self):
        result = SimpleNamespace(
            output_dir="outputs/clip_gazelle",
            predictions_jsonl_path="outputs/clip_gazelle/predictions.jsonl",
            head_observations_jsonl_path="outputs/clip_gazelle/head_observations.jsonl",
            run_config_path="outputs/clip_gazelle/run_config.json",
            rendered_video_path=None,
            frames_read=1,
            frames_written=1,
        )
        with patch("gazelle.runtime.media.detect_media_type", return_value="video"):
            with patch("gazelle.runtime.pipeline.run_video_pipeline", return_value=result):
                stdout = io.StringIO()
                exit_code = main(["--input", "clip.mp4"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        self.assertIn(
            "head_observations_jsonl: outputs/clip_gazelle/head_observations.jsonl",
            stdout.getvalue(),
        )

    def test_video_input_route_prints_rendered_video_path_when_present(self):
        result = SimpleNamespace(
            output_dir="outputs/clip_gazelle",
            predictions_jsonl_path="outputs/clip_gazelle/predictions.jsonl",
            head_observations_jsonl_path="outputs/clip_gazelle/head_observations.jsonl",
            run_config_path="outputs/clip_gazelle/run_config.json",
            rendered_video_path="outputs/clip_gazelle/rendered.mp4",
            frames_read=1,
            frames_written=1,
        )
        with patch("gazelle.runtime.media.detect_media_type", return_value="video"):
            with patch("gazelle.runtime.pipeline.run_video_pipeline", return_value=result):
                stdout = io.StringIO()
                exit_code = main(["--input", "clip.mp4", "--save-rendered"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        self.assertIn("rendered_video: outputs/clip_gazelle/rendered.mp4", stdout.getvalue())

    def test_image_input_route_prints_rendered_path_when_present(self):
        result = SimpleNamespace(
            output_dir="outputs/frame_gazelle",
            predictions_path="outputs/frame_gazelle/predictions.json",
            head_observations_path="outputs/frame_gazelle/head_observations.json",
            run_config_path="outputs/frame_gazelle/run_config.json",
            rendered_path="outputs/frame_gazelle/rendered.png",
        )
        with patch("gazelle.runtime.pipeline.run_image_pipeline", return_value=result):
            stdout = io.StringIO()
            exit_code = main(["--input", "image.jpg", "--save-rendered"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        self.assertIn("rendered: outputs/frame_gazelle/rendered.png", stdout.getvalue())

    def test_list_models_does_not_call_pipeline(self):
        with patch("gazelle.runtime.pipeline.run_image_pipeline") as mock_image_pipeline:
            with patch("gazelle.runtime.pipeline.run_video_pipeline") as mock_video_pipeline:
                stdout = io.StringIO()
                exit_code = main(["--list-models", "--input", "image.jpg"], stdout=stdout)

        self.assertEqual(exit_code, 0)
        mock_image_pipeline.assert_not_called()
        mock_video_pipeline.assert_not_called()

    def test_prepare_only_does_not_call_pipeline(self):
        prepared = SimpleNamespace(
            model_name="gazelle_dinov2_vitb14_inout",
            checkpoint_path="models/checkpoints/example.pt",
            checkpoint_candidate=None,
            cache_paths=SimpleNamespace(root_dir="models", torch_hub_dir="models/torch_hub"),
            candidate_results=(),
        )
        with patch("gazelle.runtime.pipeline.run_image_pipeline") as mock_image_pipeline:
            with patch("gazelle.runtime.pipeline.run_video_pipeline") as mock_video_pipeline:
                with patch("gazelle.runtime.resources.prepare_runtime_resources", return_value=prepared):
                    stdout = io.StringIO()
                    exit_code = main(
                        ["--prepare-only", "--input", "image.jpg", "--cache-dir", "models"],
                        stdout=stdout,
                    )

        self.assertEqual(exit_code, 0)
        mock_image_pipeline.assert_not_called()
        mock_video_pipeline.assert_not_called()

    def test_invalid_model_uses_registry_error(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--list-models", "--model", "bad"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("Unknown Gazelle model", stderr.getvalue())
        self.assertIn("Supported models", stderr.getvalue())

    def test_valid_device_names(self):
        for device in ("auto", "cpu", "cuda", "cuda:0", "cuda:1"):
            with self.subTest(device=device):
                self.assertEqual(validate_device_name(device), device)

    def test_device_names_are_stripped(self):
        self.assertEqual(validate_device_name(" cuda:2 "), "cuda:2")

    def test_invalid_device_names(self):
        invalid_devices = (
            "gpu0",
            "cuda:",
            "cuda:abc",
            "cuda:-1",
            "cuda:0:1",
            "cuda: 0",
            "cuda:+1",
            "",
            "   ",
        )
        for device in invalid_devices:
            with self.subTest(device=device):
                with self.assertRaisesRegex(ValueError, "Invalid device"):
                    validate_device_name(device)

    def test_invalid_device_is_rejected_by_config(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--list-models", "--device", "gpu0"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("auto, cpu, cuda, or cuda:<non-negative-index>", stderr.getvalue())

    def test_invalid_output_fps_rejected(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--input", "clip.mp4", "--output-fps", "0"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("output_fps", stderr.getvalue())

    def test_invalid_max_frames_rejected(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--input", "clip.mp4", "--max-frames", "0"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("max_frames", stderr.getvalue())

    def test_invalid_frame_step_rejected(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--input", "clip.mp4", "--frame-step", "0"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("frame_step", stderr.getvalue())

    def test_invalid_output_video_name_rejected(self):
        invalid_names = ("../rendered.mp4", "subdir/rendered.mp4", "rendered.avi", "")
        for name in invalid_names:
            with self.subTest(name=name):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
                    parse_runtime_config(["--input", "clip.mp4", "--output-video-name", name])
                self.assertEqual(cm.exception.code, 2)
                self.assertIn("output_video_name", stderr.getvalue())

    def test_invalid_heatmap_contour_quantile_rejected(self):
        invalid_quantiles = ("-0.1", "1.1", "nan")
        for quantile in invalid_quantiles:
            with self.subTest(quantile=quantile):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
                    parse_runtime_config(["--input", "image.jpg", "--heatmap-contour-quantile", quantile])
                self.assertEqual(cm.exception.code, 2)
                self.assertIn("heatmap_contour_quantile", stderr.getvalue())

    def test_parse_heatmap_contour_width(self):
        config = parse_runtime_config(
            ["--input", "image.jpg", "--draw-heatmap-contour", "--heatmap-contour-width", "4"]
        )

        self.assertEqual(config.heatmap_contour_width, 4)

    def test_invalid_heatmap_contour_width_rejected(self):
        for width in ("0", "-1"):
            with self.subTest(width=width):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
                    parse_runtime_config(["--input", "image.jpg", "--heatmap-contour-width", width])
                self.assertEqual(cm.exception.code, 2)
                self.assertIn("heatmap_contour_width", stderr.getvalue())
        with self.assertRaises(ValueError):
            RuntimeConfig(heatmap_contour_width=True).validate()

    def test_no_head_box_argument_is_removed(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--input", "image.jpg", "--no-head-box"])

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("unrecognized arguments", stderr.getvalue())

    def test_video_numeric_config_rejects_bool_values(self):
        for kwargs in (
            {"output_fps": True},
            {"max_frames": True},
            {"frame_step": True},
            {"heatmap_contour_quantile": True},
            {"heatmap_contour_width": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    RuntimeConfig(**kwargs).validate()

    def test_no_action_returns_argparse_error(self):
        with self.assertRaises(SystemExit) as cm:
            main([])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
