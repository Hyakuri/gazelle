import math
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from gazelle.runtime.perception.contracts import (
    HeadCandidate,
    HeadPerceptionState,
    HeadViewState,
)
from gazelle.runtime.perception.tracking import (
    ByteTrackHeadTracker,
    ShortOcclusionBridge,
    TrackedHeadCandidate,
)


def candidate(index=0, confidence=0.8, bbox=(0.1, 0.2, 0.3, 0.4)):
    return HeadCandidate(
        source_index=index,
        head_bbox=bbox,
        face_bbox=bbox,
        confidence=confidence,
        state=HeadPerceptionState.FACE_ONLY,
        view_state=HeadViewState.FRONTAL,
    )


def tracked_candidate(person_id, confidence=0.8, track_age_frames=4):
    return TrackedHeadCandidate(
        person_id=person_id,
        candidate=candidate(person_id, confidence=confidence),
        track_age_frames=track_age_frames,
    )


class FakeDetections:
    def __init__(self, xyxy, confidence, class_id, data=None, tracker_id=None):
        self.xyxy = xyxy
        self.confidence = confidence
        self.class_id = class_id
        self.data = {} if data is None else data
        self.tracker_id = tracker_id

    @classmethod
    def empty(cls):
        return cls(
            xyxy=np.empty((0, 4), dtype=np.float32),
            confidence=np.empty((0,), dtype=np.float32),
            class_id=np.empty((0,), dtype=np.int32),
            data={"candidate_index": np.empty((0,), dtype=np.int32)},
            tracker_id=np.empty((0,), dtype=np.int32),
        )


FAKE_SUPERVISION = SimpleNamespace(Detections=FakeDetections)


class FakeTracker:
    def __init__(self, output_builder=None):
        self.output_builder = output_builder or self._echo
        self.updates = []
        self.reset_calls = 0
        self.close_calls = 0

    @staticmethod
    def _echo(detections):
        count = len(detections.xyxy)
        return FakeDetections(
            xyxy=detections.xyxy,
            confidence=detections.confidence,
            class_id=detections.class_id,
            data={"candidate_index": detections.data["candidate_index"]},
            tracker_id=np.arange(10, 10 + count, dtype=np.int32),
        )

    def update(self, detections):
        self.updates.append(detections)
        return self.output_builder(detections)

    def reset(self):
        self.reset_calls += 1

    def close(self):
        self.close_calls += 1


class RecordingFactory:
    def __init__(self, tracker):
        self.tracker = tracker
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.tracker


def make_tracker(fake_tracker=None, source_fps=24.0):
    fake_tracker = fake_tracker or FakeTracker()
    factory = RecordingFactory(fake_tracker)
    adapter = ByteTrackHeadTracker(
        source_fps=source_fps,
        tracker_factory=factory,
        supervision_module=FAKE_SUPERVISION,
    )
    return adapter, fake_tracker, factory


