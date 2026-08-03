from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from gazelle.runtime.contracts import BBox, GazeStatus, HeadObservation


class HeadPerceptionState(str, Enum):
    FACE_POSE = "face_pose"
    FACE_ONLY = "face_only"
    POSE_ONLY = "pose_only"
    TRACKED_ONLY = "tracked_only"


class HeadViewState(str, Enum):
    FRONTAL = "frontal"
    PROFILE = "profile"
    BACK_OR_OCCLUDED = "back_or_occluded"
    UNKNOWN = "unknown"


class ReferenceRaySource(str, Enum):
    FACE_POSE = "face_pose"
    POSE_HEAD = "pose_head"


class ReferenceRayProjectionStatus(str, Enum):
    AVAILABLE = "available"
    AXIAL = "axial_projection"


@dataclass(frozen=True)
class HeadPoseAngles:
    yaw_deg: float
    pitch_deg: float
    roll_deg: float


@dataclass(frozen=True)
class NormalizedLandmark:
    x: float
    y: float
    z: Optional[float] = None
    visibility: Optional[float] = None
    presence: Optional[float] = None


@dataclass(frozen=True)
class PoseHeadKeypoints:
    nose: Optional[NormalizedLandmark] = None
    left_eye: Optional[NormalizedLandmark] = None
    right_eye: Optional[NormalizedLandmark] = None
    left_ear: Optional[NormalizedLandmark] = None
    right_ear: Optional[NormalizedLandmark] = None
    mouth_left: Optional[NormalizedLandmark] = None
    mouth_right: Optional[NormalizedLandmark] = None
    left_shoulder: Optional[NormalizedLandmark] = None
    right_shoulder: Optional[NormalizedLandmark] = None


@dataclass(frozen=True)
class ReferenceRay2D:
    source: ReferenceRaySource
    origin: Tuple[float, float]
    direction: Optional[Tuple[float, float]]
    endpoint: Optional[Tuple[float, float]]
    confidence: float
    projection_status: ReferenceRayProjectionStatus


@dataclass(frozen=True)
class FaceObservation:
    bbox: BBox
    confidence: float
    keypoints: Tuple[NormalizedLandmark, ...] = ()
    landmarks: Tuple[NormalizedLandmark, ...] = ()
    transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    head_pose: Optional[HeadPoseAngles] = None


@dataclass(frozen=True)
class PoseObservation:
    pose_index: int
    landmarks: Tuple[NormalizedLandmark, ...]
    world_landmarks: Tuple[NormalizedLandmark, ...] = ()


@dataclass(frozen=True)
class HeadCandidate:
    source_index: int
    head_bbox: BBox
    face_bbox: Optional[BBox]
    confidence: float
    state: HeadPerceptionState
    view_state: HeadViewState
    observed: bool = True
    face_keypoints: Tuple[NormalizedLandmark, ...] = ()
    pose_head_landmarks: Tuple[NormalizedLandmark, ...] = ()
    pose_head_keypoints: PoseHeadKeypoints = field(default_factory=PoseHeadKeypoints)
    facial_transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    head_pose: Optional[HeadPoseAngles] = None
    face_landmarks: Tuple[NormalizedLandmark, ...] = ()
    face_pose_reference_ray: Optional[ReferenceRay2D] = None
    pose_head_reference_ray: Optional[ReferenceRay2D] = None


@dataclass(frozen=True)
class HeadPerception:
    person_id: int
    head_bbox: BBox
    face_bbox: Optional[BBox]
    confidence: float
    state: HeadPerceptionState
    view_state: HeadViewState
    observed: bool
    track_age_frames: int = 0
    missed_frames: int = 0
    missed_ms: float = 0.0
    face_keypoints: Tuple[NormalizedLandmark, ...] = ()
    pose_head_landmarks: Tuple[NormalizedLandmark, ...] = ()
    pose_head_keypoints: PoseHeadKeypoints = field(default_factory=PoseHeadKeypoints)
    facial_transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    head_pose: Optional[HeadPoseAngles] = None
    face_landmarks: Tuple[NormalizedLandmark, ...] = ()
    face_pose_reference_ray: Optional[ReferenceRay2D] = None
    pose_head_reference_ray: Optional[ReferenceRay2D] = None
    gaze_eligible: bool = True
    gaze_status: Optional[GazeStatus] = None


@dataclass(frozen=True)
class HeadFrameResult:
    heads: Tuple[HeadObservation, ...]
    perceptions: Tuple[HeadPerception, ...] = ()
    timings_ms: Mapping[str, float] = field(default_factory=dict)
