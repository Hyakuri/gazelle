from dataclasses import replace
import unittest

from gazelle.runtime.contracts import GazePrediction, GazeStatus, HeadObservation
from gazelle.runtime.perception.contracts import (
    HeadFrameResult,
    HeadPerception,
    HeadPerceptionState,
    HeadViewState,
    ReferenceRay2D,
    ReferenceRayProjectionStatus,
    ReferenceRaySource,
)
from gazelle.runtime.perception.gaze_policy import (
    annotate_gaze_eligibility,
    apply_prediction_gaze_status,
    arbitrate_perceptions,
    select_gazelle_heads,
)


def face_ray(confidence=0.9):
    return ReferenceRay2D(
        source=ReferenceRaySource.FACE_POSE,
        origin=(0.4, 0.3),
        direction=(1.0, 0.0),
        endpoint=(0.8, 0.3),
        confidence=confidence,
        projection_status=ReferenceRayProjectionStatus.AVAILABLE,
    )


def perception(
    person_id,
    *,
    state=HeadPerceptionState.FACE_ONLY,
    view_state=HeadViewState.PROFILE,
    observed=True,
    confidence=0.9,
    ray=None,
    missed_ms=0.0,
):
    return HeadPerception(
        person_id=person_id,
        head_bbox=(0.1, 0.2, 0.4, 0.6),
        face_bbox=(0.15, 0.25, 0.35, 0.50) if observed else None,
        confidence=confidence,
        state=state,
        view_state=view_state,
        observed=observed,
        missed_ms=missed_ms,
        face_pose_reference_ray=ray,
    )


class GazePolicyTest(unittest.TestCase):
    def test_tracked_only_is_continuity_only(self):
        item = perception(
            3,
            state=HeadPerceptionState.TRACKED_ONLY,
            view_state=HeadViewState.UNKNOWN,
            observed=False,
            ray=None,
            missed_ms=100.0,
        )

        annotated = annotate_gaze_eligibility((item,))[0]

        self.assertFalse(annotated.gaze_eligible)
        self.assertEqual(annotated.gaze_status, GazeStatus.TRACKED_NO_GAZE)

    def test_pose_only_and_back_view_are_not_sent_to_gazelle(self):
        items = (
            perception(
                1,
                state=HeadPerceptionState.POSE_ONLY,
                view_state=HeadViewState.BACK_OR_OCCLUDED,
                ray=None,
            ),
            perception(
                2,
                state=HeadPerceptionState.FACE_ONLY,
                view_state=HeadViewState.BACK_OR_OCCLUDED,
                ray=face_ray(),
            ),
        )

        annotated = annotate_gaze_eligibility(items)

        self.assertTrue(all(not item.gaze_eligible for item in annotated))
        self.assertEqual(
            tuple(item.gaze_status for item in annotated),
            (GazeStatus.UNAVAILABLE_OCCLUDED, GazeStatus.UNAVAILABLE_OCCLUDED),
        )

    def test_current_face_with_reference_evidence_is_eligible(self):
        annotated = annotate_gaze_eligibility((perception(4, ray=face_ray()),))[0]

        self.assertTrue(annotated.gaze_eligible)
        self.assertIsNone(annotated.gaze_status)

    def test_face_without_reference_evidence_is_rejected_low_quality(self):
        annotated = annotate_gaze_eligibility((perception(4, ray=None),))[0]

        self.assertFalse(annotated.gaze_eligible)
        self.assertEqual(annotated.gaze_status, GazeStatus.REJECTED_LOW_QUALITY)

    def test_face_below_minimum_quality_is_rejected_low_quality(self):
        annotated = annotate_gaze_eligibility(
            (
                perception(4, confidence=0.9, ray=face_ray(confidence=0.49)),
                perception(5, confidence=0.49, ray=face_ray(confidence=0.9)),
            )
        )

        self.assertTrue(all(not item.gaze_eligible for item in annotated))
        self.assertEqual(
            tuple(item.gaze_status for item in annotated),
            (
                GazeStatus.REJECTED_LOW_QUALITY,
                GazeStatus.REJECTED_LOW_QUALITY,
            ),
        )

    def test_single_person_arbitration_prefers_current_observation(self):
        stale = perception(
            1,
            state=HeadPerceptionState.TRACKED_ONLY,
            view_state=HeadViewState.UNKNOWN,
            observed=False,
            confidence=0.99,
            missed_ms=100.0,
        )
        current = perception(9, confidence=0.60, ray=face_ray())

        selected = arbitrate_perceptions((stale, current), max_heads=1)

        self.assertEqual(tuple(item.person_id for item in selected), (9,))

    def test_select_gazelle_heads_preserves_head_order_for_eligible_people(self):
        perceptions = annotate_gaze_eligibility(
            (
                perception(1, ray=face_ray()),
                perception(
                    2,
                    state=HeadPerceptionState.TRACKED_ONLY,
                    view_state=HeadViewState.UNKNOWN,
                    observed=False,
                ),
                perception(3, ray=face_ray()),
            )
        )
        result = HeadFrameResult(
            heads=tuple(
                HeadObservation(item.person_id, item.head_bbox, item.confidence)
                for item in perceptions
            ),
            perceptions=perceptions,
        )

        selected = select_gazelle_heads(result)

        self.assertEqual(tuple(head.person_id for head in selected), (1, 3))

    def test_select_gazelle_heads_rechecks_unannotated_perception_state(self):
        perceptions = (
            perception(
                1,
                state=HeadPerceptionState.TRACKED_ONLY,
                view_state=HeadViewState.UNKNOWN,
                observed=False,
                ray=None,
            ),
            perception(
                2,
                state=HeadPerceptionState.POSE_ONLY,
                view_state=HeadViewState.BACK_OR_OCCLUDED,
                ray=None,
            ),
            perception(3, ray=face_ray()),
        )
        result = HeadFrameResult(
            heads=tuple(
                HeadObservation(item.person_id, item.head_bbox, item.confidence)
                for item in perceptions
            ),
            perceptions=perceptions,
        )

        selected = select_gazelle_heads(result)

        self.assertEqual(tuple(head.person_id for head in selected), (3,))

    def test_inout_threshold_assigns_final_gaze_status(self):
        predictions = (
            GazePrediction(1, (0.1, 0.2, 0.4, 0.6), inout_score=0.7),
            GazePrediction(2, (0.1, 0.2, 0.4, 0.6), inout_score=0.3),
            GazePrediction(3, (0.1, 0.2, 0.4, 0.6), inout_score=None),
        )

        classified = apply_prediction_gaze_status(predictions, inout_threshold=0.5)

        self.assertEqual(
            tuple(item.gaze_status for item in classified),
            (GazeStatus.VALID, GazeStatus.OUT_OF_FRAME, GazeStatus.VALID),
        )
        self.assertEqual(
            replace(classified[1], gaze_status=GazeStatus.VALID),
            predictions[1],
        )


if __name__ == "__main__":
    unittest.main()
