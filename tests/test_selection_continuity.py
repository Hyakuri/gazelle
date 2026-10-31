"""Selection contracts using synthetic observations, never MediaPipe or a model."""
import random
import importlib.util
import unittest
from dataclasses import replace
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

from gazelle.runtime.perception.contracts import HeadCandidate, HeadPerceptionState, HeadViewState, candidate_pool_size
from gazelle.runtime.perception.gaze_policy import arbitrate_perceptions
from gazelle.runtime.perception.provider import MediaPipeHeadProvider
from gazelle.runtime.perception.tracking import ByteTrackHeadTracker, ShortOcclusionBridge, TrackedHeadCandidate
from tests.test_gaze_policy import perception
from tests import test_mediapipe_head_provider as provider_tests


def candidate(x, confidence=.9, state=HeadPerceptionState.FACE_POSE):
    bbox = (x, .1, x+.1, .2)
    return HeadCandidate(source_index=0, head_bbox=bbox, face_bbox=bbox,
                         confidence=confidence, state=state, view_state=HeadViewState.FRONTAL)


def real_trace(frames, max_heads=1):
    bridge = ShortOcclusionBridge(max_gap_ms=500.)
    provider = MediaPipeHeadProvider(backend=SimpleNamespace(), max_heads=max_heads,
                                    tracker=ByteTrackHeadTracker(30.), bridge=bridge)
    raw = []
    update = bridge.update
    def capture(*args, **kwargs):
        rows = update(*args, **kwargs)
        raw.append(rows)
        return rows
    bridge.update = capture
    trace = []
    for index, rows in enumerate(frames):
        selected = provider._assign_people(rows, frame_index=index, timestamp_ms=index*1000/30,
                                           image_width=1000, image_height=1000)
        physical = tuple(sorted((round(p.head_bbox[0], 4), p.state.value) for p in selected))
        retained = tuple(sorted(round(s.head_bbox[0], 4) for s in bridge._states.values()))
        trace.append((physical, retained, selected, raw[-1]))
    provider.close()
    return trace


