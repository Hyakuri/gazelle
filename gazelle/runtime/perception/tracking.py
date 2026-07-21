import importlib
import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Optional, Tuple

import numpy as np

from gazelle.runtime.perception.contracts import (
    HeadCandidate,
    HeadPerception,
    HeadPerceptionState,
    HeadViewState,
)


_TRACKER_CONFIGURATION = {
    "track_activation_threshold": 0.50,
    "high_conf_det_threshold": 0.50,
    "minimum_iou_threshold": 0.20,
    "minimum_consecutive_frames": 1,
    "lost_track_buffer": 15,
}
_DECAY_TIME_MS = 500.0


@dataclass(frozen=True)
class TrackedHeadCandidate:
    person_id: int
    candidate: HeadCandidate
    track_age_frames: int


@dataclass(frozen=True)
class _BridgeState:
    head_bbox: Tuple[float, float, float, float]
    confidence: float
    track_age_frames: int
    last_observed_timestamp_ms: float
    missed_frames: int = 0


def _timestamp(value: object) -> float:
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise ValueError("timestamp_ms must be a finite non-negative real number")
    return float(value)


def _nonnegative_int(value: object, *, name: str, error_type=ValueError) -> int:
    if not isinstance(value, Integral) or isinstance(value, (bool, np.bool_)) or int(value) < 0:
        raise error_type(f"{name} must be a non-negative integer")
    return int(value)


