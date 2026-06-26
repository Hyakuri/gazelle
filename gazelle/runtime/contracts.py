from dataclasses import dataclass
from typing import Optional, Tuple


BBox = Tuple[float, float, float, float]


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
    gaze_peak: Optional[Tuple[float, float]] = None
    heatmap_peak_value: Optional[float] = None
    inout_score: Optional[float] = None


@dataclass(frozen=True)
class FramePacket:
    """Frame metadata and head observations for one image or video frame."""

    frame_index: int
    timestamp_ms: float
    width: int
    height: int
    heads: Tuple[HeadObservation, ...]
