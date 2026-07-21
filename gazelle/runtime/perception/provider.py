from dataclasses import replace
from time import perf_counter
from typing import Optional, Tuple

from gazelle.runtime.contracts import HeadObservation
from gazelle.runtime.geometry import sanitize_normalized_bbox
from gazelle.runtime.heads import HeadProvider
from gazelle.runtime.perception.contracts import HeadFrameResult, HeadPerception
from gazelle.runtime.perception.fusion import build_head_candidates


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
        facial_transformation_matrix=candidate.facial_transformation_matrix,
        head_pose=candidate.head_pose,
        face_landmarks=candidate.face_landmarks,
    )


class MediaPipeHeadProvider(HeadProvider):
    def __init__(
        self,
        *,
        backend,
        max_heads: int,
        tracker=None,
        bridge=None,
    ):
        self._backend = backend
        self._max_heads = max_heads
        self._tracker = tracker
        self._bridge = bridge
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
            return cls(backend=backend, max_heads=config.max_heads)

        tracker_factory = _create_default_tracker if tracker_factory is None else tracker_factory
        return cls(
            backend=backend,
            max_heads=config.max_heads,
            tracker=tracker_factory(source_fps),
            bridge=_create_short_occlusion_bridge(config.head_track_max_gap_ms),
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
            return tuple(
                _image_perception(person_id, candidate)
                for person_id, candidate in enumerate(candidates)
            )
        tracked = self._tracker.update(
            candidates,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            image_width=image_width,
            image_height=image_height,
        )
        return self._bridge.update(tracked, timestamp_ms=timestamp_ms)

    def get_frame_result(self, frame, frame_index, timestamp_ms, image_width, image_height):
        if self._closed:
            raise RuntimeError("MediaPipe head provider is closed")
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
        timings["fusion"] = fusion_ms
        if self._tracker is not None:
            timings["tracking"] = tracking_ms
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
