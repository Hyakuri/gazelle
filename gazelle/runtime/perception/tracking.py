import importlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
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


def _tracker_person_id(value: object) -> Optional[int]:
    if not isinstance(value, Integral) or isinstance(value, (bool, np.bool_)):
        raise RuntimeError("tracker output person_id must be -1 or a non-negative integer")
    person_id = int(value)
    if person_id < -1:
        raise RuntimeError("tracker output person_id must be -1 or a non-negative integer")
    return None if person_id == -1 else person_id


def _confidence(value: object) -> float:
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError("confidence must be a finite clipped value from 0 through 1")
    return float(value)


def _normalized_box_copy(value: object) -> Tuple[float, float, float, float]:
    try:
        coordinates = tuple(value)
    except TypeError as exc:
        raise ValueError("head_bbox must contain four finite normalized coordinates") from exc
    if len(coordinates) != 4 or any(
        not isinstance(coordinate, Real)
        or isinstance(coordinate, (bool, np.bool_))
        or not math.isfinite(float(coordinate))
        for coordinate in coordinates
    ):
        raise ValueError("head_bbox must contain four finite normalized coordinates")
    return tuple(float(coordinate) for coordinate in coordinates)


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
        self._public_id_by_raw_id = {}
        self._reserved_public_ids = set()
        self._next_public_id = 0
        self._last_frame_index: Optional[int] = None
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
    ):
        if not candidates:
            output_fields = tuple(
                getattr(tracked, name, None)
                for name in ("xyxy", "tracker_id", "confidence", "class_id")
            )
            data = getattr(tracked, "data", None)
            if isinstance(data, Mapping):
                output_fields += tuple(data.values())
            try:
                has_rows = len(tracked) > 0
            except TypeError:
                has_rows = False
            if has_rows or any(self._has_output_values(value) for value in output_fields):
                raise RuntimeError(
                    "Invalid tracker output for empty candidate frame: expected no rows"
                )
            return (
                (),
                dict(self._first_frame_by_person),
                dict(self._public_id_by_raw_id),
                set(self._reserved_public_ids),
                self._next_public_id,
            )
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

        parsed_rows = []
        seen_people = set()
        seen_candidates = set()
        for raw_person_id, raw_candidate_index in zip(tracker_ids, candidate_indexes):
            raw_person_id = _tracker_person_id(raw_person_id)
            candidate_index = _nonnegative_int(
                raw_candidate_index,
                name="tracker output candidate_index",
                error_type=RuntimeError,
            )
            if candidate_index >= len(candidates):
                raise RuntimeError("Invalid tracker output: candidate_index is out of range")
            if candidate_index in seen_candidates:
                raise RuntimeError("Invalid tracker output: duplicate candidate index")
            seen_candidates.add(candidate_index)
            if raw_person_id is None:
                continue
            if raw_person_id in seen_people:
                raise RuntimeError("Invalid tracker output: duplicate person ID")
            seen_people.add(raw_person_id)
            parsed_rows.append((candidate_index, raw_person_id))

        next_first_frames = dict(self._first_frame_by_person)
        next_public_ids = dict(self._public_id_by_raw_id)
        next_reserved_ids = set(self._reserved_public_ids)
        next_public_id = self._next_public_id
        mapped = []
        for candidate_index, raw_person_id in sorted(parsed_rows):
            person_id = next_public_ids.get(raw_person_id)
            if person_id is None:
                while next_public_id in next_reserved_ids:
                    next_public_id += 1
                person_id = next_public_id
                next_public_id += 1
                next_public_ids[raw_person_id] = person_id
                next_reserved_ids.add(person_id)
            first_frame = next_first_frames.setdefault(person_id, frame_index)
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
        result = tuple(item for _, item in mapped)
        return (
            result,
            next_first_frames,
            next_public_ids,
            next_reserved_ids,
            next_public_id,
        )

    @staticmethod
    def _has_output_values(value: object) -> bool:
        if value is None:
            return False
        try:
            return len(value) > 0
        except TypeError:
            return True

    @staticmethod
    def _cleanup_backend(tracker) -> None:
        close = getattr(tracker, "close", None)
        if callable(close):
            close()
            return
        reset = getattr(tracker, "reset", None)
        if callable(reset):
            reset()

    def _invalidate_tracker(self, original_error: Exception) -> None:
        tracker = self._tracker
        self._tracker = None
        self._first_frame_by_person.clear()
        self._public_id_by_raw_id.clear()
        if tracker is None:
            return
        try:
            self._cleanup_backend(tracker)
        except Exception as cleanup_error:
            if hasattr(original_error, "add_note"):
                original_error.add_note(
                    f"Backend cleanup also failed: {cleanup_error!r}"
                )

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
        if self._last_frame_index is not None and frame_index <= self._last_frame_index:
            raise ValueError("frame_index must increase strictly")
        candidates = tuple(candidates)
        tracker = self._ensure_tracker()
        detections = self._build_detections(
            candidates,
            image_width=image_width,
            image_height=image_height,
        )
        try:
            tracked = tracker.update(detections)
            (
                result,
                next_first_frames,
                next_public_ids,
                next_reserved_ids,
                next_public_id,
            ) = self._map_tracked_candidates(
                tracked,
                candidates,
                frame_index=frame_index,
            )
        except Exception as exc:
            self._invalidate_tracker(exc)
            raise
        self._first_frame_by_person = next_first_frames
        self._public_id_by_raw_id = next_public_ids
        self._reserved_public_ids = next_reserved_ids
        self._next_public_id = next_public_id
        self._last_frame_index = frame_index
        self._last_timestamp_ms = timestamp_ms
        return result

    def reset(self) -> None:
        if self._closed:
            raise RuntimeError("ByteTrackHeadTracker is closed")
        tracker = self._tracker
        self._first_frame_by_person.clear()
        self._public_id_by_raw_id.clear()
        self._reserved_public_ids.clear()
        self._next_public_id = 0
        self._last_frame_index = None
        self._last_timestamp_ms = None
        if tracker is None:
            return
        reset = getattr(tracker, "reset", None)
        if callable(reset):
            try:
                reset()
            except Exception:
                self._tracker = None
                raise
            return
        self._tracker = None
        close = getattr(tracker, "close", None)
        if callable(close):
            close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        tracker = self._tracker
        self._tracker = None
        self._first_frame_by_person.clear()
        self._public_id_by_raw_id.clear()
        self._reserved_public_ids.clear()
        self._next_public_id = 0
        self._last_frame_index = None
        self._last_timestamp_ms = None
        if tracker is None:
            return
        self._cleanup_backend(tracker)


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

    @staticmethod
    def _stage_tracked_candidate(
        tracked: TrackedHeadCandidate,
        *,
        timestamp_ms: float,
    ):
        if not isinstance(tracked, TrackedHeadCandidate):
            raise ValueError("tracked_candidates must contain TrackedHeadCandidate values")
        person_id = _nonnegative_int(tracked.person_id, name="person_id")
        track_age_frames = _nonnegative_int(
            tracked.track_age_frames,
            name="track_age_frames",
        )
        candidate = tracked.candidate
        if not isinstance(candidate, HeadCandidate):
            raise ValueError("tracked candidate must contain a HeadCandidate")
        confidence = _confidence(candidate.confidence)
        if not isinstance(candidate.state, HeadPerceptionState):
            raise ValueError("candidate state must be a HeadPerceptionState")
        head_bbox = _normalized_box_copy(candidate.head_bbox)
        staged_candidate = replace(
            candidate,
            head_bbox=head_bbox,
            confidence=confidence,
        )
        staged_tracked = TrackedHeadCandidate(
            person_id=person_id,
            candidate=staged_candidate,
            track_age_frames=track_age_frames,
        )
        state = _BridgeState(
            head_bbox=head_bbox,
            confidence=confidence,
            track_age_frames=track_age_frames,
            last_observed_timestamp_ms=timestamp_ms,
        )
        return person_id, staged_tracked, state

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
        staged = []
        observed_ids = set()
        for tracked in tracked_candidates:
            person_id, staged_tracked, state = self._stage_tracked_candidate(
                tracked,
                timestamp_ms=timestamp_ms,
            )
            if person_id in observed_ids:
                raise ValueError("tracked_candidates must contain unique person IDs")
            observed_ids.add(person_id)
            staged.append((person_id, staged_tracked, state))

        next_states = dict(self._states)
        perceptions = []
        for person_id, staged_tracked, state in staged:
            next_states[person_id] = state
            perceptions.append(self._observed_perception(staged_tracked))

        for person_id in sorted(tuple(next_states)):
            if person_id in observed_ids:
                continue
            state = next_states[person_id]
            missed_ms = timestamp_ms - state.last_observed_timestamp_ms
            confidence = state.confidence * math.exp(-missed_ms / _DECAY_TIME_MS)
            if missed_ms > self._max_gap_ms or confidence < self._min_confidence:
                del next_states[person_id]
                continue
            perceptions.append(
                self._tracked_only_perception(
                    person_id,
                    state,
                    confidence=confidence,
                    missed_ms=missed_ms,
                )
            )
            next_states[person_id] = _BridgeState(
                head_bbox=state.head_bbox,
                confidence=state.confidence,
                track_age_frames=state.track_age_frames,
                last_observed_timestamp_ms=state.last_observed_timestamp_ms,
                missed_frames=state.missed_frames + 1,
            )

        self._states = next_states
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
