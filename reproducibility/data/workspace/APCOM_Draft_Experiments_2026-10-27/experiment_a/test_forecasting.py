"""Hand-derived leakage, causal-processing and unit checks, written before fits."""
import math
import unittest
import numpy as np

try:
    import forecasting as f
except ImportError:
    f = None


class ForecastingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(f, "Experiment A forecasting implementation is absent")

    def test_outer_and_inner_whole_configuration_groups_are_disjoint(self):
        # Catches any reuse of the outer test case in inner selection or scaling.
        groups = [f"case_{i}" for i in range(9)]
        plan = f.nested_group_plan(groups)
        self.assertEqual([p["outer_test"] for p in plan], groups)
        for fold in plan:
            train = set(fold["outer_train"])
            self.assertEqual(len(train), 8)
            self.assertNotIn(fold["outer_test"], train)
            seen = []
            for inner in fold["inner"]:
                a, b = set(inner["train_groups"]), set(inner["validation_groups"])
                self.assertFalse(a & b)
                self.assertEqual(a | b, train)
                self.assertNotIn(fold["outer_test"], a | b)
                seen.extend(b)
            self.assertEqual(sorted(seen), sorted(train))

    def test_resampling_uses_only_past_values_and_does_not_bridge_gap(self):
        # At integer t=1 the source t=0.8 can be held; future t=1.2 cannot enter.
        t, y = f.resample_past_held([0, .8, 1.2, 3, 4], [[10], [20], [90], [40], [50]])
        self.assertEqual(t.tolist(), [0, 1, 2, 3, 4])
        self.assertEqual(y[1, 0], 20)
        self.assertTrue(math.isnan(y[2, 0]))
        self.assertEqual(y[3, 0], 40)

    def test_future_values_cannot_change_origin_features(self):
        x = np.array([[25 + i / 10, 2, 25] for i in range(121)], dtype=float)
        a = f.features_at(x, 60, 354, 3)
        x[61:] = 999
        b = f.features_at(x, 60, 354, 3)
        np.testing.assert_array_equal(a, b)
        self.assertAlmostEqual(a[0], 31)
        self.assertAlmostEqual(a[1], 28)
        self.assertAlmostEqual(a[4], .1)
        self.assertAlmostEqual(a[5], .1)
        self.assertEqual(a[-2:].tolist(), [354, 3])

    def test_history_gap_or_forecast_gap_excludes_origin_for_all_methods(self):
        x = np.array([[25 + i / 10, 2, 25] for i in range(241)], dtype=float)
        x[100] = np.nan
        examples = f.build_examples("test", np.arange(241), x, 354, 3, 60, spacing_s=10)
        origins = examples["origin_s"].tolist()
        self.assertNotIn(60, origins)  # future path crosses gap at 100 s
        self.assertNotIn(120, origins)  # history crosses gap at 100 s
        self.assertIn(170, origins)

    def test_direct_target_uses_horizon_seconds_not_minutes(self):
        x = np.array([[25 + i / 10, 2, 25] for i in range(121)], dtype=float)
        examples = f.build_examples("test", np.arange(121), x, 354, 3, 60, spacing_s=10)
        self.assertEqual(examples["origin_s"].tolist(), [60])
        self.assertAlmostEqual(examples["delta_c"][0], 6)
        self.assertAlmostEqual(examples["target_c"][0], 37)

    def test_ode_forecast_has_ampere_squared_and_second_units(self):
        self.assertAlmostEqual(f.physics_forecast(25, 2, 25, 60, a=.01, b=0), 27.4)
        self.assertAlmostEqual(f.physics_forecast(25, 0, 20, 1, a=0, b=1), 20 + 5 / math.e)

    def test_metrics_keep_small_celsius_errors_and_use_sample_weights(self):
        m = f.error_metrics(np.array([0., 0.]), np.array([.003, .004]))
        self.assertAlmostEqual(m["mae_c"], .0035)
        self.assertAlmostEqual(m["rmse_c"], math.sqrt(.0000125))
        self.assertGreater(m["rmse_c"], 0)

    def test_nonincreasing_source_clock_is_rejected(self):
        with self.assertRaises(ValueError):
            f.resample_past_held([0, 1, 1], [[10], [20], [30]])

    def test_outer_case_extremes_cannot_affect_scaler_selection_or_fit(self):
        # Catches preprocessing or hyperparameter selection on the outer test case.
        groups = np.array([f"case_{i}" for i in range(9)])
        fold = f.nested_group_plan(groups)[-1]
        x = np.arange(9, dtype=float).reshape(-1, 1)
        y = np.arange(9, dtype=float) * 2
        first, audit = f.fit_selected("ridge", x, y, groups, fold)
        x[-1, 0], y[-1] = 1e9, -1e12
        second, changed = f.fit_selected("ridge", x, y, groups, fold)
        self.assertAlmostEqual(first.named_steps["scale"].mean_[0], 3.5)
        self.assertAlmostEqual(second.named_steps["scale"].mean_[0], 3.5)
        self.assertEqual(audit["selected_parameters"], changed["selected_parameters"])
        np.testing.assert_array_equal(first.predict([[3.]]), second.predict([[3.]]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
