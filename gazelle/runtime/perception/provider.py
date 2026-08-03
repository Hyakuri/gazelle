from dataclasses import replace
from time import perf_counter
from typing import Optional, Tuple

from gazelle.runtime.contracts import HeadObservation
from gazelle.runtime.geometry import sanitize_normalized_bbox
from gazelle.runtime.heads import HeadProvider
from gazelle.runtime.perception.contracts import HeadFrameResult, HeadPerception
from gazelle.runtime.perception.fusion import build_head_candidates
from gazelle.runtime.perception.gaze_policy import (
    annotate_gaze_eligibility,
    arbitrate_perceptions,
)


def _create_default_backend(config, *, media_type: str):
    from gazelle.runtime.perception.mediapipe_backend import MediaPipeBackend
    from gazelle.runtime.perception.resources import prepare_mediapipe_resources

    resources = prepare_mediapipe_resources(config)
    return MediaPipeBackend.create(
        resources,
        media_type=media_type,
        max_heads=config.max_heads,
    )


def _create_default_tracker(source_fps: float):
    from gazelle.runtime.perception.tracking import ByteTrackHeadTracker

    return ByteTrackHeadTracker(source_fps)


def _create_short_occlusion_bridge(max_gap_ms: float):
    from gazelle.runtime.perception.tracking import ShortOcclusionBridge

    return ShortOcclusionBridge(max_gap_ms=max_gap_ms)


def _attach_cleanup_context(primary_error, resource_name: str, cleanup_error) -> None:
    add_note = getattr(primary_error, "add_note", None)
    if callable(add_note):
        add_note("{} cleanup also failed: {!r}".format(resource_name, cleanup_error))


def _cleanup_after_construction_failure(primary_error, resources) -> None:
    for resource_name, resource in resources:
        close = getattr(resource, "close", None)
        if not callable(close):
            continue
        try:
            close()
        except BaseException as cleanup_error:
            _attach_cleanup_context(primary_error, resource_name, cleanup_error)


def _normalized_candidate(candidate):
    return replace(
        candidate,
        head_bbox=sanitize_normalized_bbox(candidate.head_bbox, clip=True),
        face_bbox=(
            None
            if candidate.face_bbox is None
            else sanitize_normalized_bbox(candidate.face_bbox, clip=True)
        ),
    )


def _image_perception(person_id: int, candidate) -> HeadPerception:
    return HeadPerception(
        person_id=person_id,
        head_bbox=candidate.head_bbox,
        face_bbox=candidate.face_bbox,
        confidence=candidate.confidence,
        state=candidate.state,
        view_state=candidate.view_state,
        observed=candidate.observed,
        face_keypoints=candidate.face_keypoints,
        pose_head_landmarks=candidate.pose_head_landmarks,
        pose_head_keypoints=candidate.pose_head_keypoints,
        facial_transformation_matrix=candidate.facial_transformation_matrix,
        head_pose=candidate.head_pose,
        face_landmarks=candidate.face_landmarks,
        face_pose_reference_ray=candidate.face_pose_reference_ray,
        pose_head_reference_ray=candidate.pose_head_reference_ray,
    )


