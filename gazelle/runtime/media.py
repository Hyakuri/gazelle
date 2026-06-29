from dataclasses import dataclass
import math
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError


SUPPORTED_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
SUPPORTED_VIDEO_SUFFIXES = (".mp4", ".avi", ".mov", ".mkv", ".m4v")


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    width: int
    height: int
    fps: float
    frame_count: Optional[int]


@dataclass(frozen=True)
class VideoFrame:
    index: int
    timestamp_ms: float
    image: Image.Image


def is_supported_image_path(path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_IMAGE_SUFFIXES


def is_supported_video_path(path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_VIDEO_SUFFIXES


def detect_media_type(path) -> str:
    if is_supported_image_path(path):
        return "image"
    if is_supported_video_path(path):
        return "video"
    raise ValueError(
        "Unsupported input path '{}'. Supported image suffixes: {}; video suffixes: {}.".format(
            path,
            ", ".join(SUPPORTED_IMAGE_SUFFIXES),
            ", ".join(SUPPORTED_VIDEO_SUFFIXES),
        )
    )


def load_image_rgb(path) -> Tuple[Image.Image, int, int]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("Input image does not exist: {}".format(path))
    if not is_supported_image_path(path):
        raise ValueError(
            "Unsupported input path for image pipeline: {}".format(path)
        )

    try:
        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            rgb_image.load()
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Failed to open image '{}': {}".format(path, exc)) from exc

    return rgb_image, rgb_image.width, rgb_image.height


def _import_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for video input and output") from exc
    return cv2


def _import_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("NumPy is required for video input and output") from exc
    return np


def _valid_positive_number(value) -> bool:
    try:
        return math.isfinite(float(value)) and float(value) > 0.0
    except (TypeError, ValueError):
        return False


def _valid_non_negative_number(value) -> bool:
    try:
        return math.isfinite(float(value)) and float(value) >= 0.0
    except (TypeError, ValueError):
        return False


def resolve_video_fps(source_fps, output_fps=None) -> float:
    if _valid_positive_number(source_fps):
        return float(source_fps)
    if _valid_positive_number(output_fps):
        return float(output_fps)
    return 30.0


class VideoFrameReader:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError("Input video does not exist: {}".format(self.path))
        if not is_supported_video_path(self.path):
            raise ValueError("Unsupported video input path: {}".format(self.path))

        cv2 = _import_cv2()
        self._cv2 = cv2
        self._capture = cv2.VideoCapture(str(self.path))
        if not self._capture.isOpened():
            self._capture.release()
            self._capture = None
            raise ValueError("Failed to open video: {}".format(self.path))

        width = int(round(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
        height = int(round(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        if width <= 0 or height <= 0:
            self.close()
            raise ValueError("Video has invalid dimensions: {}".format(self.path))

        fps = float(self._capture.get(cv2.CAP_PROP_FPS))
        frame_count_raw = self._capture.get(cv2.CAP_PROP_FRAME_COUNT)
        frame_count = None
        if _valid_positive_number(frame_count_raw):
            frame_count = int(round(frame_count_raw))

        self._metadata = VideoMetadata(
            path=self.path,
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
        )

    @property
    def metadata(self) -> VideoMetadata:
        return self._metadata

    def __iter__(self):
        frame_index = 0
        while self._capture is not None:
            ok, frame_bgr = self._capture.read()
            if not ok:
                break

            timestamp_ms = self._capture.get(self._cv2.CAP_PROP_POS_MSEC)
            if (
                not _valid_non_negative_number(timestamp_ms)
                or (frame_index > 0 and float(timestamp_ms) <= 0.0)
            ):
                timestamp_ms = frame_index / resolve_video_fps(self._metadata.fps) * 1000.0

            frame_rgb = self._cv2.cvtColor(frame_bgr, self._cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb).convert("RGB")
            yield VideoFrame(index=frame_index, timestamp_ms=float(timestamp_ms), image=image)
            frame_index += 1

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "VideoFrameReader":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class VideoFrameWriter:
    def __init__(self, path, width: int, height: int, fps):
        if not _valid_positive_number(fps):
            raise ValueError("Video output FPS must be greater than 0")
        if int(width) <= 0 or int(height) <= 0:
            raise ValueError("Video output dimensions must be positive")

        cv2 = _import_cv2()
        self._cv2 = cv2
        self._np = _import_numpy()
        self.path = Path(path)
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, (self.width, self.height))
        if not self._writer.isOpened():
            self._writer.release()
            self._writer = None
            raise ValueError("Failed to open video writer: {}".format(self.path))

    def write(self, image) -> None:
        if self._writer is None:
            raise ValueError("Video writer is closed")
        rgb_image = image.convert("RGB")
        if rgb_image.size != (self.width, self.height):
            raise ValueError(
                "Video frame size {} does not match writer size {}".format(
                    rgb_image.size,
                    (self.width, self.height),
                )
            )
        frame_rgb = self._np.asarray(rgb_image)
        frame_bgr = self._cv2.cvtColor(frame_rgb, self._cv2.COLOR_RGB2BGR)
        self._writer.write(frame_bgr)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def __enter__(self) -> "VideoFrameWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