class ByteTrackHeadTracker:
    def __init__(
        self,
        source_fps: float,
        *,
        tracker_factory=None,
        supervision_module=None,
    ):
        if (
            not isinstance(source_fps, Real)
            or isinstance(source_fps, (bool, np.bool_))
            or not math.isfinite(float(source_fps))
            or float(source_fps) <= 0.0
        ):
            raise ValueError("source_fps must be a finite positive real number")
        self._source_fps = float(source_fps)
        self._tracker_factory = tracker_factory
        self._supervision = supervision_module
        self._tracker = None
        self._first_frame_by_person = {}
        self._last_timestamp_ms: Optional[float] = None
        self._closed = False

    def _load_supervision(self):
        if self._supervision is not None:
            return self._supervision
        try:
            module = importlib.import_module("supervision")
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "ByteTrack head tracking requires the optional 'supervision' package"
            ) from exc
        if not hasattr(module, "Detections"):
            raise RuntimeError("The installed 'supervision' package does not expose Detections")
        self._supervision = module
        return module

    def _load_tracker_factory(self):
        if self._tracker_factory is not None:
            return self._tracker_factory
        try:
            module = importlib.import_module("trackers")
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "ByteTrack head tracking requires the optional 'trackers' package"
            ) from exc
        factory = getattr(module, "ByteTrackTracker", None)
        if factory is None:
            raise RuntimeError("The installed 'trackers' package does not expose ByteTrackTracker")
        self._tracker_factory = factory
        return factory

    def _ensure_tracker(self):
        if self._tracker is not None:
            return self._tracker
        self._load_supervision()
        factory = self._load_tracker_factory()
        configuration = dict(_TRACKER_CONFIGURATION)
        configuration["frame_rate"] = self._source_fps
        try:
            tracker = factory(**configuration)
        except TypeError as exc:
            raise RuntimeError(
                "Could not construct trackers.ByteTrackTracker with the required API"
            ) from exc
        if not callable(getattr(tracker, "update", None)):
            raise RuntimeError("ByteTrack tracker must expose update(detections)")
        self._tracker = tracker
        return tracker

    def _build_detections(
        self,
        candidates: Tuple[HeadCandidate, ...],
        *,
        image_width: int,
        image_height: int,
    ):
        supervision = self._load_supervision()
        if not candidates:
            return supervision.Detections.empty()
        pixel_boxes = tuple(
            (
                candidate.head_bbox[0] * image_width,
                candidate.head_bbox[1] * image_height,
                candidate.head_bbox[2] * image_width,
                candidate.head_bbox[3] * image_height,
            )
            for candidate in candidates
        )
        return supervision.Detections(
            xyxy=np.asarray(pixel_boxes, dtype=np.float32),
            confidence=np.asarray(
                tuple(candidate.confidence for candidate in candidates),
                dtype=np.float32,
            ),
            class_id=np.zeros(len(candidates), dtype=np.int32),
            data={"candidate_index": np.arange(len(candidates), dtype=np.int32)},
        )

    def _map_tracked_candidates(
        self,
        tracked,
        candidates: Tuple[HeadCandidate, ...],
        *,
        frame_index: int,
    ) -> Tuple[TrackedHeadCandidate, ...]:
        if not candidates:
            return ()
        try:
            tracker_ids = tuple(tracked.tracker_id)
            candidate_indexes = tuple(tracked.data["candidate_index"])
        except (AttributeError, KeyError, TypeError) as exc:
            raise RuntimeError(
                "Invalid tracker output: tracker_id and data['candidate_index'] are required"
            ) from exc
        if len(tracker_ids) != len(candidate_indexes):
            raise RuntimeError(
                "Invalid tracker output: tracker IDs and candidate indexes differ in length"
            )

        mapped = []
        seen_people = set()
        seen_candidates = set()
        for raw_person_id, raw_candidate_index in zip(tracker_ids, candidate_indexes):
            person_id = _nonnegative_int(
                raw_person_id,
                name="tracker output person_id",
                error_type=RuntimeError,
            )
            candidate_index = _nonnegative_int(
                raw_candidate_index,
                name="tracker output candidate_index",
                error_type=RuntimeError,
            )
            if candidate_index >= len(candidates):
                raise RuntimeError("Invalid tracker output: candidate_index is out of range")
            if person_id in seen_people or candidate_index in seen_candidates:
                raise RuntimeError("Invalid tracker output: duplicate person ID or candidate index")
            seen_people.add(person_id)
            seen_candidates.add(candidate_index)
            first_frame = self._first_frame_by_person.setdefault(person_id, frame_index)
            mapped.append(
                (
                    candidate_index,
                    TrackedHeadCandidate(
                        person_id=person_id,
                        candidate=candidates[candidate_index],
                        track_age_frames=frame_index - first_frame + 1,
                    ),
                )
            )
        return tuple(item for _, item in sorted(mapped, key=lambda entry: entry[0]))

    def update(
        self,
        candidates: Tuple[HeadCandidate, ...],
        *,
        frame_index: int,
        timestamp_ms: float,
        image_width: int,
        image_height: int,
    ) -> Tuple[TrackedHeadCandidate, ...]:
        if self._closed:
            raise RuntimeError("ByteTrackHeadTracker is closed")
        timestamp_ms = _timestamp(timestamp_ms)
        if self._last_timestamp_ms is not None and timestamp_ms < self._last_timestamp_ms:
            raise ValueError("timestamp_ms must be monotonic")
        frame_index = _nonnegative_int(frame_index, name="frame_index")
        candidates = tuple(candidates)
        tracker = self._ensure_tracker()
        detections = self._build_detections(
            candidates,
            image_width=image_width,
            image_height=image_height,
        )
        tracked = tracker.update(detections)
        result = self._map_tracked_candidates(
            tracked,
            candidates,
            frame_index=frame_index,
        )
        self._last_timestamp_ms = timestamp_ms
        return result

    def reset(self) -> None:
        if self._closed:
            raise RuntimeError("ByteTrackHeadTracker is closed")
        tracker = self._tracker
        try:
            if tracker is not None:
                reset = getattr(tracker, "reset", None)
                if callable(reset):
                    reset()
                else:
                    close = getattr(tracker, "close", None)
                    if callable(close):
                        close()
                    self._tracker = None
        finally:
            self._first_frame_by_person.clear()
            self._last_timestamp_ms = None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        tracker = self._tracker
        self._tracker = None
        self._first_frame_by_person.clear()
        self._last_timestamp_ms = None
        if tracker is None:
            return
        close = getattr(tracker, "close", None)
        if callable(close):
            close()
            return
        reset = getattr(tracker, "reset", None)
        if callable(reset):
            reset()


