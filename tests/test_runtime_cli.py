from contextlib import redirect_stderr
import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gazelle.runtime.cli import build_parser, main, parse_runtime_config
from gazelle.runtime.config import validate_device_name


class RuntimeCliTest(unittest.TestCase):
    def assert_no_model_modules_newly_imported(self, callback):
        before = set(sys.modules)
        callback()
        newly_imported = set(sys.modules) - before
        self.assertNotIn("gazelle.model", newly_imported)
        self.assertNotIn("gazelle.backbone", newly_imported)

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

    def test_prepare_only_config_does_not_require_input(self):
        config = parse_runtime_config(["--prepare-only", "--cache-dir", "models"])
        self.assertTrue(config.prepare_only)
        self.assertIsNone(config.input_path)
        self.assertEqual(config.cache_dir, "models")

    def test_prepare_only_route_calls_resource_preparation(self):
        prepared = SimpleNamespace(
            model_name="gazelle_dinov2_vitb14_inout",
            checkpoint_path="models/checkpoints/example.pt",
            cache_paths=SimpleNamespace(root_dir="models", torch_hub_dir="models/torch_hub"),
            candidate_results=(),
        )
        with patch("gazelle.runtime.resources.prepare_runtime_resources", return_value=prepared) as mock_prepare:
            stdout = io.StringIO()
            exit_code = main(["--prepare-only", "--cache-dir", "models"], stdout=stdout)
        self.assertEqual(exit_code, 0)
        mock_prepare.assert_called_once()
        self.assertIn("Prepared Gazelle resources", stdout.getvalue())

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

    def test_no_action_returns_argparse_error(self):
        with self.assertRaises(SystemExit) as cm:
            main([])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
