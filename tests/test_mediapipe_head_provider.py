import math
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from gazelle.runtime.perception.contracts import (
    HeadCandidate,
    HeadPerceptionState,
    HeadViewState,
    NormalizedLandmark,
)
from gazelle.runtime.perception.provider import MediaPipeHeadProvider
from gazelle.runtime.perception.tracking import TrackedHeadCandidate, ShortOcclusionBridge
from tests.test_head_tracking import FakeTracker as RawTracker, make_tracker, tracked_output


def make_config(**overrides):
    values = {
        "max_heads": 2,
        "head_track_max_gap_ms": 500.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_candidate(*, confidence=0.8, landmarks=()):
    return HeadCandidate(
        source_index=4,
        head_bbox=(-0.20, 0.10, 1.20, 0.60),
        face_bbox=(-0.10, 0.15, 0.80, 0.50),
        confidence=confidence,
        state=HeadPerceptionState.FACE_POSE,
        view_state=HeadViewState.FRONTAL,
        face_keypoints=(NormalizedLandmark(0.2, 0.3),),
        pose_head_landmarks=(NormalizedLandmark(0.4, 0.5),),
        facial_transformation_matrix=((1.0, 0.0, 0.0),),
        face_landmarks=tuple(landmarks),
    )


class FakeBackend:
    def __init__(self, observations):
        self._observations = list(observations)
        self.calls = []
        self.close_calls = 0
        self.close_error = None

    def observe(self, frame, **kwargs):
        self.calls.append((frame, kwargs))
        return self._observations.pop(0)

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class FakeTracker:
    def __init__(self, person_id=7):
        self.person_id = person_id
        self.calls = []
        self.close_calls = 0
        self.close_error = None

    def update(self, candidates, **kwargs):
        candidates = tuple(candidates)
        self.calls.append((candidates, kwargs))
        if not candidates:
            return ()
        return (
            TrackedHeadCandidate(
                person_id=self.person_id,
                candidate=candidates[0],
                track_age_frames=3,
            ),
        )

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class SequencedTracker:
    def __init__(self, person_ids):
        self._person_ids = iter(person_ids)

    def update(self, candidates, **kwargs):
        person_id = next(self._person_ids)
        candidates = tuple(candidates)
        if person_id is None or not candidates:
            return ()
        return (
            TrackedHeadCandidate(
                person_id=person_id,
                candidate=candidates[0],
                track_age_frames=1,
            ),
        )

    def close(self):
        return None


class FakeTrackerFactory:
    def __init__(self, tracker):
        self.tracker = tracker
        self.source_fps = None

    def __call__(self, source_fps):
        self.source_fps = source_fps
        return self.tracker


class MediaPipeHeadProviderTest(unittest.TestCase):
    def _sequence(self, sequence, max_heads=1):
        # Scripted upstream rows use ByteTrack spawn=-1, later confirmation IDs,
        # and no output row during misses; the real adapter and bridge are used.
        raw=RawTracker()
        raw.output_builder=lambda d: tracked_output(d,sequence[len(raw.updates)-1][1])
        tracker,_,_=make_tracker(raw,source_fps=30.)
        bridge=ShortOcclusionBridge(max_gap_ms=500.)
        backend=FakeBackend([SimpleNamespace(faces=(),poses=(),timings_ms={}) for _ in sequence])
        provider=MediaPipeHeadProvider(backend=backend,max_heads=max_heads,tracker=tracker,bridge=bridge)
        retained=[]
        original_retain=bridge.retain_person_ids
        def retain(ids):
            retained.append(tuple(ids))
            original_retain(ids)
        with patch('gazelle.runtime.perception.provider.build_head_candidates',
                   side_effect=[row[0] for row in sequence]) as build, patch.object(bridge,'retain_person_ids',side_effect=retain):
            results=[provider.get_frame_result('frame',i,i*1000/30,100,100) for i in range(len(sequence))]
        self.assertTrue(all(call.kwargs['max_heads']==max(3,max_heads) for call in build.call_args_list))
        provider.close()
        return results,retained

    @staticmethod
    def _small_candidate(x, **changes):
        return replace(make_candidate(),head_bbox=(x,.1,x+.1,.2),face_bbox=(x,.1,x+.1,.2),**changes)

    def test_far_spawn_keeps_previous_subject_until_bridge_expiry(self):
        a,b=self._small_candidate(.1),self._small_candidate(.7)
        sequence=[((a,),(-1,))]+[((a,),(10,))]*4+[((b,),(-1,))]+[((),())]*15
        results,retained=self._sequence(sequence)
        self.assertEqual([r.perceptions[0].person_id for r in results[:20]],[0]*20)
        self.assertTrue(all(r.perceptions[0].state is HeadPerceptionState.TRACKED_ONLY for r in results[5:20]))
        self.assertEqual(results[20].perceptions,())
        self.assertEqual(retained[5],(0,))

    def test_same_position_spawn_preserves_old_bridge_until_new_confirmation(self):
        a=self._small_candidate(.2)
        prefix=[((a,),(-1,))]+[((a,),(10,))]*4+[((a,),(-1,))]
        for next_raw,expected in ((10,0),(30,1)):
            with self.subTest(next_raw=next_raw):
                results,retained=self._sequence(prefix+[((a,),(next_raw,)),((),())])
                self.assertTrue(results[5].perceptions[0].provisional)
                self.assertEqual(results[5].perceptions[0].person_id,1)
                self.assertEqual(retained[5],(0,))
                self.assertEqual(retained[6],(expected,))
                self.assertEqual([r.perceptions[0].person_id for r in results[6:]],[expected,expected])

    def test_s4_spawn_is_neutral_to_bridge_retention(self):
        a=self._small_candidate(.1)
        b=self._small_candidate(.15,state=HeadPerceptionState.POSE_ONLY,face_pose_reference_ray=None)
        prefix=[((a,),(-1,))]+[((a,),(10,))]*2+[((a,b),(10,-1)),((a,b),(10,20))]
        baseline,base_retained=self._sequence(prefix+[((b,),(20,))]+[((),())]*3)
        for x in (.1,.7):
            spawn=self._small_candidate(x)
            results,retained=self._sequence(prefix+[((b,spawn),(20,-1))]+[((),())]*3)
            self.assertEqual(retained[5:],base_retained[5:])
            self.assertEqual([r.perceptions for r in results[6:]],[r.perceptions for r in baseline[6:]])
        self.assertEqual([r.perceptions[0].person_id for r in baseline[5:]],[1]*4)

    def test_multiple_heads_also_prune_replaced_bridge_ids(self):
        a,b=self._small_candidate(.1),self._small_candidate(.7)
        results,retained=self._sequence([((a,b),(-1,-1)),((a,b),(10,20)),
            ((a,b),(-1,-1)),((a,b),(30,40)),((),())],max_heads=2)
        self.assertEqual(retained[2],(0,1))
        self.assertEqual(retained[3],(2,3))
        self.assertEqual([p.person_id for p in results[4].perceptions],[2,3])

    def test_image_selection_renumbers_after_priority_filter(self):
        backend=FakeBackend([SimpleNamespace(faces=(),poses=(),timings_ms={})])
        provider=MediaPipeHeadProvider(backend=backend,max_heads=2)
        candidates=(self._small_candidate(.1,state=HeadPerceptionState.POSE_ONLY),
                    self._small_candidate(.4,confidence=.9),self._small_candidate(.7,confidence=.8))
        with patch('gazelle.runtime.perception.provider.build_head_candidates',return_value=candidates):
            result=provider.get_frame_result('frame',0,0,100,100)
        self.assertEqual([p.person_id for p in result.perceptions],[0,1])
        self.assertEqual([p.head_bbox[0] for p in result.perceptions],[.4,.7])
        provider.close()

    def test_tracker_construction_failure_closes_backend_without_masking_error(self):
        backend = FakeBackend([])
        construction_error = RuntimeError("tracker construction failed")
        backend.close_error = RuntimeError("backend cleanup failed")

        def fail_tracker_construction(source_fps):
            raise construction_error

        with self.assertRaises(RuntimeError) as caught:
            MediaPipeHeadProvider.create(
                make_config(),
                media_type="video",
                source_fps=25.0,
                backend_factory=lambda config, *, media_type: backend,
                tracker_factory=fail_tracker_construction,
            )

        self.assertIs(caught.exception, construction_error)
        self.assertEqual(backend.close_calls, 1)
        self.assertTrue(
            any("backend cleanup failed" in note for note in caught.exception.__notes__)
        )

    def test_bridge_construction_failure_closes_tracker_and_backend(self):
        backend = FakeBackend([])
        tracker = FakeTracker()
        construction_error = RuntimeError("bridge construction failed")
        tracker.close_error = RuntimeError("tracker cleanup failed")
        backend.close_error = RuntimeError("backend cleanup failed")

        with patch(
            "gazelle.runtime.perception.provider._create_short_occlusion_bridge",
            side_effect=construction_error,
        ):
            with self.assertRaises(RuntimeError) as caught:
                MediaPipeHeadProvider.create(
                    make_config(),
                    media_type="video",
                    source_fps=25.0,
                    backend_factory=lambda config, *, media_type: backend,
                    tracker_factory=lambda source_fps: tracker,
                )

        self.assertIs(caught.exception, construction_error)
        self.assertEqual(tracker.close_calls, 1)
        self.assertEqual(backend.close_calls, 1)
        notes = caught.exception.__notes__
        self.assertTrue(any("tracker cleanup failed" in note for note in notes))
        self.assertTrue(any("backend cleanup failed" in note for note in notes))

    def test_image_result_assigns_ordered_ids_and_retains_rich_landmarks(self):
        landmarks = tuple(NormalizedLandmark(index / 478.0, 0.5) for index in range(478))
        backend = FakeBackend(
            [SimpleNamespace(faces=(), poses=(), timings_ms={"face_detector": 1.25})]
        )
        candidates = (make_candidate(landmarks=landmarks), make_candidate(confidence=0.6))
        provider = MediaPipeHeadProvider(backend=backend, max_heads=2)

        with patch(
            "gazelle.runtime.perception.provider.build_head_candidates",
            return_value=candidates,
        ):
            result = provider.get_frame_result("frame", 0, 0.0, 100, 80)

        self.assertEqual([item.person_id for item in result.heads], [0, 1])
        self.assertEqual(result.heads[0].bbox, (0.0, 0.1, 1.0, 0.6))
        self.assertEqual(result.perceptions[0].face_bbox, (0.0, 0.15, 0.8, 0.5))
        self.assertEqual(len(result.perceptions[0].face_landmarks), 478)
        self.assertFalse(result.perceptions[0].provisional)
        self.assertEqual(result.timings_ms["face_detector"], 1.25)
        self.assertTrue(math.isfinite(result.timings_ms["fusion"]))

    def test_total_timing_covers_the_whole_provider_and_preserves_backend_total(self):
        backend = FakeBackend(
            [SimpleNamespace(faces=(), poses=(), timings_ms={"total": 2.5})]
        )
        provider = MediaPipeHeadProvider(backend=backend, max_heads=1)

        with patch(
            "gazelle.runtime.perception.provider.build_head_candidates",
            return_value=(),
        ):
            with patch(
                "gazelle.runtime.perception.provider.perf_counter",
                side_effect=(10.000, 10.002, 10.003, 10.004, 10.005, 10.010),
            ):
                result = provider.get_frame_result("frame", 0, 0.0, 100, 80)

        self.assertEqual(result.timings_ms["backend_total"], 2.5)
        self.assertAlmostEqual(result.timings_ms["fusion"], 1.0)
        self.assertAlmostEqual(result.timings_ms["total"], 10.0)
        self.assertGreater(result.timings_ms["total"], result.timings_ms["backend_total"])

    def test_video_result_uses_tracker_and_short_occlusion_bridge(self):
        backend = FakeBackend(
            [
                SimpleNamespace(faces=(), poses=(), timings_ms={"total": 3.0}),
                SimpleNamespace(faces=(), poses=(), timings_ms={"total": 4.0}),
            ]
        )
        tracker = FakeTracker(person_id=12)
        tracker_factory = FakeTrackerFactory(tracker)
        provider = MediaPipeHeadProvider.create(
            make_config(),
            media_type="video",
            source_fps=25.0,
            backend_factory=lambda config, *, media_type: backend,
            tracker_factory=tracker_factory,
        )

        with patch(
            "gazelle.runtime.perception.provider.build_head_candidates",
            side_effect=((make_candidate(),), ()),
        ):
            observed = provider.get_frame_result("first", 0, 0.0, 100, 80)
            bridged = provider.get_frame_result("second", 1, 100.0, 100, 80)

        self.assertEqual(tracker_factory.source_fps, 25.0)
        self.assertEqual([item.person_id for item in observed.heads], [12])
        self.assertEqual(observed.heads[0].bbox, (0.0, 0.1, 1.0, 0.6))
        self.assertEqual([item.person_id for item in bridged.heads], [12])
        self.assertFalse(bridged.perceptions[0].observed)
        self.assertIn("tracking", observed.timings_ms)
        self.assertEqual(tracker.calls[0][1]["image_width"], 100)

    def test_single_person_post_bridge_arbitration_prunes_stale_identity(self):
        backend = FakeBackend(
            [
                SimpleNamespace(faces=(), poses=(), timings_ms={}),
                SimpleNamespace(faces=(), poses=(), timings_ms={}),
                SimpleNamespace(faces=(), poses=(), timings_ms={}),
            ]
        )
        provider = MediaPipeHeadProvider.create(
            make_config(max_heads=1),
            media_type="video",
            source_fps=25.0,
            backend_factory=lambda config, *, media_type: backend,
            tracker_factory=lambda source_fps: SequencedTracker((1, 2, None)),
        )

        with patch(
            "gazelle.runtime.perception.provider.build_head_candidates",
            side_effect=((make_candidate(),), (make_candidate(confidence=0.6),), ()),
        ):
            first = provider.get_frame_result("first", 0, 0.0, 100, 80)
            replacement = provider.get_frame_result("replacement", 1, 100.0, 100, 80)
            bridged = provider.get_frame_result("missing", 2, 200.0, 100, 80)

        self.assertEqual(tuple(item.person_id for item in first.perceptions), (1,))
        self.assertEqual(tuple(item.person_id for item in replacement.perceptions), (2,))
        self.assertEqual(tuple(item.person_id for item in bridged.perceptions), (2,))

    def test_single_person_provisional_winner_preserves_confirmed_bridge(self):
        backend = FakeBackend([
            SimpleNamespace(faces=(), poses=(), timings_ms={}) for _ in range(9)
        ])
        class SpawnTracker:
            def update(self, candidates, *, frame_index, **kwargs):
                if frame_index <= 4:
                    return (TrackedHeadCandidate(0, candidates[0], frame_index + 1),)
                if frame_index == 5:
                    return (TrackedHeadCandidate(1, candidates[0], 1, provisional=True),)
                return ()

            def close(self):
                pass

        provider = MediaPipeHeadProvider.create(
            make_config(max_heads=1), media_type="video", source_fps=30.0,
            backend_factory=lambda config, *, media_type: backend,
            tracker_factory=lambda source_fps: SpawnTracker(),
        )
        try:
            with patch("gazelle.runtime.perception.provider.build_head_candidates",
                       side_effect=[(make_candidate(),)] * 6 + [()] * 3):
                results = [provider.get_frame_result("frame", i, i * 1000 / 30, 100, 80)
                           for i in range(9)]
            self.assertTrue(results[5].perceptions[0].provisional)
            for result in results[6:]:
                self.assertEqual([p.person_id for p in result.perceptions], [0])
                self.assertEqual(result.perceptions[0].state, HeadPerceptionState.TRACKED_ONLY)
                self.assertFalse(result.perceptions[0].provisional)
        finally:
            provider.close()

    def test_empty_fusion_result_is_empty_and_get_heads_remains_compatible(self):
        backend = FakeBackend(
            [
                SimpleNamespace(faces=(), poses=(), timings_ms={}),
                SimpleNamespace(faces=(), poses=(), timings_ms={}),
            ]
        )
        provider = MediaPipeHeadProvider(backend=backend, max_heads=1)

        with patch(
            "gazelle.runtime.perception.provider.build_head_candidates",
            return_value=(),
        ):
            result = provider.get_frame_result("frame", 0, 0.0, 100, 80)
            heads = provider.get_heads("frame", 1, 1.0, 100, 80)

        self.assertEqual(result.heads, ())
        self.assertEqual(result.perceptions, ())
        self.assertEqual(heads, ())

    def test_close_attempts_backend_and_tracker_cleanup_then_reraises_first_error(self):
        backend = FakeBackend([])
        tracker = FakeTracker()
        backend.close_error = RuntimeError("backend cleanup failed")
        tracker.close_error = RuntimeError("tracker cleanup failed")
        provider = MediaPipeHeadProvider(backend=backend, max_heads=1, tracker=tracker)

        with self.assertRaisesRegex(RuntimeError, "backend cleanup failed"):
            provider.close()
        provider.close()

        self.assertEqual(backend.close_calls, 1)
        self.assertEqual(tracker.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
