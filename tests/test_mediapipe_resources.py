import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gazelle.runtime.perception.resources import (
    MEDIAPIPE_ASSET_SPECS,
    MediaPipeAssetSpec,
    MediaPipeResourcePaths,
    ensure_mediapipe_asset,
    get_required_mediapipe_specs,
    prepare_mediapipe_resources,
    resolve_mediapipe_resource_paths,
)


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


class MediaPipeResourcesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root_dir = Path(self.temp_dir.name)
        self.paths = MediaPipeResourcePaths(
            root_dir=root_dir,
            mediapipe_dir=root_dir / "mediapipe",
            downloads_dir=root_dir / "mediapipe" / ".downloads",
        )
        self.new_content = b"verified-new-asset"
        self.spec = MediaPipeAssetSpec(
            key="fake_asset",
            filename="fake_asset.task",
            url="https://example.invalid/fake_asset.task",
            sha256=sha256_bytes(self.new_content),
        )

    @property
    def asset_path(self):
        return self.paths.mediapipe_dir / self.spec.filename

    @property
    def task_download_dir(self):
        return self.paths.downloads_dir / self.spec.key

    def write_cached_asset(self, content):
        self.asset_path.parent.mkdir(parents=True, exist_ok=True)
        self.asset_path.write_bytes(content)

    def test_registry_contains_exact_versioned_official_assets(self):
        expected = {
            "face_detector": (
                "blaze_face_full_range.tflite",
                "https://storage.googleapis.com/mediapipe-models/face_detector/"
                "blaze_face_full_range/float16/1/blaze_face_full_range.tflite",
                "3698b18f063835bc609069ef052228fbe86d9c9a6dc8dcb7c7c2d69aed2b181b",
            ),
            "face_landmarker": (
                "face_landmarker.task",
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                "face_landmarker/float16/1/face_landmarker.task",
                "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
            ),
            "pose_landmarker_lite": (
                "pose_landmarker_lite.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                "pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
                "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
            ),
            "pose_landmarker_full": (
                "pose_landmarker_full.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                "pose_landmarker_full/float16/1/pose_landmarker_full.task",
                "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1",
            ),
            "pose_landmarker_heavy": (
                "pose_landmarker_heavy.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                "pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
                "64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b",
            ),
        }

        self.assertEqual(
            {
                key: (spec.filename, spec.url, spec.sha256)
                for key, spec in MEDIAPIPE_ASSET_SPECS.items()
            },
            expected,
        )

    def test_cache_reuse_does_not_download(self):
        self.write_cached_asset(self.new_content)

        def unexpected_downloader(url, destination):
            raise AssertionError("cached assets must not be downloaded again")

        result = ensure_mediapipe_asset(
            self.spec,
            self.paths,
            downloader=unexpected_downloader,
        )

        self.assertEqual(result, self.asset_path)
        self.assertEqual(self.asset_path.read_bytes(), self.new_content)
        self.assertFalse(self.task_download_dir.exists())

    def test_force_download_failure_preserves_cached_asset(self):
        self.write_cached_asset(b"old")

        def failing_downloader(url, destination):
            raise OSError("offline")

        with self.assertRaisesRegex(RuntimeError, "preserved"):
            ensure_mediapipe_asset(
                self.spec,
                self.paths,
                force_download=True,
                downloader=failing_downloader,
            )

        self.assertEqual(self.asset_path.read_bytes(), b"old")
        self.assertFalse(self.task_download_dir.exists())

    def test_hash_mismatch_rejects_download(self):
        def wrong_content_downloader(url, destination):
            Path(destination).write_bytes(b"wrong")

        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            ensure_mediapipe_asset(
                self.spec,
                self.paths,
                downloader=wrong_content_downloader,
            )

        self.assertFalse(self.asset_path.exists())
        self.assertFalse(self.task_download_dir.exists())

    def test_missing_downloaded_file_is_rejected(self):
        def missing_file_downloader(url, destination):
            return None

        with self.assertRaisesRegex(RuntimeError, "was not found"):
            ensure_mediapipe_asset(
                self.spec,
                self.paths,
                downloader=missing_file_downloader,
            )

        self.assertFalse(self.asset_path.exists())
        self.assertFalse(self.task_download_dir.exists())

    def test_verified_download_atomically_replaces_cached_asset(self):
        self.write_cached_asset(b"old")
        observed_download_paths = []

        def successful_downloader(url, destination):
            destination = Path(destination)
            observed_download_paths.append(destination)
            self.assertEqual(self.asset_path.read_bytes(), b"old")
            destination.write_bytes(self.new_content)

        result = ensure_mediapipe_asset(
            self.spec,
            self.paths,
            force_download=True,
            downloader=successful_downloader,
        )

        self.assertEqual(result, self.asset_path)
        self.assertEqual(self.asset_path.read_bytes(), self.new_content)
        self.assertEqual(
            observed_download_paths,
            [self.task_download_dir / self.spec.filename],
        )
        self.assertFalse(self.task_download_dir.exists())

    def test_hash_failure_preserves_cached_asset_and_cleans_download(self):
        self.write_cached_asset(b"old")

        def wrong_content_downloader(url, destination):
            Path(destination).write_bytes(b"wrong")

        with self.assertRaisesRegex(RuntimeError, "preserved"):
            ensure_mediapipe_asset(
                self.spec,
                self.paths,
                force_download=True,
                downloader=wrong_content_downloader,
            )

        self.assertEqual(self.asset_path.read_bytes(), b"old")
        self.assertFalse(self.task_download_dir.exists())

    def test_selected_pose_variant_is_required(self):
        specs = get_required_mediapipe_specs("heavy")

        self.assertEqual(
            tuple(spec.key for spec in specs),
            ("face_detector", "face_landmarker", "pose_landmarker_heavy"),
        )

    def test_unknown_pose_variant_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported MediaPipe pose model"):
            get_required_mediapipe_specs("medium")

    def test_cache_root_priority_matches_runtime_resources(self):
        with patch.dict(os.environ, {"GAZELLE_CACHE_DIR": "env-cache"}, clear=True):
            self.assertEqual(
                resolve_mediapipe_resource_paths("cli-cache").root_dir,
                Path("cli-cache"),
            )
            self.assertEqual(
                resolve_mediapipe_resource_paths(None).root_dir,
                Path("env-cache"),
            )
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                resolve_mediapipe_resource_paths(None).root_dir,
                Path("models"),
            )

    def test_prepare_returns_selected_resource_paths(self):
        config = SimpleNamespace(
            cache_dir=self.temp_dir.name,
            pose_model="lite",
            force_download=True,
        )

        def fake_ensure(spec, paths, force_download=False, downloader=None):
            self.assertTrue(force_download)
            return paths.mediapipe_dir / spec.filename

        with patch(
            "gazelle.runtime.perception.resources.ensure_mediapipe_asset",
            side_effect=fake_ensure,
        ) as mock_ensure:
            prepared = prepare_mediapipe_resources(config)

        self.assertEqual(mock_ensure.call_count, 3)
        self.assertEqual(prepared.pose_model, "lite")
        self.assertEqual(prepared.face_detector_path.name, "blaze_face_full_range.tflite")
        self.assertEqual(prepared.face_landmarker_path.name, "face_landmarker.task")
        self.assertEqual(prepared.pose_landmarker_path.name, "pose_landmarker_lite.task")
        self.assertEqual(prepared.cache_paths.root_dir, Path(self.temp_dir.name))


if __name__ == "__main__":
    unittest.main()
