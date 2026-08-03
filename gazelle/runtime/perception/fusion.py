import math
from dataclasses import dataclass, replace
from numbers import Real
from statistics import median
from typing import Optional, Tuple

from gazelle.runtime.geometry import sanitize_normalized_bbox
from gazelle.runtime.perception.contracts import (
    FaceObservation,
    HeadCandidate,
    HeadPerceptionState,
    HeadViewState,
    NormalizedLandmark,
    PoseHeadKeypoints,
    PoseObservation,
)
from gazelle.runtime.perception.reference_rays import (
    estimate_face_pose_reference_ray,
    estimate_pose_head_reference_ray,
)


@dataclass(frozen=True)
class HeadBoxFusionConfig:
    min_visibility: float = 0.50
    min_presence: float = 0.50
    face_expand_x: float = 0.20
    face_expand_top: float = 0.45
    face_expand_bottom: float = 0.10
    min_consistent_iou: float = 0.10
    max_center_distance_diagonal_ratio: float = 0.75


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _clipped_confidence(value: object) -> float:
    if not _is_finite_real(value):
        return 0.0
    return min(max(float(value), 0.0), 1.0)


def _sanitize_or_none(bbox) -> Optional[Tuple[float, float, float, float]]:
    try:
        return sanitize_normalized_bbox(bbox, clip=True)
    except ValueError:
        return None


def _sanitized_candidate(candidate: HeadCandidate) -> HeadCandidate:
    return replace(
        candidate,
        head_bbox=sanitize_normalized_bbox(candidate.head_bbox, clip=True),
        face_bbox=(
            None
            if candidate.face_bbox is None
            else sanitize_normalized_bbox(candidate.face_bbox, clip=True)
        ),
        confidence=_clipped_confidence(candidate.confidence),
    )


def _is_reliable(landmark: NormalizedLandmark, config: HeadBoxFusionConfig) -> bool:
    if not (_is_finite_real(landmark.x) and _is_finite_real(landmark.y)):
        return False
    for score, minimum in (
        (landmark.visibility, config.min_visibility),
        (landmark.presence, config.min_presence),
    ):
        if score is not None and (not _is_finite_real(score) or float(score) < minimum):
            return False
    return True


def _landmark_quality(landmarks: Tuple[NormalizedLandmark, ...]) -> float:
    scores = []
    for landmark in landmarks:
        for score in (landmark.visibility, landmark.presence):
            if _is_finite_real(score):
                scores.append(float(score))
    return _clipped_confidence(sum(scores) / len(scores)) if scores else 0.0


def _bbox_center(bbox):
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _bbox_diagonal(bbox) -> float:
    return math.hypot(bbox[2] - bbox[0], bbox[3] - bbox[1])


def _bbox_iou(first, second) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = (
        (first[2] - first[0]) * (first[3] - first[1])
        + (second[2] - second[0]) * (second[3] - second[1])
        - intersection
    )
    return intersection / union if union > 0.0 else 0.0


def _normalized_center_distance(first, second) -> float:
    first_center = _bbox_center(first)
    second_center = _bbox_center(second)
    diagonal = max(_bbox_diagonal(first), _bbox_diagonal(second))
    if not math.isfinite(diagonal) or diagonal <= 0.0:
        return math.inf
    return math.hypot(first_center[0] - second_center[0], first_center[1] - second_center[1]) / diagonal


def _face_view_state(face: FaceObservation) -> HeadViewState:
    angles = face.head_pose
    if angles is None or not all(
        _is_finite_real(value)
        for value in (angles.yaw_deg, angles.pitch_deg, angles.roll_deg)
    ):
        return HeadViewState.UNKNOWN
    return HeadViewState.FRONTAL if abs(float(angles.yaw_deg)) < 35.0 else HeadViewState.PROFILE