class ShortOcclusionBridge:
    def __init__(self, max_gap_ms: float = 500.0, min_confidence: float = 0.15):
        if (
            not isinstance(max_gap_ms, Real)
            or isinstance(max_gap_ms, (bool, np.bool_))
            or not math.isfinite(float(max_gap_ms))
            or float(max_gap_ms) < 0.0
        ):
            raise ValueError("max_gap_ms must be a finite non-negative real number")
        if (
            not isinstance(min_confidence, Real)
            or isinstance(min_confidence, (bool, np.bool_))
            or not math.isfinite(float(min_confidence))
            or not 0.0 <= float(min_confidence) <= 1.0
        ):
            raise ValueError("min_confidence must be a finite real number from 0 through 1")
        self._max_gap_ms = float(max_gap_ms)
        self._min_confidence = float(min_confidence)
        self._states = {}
        self._last_timestamp_ms: Optional[float] = None

    @staticmethod
    def _observed_perception(tracked: TrackedHeadCandidate) -> HeadPerception:
        candidate = tracked.candidate
        return HeadPerception(
            person_id=tracked.person_id,
            head_bbox=candidate.head_bbox,
            face_bbox=candidate.face_bbox,
            confidence=candidate.confidence,
            state=candidate.state,
            view_state=candidate.view_state,
            observed=candidate.observed,
            track_age_frames=tracked.track_age_frames,
            face_keypoints=candidate.face_keypoints,
            pose_head_landmarks=candidate.pose_head_landmarks,
            facial_transformation_matrix=candidate.facial_transformation_matrix,
            head_pose=candidate.head_pose,
            face_landmarks=candidate.face_landmarks,
        )

    @staticmethod
    def _tracked_only_perception(
        person_id: int,
        state: _BridgeState,
        *,
        confidence: float,
        missed_ms: float,
    ) -> HeadPerception:
        return HeadPerception(
            person_id=person_id,
            head_bbox=state.head_bbox,
            face_bbox=None,
            confidence=confidence,
            state=HeadPerceptionState.TRACKED_ONLY,
            view_state=HeadViewState.UNKNOWN,
            observed=False,
            track_age_frames=state.track_age_frames + state.missed_frames + 1,
            missed_frames=state.missed_frames + 1,
            missed_ms=missed_ms,
        )

    def update(
        self,
        tracked_candidates: Tuple[TrackedHeadCandidate, ...],
        *,
        timestamp_ms: float,
    ) -> Tuple[HeadPerception, ...]:
        timestamp_ms = _timestamp(timestamp_ms)
        if self._last_timestamp_ms is not None and timestamp_ms < self._last_timestamp_ms:
            raise ValueError("timestamp_ms must be monotonic")
        tracked_candidates = tuple(tracked_candidates)
        observed_ids = tuple(tracked.person_id for tracked in tracked_candidates)
        if len(set(observed_ids)) != len(observed_ids):
            raise ValueError("tracked_candidates must contain unique person IDs")

        perceptions = []
        for tracked in tracked_candidates:
            person_id = _nonnegative_int(tracked.person_id, name="person_id")
            candidate = tracked.candidate
            self._states[person_id] = _BridgeState(
                head_bbox=tuple(float(value) for value in candidate.head_bbox),
                confidence=float(candidate.confidence),
                track_age_frames=tracked.track_age_frames,
                last_observed_timestamp_ms=timestamp_ms,
            )
            perceptions.append(self._observed_perception(tracked))

        observed_set = set(observed_ids)
        for person_id in sorted(tuple(self._states)):
            if person_id in observed_set:
                continue
            state = self._states[person_id]
            missed_ms = timestamp_ms - state.last_observed_timestamp_ms
            confidence = state.confidence * math.exp(-missed_ms / _DECAY_TIME_MS)
            if missed_ms > self._max_gap_ms or confidence < self._min_confidence:
                del self._states[person_id]
                continue
            perceptions.append(
                self._tracked_only_perception(
                    person_id,
                    state,
                    confidence=confidence,
                    missed_ms=missed_ms,
                )
            )
            self._states[person_id] = _BridgeState(
                head_bbox=state.head_bbox,
                confidence=state.confidence,
                track_age_frames=state.track_age_frames,
                last_observed_timestamp_ms=state.last_observed_timestamp_ms,
                missed_frames=state.missed_frames + 1,
            )

        self._last_timestamp_ms = timestamp_ms
        return tuple(perceptions)

    def reset(self) -> None:
        self._states.clear()
        self._last_timestamp_ms = None


__all__ = [
    "ByteTrackHeadTracker",
    "ShortOcclusionBridge",
    "TrackedHeadCandidate",
]
