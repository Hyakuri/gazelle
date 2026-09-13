import math
from numbers import Real
from typing import Optional, Tuple

from gazelle.runtime.geometry import sanitize_normalized_bbox
from gazelle.runtime.perception.contracts import (
    HeadPoseAngles,
    NormalizedLandmark,
    PoseHeadKeypoints,
    ReferenceRay2D,
    ReferenceRayProjectionStatus,
    ReferenceRaySource,
)


_AXIAL_PROJECTION_EPSILON = 0.05
_MIN_ANCHOR_SPAN = 1e-4
_POSE_EYE_NEUTRAL_VERTICAL_RATIO = 0.45
_POSE_EAR_NEUTRAL_VERTICAL_RATIO = 0.10


def _finite_real(value) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _finite_point(landmark: Optional[NormalizedLandmark]) -> bool:
    return (
        landmark is not None
        and _finite_real(landmark.x)
        and _finite_real(landmark.y)
    )


def _validate_length_multiplier(value) -> float:
    if not _finite_real(value) or float(value) <= 0.0:
        raise ValueError("length_multiplier must be a finite positive real number")
    return float(value)


def _clipped_confidence(value) -> Optional[float]:
    if not _finite_real(value):
        return None
    return min(max(float(value), 0.0), 1.0)


def _point_quality(landmarks) -> float:
    scores = []
    for landmark in landmarks:
        for value in (landmark.visibility, landmark.presence):
            if _finite_real(value):
                scores.append(min(max(float(value), 0.0), 1.0))
    return sum(scores) / len(scores) if scores else 1.0


def _clipped_point(point: Tuple[float, float]) -> Tuple[float, float]:
    return (
        min(max(float(point[0]), 0.0), 1.0),
        min(max(float(point[1]), 0.0), 1.0),
    )


def _bbox_diagonal(bbox) -> float:
    xmin, ymin, xmax, ymax = sanitize_normalized_bbox(bbox, clip=True)
    return math.hypot(xmax - xmin, ymax - ymin)


def _endpoint_at_boundary(
    origin: Tuple[float, float],
    direction: Tuple[float, float],
    requested_distance: float,
) -> Tuple[float, float]:
    max_distance = requested_distance
    for coordinate, component in zip(origin, direction):
        if component > 0.0:
            max_distance = min(max_distance, (1.0 - coordinate) / component)
        elif component < 0.0:
            max_distance = min(max_distance, coordinate / -component)
    distance = max(0.0, max_distance)
    return _clipped_point(
        (
            origin[0] + direction[0] * distance,
            origin[1] + direction[1] * distance,
        )
    )


def _build_ray(
    *,
    source: ReferenceRaySource,
    origin: Tuple[float, float],
    vector: Tuple[float, float],
    head_bbox,
    confidence,
    length_multiplier: float,
) -> Optional[ReferenceRay2D]:
    length_multiplier = _validate_length_multiplier(length_multiplier)
    confidence = _clipped_confidence(confidence)
    if confidence is None or not all(_finite_real(value) for value in origin + vector):
        return None
    origin = _clipped_point(origin)
    magnitude = math.hypot(vector[0], vector[1])
    if magnitude < _AXIAL_PROJECTION_EPSILON:
        return ReferenceRay2D(
            source=source,
            origin=origin,
            direction=None,
            endpoint=None,
            confidence=confidence,
            projection_status=ReferenceRayProjectionStatus.AXIAL,
        )
    direction = (float(vector[0]) / magnitude, float(vector[1]) / magnitude)
    requested_distance = _bbox_diagonal(head_bbox) * length_multiplier
    endpoint = _endpoint_at_boundary(origin, direction, requested_distance)
    return ReferenceRay2D(
        source=source,
        origin=origin,
        direction=direction,
        endpoint=endpoint,
        confidence=confidence,
        projection_status=ReferenceRayProjectionStatus.AVAILABLE,
    )


