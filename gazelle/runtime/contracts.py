from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import torch


BBox = Tuple[float, float, float, float]


class GazeStatus(str, Enum):
    VALID = "valid"
    OUT_OF_FRAME = "out_of_frame"
    UNAVAILABLE_OCCLUDED = "unavailable_occluded"
    TRACKED_NO_GAZE = "tracked_no_gaze"
    REJECTED_LOW_QUALITY = "rejected_low_quality"


@dataclass(frozen=True)
class HeadObservation:
    """A single person/head observation passed into the Gazelle runtime."""

    person_id: int
    bbox: Optional[BBox]
    confidence: Optional[float] = None


@dataclass(frozen=True)
class GazePrediction:
    """Structured per-person output produced by the runtime."""

    person_id: int
    bbox: Optional[BBox]
    heatmap: Optional["torch.Tensor"] = None
    gaze_peak: Optional[Tuple[float, float]] = None
    heatmap_peak_value: Optional[float] = None
    inout_score: Optional[float] = None
    gaze_status: GazeStatus = GazeStatus.VALID


@dataclass(frozen=True)
class FramePacket:
    """Frame metadata and head observations for one image or video frame."""

    frame_index: int
    timestamp_ms: float
    width: int
    height: int
    heads: Tuple[HeadObservation, ...]
