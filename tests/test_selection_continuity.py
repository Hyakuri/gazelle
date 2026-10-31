"""Selection contracts using synthetic observations, never MediaPipe or a model."""
import random
import unittest
from dataclasses import replace
from time import perf_counter
from types import SimpleNamespace

from gazelle.runtime.perception.contracts import HeadCandidate, HeadPerceptionState, HeadViewState
from gazelle.runtime.perception.gaze_policy import arbitrate_perceptions
from gazelle.runtime.perception.provider import MediaPipeHeadProvider
from gazelle.runtime.perception.tracking import ByteTrackHeadTracker, ShortOcclusionBridge
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
    def test_all_provisional_startup_remembers_output_when_confidence_flips(self):
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
        a, b = candidate(.1), candidate(.18, .7)
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
        rng = random.Random(101)
        # Import the tracker backend before timing the scenarios, not its startup.
        ByteTrackHeadTracker(30.).close()
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
            true_spawns += 1
            winners += any(p.person_id == spawned[0].person_id for p in actual[t][2])
            with self.subTest(trial=trial):
                self.assertEqual([r[:2] for r in actual[t+1:]], [r[:2] for r in baseline[t+1:]])
            if true_spawns == 200:
                break
        self.assertEqual(true_spawns, 200)
        self.assertGreater(winners, 0)
        self.assertLess(perf_counter()-start, 5., '200 real-ByteTrack scenarios exceeded the contract budget')


if __name__ == '__main__':
    unittest.main()
