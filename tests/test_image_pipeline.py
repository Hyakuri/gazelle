import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import torch
from PIL import Image

from gazelle.runtime.config import RuntimeConfig
from gazelle.runtime.contracts import GazePrediction
from gazelle.runtime.heads import JsonHeadProvider, NoneHeadProvider, StaticHeadProvider
from gazelle.runtime.pipeline import (
    build_head_provider_from_config,
    create_output_dir,
    run_image_pipeline,
)


class FakePredictor:
    def __init__(self):
        self.calls = []

    def predict_frame(self, image, heads):
        heads = tuple(heads)
        self.calls.append((image, heads))
        predictions = []
        for index, head in enumerate(heads):
            heatmap = torch.tensor(
                [
                    [0.1 + index, 0.2 + index],
                    [0.8 + index, 0.3 + index],
                ]
            )
            predictions.append(
                GazePrediction(
                    person_id=head.person_id,
                    bbox=head.bbox,
                    heatmap=heatmap,
                    gaze_peak=(0.0, 0.5),
                    heatmap_peak_value=float(0.8 + index),
                    inout_score=float(0.4 + index),
                )
            )
        return predictions


def write_test_image(path, mode="RGB"):
    image = Image.new(mode, (10, 8), color=128 if mode == "L" else (10, 20, 30))
    image.save(path)


def make_config(**overrides):
    values = {
        "input_path": "frame.png",
        "output_dir": "outputs",
        "head_source": "none",
    }
    values.update(overrides)
    return RuntimeConfig(**values).validate()