def expand_face_to_head_bbox(face_bbox, config: HeadBoxFusionConfig = HeadBoxFusionConfig()):
    xmin, ymin, xmax, ymax = sanitize_normalized_bbox(face_bbox, clip=True)
    width = xmax - xmin
    height = ymax - ymin
    return sanitize_normalized_bbox(
        (
            xmin - config.face_expand_x * width,
            ymin - config.face_expand_top * height,
            xmax + config.face_expand_x * width,
            ymax + config.face_expand_bottom * height,
        ),
        clip=True,
    )


def _build_face_head_candidate(
    face: FaceObservation,
    source_index: int,
    config: HeadBoxFusionConfig,
    reference_ray_length: float,
):
    try:
        face_bbox = sanitize_normalized_bbox(face.bbox, clip=True)
        head_bbox = expand_face_to_head_bbox(face_bbox, config)
    except ValueError:
        return None
    confidence = _clipped_confidence(face.confidence)
    return HeadCandidate(
        source_index=source_index,
        head_bbox=head_bbox,
        face_bbox=face_bbox,
        confidence=confidence,
        state=HeadPerceptionState.FACE_ONLY,
        view_state=_face_view_state(face),
        face_keypoints=tuple(face.keypoints),
        facial_transformation_matrix=face.transformation_matrix,
        head_pose=face.head_pose,
        face_landmarks=tuple(face.landmarks),
        face_pose_reference_ray=estimate_face_pose_reference_ray(
            head_bbox=head_bbox,
            face_bbox=face_bbox,
            face_keypoints=face.keypoints,
            head_pose=face.head_pose,
            confidence=confidence,
            length_multiplier=reference_ray_length,
        ),
    )


def _pose_head_keypoints(landmarks, config: HeadBoxFusionConfig) -> PoseHeadKeypoints:
    def reliable(index):
        if index >= len(landmarks):
            return None
        landmark = landmarks[index]
        return landmark if _is_reliable(landmark, config) else None

    return PoseHeadKeypoints(
        nose=reliable(0),
        left_eye=reliable(2),
        right_eye=reliable(5),
        left_ear=reliable(7),
        right_ear=reliable(8),
        mouth_left=reliable(9),
        mouth_right=reliable(10),
        left_shoulder=reliable(11),
        right_shoulder=reliable(12),
    )


def build_pose_head_candidate(
    pose: PoseObservation,
    config: HeadBoxFusionConfig = HeadBoxFusionConfig(),
    reference_ray_length: float = 2.5,
) -> Optional[HeadCandidate]:
    landmarks = tuple(pose.landmarks)
    named_keypoints = _pose_head_keypoints(landmarks, config)
    head_landmarks = tuple(
        landmark
        for landmark in landmarks[:11]
        if _is_reliable(landmark, config)
    )
    shoulders = tuple(
        landmark
        for landmark in landmarks[11:13]
        if _is_reliable(landmark, config)
    )

    used_landmarks = ()
    if len(head_landmarks) >= 2:
        center_x = float(median(landmark.x for landmark in head_landmarks))
        center_y = float(median(landmark.y for landmark in head_landmarks))
        horizontal_span = max(landmark.x for landmark in head_landmarks) - min(
            landmark.x for landmark in head_landmarks
        )
        vertical_span = max(landmark.y for landmark in head_landmarks) - min(
            landmark.y for landmark in head_landmarks
        )
        shoulder_width = 0.0
        if len(shoulders) == 2:
            shoulder_width = math.hypot(
                shoulders[1].x - shoulders[0].x,
                shoulders[1].y - shoulders[0].y,
            )
        width = max(1.40 * horizontal_span, 0.30 * shoulder_width)
        height = max(1.50 * vertical_span, 0.40 * shoulder_width)
        center_y -= 0.10 * height
        raw_bbox = (
            center_x - width / 2.0,
            center_y - height / 2.0,
            center_x + width / 2.0,
            center_y + height / 2.0,
        )
        used_landmarks = head_landmarks + (shoulders if len(shoulders) == 2 else ())
    elif len(shoulders) == 2:
        first_shoulder, second_shoulder = shoulders
        shoulder_width = math.hypot(
            second_shoulder.x - first_shoulder.x,
            second_shoulder.y - first_shoulder.y,
        )
        center_x = (first_shoulder.x + second_shoulder.x) / 2.0
        shoulder_midpoint_y = (first_shoulder.y + second_shoulder.y) / 2.0
        width = 0.42 * shoulder_width
        height = 0.55 * shoulder_width
        lower_edge = shoulder_midpoint_y - 0.08 * shoulder_width
        raw_bbox = (
            center_x - width / 2.0,
            lower_edge - height,
            center_x + width / 2.0,
            lower_edge,
        )
        used_landmarks = shoulders
    else:
        return None

    if not all(_is_finite_real(value) and float(value) > 0.0 for value in (width, height)):
        return None
    head_bbox = _sanitize_or_none(raw_bbox)
    if head_bbox is None:
        return None
    confidence = _landmark_quality(used_landmarks)
    return HeadCandidate(
        source_index=pose.pose_index,
        head_bbox=head_bbox,
        face_bbox=None,
        confidence=confidence,
        state=HeadPerceptionState.POSE_ONLY,
        view_state=HeadViewState.BACK_OR_OCCLUDED,
        pose_head_landmarks=tuple(used_landmarks),
        pose_head_keypoints=named_keypoints,
        pose_head_reference_ray=estimate_pose_head_reference_ray(
            head_bbox=head_bbox,
            keypoints=named_keypoints,
            confidence=confidence,
            length_multiplier=reference_ray_length,
        ),
    )


