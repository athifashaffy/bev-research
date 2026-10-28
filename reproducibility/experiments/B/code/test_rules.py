"""Synthetic tests: causal clocks, strict thresholds, gap resets and units."""
import math
import unittest
try:
    from rules import causal_grid, trailing_rate, alarm_response, voltage_condition
except ImportError:
    causal_grid=trailing_rate=alarm_response=voltage_condition=None


class InterfaceTest(unittest.TestCase):
    def test_requested_rule_interface_exists(self):
        self.assertTrue(callable(causal_grid),'Causal rule implementation is missing')


@unittest.skipIf(causal_grid is None,'Implementation not written yet')
class RuleTests(unittest.TestCase):
    def test_no_future_interpolation_on_irregular_clock(self):
        g=causal_grid([0,0.9,1.9,2.9],[10,20,30,40],gap_limit=2)
        self.assertEqual(g['time_s'],[0.,1.,2.])
        self.assertEqual(g['values'],[10.,20.,30.])
        self.assertEqual(g['measurement_time_s'],[0.,0.9,1.9])

    def test_future_append_cannot_change_past_grid(self):
        a=causal_grid([0,.9,1.9,2.9],[10,20,30,40],gap_limit=2)
        b=causal_grid([0,.9,1.9,2.9,99],[10,20,30,40,999],gap_limit=2)
        self.assertEqual(a['values'],b['values'][:3])
        self.assertEqual(a['segment'],b['segment'][:3])

    def test_gap_has_no_held_value_and_restarts_segment(self):
        g=causal_grid([0,1,5,6],[60,60,60,60],gap_limit=1.01)
        self.assertTrue(math.isnan(g['values'][2]))
        self.assertTrue(math.isnan(g['values'][3]))
        self.assertNotEqual(g['segment'][1],g['segment'][5])
        self.assertIsNone(alarm_response(g['time_s'],g['values'],g['segment'],50)['alarm_s'])

    def test_subsecond_missing_sample_prevents_history_bridging(self):
        g=causal_grid([0,.2,.4,.8,1,2],[50,50,None,50,50,50],gap_limit=2)
        self.assertNotEqual(g['segment'][0],g['segment'][1])

    def test_rate_requires_full_past_sixty_seconds(self):
        t=list(range(66));g=causal_grid(t,[20+x/60 for x in t])
        r=trailing_rate(g['values'],g['segment'])
        self.assertTrue(all(x is None for x in r[:60]))
        self.assertAlmostEqual(r[60],1.,places=10)
        self.assertAlmostEqual(r[65],1.,places=10)

    def test_rate_does_not_bridge_one_missing_grid_sample(self):
        y=[float(x) for x in range(125)];y[61]=math.nan
        g=causal_grid(range(125),y)
        r=trailing_rate(g['values'],g['segment'])
        self.assertIsNone(r[62]);self.assertIsNone(r[121])
        self.assertAlmostEqual(r[122],60.)

    def test_fixed_strict_threshold_and_elapsed_debounce(self):
        self.assertIsNone(alarm_response(range(7),[50.]*7,[0]*7,50)['alarm_s'])
        a=alarm_response(range(7),[51.]*7,[0]*7,50)
        self.assertEqual(a['first_crossing_s'],0.)
        self.assertEqual(a['alarm_s'],5.)

    def test_false_predicate_resets_debounce(self):
        y=[51,51,51,50,51,51,51,51,51,51]
        self.assertEqual(alarm_response(range(10),y,[0]*10,50)['alarm_s'],9.)

    def test_rate_units_and_strict_threshold_roundoff(self):
        g=causal_grid(range(71),[20+x/60 for x in range(71)])
        r=trailing_rate(g['values'],g['segment'])
        self.assertIsNone(alarm_response(g['time_s'],r,g['segment'],1,rate=True)['alarm_s'])
        self.assertEqual(alarm_response(g['time_s'],r,g['segment'],.5,rate=True)['alarm_s'],65.)

    def test_nonfinite_and_nonincreasing_clocks_rejected(self):
        for t in ([0,1,1],[0,2,1],[0,1,math.nan]):
            with self.assertRaises(ValueError):causal_grid(t,[50,50,50])

    def test_voltage_condition_bracket_and_confirmation(self):
        t=list(range(-10,21));u=[3.4]*15+[0.]*16
        r=voltage_condition(t,u)
        self.assertEqual(r['condition_start_s'],5.)
        self.assertEqual(r['confirmed_s'],10.)
        self.assertEqual(r['bracket_s'],[4.,5.])

    def test_voltage_condition_needs_normal_context_and_no_gap(self):
        self.assertIsNone(voltage_condition(list(range(-10,10)),[0.]*20)['condition_start_s'])
        t=list(range(-10,6))+[20,21,22,23,24]
        u=[3.4]*15+[0.]*6
        self.assertIsNone(voltage_condition(t,u)['condition_start_s'])


if __name__=='__main__':unittest.main(verbosity=2)
