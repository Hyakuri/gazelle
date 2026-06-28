import unittest

from gazelle.runtime.model_registry import (
    format_model_table,
    get_model_spec,
    iter_model_specs,
    supported_model_names,
)


class ModelRegistryTest(unittest.TestCase):
    def test_lists_only_source_supported_models(self):
        self.assertEqual(
            supported_model_names(),
            (
                "gazelle_dinov2_vitb14",
                "gazelle_dinov2_vitl14",
                "gazelle_dinov2_vitb14_inout",
                "gazelle_dinov2_vitl14_inout",
            ),
        )

    def test_specs_are_unique(self):
        names = [spec.name for spec in iter_model_specs()]
        self.assertEqual(len(names), len(set(names)))

    def test_inout_flags_match_model_names(self):
        self.assertFalse(get_model_spec("gazelle_dinov2_vitb14").supports_inout)
        self.assertFalse(get_model_spec("gazelle_dinov2_vitl14").supports_inout)
        self.assertTrue(get_model_spec("gazelle_dinov2_vitb14_inout").supports_inout)
        self.assertTrue(get_model_spec("gazelle_dinov2_vitl14_inout").supports_inout)

    def test_vitb14_non_inout_uses_verified_readme_checkpoint(self):
        spec = get_model_spec("gazelle_dinov2_vitb14")
        filenames = [candidate.filename for candidate in spec.checkpoint_candidates]
        self.assertEqual(filenames, ["gazelle_dinov2_vitb14.pt"])
        self.assertFalse(spec.has_ambiguous_checkpoint)

    def test_unknown_model_has_readable_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown Gazelle model"):
            get_model_spec("gazelle_dinov2_vitb14_childplay")

    def test_format_model_table_does_not_require_model_construction(self):
        table = format_model_table()
        self.assertIn("gazelle_dinov2_vitl14_inout", table)
        self.assertIn("gazelle_dinov2_vitb14.pt", table)


if __name__ == "__main__":
    unittest.main()
