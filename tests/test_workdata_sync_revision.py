"""Round-2 synchronization contracts; synthetic pixels and mocked media only."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from tools.workdata import sync_calibrate, sync_validate


class SyncRevisionTest(unittest.TestCase):
    def test_0911_53_window_regression_and_seeded_pure_lines(self):
        # Numeric motion evidence only; no external media or cached arrays.
        times = [30,90,150,210,270,330,450,510,570,630,690,750,810,870,930,
                 990,1050,1110,1170,1230,1350,1410,1470,1530,1590,1650,1710,
                 1770,1830,1950,2010,2070,2130,2370,2430,2490,2610,2670,
                 2730,2790,2850,2910,2970,3030,3090,3150,3210,3270,3330,
                 3390,3450,3510,3570]
        lags = [-1.2430359889642466,-1.2019362306117718,-1.2549984259329217,
                -1.1639553251120887,-1.3100790238510442,-1.2173664466212248,
                -1.0802209540605092,-1.0703437750715956,-1.2497086312842658,
                -1.301686536834461,-1.243668086031678,-1.3107491357348038,
                -1.1902108801194915,-1.0306240913845675,-.8330497934499398,
                -.8246274492581962,-.8649381887568476,-.71422195225303,
                -.9603206441163877,-.6025095655331706,-.6787023042616304,
                -.6943029236430889,-.6671936319385317,-.655442534791545,
                -.7265942599134784,-.47626258048492903,-.5647223500627635,
                -.40058137431665325,-.4581944537505106,-.6003221609069451,
                -.7214061762847999,-.5090527588963937,-.41479894936353434,
                -.4487639213859854,-.47927151831074866,-.5422550178165264,
                -.5995389423427221,-.7028852539218478,-.4668932184413019,
                -.48242167042498246,-.5822682461730959,-.5375473270288365,
                -.38984458870446553,-.45358329405302944,-.47829215661333724,
                -.4194589063429369,-.5380909625976269,-.46661175254514653,
                -.3775030546580984,-.3857438204134905,-.461075262877588,
                -.26915147196796363,-.24709212495335034]
        self.assertEqual(len(times), 53)
        rows = [dict(valid=True, t_mid_seconds=t, lag_seconds=y) for t,y in zip(times,lags,strict=True)]
        fit = sync_calibrate.fit_calibration(rows,3613.8)
        self.assertTrue(fit['valid'])
        self.assertEqual([p['adjacent_window_centers'] for p in fit['breakpoints']],
                         [[810.,870.],[2490.,2610.]])
        self.assertAlmostEqual(fit['breakpoints'][0]['step_seconds'], .394, delta=.0005)
        self.assertAlmostEqual(fit['breakpoints'][1]['step_seconds'], -.243, delta=.0005)
        self.assertAlmostEqual(fit['residual_mad'], .0597, delta=.00005)
        self.assertEqual(fit['residual_tail_fraction'], 0.)
        rng = np.random.default_rng(7)
        for sigma in (.03,.02,.02,.04,.06): rng.normal(0,sigma,60)
        for trial in range(24):
            n = (20,40,60)[trial%3]
            t = np.arange(n)*60.+30
            values = -.5+.0001*t+rng.normal(0,(.02,.05)[trial%2],n)
            rows = [dict(valid=True,t_mid_seconds=float(x),lag_seconds=float(y)) for x,y in zip(t,values)]
            self.assertEqual(sync_calibrate.fit_calibration(rows,n*60.)['breakpoints'], [], trial)

    def test_uncertainty_uses_nearest_evidence_and_each_window_half_length(self):
        update = getattr(sync_calibrate, 'update_uncertainty', None)
        self.assertTrue(callable(update), 'Missing evidence-based cut uncertainty')
        cases = [
            (961.247810273165, 811.146046697371, 1111.349573848959, 60, False),
            (1835.6953119026002, 1820.1575513700504, 1851.2330724351498, 20, True),
            (533.7943862981242, 528.9774561348647, 538.6113164613837, 20, True),
            (899.0190546660601, 878.9676908830984, 919.0704184490219, 20, True),
        ]
        for cut, left, right, length, localized in cases:
            good = [dict(valid=True, b_mid_seconds=t, t_mid_seconds=t-1.) for t in (left, right)]
            point = dict(seconds=cut, refinement_windows=good if length == 20 else [])
            fit = dict(windows=good if length == 60 else [dict(valid=True, b_mid_seconds=cut-100.),
                                                        dict(valid=True, b_mid_seconds=cut+100.)],
                       breakpoints=[point])
            update(fit)
            self.assertEqual(point['localized'], localized)
            self.assertEqual(point['uncertainty_seconds'], [left-length/2, right+length/2])

    def test_uncertainty_requires_evidence_on_both_sides(self):
        update = getattr(sync_calibrate, 'update_uncertainty', None)
        self.assertTrue(callable(update))
        with self.assertRaisesRegex(ValueError, 'both sides'):
            update(dict(windows=[], breakpoints=[dict(seconds=10., refinement_windows=[])]))

    def test_source_clock_fallback_precedes_any_neighbor(self):
        calls = []
        def read(k):
            calls.append(('proxy', k))
            return None
        def source(k):
            calls.append(('source', k))
            return {'wall_time': 10.} if k == 4 else None
        import inspect
        self.assertIn('read_source', inspect.signature(sync_calibrate.clock_sample).parameters)
        row = sync_calibrate.clock_sample(4, 10, 9.2, .2, 'cam_e', read, lambda k: 10.023,
                                          read_source=source, comparison_at=lambda k: .75)
        self.assertEqual(calls, [('proxy', 4), ('source', 4)])
        self.assertTrue(row['passed'])
        self.assertEqual(row['reading_source'], 'source')
        self.assertEqual(row['thumbnail_mean_absolute_difference'], .75)
        calls.clear()
        sync_calibrate.clock_sample(4, 10, 9.2, .2, 'cam_e', read, lambda k: 10.,
                                    read_source=lambda k: calls.append(('source', k)),
                                    comparison_at=lambda k: 1.)
        self.assertEqual(calls, [(source, k) for k in (4, 3, 5, 2, 6) for source in ('proxy', 'source')])

    def test_source_clock_decode_rejects_any_pts_mismatch(self):
        pair_reader = getattr(sync_validate, 'ProxyClockReader', None)
        self.assertTrue(callable(pair_reader))
        frame = SimpleNamespace(to_ndarray=lambda **kw: np.zeros((54,96,3),dtype=np.uint8))
        class Source:
            def __init__(self, path): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def frames(self, **kwargs): return iter([(1.000001, frame)])
        rows = [dict(source='s', pts=1.)]
        sources = {'s': dict(camera='cam_e', media_path='mock.mp4', segments=[])}
        with patch.object(sync_validate, 'read_frame', return_value=np.zeros((54,96,3), dtype=np.uint8)):
            reader = pair_reader(None, rows, sources, 'cam_e', source_factory=Source)
            with self.assertRaisesRegex(ValueError, 'PTS'):
                reader.read_proxy(0)

    def test_exact_pair_comparison_is_signed_safe_and_cached(self):
        decoded = []
        class Source:
            def __init__(self, path): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def frames(self, **kwargs):
                decoded.append(kwargs)
                yield 1., SimpleNamespace(to_ndarray=lambda **kw: np.full((54,96,3),255,dtype=np.uint8))
        with patch.object(sync_validate, 'read_frame', return_value=np.zeros((54,96,3),dtype=np.uint8)):
            reader = sync_validate.ProxyClockReader(None,[dict(source='s',pts=1.)],
                {'s':dict(camera='cam_e',media_path='mock.mp4')},'cam_e', source_factory=Source,
                reader=SimpleNamespace(read=lambda image,camera: {'wall_time':float(image.mean())}))
            self.assertEqual(reader.read_proxy(0)['wall_time'], 0.)
            self.assertEqual(reader.read_source(0)['wall_time'], 255.)
            self.assertEqual(reader.comparison_at(0),255.)
            self.assertEqual(decoded,[{'start':1.}])

    def test_recognized_failed_clock_does_not_search_for_a_passing_neighbor(self):
        source = unittest.mock.Mock()
        row = sync_calibrate.clock_sample(4,10,0.,.2,'cam_a',lambda k: {'wall_time':0.},
                                          lambda k:10.,read_source=source,comparison_at=lambda k:1.)
        self.assertFalse(row['passed'])
        self.assertEqual(row['reading_source'],'proxy')
        self.assertEqual(len(row['attempts']),1)
        source.assert_not_called()

    def test_production_pair_order_keeps_positive_lag_for_delayed_camera(self):
        measure = getattr(sync_validate, 'residual_pairs', None)
        self.assertTrue(callable(measure))
        rng = np.random.default_rng(140)
        reference = rng.normal(size=6000)
        delayed = np.r_[np.zeros(2), reference[:-2]]
        result = measure({'cam_b': reference, 'cam_a': delayed, 'cam_e': np.r_[0., reference[:-1]]}, 1200.)
        for name, expected in (('A-B', .4), ('E-B', .2), ('A-E', .2)):
            values = [row['lag_seconds'] for row in result[name]['windows'] if row['valid']]
            self.assertGreaterEqual(len(values), 10)
            self.assertAlmostEqual(float(np.median(values)), expected, delta=.01)
        self.assertAlmostEqual(result['E-B']['c0_at_midpoint'], .2, delta=.01)


if __name__ == '__main__':
    unittest.main()