class SelectionContinuityTest(unittest.TestCase):
    def require_tracker(self):
        if importlib.util.find_spec('trackers') is None:
            self.skipTest('Optional trackers package unavailable')

    def test_all_provisional_startup_remembers_output_when_confidence_flips(self):
        self.require_tracker()
        provider = MediaPipeHeadProvider(backend=SimpleNamespace(), max_heads=1,
                                        tracker=ByteTrackHeadTracker(30.),
                                        bridge=ShortOcclusionBridge(max_gap_ms=500.))
        first = provider._assign_people([candidate(.1,.9),candidate(.7,.8)],
            frame_index=0,timestamp_ms=0,image_width=1000,image_height=1000)
        self.assertTrue(first[0].provisional)
        self.assertEqual(provider._previous_selection, ((first[0].person_id,first[0].head_bbox),))
        second = provider._assign_people([candidate(.1,.55),candidate(.7,.99)],
            frame_index=1,timestamp_ms=1000/30,image_width=1000,image_height=1000)
        self.assertEqual(second[0].person_id, first[0].person_id)
        provider.close()

    def test_observed_identity_wins_over_a_closer_bystander(self):
        previous = ((1, (.1,.1,.2,.2)),)
        a = replace(perception(1), head_bbox=(.13,.1,.23,.2))
        b = replace(a, person_id=2, head_bbox=previous[0][1], confidence=1.)
        self.assertEqual(arbitrate_perceptions((b,a), max_heads=1, previous_selection=previous), (a,))

    def test_previous_order_cannot_let_bystander_consume_another_subject_slot(self):
        a = replace(perception(1, observed=False, state=HeadPerceptionState.TRACKED_ONLY),
                    head_bbox=(.1,.1,.2,.2))
        b = replace(perception(2), head_bbox=(.15,.1,.25,.2))
        c = replace(perception(3), head_bbox=(.8,.1,.9,.2))
        for previous in (((1,a.head_bbox),(2,b.head_bbox)), ((2,b.head_bbox),(1,a.head_bbox))):
            self.assertEqual(arbitrate_perceptions((b,c,a), max_heads=2, previous_selection=previous), (b,a))

    def test_spatial_distance_inclusive_diagonal_and_y_component(self):
        # A 3:4:5 box makes the inclusive limit exact in binary arithmetic.
        bbox = (0., 0., .1875, .25)
        stale = replace(perception(1, observed=False, state=HeadPerceptionState.TRACKED_ONLY), head_bbox=bbox)
        for dx, dy, expected_fresh in ((.3125,0.,True),(.312501,0.,False),
                                       (0.,.3125,True),(0.,.312501,False),(.2,.25,False)):
            with self.subTest(dx=dx, dy=dy):
                fresh = replace(perception(2), head_bbox=(dx,dy,dx+.1875,dy+.25))
                result = arbitrate_perceptions((fresh,stale), max_heads=1, previous_selection=((1,bbox),))
                self.assertEqual(result, (fresh if expected_fresh else stale,))

    def test_winning_spawn_with_confirmed_bystander_is_neutral_and_subject_returns(self):
        # Script only the raw tracker IDs; the adapter, bridge and provider are real.
        helper = provider_tests.MediaPipeHeadProviderTest()
        a, b, x = candidate(.1), candidate(.34, .7), candidate(.22)
        prefix = [((a,b),(-1,-1))] + [((a,b),(10,20))]*4
        for returns in (False, True):
            tail = [((b,),(20,))]
            tail += [((a,b),(10,20)) if returns else ((b,),(20,))]*5
            baseline, kept = helper._sequence(prefix + [((b,),(20,))] + tail)
            spawned, spawn_kept = helper._sequence(prefix + [((b,x),(20,-1))] + tail)
            self.assertEqual(spawn_kept[5:], kept[5:])
            self.assertEqual([r.perceptions for r in spawned[6:]], [r.perceptions for r in baseline[6:]])
            self.assertTrue(spawned[5].perceptions[0].provisional)
            self.assertTrue(all(r.perceptions[0].person_id == 0 for r in baseline[5:]))
            self.assertEqual(baseline[7].perceptions[0].observed, returns)

    def test_coexistence_includes_provisional_and_drops_disappeared_ids(self):
        self.require_tracker()
        a, b = candidate(.1), candidate(.21, .7)
        # A and B coexist on their first provisional frame; A then misses.
        rows = [[a], [a], [a,b], [b], [b], [a,b]]
        trace = real_trace(rows)
        self.assertTrue(all(t[2][0].head_bbox[0] == .1 for t in trace))
        bridge = ShortOcclusionBridge(max_gap_ms=10.)
        provider = MediaPipeHeadProvider(backend=SimpleNamespace(), max_heads=2,
                                        tracker=ByteTrackHeadTracker(30.), bridge=bridge)
        provider._assign_people([a,b], frame_index=0, timestamp_ms=0, image_width=1000, image_height=1000)
        self.assertEqual(provider._coexisted, {(0,1)})
        provider._assign_people([], frame_index=1, timestamp_ms=40, image_width=1000, image_height=1000)
        self.assertEqual(provider._coexisted, set())
        self.assertEqual(provider._previous_selection, ())
        provider.close()

    def test_provider_multiple_heads_keep_missed_subject_with_visible_bystander(self):
        helper = provider_tests.MediaPipeHeadProviderTest()
        a, b, c = candidate(.1, .95), candidate(.18, .8), candidate(.7, .7)
        prefix = [((a,b,c),(-1,-1,-1))] + [((a,b,c),(10,20,30))]*3
        results, kept = helper._sequence(prefix + [((b,c),(20,30))]*3 + [((a,b,c),(10,20,30))], max_heads=2)
        self.assertTrue(all({p.person_id for p in r.perceptions} == {0,1} for r in results))
        self.assertTrue(all(set(ids) == {0,1} for ids in kept[1:]))
        for result in results[4:7]:
            subject = next(p for p in result.perceptions if p.person_id == 0)
            self.assertIs(subject.state, HeadPerceptionState.TRACKED_ONLY)
        self.assertTrue(all(p.observed for p in results[-1].perceptions))

    def test_seeded_real_bytetrack_spawn_neutrality(self):
        self.require_tracker()
        rng = random.Random(101)
        # Import the tracker backend before timing the scenarios, not its startup.
        warmup = ByteTrackHeadTracker(30.)
        warmup.update([candidate(.1)], frame_index=0, timestamp_ms=0,
                      image_width=1000, image_height=1000)
        warmup.close()
        start = perf_counter()
        true_spawns = winners = 0
        for trial in range(500):
            count = rng.randint(2,4)
            xs = rng.sample([.05,.13,.22,.34,.47,.60,.72,.85], count)
            people = [candidate(x, rng.uniform(.55,.98), rng.choice(tuple(HeadPerceptionState)[:3])) for x in xs]
            visibility = []
            for _ in people:
                first = rng.choice([0,0,0,2,3])
                gap = set()
                if rng.random() < .8:
                    begin = rng.randint(4,10)
                    gap = set(range(begin, begin+rng.randint(1,6)))
                visibility.append([first <= f and f not in gap for f in range(16)])
            frames = [[p for i,p in enumerate(people) if visibility[i][f]] for f in range(16)]
            t = rng.randint(3,11)
            xpos = round(rng.uniform(0.,.9),3)
            if any(abs(xpos-x) < .02 for x in xs):
                xpos += .031
            spawn = candidate(xpos, rng.uniform(.55,.98), rng.choice([p.state for p in people]))
            with_spawn = [list(row) for row in frames]
            with_spawn[t].append(spawn)
            max_heads = rng.choice([1,1,2])
            baseline, actual = real_trace(frames,max_heads), real_trace(with_spawn,max_heads)
            # Only actual provisional spawns satisfy the contract's premise.
            spawned = [p for p in actual[t][3] if p.provisional and abs(p.head_bbox[0]-xpos)<1e-6]
            if not spawned:
                continue
            if not any(not p.provisional for p in actual[t][3]):
                continue
            if len(with_spawn[t]) > candidate_pool_size(max_heads):
                continue
            # A spawn absorbed by a later detection is not a one-frame track.
            if any(p.person_id == spawned[0].person_id and p.observed
                   for row in actual[t+1:] for p in row[3]):
                continue
            true_spawns += 1
            winners += any(p.person_id == spawned[0].person_id for p in actual[t][2])
            with self.subTest(trial=trial):
                self.assertEqual([r[:2] for r in actual[t+1:]], [r[:2] for r in baseline[t+1:]])
            if true_spawns == 200:
                break
        self.assertEqual(true_spawns, 200)
        self.assertGreater(winners, 0)
        self.assertLess(perf_counter()-start, 20., '200 real-ByteTrack scenarios exceeded the contract budget')

    def test_bystander_blink_during_or_before_subject_gap(self):
        helper = provider_tests.MediaPipeHeadProviderTest()
        a, b, c = candidate(.1, .95), candidate(.21, .8), candidate(.75, .85)
        for max_heads in (1, 2):
            for before_gap in (False, True):
                with self.subTest(max_heads=max_heads, before_gap=before_gap):
                    # B is unselected; for two slots C is the other subject.
                    base, ids = ((a, c), (10, 30)) if max_heads == 2 else ((a,), (10,))
                    prefix = [(base, tuple(-1 for _ in base)), (base, ids)]
                    all_heads = (b,) + base  # Reverse candidate/identity ordering.
                    prefix += [(all_heads, (20,) + ids)] * 2
                    only_c, cid = ((c,), (30,)) if max_heads == 2 else ((), ())
                    gap = [(only_c, cid), ((b,) + only_c, (20,) + cid), (only_c, cid)]
                    if before_gap:
                        prefix += [(base, ids), (all_heads, (20,) + ids)]
                        gap = [(only_c, cid)] * 3
                    rows, kept = helper._sequence(prefix + gap + [(base, ids)], max_heads=max_heads)
                    subject = rows[1].perceptions[0].person_id
                    self.assertTrue(all(subject in keep for keep in kept[1:]))
                    for row in rows[len(prefix):-1]:
                        head = next(p for p in row.perceptions if p.person_id == subject)
                        self.assertIs(head.state, HeadPerceptionState.TRACKED_ONLY)
                    self.assertTrue(next(p for p in rows[-1].perceptions if p.person_id == subject).observed)

    def test_overlap_allows_immediate_replacement_with_intermittent_old_track(self):
        helper = provider_tests.MediaPipeHeadProviderTest()
        a, b = candidate(.1, .9), candidate(.14, .8)
        seq = [((a,), (-1,)), ((a,), (10,)), ((a,b), (10,-1)), ((a,b), (10,20)),
               ((b,), (20,)), ((a,b), (10,20)), ((b,), (20,))]
        rows, _ = helper._sequence(seq)
        self.assertEqual([r.perceptions[0].person_id for r in rows], [0,0,0,0,1,1,1])
        self.assertTrue(all(r.perceptions[0].observed for r in rows))

    def test_global_pairing_is_order_independent_and_uses_each_observation_once(self):
        a = replace(perception(9, observed=False, state=HeadPerceptionState.TRACKED_ONLY),
                    head_bbox=(.1,.1,.2,.2))
        b = replace(a, person_id=2, head_bbox=(.18,.1,.28,.2))
        new = replace(perception(3), head_bbox=(.20,.1,.30,.2))
        for previous in (((9,a.head_bbox),(2,b.head_bbox)), ((2,b.head_bbox),(9,a.head_bbox))):
            self.assertEqual(arbitrate_perceptions((new,b,a), max_heads=2,
                             previous_selection=previous), (new,a))

    def test_global_pairing_filters_every_pair_and_normalizes_identity_order(self):
        a = replace(perception(9, observed=False, state=HeadPerceptionState.TRACKED_ONLY),
                    head_bbox=(.1,.1,.2,.2))
        b = replace(a, person_id=8, head_bbox=(.6,.1,.7,.2))
        c = replace(perception(1), head_bbox=(.12,.1,.22,.2))
        d = replace(perception(2), head_bbox=(.7,.1,.8,.2))
        for previous in (((9,a.head_bbox),(8,b.head_bbox)), ((8,b.head_bbox),(9,a.head_bbox))):
            self.assertEqual(arbitrate_perceptions((c,d,a,b), max_heads=2,
                previous_selection=previous, coexisted={(2,8)}), (c,b))

    def test_coexistence_iou_boundary_and_timestamp_retention(self):
        # Exact rational areas: intersection 1/128, union 20/128 => IoU 0.05.
        a = replace(perception(9), head_bbox=(0., 0., .125, .5))
        at = replace(perception(2), head_bbox=(.109375, 0., .3125, .5))
        below = replace(at, head_bbox=(.109376, 0., .312501, .5))
        bridge = SimpleNamespace(max_gap_ms=10., update=lambda rows, **kw: rows,
                                 retain_person_ids=lambda ids: None)
        provider = MediaPipeHeadProvider(backend=SimpleNamespace(), max_heads=1,
            tracker=SimpleNamespace(update=lambda rows, **kw: rows), bridge=bridge)
        def step(rows, time):
            return provider._assign_people(rows, frame_index=0, timestamp_ms=time,
                                            image_width=100, image_height=100)
        step((at,a), 0.)
        self.assertEqual(provider._coexisted, set())
        step((a,below), 1.)
        self.assertEqual(provider._coexisted, {(2,9)})
        step((a,), 11.)
        self.assertEqual(provider._coexisted, {(2,9)})
        step((below,a), 11.)
        step((a,), 21.)
        self.assertEqual(provider._coexisted, {(2,9)})
        # Expiry must happen before arbitration, even with the other ID present.
        stale = replace(a, observed=False, state=HeadPerceptionState.TRACKED_ONLY)
        provider._previous_selection = ((2, below.head_bbox),)
        step((stale,), 21.001)
        self.assertEqual(provider._coexisted, set())
        step((), 40.)
        self.assertEqual(provider._coexisted, set())
        self.assertEqual(provider._last_present, {})

    def test_coexistence_storage_expires_under_identity_churn(self):
        bridge = SimpleNamespace(max_gap_ms=10., update=lambda rows, **kw: rows,
                                 retain_person_ids=lambda ids: None)
        provider = MediaPipeHeadProvider(backend=SimpleNamespace(), max_heads=1,
            tracker=SimpleNamespace(update=lambda rows, **kw: rows), bridge=bridge)
        a = replace(perception(1), head_bbox=(.1,.1,.2,.2))
        for index in range(200):
            b = replace(perception(index+2), head_bbox=(.6,.1,.7,.2))
            provider._assign_people((a,b), frame_index=index, timestamp_ms=index*11.,
                                    image_width=100, image_height=100)
            self.assertEqual(provider._coexisted, {(1,index+2)})
            self.assertEqual(len(provider._last_present), 2)

    def test_coexistence_expiry_affects_current_selection(self):
        a = replace(perception(9), head_bbox=(.1,.1,.2,.2))
        b = replace(perception(2), head_bbox=(.21,.1,.31,.2))
        bridge = SimpleNamespace(max_gap_ms=10., update=lambda rows, **kw: rows,
                                 retain_person_ids=lambda ids: None)
        provider = MediaPipeHeadProvider(backend=SimpleNamespace(), max_heads=1,
            tracker=SimpleNamespace(update=lambda rows, **kw: rows), bridge=bridge)
        def step(rows, t):
            return provider._assign_people(rows, frame_index=0, timestamp_ms=t,
                                            image_width=100, image_height=100)
        step((a,), 0.)
        step((b,a), 1.)
        step((b,), 11.)
        # Force the previous missing subject; actual bridges normally expire here.
        provider._previous_selection = ((9, a.head_bbox),)
        far = replace(perception(3), confidence=1., head_bbox=(.7,.1,.8,.2))
        self.assertEqual([p.person_id for p in step((far,b), 11.001)], [2])

    def test_real_candidate_pool_truncation_does_not_erase_bystander_pair(self):
        a, b, c, x = (replace(candidate(pos, score), source_index=pid)
                      for pos, score, pid in ((.1,.95,9),(.21,.7,2),(.7,.8,3),(.85,.99,4)))
        frames = [(a,b,c), (a,b,c), (a,b,c,x), (b,c), (a,b,c)]
        observed_pools = []
        def track(rows, **kwargs):
            observed_pools.append(tuple(p.source_index for p in rows))
            return tuple(TrackedHeadCandidate(person_id=p.source_index, candidate=p,
                         track_age_frames=3, provisional=p.source_index == 4) for p in rows)
        backend = provider_tests.FakeBackend([
            SimpleNamespace(faces=row, poses=(), timings_ms={}) for row in frames])
        provider = MediaPipeHeadProvider(backend=backend, max_heads=1,
            tracker=SimpleNamespace(update=track), bridge=ShortOcclusionBridge(max_gap_ms=500.))
        # Replace only face geometry extraction; production fusion sorting and
        # pool truncation run inside get_frame_result.
        with patch('gazelle.runtime.perception.fusion._build_face_head_candidate',
                   side_effect=lambda face, *args: face):
            results = [provider.get_frame_result(None,i,i*33.,100,100) for i in range(len(frames))]
        self.assertEqual(observed_pools[2], (4,9,3))
        self.assertNotIn(2, observed_pools[2])
        self.assertEqual([r.perceptions[0].person_id for r in results], [9]*5)
        self.assertIs(results[3].perceptions[0].state, HeadPerceptionState.TRACKED_ONLY)
        provider.close()


if __name__ == '__main__':
    unittest.main()
