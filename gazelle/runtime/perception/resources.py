import hashlib
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
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


def _validate_path_component(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError("MediaPipe asset {} must be a string path component".format(field_name))
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    if (
        value in ("", ".", "..")
        or "\x00" in value
        or "/" in value
        or "\\" in value
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or posix_path.is_absolute()
        or len(windows_path.parts) != 1
        or len(posix_path.parts) != 1
    ):
        raise ValueError(
            "MediaPipe asset {} must be a safe single path component: {!r}".format(
                field_name,
                value,
            )
        )
    return value


def _resolve_contained_path(path: Path, resolved_root: Path, description: str) -> Path:
    if not resolved_root.is_absolute():
        raise ValueError("Containment root must be an absolute resolved path: {}".format(resolved_root))
    resolved_path = path.resolve(strict=False)
    try:
        relative_path = resolved_path.relative_to(resolved_root)
    except ValueError:
        raise ValueError(
            "{} must be contained within {}: {}".format(
                description,
                resolved_root,
                resolved_path,
            )
        )
    if relative_path == Path("."):
        raise ValueError(
            "{} must be a child contained within {}".format(description, resolved_root)
        )
    return resolved_path


def _best_effort_cleanup_task_dir(task_download_dir: Path, downloads_dir: Path) -> None:
    try:
        _resolve_contained_path(
            task_download_dir,
            downloads_dir,
            "MediaPipe task download directory",
        )
        if task_download_dir.is_symlink():
            return
        if task_download_dir.exists():
            shutil.rmtree(task_download_dir)
    except Exception:
        return


def ensure_mediapipe_asset(
    spec: MediaPipeAssetSpec,
    paths: MediaPipeResourcePaths,
    force_download: bool = False,
    downloader: Optional[Callable[[str, str], object]] = None,
) -> Path:
    key = _validate_path_component(spec.key, "key")
    filename = _validate_path_component(spec.filename, "filename")
    destination = paths.mediapipe_dir / filename
    task_download_dir = paths.downloads_dir / key
    downloaded_path = task_download_dir / filename
    downloader = urllib.request.urlretrieve if downloader is None else downloader
    cached_destination_present = False
    task_scope_validated = False
    try:
        resolved_root = paths.root_dir.resolve(strict=False)
        resolved_mediapipe_dir = _resolve_contained_path(
            paths.mediapipe_dir,
            resolved_root,
            "MediaPipe cache directory",
        )
        resolved_downloads_dir = _resolve_contained_path(
            paths.downloads_dir,
            resolved_mediapipe_dir,
            "MediaPipe downloads directory",
        )
        _resolve_contained_path(
            destination,
            resolved_mediapipe_dir,
            "MediaPipe asset destination",
        )
        _resolve_contained_path(
            task_download_dir,
            resolved_downloads_dir,
            "MediaPipe task download directory",
        )
        _resolve_contained_path(
            downloaded_path,
            task_download_dir.resolve(strict=False),
            "MediaPipe downloaded asset",
        )
        task_scope_validated = True

        cached_destination_present = destination.exists() or destination.is_symlink()
        paths.mediapipe_dir.mkdir(parents=True, exist_ok=True)
        if cached_destination_present and not force_download:
            if destination.is_symlink() or not destination.is_file():
                raise RuntimeError(
                    "cached MediaPipe asset is not a regular file: {}".format(destination)
                )
            actual_cached_sha256 = _file_sha256(destination)
            if actual_cached_sha256 != spec.sha256:
                raise RuntimeError(
                    "cached MediaPipe asset SHA-256 mismatch for {}: expected {}, got {}".format(
                        spec.key,
                        spec.sha256,
                        actual_cached_sha256,
                    )
                )
            return destination

        if task_download_dir.exists() or task_download_dir.is_symlink():
            _resolve_contained_path(
                task_download_dir,
                resolved_downloads_dir,
                "MediaPipe task download directory",
            )
            if task_download_dir.is_symlink() or not task_download_dir.is_dir():
                raise RuntimeError(
                    "MediaPipe task download path is not a regular directory: {}".format(
                        task_download_dir
                    )
                )
            shutil.rmtree(task_download_dir)
        task_download_dir.mkdir(parents=True, exist_ok=True)
        resolved_task_download_dir = _resolve_contained_path(
            task_download_dir,
            resolved_downloads_dir,
            "MediaPipe task download directory",
        )
        downloader(spec.url, str(downloaded_path))
        resolved_task_download_dir = _resolve_contained_path(
            task_download_dir,
            resolved_downloads_dir,
            "MediaPipe task download directory",
        )
        _resolve_contained_path(
            downloaded_path,
            resolved_task_download_dir,
            "MediaPipe downloaded asset",
        )
        if (
            not downloaded_path.exists()
            or downloaded_path.is_symlink()
            or not downloaded_path.is_file()
        ):
            raise RuntimeError(
                "MediaPipe asset download completed but a regular file was not found: {}".format(
                    downloaded_path,
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
        resolved_task_download_dir = _resolve_contained_path(
            task_download_dir,
            resolved_downloads_dir,
            "MediaPipe task download directory",
        )
        _resolve_contained_path(
            downloaded_path,
            resolved_task_download_dir,
            "MediaPipe downloaded asset",
        )
        if downloaded_path.is_symlink() or not downloaded_path.is_file():
            raise RuntimeError(
                "Verified MediaPipe asset is no longer a regular file: {}".format(
                    downloaded_path
                )
            )
        _resolve_contained_path(
            destination,
            resolved_mediapipe_dir,
            "MediaPipe asset destination",
        )
        if destination.is_symlink():
            raise RuntimeError(
                "MediaPipe asset destination must not be a symbolic link: {}".format(destination)
            )
        downloaded_path.replace(destination)
        return destination
    except Exception as exc:
        if cached_destination_present:
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
        if task_scope_validated:
            _best_effort_cleanup_task_dir(task_download_dir, resolved_downloads_dir)


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
