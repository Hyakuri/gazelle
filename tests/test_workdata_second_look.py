"""Frozen first-pass decisions and opt-in second-look numerical contracts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.workdata import sync_calibrate as cal, sync_validate as val
from tools.validation import sample_segments as sampling


def windows(value=0., count=12):
    return [dict(valid=True,reason='valid',t_mid_seconds=60.+60*k,lag_seconds=value)
            for k in range(count)]


def fit():
    return dict(valid=False,reason='residual_tail_exceeds_0_2',duration=800.,
                segments=[dict(start=0.,end=800.,c0=.4,c1=0.)],
                residual_mad=.03,residual_tail_fraction=.13)


def pairs():
    return {name:dict(passed=True,conclusion='passed',reason='passed',windows=[])
            for name in ('A-B','E-B','A-E','W-B')}


class SecondLookTest(unittest.TestCase):
    def test_fit_keeps_coefficients_and_original_tail_pass_or_fail(self):
        for residual,passed in ((0.,True),(.10001,False),(-.10001,False)):
            with self.subTest(residual=residual):
                value=fit();original=deepcopy(value)
                with patch.object(cal,'window_lags',return_value=windows(.4+residual)) as lag:
                    cal.second_look_fit(value,[1],[2])
                lag.assert_called_once_with([1],[2],window=120.,step=60.)
                self.assertEqual(value['valid'],passed)
                self.assertEqual(value['reason'],'valid_second_look' if passed else original['reason'])
                for key in ('segments','residual_mad','residual_tail_fraction'):
                    self.assertEqual(value[key],original[key])
                self.assertEqual(value['second_look']['passed'],passed)
                self.assertEqual(len(value['second_look']['validation_sha256']),64)

    def test_fit_uses_base_time_crossing_cut_and_endpoint_fallback_without_dropping_windows(self):
        value=fit();value['segments']=[dict(start=0.,end=100.,c0=1.,c1=.01),
                                     dict(start=100.,end=800.,c0=3.,c1=.02)]
        rows=[dict(valid=True,reason='valid',t_mid_seconds=t,lag_seconds=lag)
              for t,lag in ((-5.,1.),(99.,2.),(900.,1.))]
        rows.append(dict(valid=False,reason='low_motion',t_mid_seconds=150.))
        with patch.object(cal,'window_lags',return_value=deepcopy(rows)), \
             patch.object(val,'residual_summary',return_value=dict(passed=False)) as summary:
            cal.second_look_fit(value,[1],[2])
        actual=summary.call_args.args[0]
        self.assertEqual(len(actual),4)
        for row,expected in zip(actual[:3],[.04,-3.02,-20.02]):
            self.assertAlmostEqual(row['lag_seconds'],expected)
        self.assertEqual(actual[3],rows[3])
        self.assertEqual(summary.call_args.args[1],800.)

    def test_fit_other_failure_or_already_valid_never_rechecks(self):
        for reason in ('valid','residual_mad_exceeds_limit','insufficient_windows','valid_second_look'):
            value=dict(fit(),reason=reason);original=deepcopy(value)
            with patch.object(cal,'window_lags',side_effect=AssertionError('must not recheck')):
                cal.second_look_fit(value,[],[])
            self.assertEqual(value,original)

    def test_pair_recheck_preserves_first_pass_and_ignores_w(self):
        original=pairs()
        original['A-B'].update(passed=False,conclusion='failed',reason='fraction_within_0_2 < 0.9')
        original['A-E'].update(passed=False,conclusion='failed',reason='median_absolute_seconds > 0.1')
        original['W-B'].update(passed=False,conclusion='failed',reason='fraction_within_0_2 < 0.9')
        value=deepcopy(original);signals={c:[c] for c in ('cam_a','cam_b','cam_e','cam_w')}
        with patch.object(val,'window_lags',side_effect=[windows(),windows(-.14)]) as lag:
            val.second_look_pairs(value,signals,800.)
        self.assertEqual(lag.call_count,2)
        self.assertEqual(lag.call_args_list[0].args,(['cam_b'],['cam_a']))
        self.assertEqual(lag.call_args_list[1].args,(['cam_e'],['cam_a']))
        for name in value:
            self.assertEqual({k:v for k,v in value[name].items() if k!='second_look'},original[name])
        self.assertNotIn('second_look',value['W-B'])
        self.assertEqual(val.second_look_outcome(value,{}),(True,'second_look'))

    def test_ab_eb_only_fraction_failure_triggers_and_insufficient_ae_is_allowed(self):
        for name in ('A-B','E-B'):
            for reason in ('fraction_within_0_2 < 0.9; median_absolute_seconds > 0.1','abs(c0_at_midpoint) > 0.1'):
                value=pairs();value[name].update(passed=False,conclusion='failed',reason=reason)
                with patch.object(val,'window_lags',side_effect=AssertionError('not eligible')):
                    val.second_look_pairs(value,{},800.)
                self.assertEqual(val.second_look_outcome(value,{}),(False,None))
        value=pairs();value['A-E'].update(passed=False,conclusion='insufficient_evidence')
        with patch.object(val,'window_lags',side_effect=AssertionError('original allowance')):
            val.second_look_pairs(value,{},800.)
        self.assertEqual(val.second_look_outcome(value,{}),(True,'official'))

    def test_three_pair_thresholds_and_negative_values(self):
        for name in ('A-B','E-B','A-E'):
            limit=.15 if name=='A-E' else .1
            for field in ('median_absolute_seconds','c0_at_midpoint','c1_seconds_per_hour'):
                for sign in (-1,1):
                    if field=='median_absolute_seconds' and sign<0:continue
                    for delta in (0.,.00001):
                        with self.subTest(name=name,field=field,sign=sign,delta=delta):
                            stats=dict(passed=False,conclusion='failed',reason='fixture',valid_windows=10,
                                       coverage_fraction=.3,fraction_within_0_2=.9,
                                       median_absolute_seconds=0.,c0_at_midpoint=0.,c1_seconds_per_hour=0.)
                            stats[field]=sign*(limit+delta)
                            if name!='A-E':stats['passed']=delta==0
                            else:stats['fraction_within_0_2']=0.  # No A-E fraction gate.
                            value=pairs();value[name].update(passed=False,conclusion='failed',reason='fraction_within_0_2 < 0.9')
                            with patch.object(val,'window_lags',return_value=[]),patch.object(val,'residual_summary',return_value=stats):
                                val.second_look_pairs(value,dict(cam_a=[],cam_b=[],cam_e=[]),800.)
                            self.assertEqual(val.second_look_outcome(value,{}),(delta==0,'second_look' if delta==0 else None))

    def test_actual_four_gates_fraction_boundary_negative_bias_and_drift(self):
        rows=windows(count=20)
        for row in rows[-2:]:row['lag_seconds']=.21
        with patch.object(val,'_line',return_value=dict(c0=-.1,c1=-.1/3600)):
            result=val.residual_summary(rows,1300.)
        self.assertTrue(result['passed']);self.assertEqual(result['fraction_within_0_2'],.9)
        rows[-3]['lag_seconds']=.21
        self.assertFalse(val.residual_summary(rows,1300.)['passed'])
        for c0,c1 in ((-.10001,0.),(0.,-.10001/3600)):
            with patch.object(val,'_line',return_value=dict(c0=c0,c1=c1)):
                self.assertFalse(val.residual_summary(windows(),800.)['passed'])

    def test_insufficient_second_look_never_passes_or_grades(self):
        for name in ('A-B','E-B','A-E'):
            for rows,duration in ((windows(count=9),800.),(windows(count=10),4000.)):
                value=pairs();value[name].update(passed=False,conclusion='failed',reason='fraction_within_0_2 < 0.9')
                with patch.object(val,'window_lags',return_value=rows):
                    val.second_look_pairs(value,dict(cam_a=[],cam_b=[],cam_e=[]),duration)
                self.assertEqual(val.second_look_outcome(value,{}),(False,None))
        value=fit()
        with patch.object(cal,'window_lags',return_value=windows(.4,count=9)):
            cal.second_look_fit(value,[],[])
        self.assertFalse(value['valid'])

    def test_grade_uses_abe_fit_or_proxy_not_w(self):
        for camera,expected in (('cam_a','second_look'),('cam_e','second_look'),('cam_w','official')):
            self.assertEqual(val.second_look_outcome(pairs(),{camera:dict(reason='valid_second_look')}),(True,expected))
        value=pairs();value['E-B']['conclusion']='failed'
        self.assertEqual(val.second_look_outcome(value,{'cam_a':dict(reason='valid_second_look')}),(False,None))

    def test_index_grade_legacy_default_new_required_and_null_rejected_for_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            index=Path(directory)/'manifest.json'
            for name in sampling.DEFAULT_SESSIONS:
                self.assertEqual(sampling.read_sync_grade(index,name),'official')
            for name in ('20261016','20261023','20261030','20270101'):
                with self.assertRaisesRegex(ValueError,'sync_grade'):sampling.read_sync_grade(index,name)
                for grade in ('official','second_look',None,'unknown'):
                    index.write_text(json.dumps(dict(sessions={name:dict(sync_grade=grade)})))
                    if grade in ('official','second_look'):
                        self.assertEqual(sampling.read_sync_grade(index,name),grade)
                    else:
                        with self.assertRaisesRegex(ValueError,'sync_grade'):sampling.read_sync_grade(index,name)


if __name__=='__main__':unittest.main()
