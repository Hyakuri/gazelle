import math
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Mapping, Optional, Tuple

import numpy as np

from gazelle.runtime.perception.contracts import (
    FaceObservation,
    HeadPoseAngles,
    NormalizedLandmark,
    PoseObservation,
)
from gazelle.runtime.perception.resources import PreparedMediaPipeResources


def import_mediapipe():
    try:
        import mediapipe as mp
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MediaPipe head detection requires the 'mediapipe' package"
        ) from exc
    return mp


@dataclass(frozen=True)
class FaceCropConfig:
    expand_left: float = 0.20
    expand_right: float = 0.20
    expand_top: float = 0.40
    expand_bottom: float = 0.15
    min_size_pixels: int = 2


@dataclass(frozen=True)
class MediaPipeTaskBundle:
    face_detector: object
    face_landmarker: object
    pose_landmarker: object
    image_factory: Callable[[np.ndarray], object]


@dataclass(frozen=True)
class MediaPipeFrameObservations:
    faces: Tuple[FaceObservation, ...]
    poses: Tuple[PoseObservation, ...]
    timings_ms: Mapping[str, float]


def _close_tasks(tasks, *, suppress_errors: bool) -> None:
    first_error = None
    for task in reversed(tuple(tasks)):
        try:
            task.close()
        except Exception as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None and not suppress_errors:
        raise first_error


def _create_mediapipe_task_bundle(
    *,
    face_detector_path: Path,
    face_landmarker_path: Path,
    pose_landmarker_path: Path,
    running_mode: str,
    max_heads: int,
    face_landmarker_running_mode: str,
) -> MediaPipeTaskBundle:
    mp = import_mediapipe()
    vision = mp.tasks.vision
    detector_pose_mode = getattr(vision.RunningMode, running_mode)
    face_mode = getattr(vision.RunningMode, face_landmarker_running_mode)
    created_tasks = []
    try:
        face_detector = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path=str(face_detector_path),
                ),
                running_mode=detector_pose_mode,
            )
        )
        created_tasks.append(face_detector)
        face_landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path=str(face_landmarker_path),
                ),
                running_mode=face_mode,
                num_faces=max_heads,
                output_facial_transformation_matrixes=True,
            )
        )
        created_tasks.append(face_landmarker)
        pose_landmarker = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path=str(pose_landmarker_path),
                ),
                running_mode=detector_pose_mode,
                num_poses=max_heads,
            )
        )
        created_tasks.append(pose_landmarker)
    except Exception:
        _close_tasks(created_tasks, suppress_errors=True)
        raise

    def image_factory(array):
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=array)

    return MediaPipeTaskBundle(
        face_detector=face_detector,
        face_landmarker=face_landmarker,
        pose_landmarker=pose_landmarker,
        image_factory=image_factory,
    )


def _optional_float(value):
    if value is None:
        return None
    return float(value)


def _convert_landmark(landmark) -> NormalizedLandmark:
    return NormalizedLandmark(
        x=float(landmark.x),
        y=float(landmark.y),
        z=_optional_float(getattr(landmark, "z", None)),
        visibility=_optional_float(getattr(landmark, "visibility", None)),
        presence=_optional_float(getattr(landmark, "presence", None)),
    )


def _detection_confidence(detection) -> float:
    categories = getattr(detection, "categories", ())
    if not categories:
        return 0.0
    score = float(categories[0].score)
    return score if math.isfinite(score) else 0.0


def _crop_box(
    detection,
    image_width: int,
    image_height: int,
    config: FaceCropConfig,
):
    box = detection.bounding_box
    x1 = float(box.origin_x)
    y1 = float(box.origin_y)
    width = float(box.width)
    height = float(box.height)
    if not all(math.isfinite(value) for value in (x1, y1, width, height)):
        return None
    if width <= 0.0 or height <= 0.0:
        return None

    expanded_left = max(0.0, x1 - config.expand_left * width)
    expanded_top = max(0.0, y1 - config.expand_top * height)
    expanded_right = min(
        float(image_width),
        x1 + width + config.expand_right * width,
    )
    expanded_bottom = min(
        float(image_height),
        y1 + height + config.expand_bottom * height,
    )
    if (
        expanded_right - expanded_left < config.min_size_pixels
        or expanded_bottom - expanded_top < config.min_size_pixels
    ):
        return None

    left = max(0, int(math.floor(expanded_left)))
    top = max(0, int(math.floor(expanded_top)))
    right = min(image_width, int(math.ceil(expanded_right)))
    bottom = min(image_height, int(math.ceil(expanded_bottom)))
    if right - left < config.min_size_pixels or bottom - top < config.min_size_pixels:
        return None
    return left, top, right, bottom


