import math
import unittest

from gazelle.runtime.perception.contracts import (
    FaceObservation,
    HeadCandidate,
    HeadPerceptionState,
    HeadPoseAngles,
    HeadViewState,
    NormalizedLandmark,
    PoseObservation,
)
from gazelle.runtime.perception.fusion import (
    HeadBoxFusionConfig,
    associate_face_pose,
    build_head_candidates,
    build_pose_head_candidate,
    expand_face_to_head_bbox,
    fuse_head_candidates,
)


def make_face(bbox, confidence=0.9, yaw=None):
    head_pose = None if yaw is None else HeadPoseAngles(yaw_deg=yaw, pitch_deg=0.0, roll_deg=0.0)
    return FaceObservation(bbox=bbox, confidence=confidence, head_pose=head_pose)


def landmark(x, y, visibility=0.9, presence=0.9):
    return NormalizedLandmark(x=x, y=y, visibility=visibility, presence=presence)


def make_pose(landmarks, pose_index=0):
    return PoseObservation(pose_index=pose_index, landmarks=tuple(landmarks))


def make_pose_head_at(x, y, quality=0.9, pose_index=0):
    points = [landmark(x, y, quality, quality) for _ in range(13)]
    points[0] = landmark(x - 0.02, y - 0.02, quality, quality)
    points[1] = landmark(x + 0.02, y + 0.02, quality, quality)
    points[11] = landmark(x - 0.10, y + 0.15, quality, quality)
    points[12] = landmark(x + 0.10, y + 0.15, quality, quality)
    return make_pose(points, pose_index=pose_index)