def associate_face_pose(
    face_candidate: HeadCandidate,
    pose_candidate: HeadCandidate,
    config: HeadBoxFusionConfig = HeadBoxFusionConfig(),
) -> bool:
    face_bbox = _sanitize_or_none(face_candidate.head_bbox)
    pose_bbox = _sanitize_or_none(pose_candidate.head_bbox)
    if face_bbox is None or pose_bbox is None:
        return False
    return (
        _bbox_iou(face_bbox, pose_bbox) >= config.min_consistent_iou
        or _normalized_center_distance(face_bbox, pose_bbox)
        <= config.max_center_distance_diagonal_ratio
    )


def _fused_bbox(first, second):
    return sanitize_normalized_bbox(
        (
            min(first[0], second[0]),
            min(first[1], second[1]),
            max(first[2], second[2]),
            max(first[3], second[3]),
        ),
        clip=True,
    )


def fuse_head_candidates(
    face_candidate: HeadCandidate,
    pose_candidate: HeadCandidate,
    config: HeadBoxFusionConfig = HeadBoxFusionConfig(),
    reference_ray_length: float = 2.5,
) -> HeadCandidate:
    face_candidate = _sanitized_candidate(face_candidate)
    pose_candidate = _sanitized_candidate(pose_candidate)
    if not associate_face_pose(face_candidate, pose_candidate, config):
        return face_candidate if face_candidate.confidence >= pose_candidate.confidence else pose_candidate
    head_bbox = _fused_bbox(face_candidate.head_bbox, pose_candidate.head_bbox)
    face_pose_reference_ray = estimate_face_pose_reference_ray(
        head_bbox=head_bbox,
        face_bbox=face_candidate.face_bbox,
        face_keypoints=face_candidate.face_keypoints,
        head_pose=face_candidate.head_pose,
        confidence=face_candidate.confidence,
        length_multiplier=reference_ray_length,
    )
    pose_head_reference_ray = estimate_pose_head_reference_ray(
        head_bbox=head_bbox,
        keypoints=pose_candidate.pose_head_keypoints,
        confidence=pose_candidate.confidence,
        length_multiplier=reference_ray_length,
    )
    return HeadCandidate(
        source_index=face_candidate.source_index,
        head_bbox=head_bbox,
        face_bbox=sanitize_normalized_bbox(face_candidate.face_bbox, clip=True),
        confidence=_clipped_confidence(0.50 * face_candidate.confidence + 0.50 * pose_candidate.confidence),
        state=HeadPerceptionState.FACE_POSE,
        view_state=face_candidate.view_state,
        face_keypoints=face_candidate.face_keypoints,
        pose_head_landmarks=pose_candidate.pose_head_landmarks,
        pose_head_keypoints=pose_candidate.pose_head_keypoints,
        facial_transformation_matrix=face_candidate.facial_transformation_matrix,
        head_pose=face_candidate.head_pose,
        face_landmarks=face_candidate.face_landmarks,
        face_pose_reference_ray=face_pose_reference_ray,
        pose_head_reference_ray=pose_head_reference_ray,
    )