def _normalized_detection_box(detection, image_width: int, image_height: int):
    box = detection.bounding_box
    x1 = max(0.0, min(float(image_width), float(box.origin_x)))
    y1 = max(0.0, min(float(image_height), float(box.origin_y)))
    x2 = max(0.0, min(float(image_width), float(box.origin_x) + float(box.width)))
    y2 = max(0.0, min(float(image_height), float(box.origin_y) + float(box.height)))
    return (
        x1 / image_width,
        y1 / image_height,
        x2 / image_width,
        y2 / image_height,
    )


def _remap_face_landmark(
    landmark,
    crop_box,
    image_width: int,
    image_height: int,
) -> NormalizedLandmark:
    left, top, right, bottom = crop_box
    crop_width = right - left
    crop_height = bottom - top
    z = getattr(landmark, "z", None)
    return NormalizedLandmark(
        x=(left + float(landmark.x) * crop_width) / image_width,
        y=(top + float(landmark.y) * crop_height) / image_height,
        z=None if z is None else float(z) * crop_width / image_width,
        visibility=_optional_float(getattr(landmark, "visibility", None)),
        presence=_optional_float(getattr(landmark, "presence", None)),
    )


def _matrix_tuple(matrix):
    try:
        rows = tuple(tuple(float(value) for value in row) for row in matrix)
    except (TypeError, ValueError):
        return None
    if len(rows) < 3 or any(len(row) < 3 for row in rows[:3]):
        return None
    if not all(math.isfinite(value) for row in rows for value in row):
        return None
    return rows


def _matrix_to_head_pose(matrix) -> Optional[HeadPoseAngles]:
    if matrix is None:
        return None
    r00, _, _ = matrix[0][:3]
    r10, r11, r12 = matrix[1][:3]
    r20, r21, r22 = matrix[2][:3]
    horizontal = math.hypot(r00, r10)
    yaw = math.atan2(-r20, horizontal)
    if horizontal > 1e-8:
        pitch = math.atan2(r21, r22)
        roll = math.atan2(r10, r00)
    else:
        pitch = math.atan2(-r12, r11)
        roll = 0.0
    return HeadPoseAngles(
        yaw_deg=math.degrees(yaw),
        pitch_deg=math.degrees(pitch),
        roll_deg=math.degrees(roll),
    )


def _first_face_landmarker_values(result):
    faces = getattr(result, "face_landmarks", ())
    matrices = getattr(result, "facial_transformation_matrixes", ())
    landmarks = faces[0] if faces else ()
    matrix = _matrix_tuple(matrices[0]) if matrices else None
    return landmarks, matrix


def _convert_pose_result(result) -> Tuple[PoseObservation, ...]:
    pose_landmarks = getattr(result, "pose_landmarks", ())
    world_landmarks = getattr(result, "pose_world_landmarks", ())
    observations = []
    for pose_index, landmarks in enumerate(pose_landmarks):
        world = world_landmarks[pose_index] if pose_index < len(world_landmarks) else ()
        observations.append(
            PoseObservation(
                pose_index=pose_index,
                landmarks=tuple(_convert_landmark(item) for item in landmarks),
                world_landmarks=tuple(_convert_landmark(item) for item in world),
            )
        )
    return tuple(observations)


