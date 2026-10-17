import unittest

import numpy as np

from tools.workdata.sync_calibrate import (
    lag_peak, window_lags, fit_calibration, corrected_time, motion_cells,
    clock_sample, clock_summary, select_signals, refine_breakpoints,
)
from tools.workdata.timemap import fit_time_map, detect_pts_runs, map_time
from tools.workdata.sync_validate import residual_summary, event_indices


class CalibrationTest(unittest.TestCase):
    def test_coherent_clock_offsets_and_ramps_do_not_create_segments(self):
        x = np.arange(300) * 10.
        y = 1000 + .998 * x
        disturbed = y.copy()
        disturbed[40:70] += .5
        disturbed[160:190] += np.linspace(.5, .9, 30)
        fit = fit_time_map([dict(pts=a, wall_time=b) for a,b in zip(x,disturbed)],0,3000)
        self.assertEqual(len(fit),1)
        self.assertLess(np.max(np.abs([map_time(fit,t)-v for t,v in zip(x,y)])),.1)
        self.assertGreater(fit[0]['residuals']['p95'],.45)
        self.assertEqual(fit[0]['anchor_count'],300)
        bad = disturbed.copy()
        bad[::2] += 5
        fit = fit_time_map([dict(pts=a,wall_time=b) for a,b in zip(x,bad)],0,3000)
        self.assertFalse(fit[0]['valid'])

    def test_pts_breaks_are_between_actual_frames_and_disambiguate_reset(self):
        pts = [0,.1,.2,2,2.1,2.2,0,.1,.2]
        runs = detect_pts_runs(pts)
        self.assertEqual([(r['frame_start'],r['frame_end']) for r in runs],[(0,2),(3,5),(6,8)])
        rows = [dict(pts=p,wall_time=100+i*.1,frame_index=i) for i,p in enumerate(pts)]
        fit = fit_time_map(rows,0,2.3,pts_runs=runs)
        self.assertEqual(len(fit),3)
        self.assertEqual(fit[0]['pts_end'],.2)
        self.assertEqual(fit[1]['pts_start'],2)
        self.assertAlmostEqual(map_time(fit,.1,frame_index=7),100.7)
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            map_time(fit,.1)

    def test_equal_pts_is_not_a_backward_discontinuity(self):
        runs=detect_pts_runs([0.,0.,.05,.1])
        self.assertEqual(len(runs),1)
        self.assertEqual((runs[0]['frame_start'],runs[0]['frame_end']),(0,3))

    def test_lag_sign_interpolation_and_invalid_peaks(self):
        rng = np.random.default_rng(139)
        x = np.convolve(rng.normal(size=1200),np.ones(5)/5,'same')
        delayed = np.interp(np.arange(1200)-2.3,np.arange(1200),x)
        result = lag_peak(x,delayed)
        self.assertTrue(result['valid'])
        self.assertAlmostEqual(result['lag_seconds'],.46,delta=.025)
        self.assertTrue(lag_peak(x,np.roll(x,50))['at_boundary'])
        self.assertFalse(lag_peak(np.ones(300),np.ones(300))['valid'])
        periodic = np.sin(np.arange(600)*np.pi/5)
        self.assertEqual(lag_peak(periodic,periodic)['reason'],'peak_not_prominent')

    def test_step_fit_has_strict_coverage_and_mad_gates(self):
        noise=np.random.default_rng(139).normal(0,.005,60)
        rows = [dict(t_mid_seconds=t,lag_seconds=.2+.00001*t+(.4 if t>=1350 else 0)+e,valid=True)
                for t,e in zip(np.arange(30,3600,60),noise)]
        fit = fit_calibration(rows,3600)
        self.assertTrue(fit['valid'])
        self.assertEqual(len(fit['breakpoints']),1)
        self.assertAlmostEqual(fit['breakpoints'][0]['seconds'],1320,delta=60)
        self.assertAlmostEqual(fit['breakpoints'][0]['step_seconds'],.4,delta=.01)
        self.assertFalse(fit_calibration(rows[:9],3600)['valid'])
        self.assertFalse(fit_calibration(rows[:10],3600)['valid'])

    def test_fixed_point_solves_linear_clock_equation(self):
        fit = dict(valid=True,origin=1000,segments=[dict(start=0,end=3600,c0=2.5,c1=.0002)])
        base = 2800.
        actual = corrected_time(base,fit)
        self.assertAlmostEqual(actual,(base-2.5+.0002*1000)/1.0002,delta=.001)

    def test_gap_motion_and_clock_neighbor_reading_preserve_missing(self):
        thumbs = np.zeros((4,54,96),dtype=np.uint8)
        thumbs[1:] = 20
        cells = motion_cells(thumbs,np.array([False,False,True,False]))
        self.assertEqual(cells.shape,(3,72))
        self.assertTrue(np.all(np.isnan(cells[1:])))
        attempts = []
        def read(k):
            attempts.append(k)
            return {'wall_time':10.2} if k==6 else None
        row = clock_sample(5,20,9.,.2,'cam_a',read)
        self.assertEqual(attempts,[5,4,6])
        self.assertEqual(row['used_k'],6)
        self.assertTrue(row['passed'])
        missing = clock_sample(5,20,9.,.2,'cam_a',lambda k:None)
        self.assertFalse(missing['evaluable'])
        summary = clock_summary([row]*8+[missing])
        self.assertFalse(summary['evaluable_passed'])

    def test_window_grid_is_nonoverlapping_sixty_seconds(self):
        x = np.random.default_rng(139).normal(size=900)
        rows = window_lags(x,np.roll(x,2))
        self.assertEqual([r['t_mid_seconds'] for r in rows],[30,90,150])
        self.assertTrue(all(r['valid'] for r in rows))

    def test_cell_selection_follows_motion_at_nonzero_lag(self):
        rng=np.random.default_rng(2)
        reference=rng.normal(size=1000)
        cells={camera:rng.normal(size=(1000,72)) for camera in ('cam_a','cam_b','cam_e')}
        cells['cam_b'][:]=reference[:,None]
        for camera in ('cam_a','cam_e'):
            cells[camera][:,:6]=np.roll(reference,20)[:,None]
        _,selection=select_signals(cells)
        for value in selection.values():
            self.assertEqual(set(value['cells']),set(range(6)))

    def test_residual_gate_keeps_failing_values_and_reports_invalid_windows(self):
        rows=[dict(t_mid_seconds=t,lag_seconds=.02,valid=True,reason='valid') for t in range(30,1200,60)]
        rows.append(dict(t_mid_seconds=1230,lag_seconds=10.,valid=False,reason='peak_at_boundary'))
        self.assertTrue(residual_summary(rows,1260)['passed'])
        for row in rows[:3]:
            row['lag_seconds']=.5
        result=residual_summary(rows,1260)
        self.assertFalse(result['passed'])
        self.assertEqual(result['valid_windows'],20)
        self.assertEqual(result['window_categories']['peak_at_boundary'],1)
        self.assertEqual(event_indices({'cam_b':np.zeros(900)}),[])

    def test_nonconvergent_clock_correction_is_rejected(self):
        calibration=dict(valid=True,origin=0,segments=[dict(start=0,end=100,c0=5,c1=.1)])
        with self.assertRaisesRegex(ValueError,'converge'):
            corrected_time(50,calibration)


if __name__ == '__main__':
    unittest.main()
