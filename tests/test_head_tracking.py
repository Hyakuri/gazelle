import math
import pickle
import subprocess
import sys
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from gazelle.runtime.perception.contracts import (
    HeadCandidate,
    HeadPerceptionState,
    HeadPoseAngles,
    HeadViewState,
    NormalizedLandmark,
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


def tracked_output(detections, tracker_ids, candidate_indexes=None):
    if candidate_indexes is None:
        candidate_indexes = tuple(range(len(tracker_ids)))
    indexes = np.asarray(candidate_indexes, dtype=np.int32)
    return FakeDetections(
        xyxy=detections.xyxy[indexes],
        confidence=detections.confidence[indexes],
        class_id=detections.class_id[indexes],
        data={"candidate_index": indexes},
        tracker_id=np.asarray(tracker_ids, dtype=object),
    )


class FakeTracker:
    def __init__(self, output_builder=None, *, reset_error=None, close_error=None):
        self.output_builder = output_builder or self._echo
        self.reset_error = reset_error
        self.close_error = close_error
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
        if self.reset_error is not None:
            raise self.reset_error

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class CloseOnlyTracker:
    def __init__(self, *, close_error=None):
        self.close_error = close_error
        self.updates = []
        self.close_calls = 0

    def update(self, detections):
        self.updates.append(detections)
        return FakeTracker._echo(detections)

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class RecordingFactory:
    def __init__(self, tracker):
        self.tracker = tracker
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.tracker


class SequencedFactory:
    def __init__(self, *trackers):
        self.trackers = trackers
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.trackers[len(self.calls) - 1]


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
    def test_rejects_invalid_source_fps(self):
        for value in (
            True,
            False,
            0,
            -1,
            float("nan"),
            float("inf"),
            float("-inf"),
            "30",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "source_fps"):
                    ByteTrackHeadTracker(
                        source_fps=value,
                        tracker_factory=RecordingFactory(FakeTracker()),
                        supervision_module=FAKE_SUPERVISION,
                    )

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
        self.assertEqual(tuple(item.person_id for item in result), (0, 1))
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

        self.assertEqual(tuple(item.person_id for item in result), (0, 1))
        self.assertEqual(tuple(item.candidate for item in result), candidates)

    def test_filters_untracked_sentinel_and_returns_stable_candidates(self):
        def mixed_output(detections):
            return FakeDetections(
                xyxy=detections.xyxy[[1, 3, 2, 0]],
                confidence=detections.confidence[[1, 3, 2, 0]],
                class_id=detections.class_id[[1, 3, 2, 0]],
                data={
                    "candidate_index": np.asarray((1, 3, 2, 0), dtype=np.int32)
                },
                tracker_id=np.asarray((-1, -1, 21, 7), dtype=np.int32),
            )

        adapter, _, _ = make_tracker(FakeTracker(mixed_output))
        candidates = (candidate(0), candidate(1), candidate(2), candidate(3))

        result = adapter.update(
            candidates,
            frame_index=0,
            timestamp_ms=0.0,
            image_width=640,
            image_height=480,
        )

        self.assertEqual(tuple(item.person_id for item in result), (0, 1))
        self.assertEqual(
            tuple(item.candidate for item in result),
            (candidates[0], candidates[2]),
        )
        self.assertTrue(all(item.track_age_frames >= 1 for item in result))

    def test_rejects_invalid_tracker_ids_and_candidate_indexes(self):
        bad_values = (
            (-2, 0),
            (True, 0),
            (1.5, 0),
            (float("nan"), 0),
            (-1, -1),
            (-1, 2),
            (1, -1),
            (1, True),
            (1, 0.5),
            (1, 2),
        )
        for tracker_id, candidate_index in bad_values:
            output = FakeDetections(
                xyxy=np.empty((1, 4), dtype=np.float32),
                confidence=np.ones(1, dtype=np.float32),
                class_id=np.zeros(1, dtype=np.int32),
                data={"candidate_index": np.asarray((candidate_index,))},
                tracker_id=np.asarray((tracker_id,)),
            )
            with self.subTest(tracker_id=tracker_id, candidate_index=candidate_index):
                adapter, _, _ = make_tracker(FakeTracker(lambda detections, output=output: output))
                with self.assertRaisesRegex(RuntimeError, "tracker output"):
                    adapter.update(
                        (candidate(),),
                        frame_index=0,
                        timestamp_ms=0.0,
                        image_width=100,
                        image_height=100,
                    )

    def test_rejects_duplicate_or_missing_tracker_mapping_data(self):
        bad_outputs = (
            FakeDetections(
                xyxy=np.empty((2, 4), dtype=np.float32),
                confidence=np.ones(2, dtype=np.float32),
                class_id=np.zeros(2, dtype=np.int32),
                data={"candidate_index": np.asarray((0, 1), dtype=np.int32)},
                tracker_id=np.asarray((5, 5), dtype=np.int32),
            ),
            FakeDetections(
                xyxy=np.empty((2, 4), dtype=np.float32),
                confidence=np.ones(2, dtype=np.float32),
                class_id=np.zeros(2, dtype=np.int32),
                data={"candidate_index": np.asarray((0, 0), dtype=np.int32)},
                tracker_id=np.asarray((5, 6), dtype=np.int32),
            ),
            FakeDetections(
                xyxy=np.empty((1, 4), dtype=np.float32),
                confidence=np.ones(1, dtype=np.float32),
                class_id=np.zeros(1, dtype=np.int32),
                data={},
                tracker_id=np.asarray((5,), dtype=np.int32),
            ),
            FakeDetections(
                xyxy=np.empty((2, 4), dtype=np.float32),
                confidence=np.ones(2, dtype=np.float32),
                class_id=np.zeros(2, dtype=np.int32),
                data={"candidate_index": np.asarray((0,), dtype=np.int32)},
                tracker_id=np.asarray((5, 6), dtype=np.int32),
            ),
        )
        for output in bad_outputs:
            with self.subTest(output=output):
                adapter, _, _ = make_tracker(FakeTracker(lambda detections, output=output: output))
                with self.assertRaisesRegex(RuntimeError, "tracker output"):
                    adapter.update(
                        (candidate(0), candidate(1)),
                        frame_index=0,
                        timestamp_ms=0.0,
                        image_width=100,
                        image_height=100,
                    )

    def test_malformed_output_detaches_backend_and_discards_partial_ages(self):
        malformed = FakeDetections(
            xyxy=np.empty((2, 4), dtype=np.float32),
            confidence=np.ones(2, dtype=np.float32),
            class_id=np.zeros(2, dtype=np.int32),
            data={"candidate_index": np.asarray((0, 1), dtype=np.int32)},
            tracker_id=np.asarray((5, True), dtype=object),
        )
        bad_tracker = FakeTracker(lambda detections: malformed)
        fresh_tracker = FakeTracker()
        factory = SequencedFactory(bad_tracker, fresh_tracker)
        adapter = ByteTrackHeadTracker(
            source_fps=30.0,
            tracker_factory=factory,
            supervision_module=FAKE_SUPERVISION,
        )

        with self.assertRaisesRegex(RuntimeError, "tracker output"):
            adapter.update(
                (candidate(0), candidate(1)),
                frame_index=7,
                timestamp_ms=100.0,
                image_width=100,
                image_height=100,
            )

        result = adapter.update(
            (candidate(0),),
            frame_index=8,
            timestamp_ms=50.0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(len(factory.calls), 2)
        self.assertEqual(bad_tracker.close_calls, 1)
        self.assertEqual(result[0].person_id, 0)
        self.assertEqual(result[0].track_age_frames, 1)

    def test_public_id_is_stable_within_backend_generation(self):
        raw_id = 10**100
        tracker = FakeTracker(
            lambda detections: tracked_output(detections, (raw_id,))
        )
        adapter, _, _ = make_tracker(tracker)

        first = adapter.update(
            (candidate(),),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )[0]
        second = adapter.update(
            (candidate(),),
            frame_index=1,
            timestamp_ms=1.0,
            image_width=100,
            image_height=100,
        )[0]

        self.assertEqual(first.person_id, second.person_id)
        self.assertEqual(first.person_id, 0)
        self.assertEqual((first.track_age_frames, second.track_age_frames), (1, 2))

    def test_same_raw_id_after_backend_retirement_gets_new_public_id(self):
        raw_id = 91
        malformed = FakeDetections(
            xyxy=np.empty((2, 4), dtype=np.float32),
            confidence=np.ones(2, dtype=np.float32),
            class_id=np.zeros(2, dtype=np.int32),
            data={"candidate_index": np.asarray((0, 1), dtype=np.int32)},
            tracker_id=np.asarray((raw_id, True), dtype=object),
        )
        old_tracker = None

        def old_output(detections):
            if len(old_tracker.updates) == 1:
                return tracked_output(detections, (raw_id,))
            return malformed

        old_tracker = FakeTracker(old_output)
        fresh_tracker = FakeTracker(
            lambda detections: tracked_output(detections, (raw_id,))
        )
        factory = SequencedFactory(old_tracker, fresh_tracker)
        adapter = ByteTrackHeadTracker(
            source_fps=30.0,
            tracker_factory=factory,
            supervision_module=FAKE_SUPERVISION,
        )
        old = adapter.update(
            (candidate(),),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )[0]

        with self.assertRaisesRegex(RuntimeError, "tracker output"):
            adapter.update(
                (candidate(0), candidate(1)),
                frame_index=1,
                timestamp_ms=1.0,
                image_width=100,
                image_height=100,
            )

        fresh = adapter.update(
            (candidate(),),
            frame_index=2,
            timestamp_ms=2.0,
            image_width=100,
            image_height=100,
        )[0]
        self.assertNotEqual(fresh.person_id, old.person_id)
        self.assertEqual(old.person_id, 0)
        self.assertEqual(fresh.person_id, 1)
        self.assertEqual(fresh.track_age_frames, 1)

    def test_distinct_arbitrarily_large_raw_ids_never_collide(self):
        raw_ids = (10**100, 10**200)
        adapter, _, _ = make_tracker(
            FakeTracker(lambda detections: tracked_output(detections, raw_ids))
        )

        result = adapter.update(
            (candidate(0), candidate(1)),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(tuple(item.person_id for item in result), (0, 1))
        self.assertEqual(len({item.person_id for item in result}), 2)

    def test_reset_starts_clean_public_id_namespace_for_new_video(self):
        def output(detections):
            raw_ids = (111, 222) if len(detections.xyxy) == 2 else (222,)
            return tracked_output(detections, raw_ids)

        adapter, _, _ = make_tracker(FakeTracker(output))
        before_reset = adapter.update(
            (candidate(0), candidate(1)),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )

        adapter.reset()

        after_reset = adapter.update(
            (candidate(),),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )[0]
        self.assertEqual(tuple(item.person_id for item in before_reset), (0, 1))
        self.assertEqual(after_reset.person_id, 0)
        self.assertEqual(after_reset.track_age_frames, 1)

    def test_untracked_sentinel_never_consumes_public_id(self):
        tracker = None

        def output(detections):
            raw_id = -1 if len(tracker.updates) == 1 else 77
            return tracked_output(detections, (raw_id,))

        tracker = FakeTracker(output)
        adapter, _, _ = make_tracker(tracker)

        untracked = adapter.update(
            (candidate(),),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )
        tracked = adapter.update(
            (candidate(),),
            frame_index=1,
            timestamp_ms=1.0,
            image_width=100,
            image_height=100,
        )[0]

        self.assertEqual(untracked, ())
        self.assertEqual(tracked.person_id, 0)

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
        detections = fake.updates[0]
        self.assertEqual(detections.xyxy.shape, (0, 4))
        self.assertEqual(detections.xyxy.dtype, np.float32)
        self.assertEqual(detections.confidence.shape, (0,))
        self.assertEqual(detections.confidence.dtype, np.float32)
        self.assertEqual(detections.class_id.shape, (0,))
        self.assertEqual(detections.class_id.dtype, np.int32)
        self.assertEqual(set(detections.data), {"candidate_index"})
        self.assertEqual(detections.data["candidate_index"].shape, (0,))
        self.assertEqual(detections.data["candidate_index"].dtype, np.int32)

    def test_empty_candidates_reject_nonempty_output_and_recreate_backend(self):
        malformed_outputs = (
            SimpleNamespace(xyxy=np.ones((1, 4), dtype=np.float32)),
            SimpleNamespace(
                xyxy=np.empty((0, 4), dtype=np.float32),
                tracker_id=np.asarray((17,), dtype=np.int32),
            ),
            SimpleNamespace(
                xyxy=np.empty((0, 4), dtype=np.float32),
                confidence=np.ones((1,), dtype=np.float32),
            ),
        )
        for malformed in malformed_outputs:
            with self.subTest(malformed=malformed):
                bad_tracker = FakeTracker(lambda detections, value=malformed: value)
                fresh_tracker = FakeTracker()
                factory = SequencedFactory(bad_tracker, fresh_tracker)
                adapter = ByteTrackHeadTracker(
                    source_fps=30.0,
                    tracker_factory=factory,
                    supervision_module=FAKE_SUPERVISION,
                )

                with self.assertRaisesRegex(RuntimeError, "empty candidate"):
                    adapter.update(
                        (),
                        frame_index=7,
                        timestamp_ms=100.0,
                        image_width=100,
                        image_height=100,
                    )

                result = adapter.update(
                    (candidate(),),
                    frame_index=7,
                    timestamp_ms=50.0,
                    image_width=100,
                    image_height=100,
                )
                self.assertEqual(len(factory.calls), 2)
                self.assertEqual(bad_tracker.close_calls, 1)
                self.assertEqual(result[0].track_age_frames, 1)

    def test_empty_candidates_reject_structurally_invalid_empty_outputs(self):
        malformed_outputs = (
            None,
            object(),
            {},
            SimpleNamespace(data={}),
            SimpleNamespace(xyxy=np.empty((0, 4), dtype=np.float32)),
            SimpleNamespace(xyxy=np.empty((0,), dtype=np.float32), data={}),
            SimpleNamespace(xyxy=np.empty((0, 5), dtype=np.float32), data={}),
            SimpleNamespace(xyxy=[], data={}),
            SimpleNamespace(
                xyxy=np.empty((0, 4), dtype=np.float32),
                data=(),
            ),
        )
        for malformed in malformed_outputs:
            with self.subTest(malformed=malformed):
                bad_tracker = FakeTracker(
                    lambda detections, value=malformed: value
                )
                fresh_tracker = FakeTracker()
                factory = SequencedFactory(bad_tracker, fresh_tracker)
                adapter = ByteTrackHeadTracker(
                    source_fps=30.0,
                    tracker_factory=factory,
                    supervision_module=FAKE_SUPERVISION,
                )

                with self.assertRaisesRegex(RuntimeError, "empty candidate"):
                    adapter.update(
                        (),
                        frame_index=7,
                        timestamp_ms=100.0,
                        image_width=100,
                        image_height=100,
                    )

                result = adapter.update(
                    (candidate(),),
                    frame_index=7,
                    timestamp_ms=50.0,
                    image_width=100,
                    image_height=100,
                )
                self.assertEqual(len(factory.calls), 2)
                self.assertEqual(bad_tracker.close_calls, 1)
                self.assertEqual(result[0].track_age_frames, 1)

    def test_malformed_output_preserves_cleanup_failure_context(self):
        cleanup_error = RuntimeError("cleanup failed")
        bad_tracker = FakeTracker(
            lambda detections: None,
            close_error=cleanup_error,
        )
        fresh_tracker = FakeTracker()
        factory = SequencedFactory(bad_tracker, fresh_tracker)
        adapter = ByteTrackHeadTracker(
            source_fps=30.0,
            tracker_factory=factory,
            supervision_module=FAKE_SUPERVISION,
        )

        with self.assertRaisesRegex(RuntimeError, "empty candidate") as caught:
            adapter.update(
                (),
                frame_index=7,
                timestamp_ms=100.0,
                image_width=100,
                image_height=100,
            )

        self.assertIn(
            "cleanup failed",
            "\n".join(getattr(caught.exception, "__notes__", ())),
        )
        result = adapter.update(
            (candidate(),),
            frame_index=7,
            timestamp_ms=50.0,
            image_width=100,
            image_height=100,
        )
        self.assertEqual(len(factory.calls), 2)
        self.assertEqual(bad_tracker.close_calls, 1)
        self.assertEqual(result[0].track_age_frames, 1)

    def test_empty_candidates_accept_detections_like_output_without_optional_fields(self):
        empty_output = SimpleNamespace(
            xyxy=np.empty((0, 4), dtype=np.float32),
            data={},
        )
        adapter, fake, factory = make_tracker(FakeTracker(lambda detections: empty_output))

        result = adapter.update(
            (),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(result, ())
        self.assertEqual(len(fake.updates), 1)
        self.assertEqual(len(factory.calls), 1)

    def test_frame_index_must_increase_strictly_without_mutating_age_state(self):
        adapter, fake, _ = make_tracker()
        head = (candidate(),)
        first = adapter.update(
            head,
            frame_index=4,
            timestamp_ms=100.0,
            image_width=100,
            image_height=100,
        )
        self.assertEqual(first[0].track_age_frames, 1)

        for frame_index in (4, 3, True, 4.5, -1):
            with self.subTest(frame_index=frame_index):
                with self.assertRaisesRegex(ValueError, "frame_index"):
                    adapter.update(
                        (),
                        frame_index=frame_index,
                        timestamp_ms=101.0,
                        image_width=100,
                        image_height=100,
                    )

        result = adapter.update(
            head,
            frame_index=5,
            timestamp_ms=101.0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(len(fake.updates), 2)
        self.assertEqual(result[0].track_age_frames, 2)
        self.assertGreaterEqual(result[0].track_age_frames, 1)

    def test_empty_frames_commit_frame_index_and_reset_clears_it(self):
        adapter, _, _ = make_tracker()
        adapter.update(
            (), frame_index=8, timestamp_ms=80.0, image_width=100, image_height=100
        )
        with self.assertRaisesRegex(ValueError, "frame_index"):
            adapter.update(
                (), frame_index=8, timestamp_ms=81.0, image_width=100, image_height=100
            )

        adapter.reset()

        self.assertEqual(
            adapter.update(
                (), frame_index=0, timestamp_ms=0.0, image_width=100, image_height=100
            ),
            (),
        )

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

    def test_reset_exception_detaches_backend_and_allows_fresh_update(self):
        failing = FakeTracker(reset_error=RuntimeError("reset failed"))
        fresh = FakeTracker()
        factory = SequencedFactory(failing, fresh)
        adapter = ByteTrackHeadTracker(
            source_fps=30.0,
            tracker_factory=factory,
            supervision_module=FAKE_SUPERVISION,
        )
        adapter.update(
            (candidate(),),
            frame_index=9,
            timestamp_ms=900.0,
            image_width=100,
            image_height=100,
        )

        with self.assertRaisesRegex(RuntimeError, "reset failed"):
            adapter.reset()

        result = adapter.update(
            (candidate(),),
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )
        self.assertEqual(failing.reset_calls, 1)
        self.assertEqual(len(factory.calls), 2)
        self.assertEqual(result[0].track_age_frames, 1)

    def test_reset_fallback_close_exception_detaches_backend(self):
        failing = CloseOnlyTracker(close_error=RuntimeError("close failed"))
        fresh = FakeTracker()
        factory = SequencedFactory(failing, fresh)
        adapter = ByteTrackHeadTracker(
            source_fps=30.0,
            tracker_factory=factory,
            supervision_module=FAKE_SUPERVISION,
        )
        adapter.update(
            (), frame_index=3, timestamp_ms=30.0, image_width=100, image_height=100
        )

        with self.assertRaisesRegex(RuntimeError, "close failed"):
            adapter.reset()

        self.assertEqual(
            adapter.update(
                (), frame_index=0, timestamp_ms=0.0, image_width=100, image_height=100
            ),
            (),
        )
        self.assertEqual(failing.close_calls, 1)
        self.assertEqual(len(factory.calls), 2)

    def test_close_exception_is_idempotent_and_never_retries_stale_backend(self):
        failing = FakeTracker(close_error=RuntimeError("close failed"))
        adapter, _, _ = make_tracker(failing)
        adapter.update(
            (), frame_index=0, timestamp_ms=0.0, image_width=100, image_height=100
        )

        with self.assertRaisesRegex(RuntimeError, "close failed"):
            adapter.close()
        adapter.close()

        self.assertEqual(failing.close_calls, 1)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            adapter.update(
                (), frame_index=1, timestamp_ms=1.0, image_width=100, image_height=100
            )

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
        self.assertEqual(
            adapter.update(timestamp_ms=2.0, **{**kwargs, "frame_index": 1}),
            (),
        )

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

    def test_observed_below_threshold_emits_once_but_is_not_bridged(self):
        bridge = ShortOcclusionBridge(max_gap_ms=500.0, min_confidence=0.15)

        observed = bridge.update(
            (tracked_candidate(3, confidence=0.10),),
            timestamp_ms=0.0,
        )

        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0].observed)
        self.assertEqual(observed[0].confidence, 0.10)
        self.assertEqual(bridge.update((), timestamp_ms=0.0), ())

    def test_reappearing_id_refreshes_box_confidence_and_missed_state(self):
        bridge = ShortOcclusionBridge()
        first = TrackedHeadCandidate(
            person_id=3,
            candidate=candidate(3, confidence=0.8, bbox=(0.1, 0.1, 0.2, 0.2)),
            track_age_frames=1,
        )
        refreshed = TrackedHeadCandidate(
            person_id=3,
            candidate=candidate(3, confidence=0.4, bbox=(0.5, 0.5, 0.7, 0.7)),
            track_age_frames=5,
        )
        bridge.update((first,), timestamp_ms=0.0)
        bridge.update((), timestamp_ms=100.0)

        observed = bridge.update((refreshed,), timestamp_ms=200.0)[0]
        missing = bridge.update((), timestamp_ms=300.0)[0]

        self.assertTrue(observed.observed)
        self.assertEqual(observed.head_bbox, refreshed.candidate.head_bbox)
        self.assertEqual(observed.confidence, 0.4)
        self.assertEqual(observed.missed_frames, 0)
        self.assertEqual(observed.missed_ms, 0.0)
        self.assertEqual(missing.head_bbox, refreshed.candidate.head_bbox)
        self.assertAlmostEqual(missing.confidence, 0.4 * math.exp(-0.2))
        self.assertEqual(missing.missed_frames, 1)
        self.assertEqual(missing.missed_ms, 100.0)

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

    def test_observed_perception_preserves_all_evidence_fields(self):
        face_keypoint = NormalizedLandmark(x=0.2, y=0.3, z=0.4)
        pose_landmark = NormalizedLandmark(
            x=0.5,
            y=0.6,
            z=0.7,
            visibility=0.8,
            presence=0.9,
        )
        face_landmark = NormalizedLandmark(x=0.7, y=0.8, z=0.9)
        head_pose = HeadPoseAngles(yaw_deg=12.0, pitch_deg=-3.0, roll_deg=1.5)
        rich_candidate = HeadCandidate(
            source_index=4,
            head_bbox=(0.1, 0.2, 0.4, 0.6),
            face_bbox=(0.15, 0.25, 0.35, 0.50),
            confidence=0.93,
            state=HeadPerceptionState.FACE_POSE,
            view_state=HeadViewState.PROFILE,
            observed=True,
            face_keypoints=(face_keypoint,),
            pose_head_landmarks=(pose_landmark,),
            facial_transformation_matrix=((1.0, 0.0), (0.0, 1.0)),
            head_pose=head_pose,
            face_landmarks=(face_landmark,),
        )

        perception = ShortOcclusionBridge().update(
            (
                TrackedHeadCandidate(
                    person_id=9,
                    candidate=rich_candidate,
                    track_age_frames=7,
                ),
            ),
            timestamp_ms=10.0,
        )[0]

        self.assertEqual(perception.face_bbox, rich_candidate.face_bbox)
        self.assertEqual(perception.face_keypoints, rich_candidate.face_keypoints)
        self.assertEqual(
            perception.pose_head_landmarks,
            rich_candidate.pose_head_landmarks,
        )
        self.assertEqual(
            perception.facial_transformation_matrix,
            rich_candidate.facial_transformation_matrix,
        )
        self.assertEqual(perception.head_pose, rich_candidate.head_pose)
        self.assertEqual(perception.face_landmarks, rich_candidate.face_landmarks)

    def test_failed_batch_is_atomic_and_cannot_create_future_bridge_state(self):
        bridge = ShortOcclusionBridge()
        bridge.update((tracked_candidate(3, confidence=0.8),), timestamp_ms=100.0)
        before = pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL)
        invalid_batch = (
            tracked_candidate(4, confidence=0.9),
            tracked_candidate(-1, confidence=0.7),
        )

        with self.assertRaisesRegex(ValueError, "person_id"):
            bridge.update(invalid_batch, timestamp_ms=200.0)

        self.assertEqual(
            pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL),
            before,
        )
        missing = bridge.update((), timestamp_ms=150.0)
        self.assertEqual(tuple(item.person_id for item in missing), (3,))
        self.assertEqual(missing[0].missed_ms, 50.0)
        self.assertLessEqual(missing[0].confidence, 0.8)

    def test_invalid_confidence_or_state_leaves_bridge_state_unchanged(self):
        invalid_candidates = tuple(
            tracked_candidate(4, confidence=value)
            for value in (True, -0.1, 1.1, float("nan"), float("inf"))
        ) + (
            TrackedHeadCandidate(
                person_id=4,
                candidate=replace(candidate(4), state="face_only"),
                track_age_frames=1,
            ),
        )
        for invalid in invalid_candidates:
            with self.subTest(invalid=invalid):
                bridge = ShortOcclusionBridge()
                bridge.update((tracked_candidate(3),), timestamp_ms=100.0)
                before = pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL)

                with self.assertRaisesRegex(ValueError, "confidence|state"):
                    bridge.update((invalid,), timestamp_ms=200.0)

                self.assertEqual(
                    pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL),
                    before,
                )

    def test_invalid_person_id_or_bbox_leaves_bridge_state_unchanged(self):
        invalid_candidates = (
            TrackedHeadCandidate(
                person_id=True,
                candidate=candidate(4),
                track_age_frames=1,
            ),
            TrackedHeadCandidate(
                person_id=1.5,
                candidate=candidate(4),
                track_age_frames=1,
            ),
            TrackedHeadCandidate(
                person_id=4,
                candidate=candidate(4, bbox=(0.1, 0.2, float("nan"), 0.4)),
                track_age_frames=1,
            ),
        )
        for invalid in invalid_candidates:
            with self.subTest(invalid=invalid):
                bridge = ShortOcclusionBridge()
                bridge.update((tracked_candidate(3),), timestamp_ms=100.0)
                before = pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL)

                with self.assertRaisesRegex(ValueError, "person_id|head_bbox"):
                    bridge.update((invalid,), timestamp_ms=200.0)

                self.assertEqual(
                    pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL),
                    before,
                )

    def test_duplicate_ids_reject_the_entire_batch_without_mutation(self):
        bridge = ShortOcclusionBridge()
        bridge.update((tracked_candidate(3),), timestamp_ms=100.0)
        before = pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL)

        with self.assertRaisesRegex(ValueError, "unique"):
            bridge.update(
                (tracked_candidate(4), tracked_candidate(4)),
                timestamp_ms=200.0,
            )

        self.assertEqual(
            pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL),
            before,
        )

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
        bridge.update((tracked_candidate(3),), timestamp_ms=2.0)
        before = pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL)
        with self.assertRaisesRegex(ValueError, "monotonic"):
            bridge.update((), timestamp_ms=1.0)
        self.assertEqual(
            pickle.dumps(vars(bridge), protocol=pickle.HIGHEST_PROTOCOL),
            before,
        )
        self.assertEqual(bridge.update((), timestamp_ms=2.0)[0].missed_ms, 0.0)

    def test_reset_clears_state_and_allows_new_video_timestamps(self):
        bridge = ShortOcclusionBridge()
        bridge.update((tracked_candidate(3),), timestamp_ms=1000.0)

        bridge.reset()

        self.assertEqual(bridge.update((), timestamp_ms=0.0), ())


if __name__ == "__main__":
    unittest.main()