def estimate_face_pose_reference_ray(
    *,
    head_bbox,
    face_bbox=None,
    face_keypoints,
    head_pose: Optional[HeadPoseAngles],
    confidence,
    length_multiplier: float = 2.5,
) -> Optional[ReferenceRay2D]:
    length_multiplier = _validate_length_multiplier(length_multiplier)
    keypoints = tuple(face_keypoints)
    if head_pose is None:
        return None
    angles = (head_pose.yaw_deg, head_pose.pitch_deg, head_pose.roll_deg)
    if not all(_finite_real(value) for value in angles):
        return None

    finite_keypoints = tuple(point for point in keypoints if _finite_point(point))
    if len(keypoints) >= 2 and all(_finite_point(point) for point in keypoints[:2]):
        right_eye, left_eye = keypoints[:2]
        origin = (
            (float(right_eye.x) + float(left_eye.x)) / 2.0,
            (float(right_eye.y) + float(left_eye.y)) / 2.0,
        )
        quality_keypoints = tuple(
            point for point in keypoints[:3] if _finite_point(point)
        )
    elif face_bbox is not None and len(finite_keypoints) >= 3:
        xmin, ymin, xmax, ymax = sanitize_normalized_bbox(face_bbox, clip=True)
        origin = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0)
        quality_keypoints = finite_keypoints
    else:
        return None

    yaw = math.radians(float(head_pose.yaw_deg))
    pitch = math.radians(float(head_pose.pitch_deg))
    roll = math.radians(float(head_pose.roll_deg))
    horizontal = math.sin(yaw) * math.cos(pitch)
    vertical = -math.sin(pitch)
    vector = (
        math.cos(roll) * horizontal - math.sin(roll) * vertical,
        math.sin(roll) * horizontal + math.cos(roll) * vertical,
    )
    ray_confidence = min(
        _clipped_confidence(confidence) or 0.0,
        _point_quality(quality_keypoints),
    )
    return _build_ray(
        source=ReferenceRaySource.FACE_POSE,
        origin=origin,
        vector=vector,
        head_bbox=head_bbox,
        confidence=ray_confidence,
        length_multiplier=length_multiplier,
    )


def estimate_pose_head_reference_ray(
    *,
    head_bbox,
    keypoints: PoseHeadKeypoints,
    confidence,
    length_multiplier: float = 2.5,
) -> Optional[ReferenceRay2D]:
    length_multiplier = _validate_length_multiplier(length_multiplier)
    if not isinstance(keypoints, PoseHeadKeypoints) or not _finite_point(keypoints.nose):
        return None

    if _finite_point(keypoints.left_eye) and _finite_point(keypoints.right_eye):
        first = keypoints.left_eye
        second = keypoints.right_eye
        neutral_vertical_ratio = _POSE_EYE_NEUTRAL_VERTICAL_RATIO
    elif _finite_point(keypoints.left_ear) and _finite_point(keypoints.right_ear):
        first = keypoints.left_ear
        second = keypoints.right_ear
        neutral_vertical_ratio = _POSE_EAR_NEUTRAL_VERTICAL_RATIO
    else:
        return None

    origin = (
        (float(first.x) + float(second.x)) / 2.0,
        (float(first.y) + float(second.y)) / 2.0,
    )
    anchor_span = math.hypot(
        float(second.x) - float(first.x),
        float(second.y) - float(first.y),
    )
    if anchor_span < _MIN_ANCHOR_SPAN:
        return None
    nose = keypoints.nose
    vector = (
        (float(nose.x) - origin[0]) / (anchor_span / 2.0),
        (float(nose.y) - origin[1]) / anchor_span - neutral_vertical_ratio,
    )
    ray_confidence = min(
        _clipped_confidence(confidence) or 0.0,
        _point_quality((nose, first, second)),
    )
    return _build_ray(
        source=ReferenceRaySource.POSE_HEAD,
        origin=origin,
        vector=vector,
        head_bbox=head_bbox,
        confidence=ray_confidence,
        length_multiplier=length_multiplier,
    )


__all__ = [
    "estimate_face_pose_reference_ray",
    "estimate_pose_head_reference_ray",
]
