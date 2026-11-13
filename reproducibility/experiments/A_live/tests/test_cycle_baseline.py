"""AI-assisted tests of causal seasonal-naive predictions and period fitting."""
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import cycle_baseline as cycle
except ModuleNotFoundError:
    cycle = None


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(cycle, "Cycle baseline is not implemented")

    def test_known_period_is_recovered_without_temperature_labels(self):
        # Asymmetric repeating current; amplitude and offset must not change lag.
        current = np.tile([0., 1., 4., 2., -1., 3., 1.], 12)
        result = cycle.estimate_period(current, 4, 10)
        self.assertEqual(result["period_s"], 7)
        self.assertAlmostEqual(result["correlation"], 1.)
        self.assertEqual(cycle.estimate_period(20 + 3 * current, 4, 10)["period_s"], 7)

    def test_constant_or_short_signal_rejects_an_invented_period(self):
        for current in (np.ones(100), np.arange(5.), np.array([0., np.nan] * 20)):
            with self.subTest(current=current), self.assertRaises(ValueError):
                cycle.estimate_period(current, 4, 10)

    def test_test_configuration_cannot_choose_its_own_period(self):
        currents = {"a": np.tile([0., 3., 1., 2., -1., 4., 2.], 12),
                    "b": np.tile([2., 0., 1., 4., 1., 3., -1.], 12),
                    "test": np.full(84, np.nan)}
        fitted = cycle.fit_period(currents, ["a", "b"], "test", 4, 10)
        self.assertEqual(fitted["period_s"], 7)
        self.assertEqual(set(fitted["training_estimates"]), {"a", "b"})
        with self.assertRaises(ValueError):
            cycle.fit_period(currents, ["a", "test"], "test", 4, 10)

    def test_forecast_repeats_last_observed_cycle_across_multiple_cycles(self):
        # Last observed time = 9. Period 4. Future times 10, 13, 14, 18
        # reuse observed times 6, 9, 6, 6 respectively.
        prefix = 25 + np.arange(10.) / 10
        for horizon, expected, source in [(1, 25.6, 6), (4, 25.9, 9),
                                           (5, 25.6, 6), (9, 25.6, 6)]:
            with self.subTest(horizon=horizon):
                p = cycle.predict_prefix(prefix, horizon, 4)
                self.assertEqual(p["prediction_c"], expected)
                self.assertEqual(p["source_s"], source)
                self.assertFalse(p["fallback"])

    def test_startup_falls_back_only_when_same_phase_is_unavailable(self):
        prefix = np.array([25., 26.])
        self.assertEqual(cycle.predict_prefix(prefix, 1, 4),
                         {"prediction_c": 26., "source_s": 1, "fallback": True})
        self.assertFalse(cycle.predict_prefix(prefix, 3, 4)["fallback"])

    def test_mutating_future_cannot_change_prediction(self):
        data = np.arange(20.)
        a = cycle.predict_prefix(data[:10], 5, 4)
        data[10:] = np.nan
        self.assertEqual(a, cycle.predict_prefix(data[:10], 5, 4))

    def test_bad_horizons_periods_or_temperatures_rejected(self):
        for h, period in [(0, 4), (-1, 4), (1.5, 4), (1, 0), (1, 2.5)]:
            with self.subTest(h=h, period=period), self.assertRaises(ValueError):
                cycle.predict_prefix(np.array([25., 26.]), h, period)
        for prefix in ([], [np.nan], [[1., 2.]]):
            with self.assertRaises(ValueError):
                cycle.predict_prefix(prefix, 1, 4)


if __name__ == "__main__":
    unittest.main()