class ByteTrackHeadTrackerTest(unittest.TestCase):
    def test_import_does_not_import_optional_tracker_packages(self):
        code = (
            "import sys; "
            "import gazelle.runtime.perception.tracking; "
            "assert 'trackers' not in sys.modules; "
            "assert 'supervision' not in sys.modules"
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_constructs_tracker_with_exact_configuration_and_pixel_detections(self):
        adapter, fake, factory = make_tracker(source_fps=29.97)
        first = candidate(0, confidence=0.75, bbox=(0.1, 0.2, 0.4, 0.6))
        second = candidate(1, confidence=0.55, bbox=(0.5, 0.1, 0.9, 0.3))

        result = adapter.update(
            (first, second),
            frame_index=5,
            timestamp_ms=100.0,
            image_width=200,
            image_height=100,
        )

        self.assertEqual(
            factory.calls,
            [{
                "track_activation_threshold": 0.50,
                "high_conf_det_threshold": 0.50,
                "minimum_iou_threshold": 0.20,
                "minimum_consecutive_frames": 1,
                "lost_track_buffer": 15,
                "frame_rate": 29.97,
            }],
        )
        detections = fake.updates[0]
        np.testing.assert_array_equal(
            detections.xyxy,
            np.asarray(((20.0, 20.0, 80.0, 60.0), (100.0, 10.0, 180.0, 30.0)), dtype=np.float32),
        )
        np.testing.assert_array_equal(
            detections.confidence,
            np.asarray((0.75, 0.55), dtype=np.float32),
        )
        np.testing.assert_array_equal(detections.class_id, np.zeros(2, dtype=np.int32))
        np.testing.assert_array_equal(
            detections.data["candidate_index"],
            np.arange(2, dtype=np.int32),
        )
        self.assertEqual(tuple(item.person_id for item in result), (10, 11))
        self.assertEqual(tuple(item.candidate for item in result), (first, second))
        self.assertEqual(tuple(item.track_age_frames for item in result), (1, 1))

    def test_maps_reordered_tracker_output_through_candidate_index(self):
        def reversed_output(detections):
            return FakeDetections(
                xyxy=detections.xyxy[::-1],
                confidence=detections.confidence[::-1],
                class_id=detections.class_id[::-1],
                data={"candidate_index": np.asarray((1, 0), dtype=np.int32)},
                tracker_id=np.asarray((41, 7), dtype=np.int32),
            )

        adapter, _, _ = make_tracker(FakeTracker(reversed_output))
        candidates = (candidate(0), candidate(1))

        result = adapter.update(
            candidates,
            frame_index=0,
            timestamp_ms=0.0,
            image_width=640,
            image_height=480,
        )

        self.assertEqual(tuple(item.person_id for item in result), (7, 41))
        self.assertEqual(tuple(item.candidate for item in result), candidates)

    def test_rejects_invalid_tracker_ids_and_candidate_indexes(self):
        bad_outputs = (
            FakeDetections(
                xyxy=np.empty((1, 4), dtype=np.float32),
                confidence=np.ones(1, dtype=np.float32),
                class_id=np.zeros(1, dtype=np.int32),
                data={"candidate_index": np.asarray((0,), dtype=np.int32)},
                tracker_id=np.asarray((-1,), dtype=np.int32),
            ),
            FakeDetections(
                xyxy=np.empty((1, 4), dtype=np.float32),
                confidence=np.ones(1, dtype=np.float32),
                class_id=np.zeros(1, dtype=np.int32),
                data={"candidate_index": np.asarray((2,), dtype=np.int32)},
                tracker_id=np.asarray((1,), dtype=np.int32),
            ),
        )
        for output in bad_outputs:
            with self.subTest(output=output):
                adapter, _, _ = make_tracker(FakeTracker(lambda detections, output=output: output))
                with self.assertRaisesRegex(RuntimeError, "tracker output"):
                    adapter.update(
                        (candidate(),),
                        frame_index=0,
                        timestamp_ms=0.0,
                        image_width=100,
                        image_height=100,
                    )

    def test_updates_tracker_with_empty_detections(self):
        adapter, fake, _ = make_tracker()

        result = adapter.update(
            (),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=640,
            image_height=480,
        )

        self.assertEqual(result, ())
        self.assertEqual(len(fake.updates), 1)
        self.assertEqual(fake.updates[0].xyxy.shape, (0, 4))

    def test_track_age_includes_missing_frame_gap(self):
        adapter, _, _ = make_tracker()
        head = (candidate(),)
        adapter.update(head, frame_index=4, timestamp_ms=100.0, image_width=100, image_height=100)
        adapter.update((), frame_index=5, timestamp_ms=140.0, image_width=100, image_height=100)

        result = adapter.update(
            head,
            frame_index=6,
            timestamp_ms=180.0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(result[0].track_age_frames, 3)

    def test_reset_clears_video_state_and_close_is_idempotent(self):
        adapter, fake, factory = make_tracker()
        head = (candidate(),)
        adapter.update(head, frame_index=9, timestamp_ms=900.0, image_width=100, image_height=100)

        adapter.reset()
        reset_result = adapter.update(
            head,
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )
        adapter.close()
        adapter.close()

        self.assertEqual(fake.reset_calls, 1)
        self.assertEqual(fake.close_calls, 1)
        self.assertEqual(len(factory.calls), 1)
        self.assertEqual(reset_result[0].track_age_frames, 1)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            adapter.update(head, frame_index=1, timestamp_ms=1.0, image_width=100, image_height=100)

    def test_rejects_invalid_and_nonmonotonic_timestamps(self):
        adapter, _, _ = make_tracker()
        kwargs = dict(candidates=(), frame_index=0, image_width=100, image_height=100)
        for value in (True, float("nan"), float("inf"), -1.0):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "timestamp_ms"):
                    adapter.update(timestamp_ms=value, **kwargs)

        adapter.update(timestamp_ms=2.0, **kwargs)
        with self.assertRaisesRegex(ValueError, "monotonic"):
            adapter.update(timestamp_ms=1.0, **{**kwargs, "frame_index": 1})

    def test_lazy_dependency_errors_name_the_missing_package(self):
        missing_trackers = ByteTrackHeadTracker(
            source_fps=30.0,
            supervision_module=FAKE_SUPERVISION,
        )
        with patch("importlib.import_module", side_effect=ModuleNotFoundError("trackers")):
            with self.assertRaisesRegex(RuntimeError, "trackers"):
                missing_trackers.update(
                    (), frame_index=0, timestamp_ms=0.0, image_width=10, image_height=10
                )

        factory = RecordingFactory(FakeTracker())
        missing_supervision = ByteTrackHeadTracker(source_fps=30.0, tracker_factory=factory)
        with patch("importlib.import_module", side_effect=ModuleNotFoundError("supervision")):
            with self.assertRaisesRegex(RuntimeError, "supervision"):
                missing_supervision.update(
                    (), frame_index=0, timestamp_ms=0.0, image_width=10, image_height=10
                )


class ShortOcclusionBridgeTest(unittest.TestCase):
    def test_bridge_emits_tracked_only_for_500_ms(self):
        bridge = ShortOcclusionBridge(max_gap_ms=500.0)
        bridge.update((tracked_candidate(3, confidence=0.8),), timestamp_ms=0.0)

        missing = bridge.update((), timestamp_ms=500.0)

        self.assertEqual(missing[0].person_id, 3)
        self.assertEqual(missing[0].state, HeadPerceptionState.TRACKED_ONLY)
        self.assertFalse(missing[0].observed)
        self.assertEqual(missing[0].head_bbox, candidate(3).head_bbox)
        self.assertIsNone(missing[0].face_bbox)
        self.assertEqual(missing[0].view_state, HeadViewState.UNKNOWN)
        self.assertAlmostEqual(missing[0].confidence, 0.8 * math.exp(-1.0))
        self.assertEqual(missing[0].missed_frames, 1)
        self.assertEqual(missing[0].missed_ms, 500.0)

    def test_bridge_expires_after_500_ms(self):
        bridge = ShortOcclusionBridge(max_gap_ms=500.0)
        bridge.update((tracked_candidate(3),), timestamp_ms=0.0)

        self.assertEqual(bridge.update((), timestamp_ms=500.1), ())

    def test_decay_uses_last_observed_confidence_and_never_increases(self):
        bridge = ShortOcclusionBridge(max_gap_ms=500.0)
        bridge.update((tracked_candidate(3, confidence=0.8),), timestamp_ms=100.0)

        first = bridge.update((), timestamp_ms=200.0)[0]
        second = bridge.update((), timestamp_ms=300.0)[0]

        self.assertAlmostEqual(first.confidence, 0.8 * math.exp(-100.0 / 500.0))
        self.assertAlmostEqual(second.confidence, 0.8 * math.exp(-200.0 / 500.0))
        self.assertLessEqual(second.confidence, first.confidence)

    def test_bridge_stops_below_minimum_confidence_and_deletes_state(self):
        bridge = ShortOcclusionBridge(max_gap_ms=500.0, min_confidence=0.15)
        bridge.update((tracked_candidate(3, confidence=0.15),), timestamp_ms=0.0)

        self.assertEqual(bridge.update((), timestamp_ms=0.1), ())
        self.assertEqual(bridge.update((), timestamp_ms=0.2), ())

    def test_observed_candidates_are_copied_to_perceptions(self):
        bridge = ShortOcclusionBridge()
        tracked = tracked_candidate(8, confidence=0.9, track_age_frames=6)

        result = bridge.update((tracked,), timestamp_ms=10.0)

        perception = result[0]
        self.assertEqual(perception.person_id, 8)
        self.assertEqual(perception.head_bbox, tracked.candidate.head_bbox)
        self.assertEqual(perception.face_bbox, tracked.candidate.face_bbox)
        self.assertEqual(perception.state, tracked.candidate.state)
        self.assertTrue(perception.observed)
        self.assertEqual(perception.track_age_frames, 6)
        self.assertEqual(perception.missed_frames, 0)
        self.assertEqual(perception.missed_ms, 0.0)

    def test_bridge_state_contains_no_image_arrays(self):
        bridge = ShortOcclusionBridge()
        bridge.update((tracked_candidate(3),), timestamp_ms=0.0)

        def contains_array(value):
            if isinstance(value, np.ndarray):
                return True
            if isinstance(value, dict):
                return any(contains_array(item) for item in value.values())
            if isinstance(value, (tuple, list, set)):
                return any(contains_array(item) for item in value)
            if hasattr(value, "__dict__"):
                return contains_array(vars(value))
            return False

        self.assertFalse(contains_array(vars(bridge)))

    def test_rejects_invalid_and_nonmonotonic_timestamps(self):
        for value in (True, float("nan"), float("inf"), -1.0):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "timestamp_ms"):
                    ShortOcclusionBridge().update((), timestamp_ms=value)

        bridge = ShortOcclusionBridge()
        bridge.update((), timestamp_ms=2.0)
        with self.assertRaisesRegex(ValueError, "monotonic"):
            bridge.update((), timestamp_ms=1.0)

    def test_reset_clears_state_and_allows_new_video_timestamps(self):
        bridge = ShortOcclusionBridge()
        bridge.update((tracked_candidate(3),), timestamp_ms=1000.0)

        bridge.reset()

        self.assertEqual(bridge.update((), timestamp_ms=0.0), ())


if __name__ == "__main__":
    unittest.main()
