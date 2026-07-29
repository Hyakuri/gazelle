import math
from dataclasses import replace
from numbers import Real
from typing import Tuple

from gazelle.runtime.contracts import GazePrediction, GazeStatus, HeadObservation
from gazelle.runtime.perception.contracts import (
    HeadFrameResult,
    HeadPerception,
    HeadPerceptionState,
    HeadViewState,
)


_MIN_FACE_GAZE_CONFIDENCE = 0.50


def _meets_face_gaze_quality(perception: HeadPerception) -> bool:
    ray = perception.face_pose_reference_ray
    return (
        ray is not None
        and isinstance(perception.confidence, Real)
        and not isinstance(perception.confidence, bool)
        and math.isfinite(float(perception.confidence))
        and float(perception.confidence) >= _MIN_FACE_GAZE_CONFIDENCE
        and isinstance(ray.confidence, Real)
        and not isinstance(ray.confidence, bool)
        and math.isfinite(float(ray.confidence))
        and float(ray.confidence) >= _MIN_FACE_GAZE_CONFIDENCE
    )


def _rejection_status(perception: HeadPerception):
    if perception.state is HeadPerceptionState.TRACKED_ONLY or not perception.observed:
        return GazeStatus.TRACKED_NO_GAZE
    if (
        perception.state is HeadPerceptionState.POSE_ONLY
        or perception.view_state is HeadViewState.BACK_OR_OCCLUDED
    ):
        return GazeStatus.UNAVAILABLE_OCCLUDED
    if not _meets_face_gaze_quality(perception):
        return GazeStatus.REJECTED_LOW_QUALITY
    return None


def annotate_gaze_eligibility(
    perceptions,
) -> Tuple[HeadPerception, ...]:
    annotated = []
    for perception in tuple(perceptions):
        if not isinstance(perception, HeadPerception):
            raise ValueError("perceptions must contain HeadPerception values")
        status = _rejection_status(perception)
        annotated.append(
            replace(
                perception,
                gaze_eligible=status is None,
                gaze_status=status,
            )
        )
    return tuple(annotated)


def _perception_priority(perception: HeadPerception):
    state_priority = {
        HeadPerceptionState.FACE_POSE: 0,
        HeadPerceptionState.FACE_ONLY: 1,
        HeadPerceptionState.POSE_ONLY: 2,
        HeadPerceptionState.TRACKED_ONLY: 3,
    }
    return (
        0 if perception.observed else 1,
        state_priority[perception.state],
        -float(perception.confidence),
        float(perception.missed_ms),
        -int(perception.track_age_frames),
        int(perception.person_id),
    )


def arbitrate_perceptions(perceptions, *, max_heads: int) -> Tuple[HeadPerception, ...]:
    if not isinstance(max_heads, int) or isinstance(max_heads, bool) or not 1 <= max_heads <= 10:
        raise ValueError("max_heads must be an int from 1 through 10")
    perceptions = tuple(perceptions)
    if len(perceptions) <= max_heads:
        return perceptions
    selected = sorted(perceptions, key=_perception_priority)[:max_heads]
    selected_ids = {id(item) for item in selected}
    return tuple(item for item in perceptions if id(item) in selected_ids)


def select_gazelle_heads(result: HeadFrameResult) -> Tuple[HeadObservation, ...]:
    heads = tuple(result.heads)
    perceptions = tuple(result.perceptions)
    if not perceptions:
        return heads
    if len(heads) != len(perceptions):
        raise ValueError("result.heads and result.perceptions must have the same length")
    selected = []
    for index, (head, perception) in enumerate(zip(heads, perceptions)):
        if head.person_id != perception.person_id:
            raise ValueError(
                "result head and perception person_id mismatch at index {}".format(index)
            )
        if perception.gaze_eligible and _rejection_status(perception) is None:
            selected.append(head)
    return tuple(selected)


def _validate_inout_threshold(value) -> float:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError("inout_threshold must be a finite real number from 0 through 1")
    return float(value)


def apply_prediction_gaze_status(
    predictions,
    *,
    inout_threshold,
) -> Tuple[GazePrediction, ...]:
    threshold = _validate_inout_threshold(inout_threshold)
    classified = []
    for prediction in tuple(predictions):
        if not isinstance(prediction, GazePrediction):
            raise ValueError("predictions must contain GazePrediction values")
        score = prediction.inout_score
        if score is None:
            status = GazeStatus.VALID
        elif (
            not isinstance(score, Real)
            or isinstance(score, bool)
            or not math.isfinite(float(score))
        ):
            raise ValueError("prediction inout_score must be finite when provided")
        else:
            status = (
                GazeStatus.VALID
                if float(score) >= threshold
                else GazeStatus.OUT_OF_FRAME
            )
        classified.append(replace(prediction, gaze_status=status))
    return tuple(classified)


__all__ = [
    "annotate_gaze_eligibility",
    "apply_prediction_gaze_status",
    "arbitrate_perceptions",
    "select_gazelle_heads",
]