class MediaPipeBackend:
    def __init__(
        self,
        tasks: MediaPipeTaskBundle,
        *,
        media_type: str,
        max_heads: int,
        crop_config: FaceCropConfig = FaceCropConfig(),
    ):
        self._tasks = tasks
        self._media_type = media_type
        self._max_heads = max_heads
        self._crop_config = crop_config
        self._last_timestamp_ms = None
        self._closed = False

    @classmethod
    def create(
        cls,
        resources: PreparedMediaPipeResources,
        *,
        media_type: str,
        max_heads: int,
        task_factory=None,
    ) -> "MediaPipeBackend":
        if media_type not in ("image", "video"):
            raise ValueError("media_type must be 'image' or 'video'")
        if not isinstance(max_heads, int) or isinstance(max_heads, bool) or max_heads < 1:
            raise ValueError("max_heads must be a positive int")
        running_mode = "IMAGE" if media_type == "image" else "VIDEO"
        factory = _create_mediapipe_task_bundle if task_factory is None else task_factory
        tasks = factory(
            face_detector_path=resources.face_detector_path.resolve(),
            face_landmarker_path=resources.face_landmarker_path.resolve(),
            pose_landmarker_path=resources.pose_landmarker_path.resolve(),
            running_mode=running_mode,
            max_heads=max_heads,
            face_landmarker_running_mode="IMAGE",
        )
        return cls(tasks, media_type=media_type, max_heads=max_heads)

    def _video_timestamp(self, timestamp_ms) -> int:
        try:
            value = float(timestamp_ms)
        except (TypeError, ValueError) as exc:
            raise ValueError("video timestamp_ms must be a finite number") from exc
        if not math.isfinite(value):
            raise ValueError("video timestamp_ms must be a finite number")
        rounded = max(0, int(round(value)))
        if self._last_timestamp_ms is not None and rounded <= self._last_timestamp_ms:
            raise ValueError(
                "MediaPipe video timestamps must strictly increase after rounding"
            )
        self._last_timestamp_ms = rounded
        return rounded

    def _detect(self, task, image, timestamp_ms):
        if self._media_type == "image":
            return task.detect(image)
        return task.detect_for_video(image, timestamp_ms)

    def observe(
        self,
        frame,
        *,
        frame_index: int,
        timestamp_ms,
        image_width: int,
        image_height: int,
    ) -> MediaPipeFrameObservations:
        del frame_index
        if self._closed:
            raise RuntimeError("MediaPipe backend is closed")
        total_start = perf_counter()
        try:
            if image_width < 1 or image_height < 1:
                raise ValueError("image dimensions must be positive")
            task_timestamp = (
                None if self._media_type == "image" else self._video_timestamp(timestamp_ms)
            )
            rgb_frame = frame.convert("RGB")
            full_image = self._tasks.image_factory(np.asarray(rgb_frame))

            detector_start = perf_counter()
            detector_result = self._detect(
                self._tasks.face_detector,
                full_image,
                task_timestamp,
            )
            detector_ms = (perf_counter() - detector_start) * 1000.0

            detections = sorted(
                getattr(detector_result, "detections", ()),
                key=_detection_confidence,
                reverse=True,
            )[: self._max_heads]
            face_start = perf_counter()
            faces = []
            for detection in detections:
                crop_box = _crop_box(
                    detection,
                    image_width,
                    image_height,
                    self._crop_config,
                )
                if crop_box is None:
                    continue
                crop = rgb_frame.crop(crop_box)
                crop_image = self._tasks.image_factory(np.asarray(crop))
                face_result = self._tasks.face_landmarker.detect(crop_image)
                crop_landmarks, transformation_matrix = _first_face_landmarker_values(
                    face_result
                )
                faces.append(
                    FaceObservation(
                        bbox=_normalized_detection_box(
                            detection,
                            image_width,
                            image_height,
                        ),
                        confidence=_detection_confidence(detection),
                        keypoints=tuple(
                            _convert_landmark(keypoint)
                            for keypoint in getattr(detection, "keypoints", ())
                        ),
                        landmarks=tuple(
                            _remap_face_landmark(
                                landmark,
                                crop_box,
                                image_width,
                                image_height,
                            )
                            for landmark in crop_landmarks
                        ),
                        transformation_matrix=transformation_matrix,
                        head_pose=_matrix_to_head_pose(transformation_matrix),
                    )
                )
            face_ms = (perf_counter() - face_start) * 1000.0

            pose_start = perf_counter()
            pose_result = self._detect(
                self._tasks.pose_landmarker,
                full_image,
                task_timestamp,
            )
            poses = _convert_pose_result(pose_result)
            pose_ms = (perf_counter() - pose_start) * 1000.0
            total_ms = (perf_counter() - total_start) * 1000.0
            return MediaPipeFrameObservations(
                faces=tuple(faces),
                poses=poses,
                timings_ms={
                    "face_detector": detector_ms,
                    "face_landmarker": face_ms,
                    "pose_landmarker": pose_ms,
                    "total": total_ms,
                },
            )
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _close_tasks(
            (
                self._tasks.face_detector,
                self._tasks.face_landmarker,
                self._tasks.pose_landmarker,
            ),
            suppress_errors=False,
        )
