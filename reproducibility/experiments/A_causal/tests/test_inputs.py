"""Regression tests for information availability and numerical feature artifacts."""
import copy
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import inputs as causal
except ImportError:
    causal = None


class InputTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(causal, 'Causal input implementation is missing')
        self.events = [dict(start_s=0., end_s=100., energy_kwh=100/3600),
                       dict(start_s=100., end_s=900., energy_kwh=2.)]

    def test_unfinished_event_total_cannot_change_past_features(self):
        # Would catch using the ongoing event average or its induced temperature.
        original = copy.deepcopy(self.events)
        first, meta = causal.history_as_of(self.events, 150, 2.5, a=.01, b=0.)
        other = copy.deepcopy(self.events)
        other[1]['energy_kwh'] = 200.
        other[1]['end_s'] = 1800.
        second, changed_meta = causal.history_as_of(other, 150, 2.5, a=.01, b=0.)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(meta, changed_meta)
        self.assertEqual(self.events, original)
        self.assertEqual(meta['latest_available_event_end_s'], 100.)
        self.assertEqual(meta['completed_events'], 1)

    def test_completed_event_becomes_available_exactly_at_end(self):
        before, _ = causal.history_as_of(self.events, 99.999, 2.5, a=.01, b=0.)
        after, meta = causal.history_as_of(self.events, 100., 2.5, a=.01, b=0.)
        self.assertEqual(before[-1].tolist(), [25., 0., 25.])
        np.testing.assert_allclose(after[-1], [26., 1., 25.], rtol=0, atol=1e-12)
        self.assertEqual(meta['latest_available_event_end_s'], 100.)

    def test_temperature_advances_with_last_completed_current(self):
        values, _ = causal.history_as_of(self.events, 150., 2.5, a=.01, b=0.)
        np.testing.assert_allclose(values[0], [25.9, 1., 25.], atol=1e-12)
        np.testing.assert_allclose(values[-1], [26.5, 1., 25.], atol=1e-12)

    def test_empty_ledger_uses_explicit_initial_state(self):
        values, meta = causal.history_as_of([], 80., 354.)
        np.testing.assert_array_equal(values, np.tile([25.,0.,25.],(61,1)))
        self.assertEqual(meta['completed_events'], 0)

    def test_invalid_energy_and_overlapping_events_are_rejected(self):
        for change in [dict(energy_kwh=-1.),dict(end_s=float('nan'))]:
            events=copy.deepcopy(self.events);events[0].update(change)
            with self.assertRaises(ValueError):causal.history_as_of(events,150.,2.5)
        events=copy.deepcopy(self.events);events[1]['start_s']=99.
        with self.assertRaises(ValueError):causal.history_as_of(events,150.,2.5)

    def test_constant_channels_have_exact_zero_slopes(self):
        values=np.tile([25.05864372584169,2.206514275058151,25.],(61,1))
        features=causal.stable_features(values,354.,3.)
        self.assertEqual(features[[4,10,16]].tolist(),[0.,0.,0.])

    def test_known_linear_history_and_roundoff_perturbation(self):
        t=np.arange(61)
        values=np.column_stack([25.+.001*t,np.full(61,2.),np.full(61,25.)])
        features=causal.stable_features(values,354.,3.)
        self.assertEqual(features[:6].tolist(),[25.06,25.03,25.,25.06,.001,.001])
        perturbed=values.copy();perturbed[::2,0]+=1e-14
        np.testing.assert_array_equal(features,causal.stable_features(perturbed,354.,3.))

    def test_nonfinite_or_wrong_shape_history_is_rejected(self):
        for values in [np.ones((60,3)),np.full((61,3),np.nan)]:
            with self.assertRaises(ValueError):causal.stable_features(values,354.,3.)


if __name__=='__main__':unittest.main()