def _association_cost(face_candidate: HeadCandidate, pose_candidate: HeadCandidate) -> float:
    face_bbox = sanitize_normalized_bbox(face_candidate.head_bbox, clip=True)
    pose_bbox = sanitize_normalized_bbox(pose_candidate.head_bbox, clip=True)
    cost = 0.60 * _normalized_center_distance(face_bbox, pose_bbox) + 0.40 * (1.0 - _bbox_iou(face_bbox, pose_bbox))
    return cost if math.isfinite(cost) else math.inf


def _sort_candidates(candidates):
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -_clipped_confidence(candidate.confidence),
                candidate.head_bbox[1],
                candidate.head_bbox[0],
                candidate.source_index,
            ),
        )
    )


def _validate_max_heads(max_heads: int) -> int:
    if not isinstance(max_heads, int) or isinstance(max_heads, bool) or not 1 <= max_heads <= 10:
        raise ValueError("max_heads must be an int from 1 through 10")
    return max_heads


def build_head_candidates(
    *,
    faces: Tuple[FaceObservation, ...],
    poses: Tuple[PoseObservation, ...],
    max_heads: int,
    config: HeadBoxFusionConfig = HeadBoxFusionConfig(),
    reference_ray_length: float = 2.5,
) -> Tuple[HeadCandidate, ...]:
    max_heads = _validate_max_heads(max_heads)
    face_candidates = tuple(
        candidate
        for index, face in enumerate(faces)
        for candidate in (
            _build_face_head_candidate(
                face,
                index,
                config,
                reference_ray_length,
            ),
        )
        if candidate is not None
    )
    pose_candidates = tuple(
        candidate
        for pose in poses
        for candidate in (
            build_pose_head_candidate(
                pose,
                config,
                reference_ray_length,
            ),
        )
        if candidate is not None
    )

    if max_heads == 1:
        face_candidate = max(
            enumerate(face_candidates), key=lambda item: (item[1].confidence, -item[0]), default=(None, None)
        )[1]
        pose_candidate = max(
            enumerate(pose_candidates), key=lambda item: (item[1].confidence, -item[0]), default=(None, None)
        )[1]
        if face_candidate is not None and pose_candidate is not None:
            return (
                fuse_head_candidates(
                    face_candidate,
                    pose_candidate,
                    config,
                    reference_ray_length,
                ),
            )
        return _sort_candidates(
            tuple(candidate for candidate in (face_candidate, pose_candidate) if candidate is not None)
        )[:1]

    pairs = []
    for face_index, face_candidate in enumerate(face_candidates):
        for pose_order, pose_candidate in enumerate(pose_candidates):
            if associate_face_pose(face_candidate, pose_candidate, config):
                pairs.append(
                    (
                        _association_cost(face_candidate, pose_candidate),
                        pose_candidate.source_index,
                        face_index,
                        pose_order,
                    )
                )
    used_faces = set()
    used_poses = set()
    fused = []
    for _, _, face_index, pose_order in sorted(pairs):
        if face_index in used_faces or pose_order in used_poses:
            continue
        fused.append(
            fuse_head_candidates(
                face_candidates[face_index],
                pose_candidates[pose_order],
                config,
                reference_ray_length,
            )
        )
        used_faces.add(face_index)
        used_poses.add(pose_order)

    remaining = list(fused)
    remaining.extend(candidate for index, candidate in enumerate(face_candidates) if index not in used_faces)
    remaining.extend(candidate for index, candidate in enumerate(pose_candidates) if index not in used_poses)
    return _sort_candidates(remaining)[:max_heads]
