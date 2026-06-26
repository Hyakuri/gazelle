import io
import sys
import unittest

from gazelle.runtime.cli import build_parser, main, parse_runtime_config


class RuntimeCliTest(unittest.TestCase):
    def test_help_exits_without_model_construction_imports(self):
        parser = build_parser()
        with self.assertRaises(SystemExit) as cm:
            parser.parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertNotIn("gazelle.backbone", sys.modules)

    def test_list_models_returns_registered_models(self):
        stdout = io.StringIO()
        exit_code = main(["--list-models"], stdout=stdout)
        self.assertEqual(exit_code, 0)
        self.assertIn("gazelle_dinov2_vitb14_inout", stdout.getvalue())
        self.assertNotIn("gazelle.backbone", sys.modules)

    def test_parse_config_accepts_default_model(self):
        config = parse_runtime_config(["--list-models"])
        self.assertTrue(config.list_models)
        self.assertEqual(config.model, "gazelle_dinov2_vitb14_inout")

    def test_invalid_model_is_rejected_by_argparse(self):
        with self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--list-models", "--model", "bad"])
        self.assertEqual(cm.exception.code, 2)

    def test_invalid_device_is_rejected_by_config(self):
        with self.assertRaises(SystemExit) as cm:
            parse_runtime_config(["--list-models", "--device", "gpu0"])
        self.assertEqual(cm.exception.code, 2)

    def test_no_action_returns_argparse_error(self):
        with self.assertRaises(SystemExit) as cm:
            main([])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