class HeadFusionTest(unittest.TestCase):
    def assertBBoxAlmostEqual(self, actual, expected):
        self.assertIsNotNone(actual)
        self.assertEqual(len(actual), 4)
        for value, wanted in zip(actual, expected):
            self.assertAlmostEqual(value, wanted)

    def test_config_uses_approved_defaults(self):
        self.assertEqual(
            HeadBoxFusionConfig(),
            HeadBoxFusionConfig(
                min_visibility=0.50,
                min_presence=0.50,
                face_expand_x=0.20,
                face_expand_top=0.45,
                face_expand_bottom=0.10,
                min_consistent_iou=0.10,
                max_center_distance_diagonal_ratio=0.75,
            ),
        )

    def test_face_only_expansion(self):
        bbox = expand_face_to_head_bbox((0.2, 0.3, 0.4, 0.5))
        self.assertBBoxAlmostEqual(bbox, (0.16, 0.21, 0.44, 0.52))

    def test_face_expansion_is_clipped(self):
        bbox = expand_face_to_head_bbox((0.0, 0.0, 0.2, 0.2))
        self.assertBBoxAlmostEqual(bbox, (0.0, 0.0, 0.24, 0.22))

    def test_pose_head_landmarks_use_median_spans_and_shoulders(self):
        points = [landmark(0.5, 0.45, 0.0, 0.0) for _ in range(13)]
        points[0] = landmark(0.4, 0.4)
        points[1] = landmark(0.6, 0.5)
        points[11] = landmark(0.3, 0.7)
        points[12] = landmark(0.7, 0.7)

        candidate = build_pose_head_candidate(make_pose(points))

        self.assertBBoxAlmostEqual(candidate.head_bbox, (0.36, 0.354, 0.64, 0.514))
        self.assertAlmostEqual(candidate.confidence, 0.9)
        self.assertEqual(candidate.view_state, HeadViewState.BACK_OR_OCCLUDED)

    def test_pose_head_uses_shoulders_when_head_landmarks_are_missing(self):
        points = [landmark(0.5, 0.5, 0.0, 0.0) for _ in range(13)]
        points[11] = landmark(0.3, 0.65)
        points[12] = landmark(0.7, 0.65)

        candidate = build_pose_head_candidate(make_pose(points))

        self.assertBBoxAlmostEqual(candidate.head_bbox, (0.416, 0.398, 0.584, 0.618))

    def test_pose_head_returns_none_with_insufficient_landmarks_and_shoulders(self):
        points = [landmark(0.5, 0.5, 0.0, 0.0) for _ in range(13)]
        points[0] = landmark(0.5, 0.5)
        points[11] = landmark(0.3, 0.65)

        self.assertIsNone(build_pose_head_candidate(make_pose(points)))

    def test_pose_head_ignores_non_finite_landmarks(self):
        points = [landmark(0.5, 0.5, 0.0, 0.0) for _ in range(13)]
        points[0] = landmark(float("nan"), 0.4)
        points[1] = landmark(0.6, float("inf"))
        points[11] = landmark(0.3, 0.65)
        points[12] = landmark(0.7, 0.65)

        candidate = build_pose_head_candidate(make_pose(points))

        self.assertBBoxAlmostEqual(candidate.head_bbox, (0.416, 0.398, 0.584, 0.618))
        self.assertTrue(all(math.isfinite(value) for value in candidate.head_bbox))

    def test_pose_quality_uses_only_landmarks_used_for_geometry(self):
        points = [landmark(0.5, 0.5, 0.0, 0.0) for _ in range(13)]
        points[0] = landmark(0.4, 0.4, 0.9, 0.9)
        points[1] = landmark(0.6, 0.5, 0.9, 0.9)
        points[11] = landmark(0.3, 0.65, 0.5, 0.5)

        candidate = build_pose_head_candidate(make_pose(points))

        self.assertAlmostEqual(candidate.confidence, 0.9)

    def test_association_accepts_iou_gate(self):
        faces = build_head_candidates(
            faces=(make_face((0.4, 0.4, 0.6, 0.6)),),
            poses=(),
            max_heads=1,
        )
        pose = build_pose_head_candidate(make_pose_head_at(0.5, 0.5))

        self.assertTrue(associate_face_pose(faces[0], pose))

    def test_association_accepts_center_distance_gate_without_iou(self):
        faces = build_head_candidates(
            faces=(make_face((0.2, 0.4, 0.3, 0.5)),),
            poses=(),
            max_heads=1,
        )
        pose = build_pose_head_candidate(make_pose_head_at(0.39, 0.48))

        self.assertTrue(associate_face_pose(faces[0], pose))

    def test_association_rejects_boxes_outside_both_gates(self):
        faces = build_head_candidates(
            faces=(make_face((0.05, 0.05, 0.15, 0.15)),),
            poses=(),
            max_heads=1,
        )
        pose = build_pose_head_candidate(make_pose_head_at(0.8, 0.8))

        self.assertFalse(associate_face_pose(faces[0], pose))

    def test_consistent_face_and_pose_are_fused_by_union(self):
        candidates = build_head_candidates(
            faces=(make_face((0.4, 0.4, 0.6, 0.6), confidence=0.8, yaw=20.0),),
            poses=(make_pose_head_at(0.5, 0.5, quality=0.6),),
            max_heads=1,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].state, HeadPerceptionState.FACE_POSE)
        self.assertBBoxAlmostEqual(candidates[0].head_bbox, (0.36, 0.31, 0.64, 0.62))
        self.assertAlmostEqual(candidates[0].confidence, 0.7)
        self.assertEqual(candidates[0].view_state, HeadViewState.FRONTAL)

    def test_inconsistent_face_pose_selects_higher_quality(self):
        candidates = build_head_candidates(
            faces=(make_face((0.05, 0.05, 0.15, 0.15), confidence=0.9),),
            poses=(make_pose_head_at(0.8, 0.8, quality=0.6),),
            max_heads=1,
        )
        self.assertEqual(candidates[0].state, HeadPerceptionState.FACE_ONLY)

    def test_inconsistent_fusion_sanitizes_selected_output(self):
        face = HeadCandidate(
            source_index=0,
            head_bbox=(-0.1, 0.2, 0.4, 0.5),
            face_bbox=(-0.1, 0.2, 0.4, 0.5),
            confidence=0.9,
            state=HeadPerceptionState.FACE_ONLY,
            view_state=HeadViewState.UNKNOWN,
        )
        pose = HeadCandidate(
            source_index=1,
            head_bbox=(0.7, 0.7, 1.2, 1.2),
            face_bbox=None,
            confidence=0.6,
            state=HeadPerceptionState.POSE_ONLY,
            view_state=HeadViewState.BACK_OR_OCCLUDED,
        )

        candidate = fuse_head_candidates(face, pose)

        self.assertBBoxAlmostEqual(candidate.head_bbox, (0.0, 0.2, 0.4, 0.5))
        self.assertBBoxAlmostEqual(candidate.face_bbox, (0.0, 0.2, 0.4, 0.5))

    def test_confidences_are_clipped_and_non_finite_scores_do_not_escape(self):
        candidates = build_head_candidates(
            faces=(make_face((0.2, 0.2, 0.4, 0.4), confidence=float("inf")),),
            poses=(make_pose_head_at(0.3, 0.3, quality=float("nan")),),
            max_heads=2,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].confidence, 0.0)
        self.assertTrue(math.isfinite(candidates[0].confidence))

    def test_face_view_states_use_angles_and_unknown_fallback(self):
        candidates = build_head_candidates(
            faces=(
                make_face((0.1, 0.1, 0.2, 0.2), yaw=34.9),
                make_face((0.3, 0.1, 0.4, 0.2), yaw=35.0),
                make_face((0.5, 0.1, 0.6, 0.2)),
            ),
            poses=(),
            max_heads=3,
        )

        self.assertEqual(
            tuple(candidate.view_state for candidate in candidates),
            (HeadViewState.FRONTAL, HeadViewState.PROFILE, HeadViewState.UNKNOWN),
        )

    def test_max_heads_accepts_only_one_through_ten(self):
        face = make_face((0.2, 0.2, 0.4, 0.4))
        for max_heads in (0, 11, True):
            with self.subTest(max_heads=max_heads):
                with self.assertRaises(ValueError):
                    build_head_candidates(faces=(face,), poses=(), max_heads=max_heads)

    def test_one_person_selection_is_deterministic(self):
        candidates = build_head_candidates(
            faces=(
                make_face((0.6, 0.2, 0.7, 0.3), confidence=0.7),
                make_face((0.1, 0.2, 0.2, 0.3), confidence=0.9),
            ),
            poses=(
                make_pose_head_at(0.65, 0.25, quality=0.6, pose_index=3),
                make_pose_head_at(0.15, 0.25, quality=0.8, pose_index=1),
            ),
            max_heads=1,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].state, HeadPerceptionState.FACE_POSE)
        self.assertLess(candidates[0].head_bbox[0], 0.2)

    def test_ten_person_ordering_is_deterministic(self):
        faces = tuple(
            make_face((0.02 + 0.09 * index, 0.2, 0.07 + 0.09 * index, 0.3), confidence=0.9)
            for index in range(10)
        )
        poses = tuple(
            make_pose_head_at(0.045 + 0.09 * index, 0.25, quality=0.8, pose_index=9 - index)
            for index in range(10)
        )

        first = build_head_candidates(faces=faces, poses=poses, max_heads=10)
        second = build_head_candidates(faces=faces, poses=poses, max_heads=10)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 10)
        self.assertEqual(
            [round(candidate.head_bbox[0], 3) for candidate in first],
            [round(0.01 + 0.09 * index, 3) for index in range(10)],
        )


if __name__ == "__main__":
    unittest.main()
