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


def landmark(x, y, visibility=0.9, presence=0.9, z=None):
    return NormalizedLandmark(
        x=x,
        y=y,
        z=z,
        visibility=visibility,
        presence=presence,
    )


def make_pose(landmarks, pose_index=0):
    return PoseObservation(pose_index=pose_index, landmarks=tuple(landmarks))


def make_pose_head_at(x, y, quality=0.9, pose_index=0, marker=None):
    points = [landmark(x, y, quality, quality, z=marker) for _ in range(13)]
    points[0] = landmark(x - 0.02, y - 0.02, quality, quality, z=marker)
    points[1] = landmark(x + 0.02, y + 0.02, quality, quality, z=marker)
    points[11] = landmark(x - 0.10, y + 0.15, quality, quality, z=marker)
    points[12] = landmark(x + 0.10, y + 0.15, quality, quality, z=marker)
    return make_pose(points, pose_index=pose_index)


def make_head_candidate(
    head_bbox,
    *,
    source_index,
    confidence,
    state,
    face_bbox=None,
):
    return HeadCandidate(
        source_index=source_index,
        head_bbox=head_bbox,
        face_bbox=face_bbox,
        confidence=confidence,
        state=state,
        view_state=(
            HeadViewState.UNKNOWN
            if state == HeadPerceptionState.FACE_ONLY
            else HeadViewState.BACK_OR_OCCLUDED
        ),
    )


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

    def test_pose_quality_averages_mixed_available_and_missing_scores(self):
        points = [landmark(0.5, 0.5, 0.0, 0.0) for _ in range(13)]
        points[0] = landmark(0.4, 0.4, visibility=0.8, presence=None)
        points[1] = landmark(0.6, 0.5, visibility=None, presence=0.6)

        candidate = build_pose_head_candidate(make_pose(points))

        self.assertAlmostEqual(candidate.confidence, 0.7)

    def test_association_accepts_iou_alone_when_center_distance_fails(self):
        face = make_head_candidate(
            (0.4, 0.45, 0.5, 1.0),
            source_index=0,
            confidence=0.9,
            state=HeadPerceptionState.FACE_ONLY,
            face_bbox=(0.4, 0.45, 0.5, 1.0),
        )
        pose = make_head_candidate(
            (0.4, 0.0, 0.5, 0.55),
            source_index=1,
            confidence=0.8,
            state=HeadPerceptionState.POSE_ONLY,
        )

        self.assertTrue(associate_face_pose(face, pose))
        self.assertFalse(
            associate_face_pose(
                face,
                pose,
                HeadBoxFusionConfig(min_consistent_iou=0.100001),
            )
        )

    def test_association_accepts_center_distance_alone_when_iou_fails(self):
        face = make_head_candidate(
            (0.1, 0.4, 0.3, 0.6),
            source_index=0,
            confidence=0.9,
            state=HeadPerceptionState.FACE_ONLY,
            face_bbox=(0.1, 0.4, 0.3, 0.6),
        )
        pose = make_head_candidate(
            (0.31, 0.4, 0.51, 0.6),
            source_index=1,
            confidence=0.8,
            state=HeadPerceptionState.POSE_ONLY,
        )

        self.assertTrue(associate_face_pose(face, pose))
        self.assertFalse(
            associate_face_pose(
                face,
                pose,
                HeadBoxFusionConfig(max_center_distance_diagonal_ratio=0.74),
            )
        )

    def test_association_rejects_boxes_outside_both_gates(self):
        faces = build_head_candidates(
            faces=(make_face((0.05, 0.05, 0.15, 0.15)),),
            poses=(),
            max_heads=1,
        )
        pose = build_pose_head_candidate(make_pose_head_at(0.8, 0.8))

        self.assertFalse(associate_face_pose(faces[0], pose))

    def test_partially_overlapping_face_and_pose_fuse_to_exact_union(self):
        face = make_head_candidate(
            (0.2, 0.3, 0.6, 0.7),
            source_index=0,
            confidence=0.8,
            state=HeadPerceptionState.FACE_ONLY,
            face_bbox=(0.25, 0.35, 0.55, 0.65),
        )
        pose = make_head_candidate(
            (0.4, 0.1, 0.8, 0.6),
            source_index=7,
            confidence=0.6,
            state=HeadPerceptionState.POSE_ONLY,
        )

        candidate = fuse_head_candidates(face, pose)

        self.assertEqual(candidate.state, HeadPerceptionState.FACE_POSE)
        self.assertBBoxAlmostEqual(candidate.head_bbox, (0.2, 0.1, 0.8, 0.7))
        self.assertAlmostEqual(candidate.confidence, 0.7)

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

    def test_finite_out_of_range_face_confidences_are_clipped(self):
        candidates = build_head_candidates(
            faces=(
                make_face((0.1, 0.2, 0.2, 0.3), confidence=1.5),
                make_face((0.7, 0.2, 0.8, 0.3), confidence=-0.5),
            ),
            poses=(),
            max_heads=2,
        )

        self.assertEqual(tuple(candidate.confidence for candidate in candidates), (1.0, 0.0))

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

    def test_ten_person_association_and_tie_breaking_survive_pose_reordering(self):
        locations = (
            (0.15, 0.15),
            (0.15, 0.15),
            (0.50, 0.15),
            (0.85, 0.15),
            (0.15, 0.50),
            (0.50, 0.50),
            (0.85, 0.50),
            (0.15, 0.85),
            (0.50, 0.85),
            (0.85, 0.85),
        )
        faces = tuple(
            make_face(
                (x - 0.025, y - 0.025, x + 0.025, y + 0.025),
                confidence=0.9,
            )
            for x, y in locations
        )
        pose_indices = (0, 9, 1, 2, 3, 4, 5, 6, 7, 8)
        poses = tuple(
            make_pose_head_at(
                x,
                y,
                quality=0.8,
                pose_index=pose_index,
                marker=float(pose_index),
            )
            for (x, y), pose_index in zip(locations, pose_indices)
        )

        aligned = build_head_candidates(faces=faces, poses=poses, max_heads=10)
        reordered = build_head_candidates(
            faces=faces,
            poses=tuple(reversed(poses)),
            max_heads=10,
        )

        self.assertEqual(aligned, reordered)
        self.assertEqual(len(aligned), 10)
        self.assertEqual(
            tuple(candidate.state for candidate in aligned),
            (HeadPerceptionState.FACE_POSE,) * 10,
        )
        self.assertEqual(tuple(candidate.source_index for candidate in aligned), tuple(range(10)))
        self.assertEqual(
            tuple(candidate.pose_head_landmarks[0].z for candidate in aligned),
            tuple(float(index) for index in pose_indices),
        )
        for candidate, (x, y) in zip(aligned, locations):
            self.assertBBoxAlmostEqual(
                candidate.face_bbox,
                (x - 0.025, y - 0.025, x + 0.025, y + 0.025),
            )
            self.assertBBoxAlmostEqual(
                candidate.head_bbox,
                (x - 0.035, y - 0.048, x + 0.035, y + 0.032),
            )


if __name__ == "__main__":
    unittest.main()
