import hashlib
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from gazelle.runtime.resources import resolve_cache_root


@dataclass(frozen=True)
class MediaPipeAssetSpec:
    key: str
    filename: str
    url: str
    sha256: str


@dataclass(frozen=True)
class MediaPipeResourcePaths:
    root_dir: Path
    mediapipe_dir: Path
    downloads_dir: Path


@dataclass(frozen=True)
class PreparedMediaPipeResources:
    face_detector_path: Path
    face_landmarker_path: Path
    pose_landmarker_path: Path
    pose_model: str
    cache_paths: MediaPipeResourcePaths


MEDIAPIPE_ASSET_SPECS = {
    "face_detector": MediaPipeAssetSpec(
        key="face_detector",
        filename="blaze_face_full_range.tflite",
        url=(
            "https://storage.googleapis.com/mediapipe-models/face_detector/"
            "blaze_face_full_range/float16/1/blaze_face_full_range.tflite"
        ),
        sha256="3698b18f063835bc609069ef052228fbe86d9c9a6dc8dcb7c7c2d69aed2b181b",
    ),
    "face_landmarker": MediaPipeAssetSpec(
        key="face_landmarker",
        filename="face_landmarker.task",
        url=(
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/1/face_landmarker.task"
        ),
        sha256="64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
    "pose_landmarker_lite": MediaPipeAssetSpec(
        key="pose_landmarker_lite",
        filename="pose_landmarker_lite.task",
        url=(
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
        ),
        sha256="59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
    ),
    "pose_landmarker_full": MediaPipeAssetSpec(
        key="pose_landmarker_full",
        filename="pose_landmarker_full.task",
        url=(
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_full/float16/1/pose_landmarker_full.task"
        ),
        sha256="5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1",
    ),
    "pose_landmarker_heavy": MediaPipeAssetSpec(
        key="pose_landmarker_heavy",
        filename="pose_landmarker_heavy.task",
        url=(
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
        ),
        sha256="64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b",
    ),
}


def resolve_mediapipe_resource_paths(cache_dir: Optional[str] = None) -> MediaPipeResourcePaths:
    root_dir = resolve_cache_root(cache_dir)
    mediapipe_dir = root_dir / "mediapipe"
    return MediaPipeResourcePaths(
        root_dir=root_dir,
        mediapipe_dir=mediapipe_dir,
        downloads_dir=mediapipe_dir / ".downloads",
    )


def get_required_mediapipe_specs(pose_model: str) -> Tuple[MediaPipeAssetSpec, ...]:
    pose_key = "pose_landmarker_{}".format(pose_model)
    if pose_key not in MEDIAPIPE_ASSET_SPECS:
        raise ValueError("Unsupported MediaPipe pose model: {}".format(pose_model))
    return (
        MEDIAPIPE_ASSET_SPECS["face_detector"],
        MEDIAPIPE_ASSET_SPECS["face_landmarker"],
        MEDIAPIPE_ASSET_SPECS[pose_key],
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_mediapipe_asset(
    spec: MediaPipeAssetSpec,
    paths: MediaPipeResourcePaths,
    force_download: bool = False,
    downloader: Optional[Callable[[str, str], object]] = None,
) -> Path:
    paths.mediapipe_dir.mkdir(parents=True, exist_ok=True)
    destination = paths.mediapipe_dir / spec.filename
    if destination.exists() and not force_download:
        return destination

    downloader = urllib.request.urlretrieve if downloader is None else downloader
    task_download_dir = paths.downloads_dir / spec.key
    downloaded_path = task_download_dir / spec.filename
    try:
        if task_download_dir.exists():
            shutil.rmtree(task_download_dir)
        task_download_dir.mkdir(parents=True, exist_ok=True)
        downloader(spec.url, str(downloaded_path))
        if not downloaded_path.exists():
            raise RuntimeError(
                "MediaPipe asset download completed but file was not found: {}".format(
                    downloaded_path
                )
            )
        actual_sha256 = _file_sha256(downloaded_path)
        if actual_sha256 != spec.sha256:
            raise RuntimeError(
                "MediaPipe asset SHA-256 mismatch for {}: expected {}, got {}".format(
                    spec.key,
                    spec.sha256,
                    actual_sha256,
                )
            )
        downloaded_path.replace(destination)
        return destination
    except Exception as exc:
        if destination.exists():
            raise RuntimeError(
                "Failed to prepare MediaPipe asset {} from {}; existing cached asset was "
                "preserved at {}: {}".format(
                    spec.key,
                    spec.url,
                    destination,
                    exc,
                )
            ) from exc
        raise RuntimeError(
            "Failed to prepare MediaPipe asset {} from {}: {}".format(
                spec.key,
                spec.url,
                exc,
            )
        ) from exc
    finally:
        if task_download_dir.exists():
            shutil.rmtree(task_download_dir)


def prepare_mediapipe_resources(config) -> PreparedMediaPipeResources:
    paths = resolve_mediapipe_resource_paths(config.cache_dir)
    prepared_by_key: Dict[str, Path] = {}
    for spec in get_required_mediapipe_specs(config.pose_model):
        prepared_by_key[spec.key] = ensure_mediapipe_asset(
            spec,
            paths,
            force_download=config.force_download,
        )
    return PreparedMediaPipeResources(
        face_detector_path=prepared_by_key["face_detector"],
        face_landmarker_path=prepared_by_key["face_landmarker"],
        pose_landmarker_path=prepared_by_key["pose_landmarker_{}".format(config.pose_model)],
        pose_model=config.pose_model,
        cache_paths=paths,
    )
