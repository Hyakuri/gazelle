from gazelle.runtime.perception.contracts import (
    FaceObservation,
    HeadCandidate,
    HeadFrameResult,
    HeadPerception,
    HeadPerceptionState,
    HeadPoseAngles,
    HeadViewState,
    NormalizedLandmark,
    PoseObservation,
)

__all__ = [
    "FaceObservation",
    "HeadCandidate",
    "HeadFrameResult",
    "HeadPerception",
    "HeadPerceptionState",
    "HeadPoseAngles",
    "HeadViewState",
    "NormalizedLandmark",
    "PoseObservation",
    "MediaPipeHeadProvider",
]


def __getattr__(name):
    if name == "MediaPipeHeadProvider":
        from gazelle.runtime.perception.provider import MediaPipeHeadProvider

        return MediaPipeHeadProvider
    raise AttributeError(name)
