import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

from gazelle.runtime.model_registry import CheckpointCandidate, ModelSpec
from gazelle.runtime.resources import (
    CandidateValidationResult,
    ensure_checkpoint,
    load_checkpoint_state_dict,
    prepare_runtime_resources,
    resolve_cache_paths,
    resolve_checkpoint_candidate,
    validate_gazelle_state_dict,
)


class FakeModel:
    def __init__(self):
        self.loaded_state = None

    def get_gazelle_state_dict(self, include_backbone=False):
        state = {
            "decoder.weight": torch.zeros(2, 3),
            "decoder.bias": torch.zeros(2),
        }
        if include_backbone:
            state["backbone.weight"] = torch.zeros(1)
        return state

    def state_dict(self):
        return {
            "backbone.weight": torch.ones(1),
            "decoder.weight": torch.ones(2, 3),
            "decoder.bias": torch.ones(2),
        }

    def load_state_dict(self, state_dict, strict=False):
        if strict and set(state_dict) != set(self.state_dict()):
            raise AssertionError("strict load received wrong keys")
        self.loaded_state = dict(state_dict)


def valid_state_dict():
    return {
        "decoder.weight": torch.ones(2, 3),
        "decoder.bias": torch.ones(2),
    }


class ResourcesTest(unittest.TestCase):
    def test_cache_paths_precedence(self):
        self.assertEqual(resolve_cache_paths("custom").root_dir, Path("custom"))
        self.assertEqual(
            resolve_cache_paths(None, env={"GAZELLE_CACHE_DIR": "env-cache"}).root_dir,
            Path("env-cache"),
        )
        self.assertEqual(resolve_cache_paths(None, env={}).root_dir, Path("models"))

    def test_existing_checkpoint_reuse_does_not_download(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_cache_paths(tmpdir)
            paths.checkpoints_dir.mkdir(parents=True)
            candidate = CheckpointCandidate("test", "model.pt", "https://example.invalid/model.pt")
            checkpoint = paths.checkpoints_dir / candidate.filename
            checkpoint.write_bytes(b"cached")

            def fail_downloader(*args, **kwargs):
                raise AssertionError("downloader should not be called")

            self.assertEqual(ensure_checkpoint(candidate, paths, downloader=fail_downloader), checkpoint)
            self.assertEqual(checkpoint.read_bytes(), b"cached")

    def test_missing_checkpoint_download_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_cache_paths(tmpdir)
            candidate = CheckpointCandidate("test", "model.pt", "https://example.invalid/model.pt")
            calls = []

            def downloader(url, model_dir, file_name, progress, weights_only):
                calls.append((url, model_dir, file_name, progress, weights_only))
                Path(model_dir, file_name).write_bytes(b"downloaded")

            checkpoint = ensure_checkpoint(candidate, paths, downloader=downloader)
            self.assertTrue(checkpoint.exists())
            temp_dir = paths.checkpoints_dir / ".downloads" / candidate.filename
            self.assertEqual(calls, [(candidate.url, str(temp_dir), candidate.filename, True, True)])

    def test_force_download_replaces_cached_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_cache_paths(tmpdir)
            paths.checkpoints_dir.mkdir(parents=True)
            candidate = CheckpointCandidate("test", "model.pt", "https://example.invalid/model.pt")
            checkpoint = paths.checkpoints_dir / candidate.filename
            checkpoint.write_bytes(b"old")

            def downloader(url, model_dir, file_name, progress, weights_only):
                Path(model_dir, file_name).write_bytes(b"new")

            ensure_checkpoint(candidate, paths, force_download=True, downloader=downloader)
            self.assertEqual(checkpoint.read_bytes(), b"new")

    def test_force_download_failure_preserves_cached_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_cache_paths(tmpdir)
            paths.checkpoints_dir.mkdir(parents=True)
            candidate = CheckpointCandidate("test", "model.pt", "https://example.invalid/model.pt")
            checkpoint = paths.checkpoints_dir / candidate.filename
            checkpoint.write_bytes(b"old")

            def downloader(*args, **kwargs):
                raise RuntimeError("network unavailable")

            with self.assertRaisesRegex(RuntimeError, "existing cached checkpoint was preserved"):
                ensure_checkpoint(candidate, paths, force_download=True, downloader=downloader)
            self.assertTrue(checkpoint.exists())
            self.assertEqual(checkpoint.read_bytes(), b"old")

    def test_download_without_created_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = resolve_cache_paths(tmpdir)
            candidate = CheckpointCandidate("test", "model.pt", "https://example.invalid/model.pt")

            def downloader(*args, **kwargs):
                return None

            with self.assertRaisesRegex(RuntimeError, "Checkpoint download completed but file was not found"):
                ensure_checkpoint(candidate, paths, downloader=downloader)
            self.assertFalse((paths.checkpoints_dir / candidate.filename).exists())

    def test_load_checkpoint_state_dict_unwraps_top_level_state_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "model.pt"
            torch.save({"state_dict": valid_state_dict()}, checkpoint)
            state_dict, top_level_type = load_checkpoint_state_dict(checkpoint)
            self.assertEqual(top_level_type, "dict")
            self.assertEqual(set(state_dict), set(valid_state_dict()))

    def test_strict_validation_success(self):
        state_dict = validate_gazelle_state_dict(FakeModel(), valid_state_dict())
        self.assertEqual(set(state_dict), set(valid_state_dict()))

    def test_strict_validation_rejects_empty_state_dict(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            validate_gazelle_state_dict(FakeModel(), {})

    def test_strict_validation_rejects_missing_keys(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_gazelle_state_dict(FakeModel(), {"decoder.weight": torch.ones(2, 3)})

    def test_strict_validation_rejects_unexpected_keys(self):
        state_dict = valid_state_dict()
        state_dict["extra.weight"] = torch.ones(1)
        with self.assertRaisesRegex(ValueError, "unexpected"):
            validate_gazelle_state_dict(FakeModel(), state_dict)

    def test_strict_validation_rejects_shape_mismatch(self):
        state_dict = valid_state_dict()
        state_dict["decoder.bias"] = torch.ones(3)
        with self.assertRaisesRegex(ValueError, "shape mismatch"):
            validate_gazelle_state_dict(FakeModel(), state_dict)

    def test_strict_validation_rejects_non_tensor_values(self):
        state_dict = valid_state_dict()
        state_dict["decoder.bias"] = [1, 2]
        with self.assertRaisesRegex(ValueError, "non-tensor"):
            validate_gazelle_state_dict(FakeModel(), state_dict)

    def test_prepare_runtime_resources_rejects_missing_user_checkpoint_before_model_construction(self):
        config = SimpleNamespace(
            model="gazelle_dinov2_vitb14_inout",
            cache_dir=None,
            checkpoint="missing.pt",
            force_download=False,
        )
        with patch.dict(sys.modules, {"gazelle.model": types.ModuleType("gazelle.model")}):
            with self.assertRaises(FileNotFoundError):
                prepare_runtime_resources(config)

    def test_prepare_runtime_resources_loads_user_checkpoint_without_download(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "user.pt"
            torch.save(valid_state_dict(), checkpoint)
            fake_module = types.ModuleType("gazelle.model")
            fake_module.get_gazelle_model = lambda name: (FakeModel(), object())
            config = SimpleNamespace(
                model="gazelle_dinov2_vitb14_inout",
                cache_dir=tmpdir,
                checkpoint=str(checkpoint),
                force_download=False,
            )
            with patch.dict(sys.modules, {"gazelle.model": fake_module}):
                prepared = prepare_runtime_resources(config)
            self.assertEqual(prepared.checkpoint_path, checkpoint)
            self.assertIsNone(prepared.checkpoint_candidate)

    def test_prepare_runtime_resources_disables_xformers_during_model_construction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "user.pt"
            torch.save(valid_state_dict(), checkpoint)
            observed_xformers_disabled = []
            fake_module = types.ModuleType("gazelle.model")

            def fake_get_gazelle_model(name):
                observed_xformers_disabled.append(os.environ.get("XFORMERS_DISABLED"))
                return FakeModel(), object()

            fake_module.get_gazelle_model = fake_get_gazelle_model
            config = SimpleNamespace(
                model="gazelle_dinov2_vitb14_inout",
                cache_dir=tmpdir,
                checkpoint=str(checkpoint),
                force_download=False,
            )

            with patch.dict(os.environ, {}, clear=True):
                with patch.dict(sys.modules, {"gazelle.model": fake_module}):
                    prepare_runtime_resources(config)
                self.assertIsNone(os.environ.get("XFORMERS_DISABLED"))

            self.assertEqual(observed_xformers_disabled, ["1"])

    def test_prepare_runtime_resources_downloads_registered_checkpoint_with_mocked_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_module = types.ModuleType("gazelle.model")
            fake_module.get_gazelle_model = lambda name: (FakeModel(), object())
            config = SimpleNamespace(
                model="gazelle_dinov2_vitb14_inout",
                cache_dir=tmpdir,
                checkpoint=None,
                force_download=False,
            )

            def downloader(url, model_dir, file_name, progress, weights_only):
                torch.save(valid_state_dict(), Path(model_dir, file_name))

            with patch.dict(sys.modules, {"gazelle.model": fake_module}):
                with patch("gazelle.runtime.resources.torch.hub.load_state_dict_from_url", side_effect=downloader):
                    prepared = prepare_runtime_resources(config)

            self.assertIsNotNone(prepared.checkpoint_candidate)
            self.assertEqual(len(prepared.candidate_results), 1)
            self.assertEqual(
                prepared.checkpoint_path,
                Path(tmpdir) / "checkpoints" / "gazelle_dinov2_vitb14_inout.pt",
            )
            self.assertTrue(prepared.checkpoint_path.exists())

    def test_resolve_checkpoint_candidate_selects_single_success(self):
        readme = CheckpointCandidate("README", "readme.pt", "https://example.invalid/readme.pt")
        hub = CheckpointCandidate("hubconf.py", "hub.pt", "https://example.invalid/hub.pt")
        spec = ModelSpec("model", "backbone", False, (448, 448), (readme, hub))
        failure = CandidateValidationResult(readme, Path("readme.pt"), None, None, None, False, "bad")
        success = CandidateValidationResult(hub, Path("hub.pt"), 10, "abc", "dict", True)

        with patch(
            "gazelle.runtime.resources._validate_candidate",
            side_effect=[(failure, None), (success, valid_state_dict())],
        ):
            candidate, checkpoint_path, results = resolve_checkpoint_candidate(
                spec,
                FakeModel(),
                resolve_cache_paths("models"),
            )

        self.assertEqual(candidate, hub)
        self.assertEqual(checkpoint_path, Path("hub.pt"))
        self.assertEqual(len(results), 2)

    def test_resolve_checkpoint_candidate_prefers_readme_when_equivalent(self):
        readme = CheckpointCandidate("README", "readme.pt", "https://example.invalid/readme.pt")
        hub = CheckpointCandidate("hubconf.py", "hub.pt", "https://example.invalid/hub.pt")
        spec = ModelSpec("model", "backbone", False, (448, 448), (readme, hub))
        readme_result = CandidateValidationResult(readme, Path("readme.pt"), 10, "abc", "dict", True)
        hub_result = CandidateValidationResult(hub, Path("hub.pt"), 10, "abc", "dict", True)

        with patch(
            "gazelle.runtime.resources._validate_candidate",
            side_effect=[
                (readme_result, valid_state_dict()),
                (hub_result, valid_state_dict()),
            ],
        ):
            candidate, checkpoint_path, _ = resolve_checkpoint_candidate(
                spec,
                FakeModel(),
                resolve_cache_paths("models"),
            )

        self.assertEqual(candidate, readme)
        self.assertEqual(checkpoint_path, Path("readme.pt"))

    def test_resolve_checkpoint_candidate_rejects_different_successes(self):
        readme = CheckpointCandidate("README", "readme.pt", "https://example.invalid/readme.pt")
        hub = CheckpointCandidate("hubconf.py", "hub.pt", "https://example.invalid/hub.pt")
        spec = ModelSpec("model", "backbone", False, (448, 448), (readme, hub))
        readme_result = CandidateValidationResult(readme, Path("readme.pt"), 10, "abc", "dict", True)
        hub_result = CandidateValidationResult(hub, Path("hub.pt"), 10, "def", "dict", True)
        other_state_dict = valid_state_dict()
        other_state_dict["decoder.bias"] = torch.zeros(2)

        with patch(
            "gazelle.runtime.resources._validate_candidate",
            side_effect=[
                (readme_result, valid_state_dict()),
                (hub_result, other_state_dict),
            ],
        ):
            with self.assertRaisesRegex(RuntimeError, "contents differ"):
                resolve_checkpoint_candidate(spec, FakeModel(), resolve_cache_paths("models"))


if __name__ == "__main__":
    unittest.main()