class ImagePipelineTest(unittest.TestCase):
    def test_build_head_provider_none(self):
        provider = build_head_provider_from_config(make_config(head_source="none"))

        self.assertIsInstance(provider, NoneHeadProvider)

    def test_build_head_provider_static(self):
        provider = build_head_provider_from_config(
            make_config(
                head_source="static",
                bboxes=((0.1, 0.2, 0.3, 0.4),),
                person_ids=(7,),
            )
        )
        heads = provider.get_heads(None, 0, 0.0, 100, 100)

        self.assertIsInstance(provider, StaticHeadProvider)
        self.assertEqual(heads[0].person_id, 7)
        self.assertEqual(heads[0].bbox, (0.1, 0.2, 0.3, 0.4))

    def test_build_head_provider_json(self):
        with TemporaryDirectory() as tmpdir:
            head_data = Path(tmpdir) / "heads.json"
            head_data.write_text(
                json.dumps(
                    {
                        "bbox_format": "normalized",
                        "heads": [{"person_id": 3, "bbox": [0.1, 0.2, 0.3, 0.4]}],
                    }
                ),
                encoding="utf-8",
            )
            provider = build_head_provider_from_config(
                make_config(head_source="json", head_data=str(head_data))
            )

        self.assertIsInstance(provider, JsonHeadProvider)

    def test_static_without_bbox_rejected(self):
        with self.assertRaisesRegex(ValueError, "--bbox"):
            build_head_provider_from_config(make_config(head_source="static"))

    def test_json_without_head_data_rejected(self):
        with self.assertRaisesRegex(ValueError, "--head-data"):
            build_head_provider_from_config(make_config(head_source="json"))

    def test_create_output_dir_rejects_existing_without_overwrite(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "outputs"
            existing = output_dir / "frame_gazelle"
            existing.mkdir(parents=True)

            with self.assertRaises(FileExistsError):
                create_output_dir("frame.png", output_dir, overwrite=False)

    def test_create_output_dir_allows_overwrite(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "outputs"
            existing = output_dir / "frame_gazelle"
            existing.mkdir(parents=True)

            result = create_output_dir("frame.png", output_dir, overwrite=True)

            self.assertEqual(result, existing)

    def test_run_image_pipeline_none_head_source(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            fake = FakePredictor()
            config = make_config(input_path=str(image_path), output_dir=str(Path(tmpdir) / "outputs"))

            result = run_image_pipeline(config, predictor_factory=lambda config: fake)

        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][1][0].bbox, None)
        self.assertEqual(result.heads[0].person_id, 0)

    def test_run_image_pipeline_existing_output_dir_rejects_before_predictor(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            output_dir = Path(tmpdir) / "outputs"
            existing_output = output_dir / "frame_gazelle"
            existing_output.mkdir(parents=True)
            factory_calls = []

            def fail_if_called(config):
                factory_calls.append(config)
                raise AssertionError("predictor should not be constructed")

            config = make_config(input_path=str(image_path), output_dir=str(output_dir))

            with self.assertRaises(FileExistsError):
                run_image_pipeline(config, predictor_factory=fail_if_called)

            self.assertEqual(factory_calls, [])
            self.assertFalse((existing_output / "predictions.json").exists())
            self.assertFalse((existing_output / "run_config.json").exists())
            self.assertFalse((existing_output / "heatmaps").exists())

    def test_run_image_pipeline_static_head_source(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            fake = FakePredictor()
            config = make_config(
                input_path=str(image_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                head_source="static",
                bboxes=((0.1, 0.2, 0.3, 0.4),),
                person_ids=(9,),
            )

            result = run_image_pipeline(config, predictor_factory=lambda config: fake)

        self.assertEqual(fake.calls[0][1][0].person_id, 9)
        self.assertEqual(result.predictions[0].person_id, 9)

    def test_run_image_pipeline_json_head_source(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            head_data = Path(tmpdir) / "heads.json"
            head_data.write_text(
                json.dumps(
                    {
                        "bbox_format": "pixel",
                        "heads": [{"person_id": 4, "bbox": [1, 2, 5, 6]}],
                    }
                ),
                encoding="utf-8",
            )
            fake = FakePredictor()
            config = make_config(
                input_path=str(image_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                head_source="json",
                head_data=str(head_data),
            )

            result = run_image_pipeline(config, predictor_factory=lambda config: fake)

        self.assertEqual(result.heads[0].person_id, 4)
        self.assertEqual(result.heads[0].bbox, (0.1, 0.25, 0.5, 0.75))

    def test_run_image_pipeline_writes_predictions_json(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            config = make_config(input_path=str(image_path), output_dir=str(Path(tmpdir) / "outputs"))

            result = run_image_pipeline(config, predictor_factory=lambda config: FakePredictor())
            payload = json.loads(result.predictions_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["width"], 10)
        self.assertEqual(payload["height"], 8)
        self.assertEqual(payload["people"][0]["person_id"], 0)

    def test_run_image_pipeline_writes_run_config_json(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            config = make_config(input_path=str(image_path), output_dir=str(Path(tmpdir) / "outputs"))

            result = run_image_pipeline(config, predictor_factory=lambda config: FakePredictor())
            payload = json.loads(result.run_config_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["input_path"], str(image_path))
        self.assertEqual(payload["image_width"], 10)
        self.assertEqual(payload["image_height"], 8)

    def test_run_image_pipeline_saves_heatmaps_when_enabled(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            config = make_config(
                input_path=str(image_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                save_heatmaps=True,
            )

            result = run_image_pipeline(config, predictor_factory=lambda config: FakePredictor())
            self.assertEqual(result.heatmap_paths, ("heatmaps/person_0.pt",))
            self.assertTrue((result.output_dir / "heatmaps" / "person_0.pt").exists())

    def test_run_image_pipeline_saves_rendered_when_enabled(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            config = make_config(
                input_path=str(image_path),
                output_dir=str(Path(tmpdir) / "outputs"),
                save_rendered=True,
            )

            result = run_image_pipeline(config, predictor_factory=lambda config: FakePredictor())

            self.assertIsNotNone(result.rendered_path)
            self.assertTrue(result.rendered_path.exists())
            with Image.open(result.rendered_path) as image:
                self.assertEqual(image.size, (10, 8))

    def test_run_image_pipeline_does_not_save_heatmaps_by_default(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            config = make_config(input_path=str(image_path), output_dir=str(Path(tmpdir) / "outputs"))

            result = run_image_pipeline(config, predictor_factory=lambda config: FakePredictor())
            self.assertEqual(result.heatmap_paths, ())
            self.assertFalse((result.output_dir / "heatmaps").exists())

    def test_run_image_pipeline_does_not_save_rendered_by_default(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            write_test_image(image_path)
            config = make_config(input_path=str(image_path), output_dir=str(Path(tmpdir) / "outputs"))

            result = run_image_pipeline(config, predictor_factory=lambda config: FakePredictor())

            self.assertIsNone(result.rendered_path)
            self.assertFalse((result.output_dir / "rendered.png").exists())

    def test_run_image_pipeline_rejects_invalid_rendered_name(self):
        invalid_names = ("../bad.png", "subdir/rendered.png", "rendered.txt", "")
        for rendered_name in invalid_names:
            with self.subTest(rendered_name=rendered_name):
                with self.assertRaises(ValueError):
                    make_config(rendered_name=rendered_name)

    def test_run_image_pipeline_rejects_invalid_heatmap_alpha(self):
        for alpha in (-0.1, 1.1):
            with self.subTest(alpha=alpha):
                with self.assertRaises(ValueError):
                    make_config(heatmap_alpha=alpha)

    def test_run_image_pipeline_rejects_unsupported_input(self):
        with TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "frame.mov"
            input_path.write_text("not a video", encoding="utf-8")
            fake = FakePredictor()
            config = make_config(input_path=str(input_path), output_dir=str(Path(tmpdir) / "outputs"))

            with self.assertRaisesRegex(ValueError, "video pipeline is not implemented"):
                run_image_pipeline(config, predictor_factory=lambda config: fake)

        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