class MediaPipeHeadProvider(HeadProvider):
    def __init__(
        self,
        *,
        backend,
        max_heads: int,
        tracker=None,
        bridge=None,
        reference_ray_length: float = 2.5,
    ):
        self._backend = backend
        self._max_heads = max_heads
        self._tracker = tracker
        self._bridge = bridge
        self._reference_ray_length = reference_ray_length
        self._closed = False

    @classmethod
    def create(
        cls,
        config,
        *,
        media_type: str,
        source_fps: float,
        backend_factory=None,
        tracker_factory=None,
    ) -> "MediaPipeHeadProvider":
        if media_type not in ("image", "video"):
            raise ValueError("media_type must be 'image' or 'video'")
        factory = _create_default_backend if backend_factory is None else backend_factory
        backend = factory(config, media_type=media_type)
        if media_type == "image":
            return cls(
                backend=backend,
                max_heads=config.max_heads,
                reference_ray_length=getattr(config, "reference_ray_length", 2.5),
            )

        tracker_factory = _create_default_tracker if tracker_factory is None else tracker_factory
        try:
            tracker = tracker_factory(source_fps)
        except BaseException as construction_error:
            _cleanup_after_construction_failure(
                construction_error,
                (("backend", backend),),
            )
            raise
        try:
            bridge = _create_short_occlusion_bridge(config.head_track_max_gap_ms)
        except BaseException as construction_error:
            _cleanup_after_construction_failure(
                construction_error,
                (("tracker", tracker), ("backend", backend)),
            )
            raise
        return cls(
            backend=backend,
            max_heads=config.max_heads,
            tracker=tracker,
            bridge=bridge,
            reference_ray_length=getattr(config, "reference_ray_length", 2.5),
        )

    def _assign_people(
        self,
        candidates,
        *,
        frame_index: int,
        timestamp_ms: float,
        image_width: int,
        image_height: int,
    ) -> Tuple[HeadPerception, ...]:
        if self._tracker is None:
            perceptions = tuple(
                _image_perception(person_id, candidate)
                for person_id, candidate in enumerate(candidates)
            )
            return annotate_gaze_eligibility(
                arbitrate_perceptions(perceptions, max_heads=self._max_heads)
            )
        tracked = self._tracker.update(
            candidates,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            image_width=image_width,
            image_height=image_height,
        )
        perceptions = self._bridge.update(tracked, timestamp_ms=timestamp_ms)
        perceptions = arbitrate_perceptions(perceptions, max_heads=self._max_heads)
        if self._max_heads == 1:
            self._bridge.retain_person_ids(
                tuple(perception.person_id for perception in perceptions)
            )
        return annotate_gaze_eligibility(perceptions)

    def get_frame_result(self, frame, frame_index, timestamp_ms, image_width, image_height):
        if self._closed:
            raise RuntimeError("MediaPipe head provider is closed")
        total_start = perf_counter()
        observed = self._backend.observe(
            frame,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            image_width=image_width,
            image_height=image_height,
        )
        fusion_start = perf_counter()
        candidates = tuple(
            _normalized_candidate(candidate)
            for candidate in build_head_candidates(
                faces=observed.faces,
                poses=observed.poses,
                max_heads=self._max_heads,
                reference_ray_length=self._reference_ray_length,
            )
        )
        fusion_ms = (perf_counter() - fusion_start) * 1000.0

        tracking_start = perf_counter()
        perceptions = self._assign_people(
            candidates,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            image_width=image_width,
            image_height=image_height,
        )
        tracking_ms = (perf_counter() - tracking_start) * 1000.0
        heads = tuple(
            HeadObservation(
                person_id=item.person_id,
                bbox=sanitize_normalized_bbox(item.head_bbox, clip=True),
                confidence=item.confidence,
            )
            for item in perceptions
        )
        timings = dict(observed.timings_ms)
        backend_total = timings.pop("total", None)
        if backend_total is not None:
            timings["backend_total"] = backend_total
        timings["fusion"] = fusion_ms
        if self._tracker is not None:
            timings["tracking"] = tracking_ms
        timings["total"] = (perf_counter() - total_start) * 1000.0
        return HeadFrameResult(heads=heads, perceptions=perceptions, timings_ms=timings)

    def get_heads(self, frame, frame_index, timestamp_ms, image_width, image_height):
        return self.get_frame_result(
            frame,
            frame_index,
            timestamp_ms,
            image_width,
            image_height,
        ).heads

    def close(self):
        if self._closed:
            return
        self._closed = True
        first_error = None
        for resource in (self._backend, self._tracker):
            if resource is None:
                continue
            close = getattr(resource, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error


__all__ = ["MediaPipeHeadProvider"]
