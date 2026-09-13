from dataclasses import FrozenInstanceError
import unittest

from gazelle.runtime.contracts import HeadObservation
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


class PerceptionContractsTest(unittest.TestCase):
    def test_contracts_are_frozen(self):
        landmark = NormalizedLandmark(x=0.1, y=0.2, z=0.3, visibility=0.4, presence=0.5)
        pose = HeadPoseAngles(yaw_deg=1.0, pitch_deg=2.0, roll_deg=3.0)
        bbox = (0.1, 0.2, 0.3, 0.4)
        contracts = (
            (landmark, "x", 0.9),
            (pose, "yaw_deg", 9.0),
            (
                FaceObservation(
                    bbox=bbox,
                    confidence=0.9,
                    keypoints=(landmark,),
                    landmarks=(landmark,),
                    transformation_matrix=((1.0, 0.0),),
                    head_pose=pose,
                ),
                "confidence",
                0.1,
            ),
            (PoseObservation(pose_index=2, landmarks=(landmark,), world_landmarks=(landmark,)), "pose_index", 3),
            (
                HeadCandidate(
                    source_index=1,
                    head_bbox=bbox,
                    face_bbox=bbox,
                    confidence=0.8,
                    state=HeadPerceptionState.FACE_POSE,
                    view_state=HeadViewState.FRONTAL,
                    face_keypoints=(landmark,),
                    pose_head_landmarks=(landmark,),
                    facial_transformation_matrix=((1.0,),),
                    head_pose=pose,
                    face_landmarks=(landmark,),
                ),
                "source_index",
                2,
            ),
            (
                HeadPerception(
                    person_id=4,
                    head_bbox=bbox,
                    face_bbox=bbox,
                    confidence=0.8,
                    state=HeadPerceptionState.FACE_ONLY,
                    view_state=HeadViewState.PROFILE,
                    observed=True,
                    track_age_frames=2,
                    missed_frames=1,
                    missed_ms=33.3,
                    face_keypoints=(landmark,),
                    pose_head_landmarks=(landmark,),
                    facial_transformation_matrix=((1.0,),),
                    head_pose=pose,
                    face_landmarks=(landmark,),
                ),
                "person_id",
                5,
            ),
            (
                HeadFrameResult(
                    heads=(HeadObservation(person_id=4, bbox=bbox, confidence=0.8),),
                    perceptions=(),
                    timings_ms={"face": 1.0},
                ),
                "heads",
                (),
            ),
        )

        for contract, attribute, value in contracts:
            with self.subTest(contract=type(contract).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(contract, attribute, value)

    def test_contract_defaults(self):
        landmark = NormalizedLandmark(x=0.1, y=0.2)
        self.assertIsNone(landmark.z)
        self.assertIsNone(landmark.visibility)
        self.assertIsNone(landmark.presence)

        self.assertEqual(FaceObservation(bbox=(0.1, 0.2, 0.3, 0.4), confidence=0.9).keypoints, ())
        self.assertEqual(PoseObservation(pose_index=0, landmarks=(landmark,)).world_landmarks, ())
        self.assertTrue(
            HeadCandidate(
                source_index=0,
                head_bbox=(0.1, 0.2, 0.3, 0.4),
                face_bbox=None,
                confidence=0.9,
                state=HeadPerceptionState.POSE_ONLY,
                view_state=HeadViewState.UNKNOWN,
            ).observed
        )
        self.assertEqual(
            HeadPerception(
                person_id=0,
                head_bbox=(0.1, 0.2, 0.3, 0.4),
                face_bbox=None,
                confidence=0.9,
                state=HeadPerceptionState.TRACKED_ONLY,
                view_state=HeadViewState.BACK_OR_OCCLUDED,
                observed=False,
            ).missed_ms,
            0.0,
        )
        self.assertEqual(HeadFrameResult(heads=()).perceptions, ())
        self.assertEqual(dict(HeadFrameResult(heads=()).timings_ms), {})

    def test_contract_enum_values(self):
        self.assertEqual(HeadPerceptionState.FACE_POSE.value, "face_pose")
        self.assertEqual(HeadPerceptionState.FACE_ONLY.value, "face_only")
        self.assertEqual(HeadPerceptionState.POSE_ONLY.value, "pose_only")
        self.assertEqual(HeadPerceptionState.TRACKED_ONLY.value, "tracked_only")
        self.assertEqual(HeadViewState.FRONTAL.value, "frontal")
        self.assertEqual(HeadViewState.PROFILE.value, "profile")
        self.assertEqual(HeadViewState.BACK_OR_OCCLUDED.value, "back_or_occluded")
        self.assertEqual(HeadViewState.UNKNOWN.value, "unknown")


if __name__ == "__main__":
    unittest.main()
