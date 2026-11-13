"""Checks for the laboratory live-sensor forecasting script. AI-written (Claude, 12 November 2026)."""
import importlib.util
import math
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("a_lab_train", HERE.parent / "train.py")
lab = importlib.util.module_from_spec(spec)
sys.modules["a_lab_train"] = lab
spec.loader.exec_module(lab)


def synthetic(n=400, seed=1):
    rng = np.random.default_rng(seed)
    grid = np.arange(100, 100 + n)
    values = np.column_stack([25 + rng.normal(0, .1, n).cumsum() * .01, rng.normal(0, 5, n), 25 + rng.normal(0, .01, n)])
    return grid, values


class LabForecastTests(unittest.TestCase):
    def test_features_never_use_later_readings(self):
        grid, values = synthetic()
        before = lab.features_at(values, 200)
        changed = values.copy()
        changed[201:] += 1000.0
        np.testing.assert_array_equal(before, lab.features_at(changed, 200))
        self.assertEqual(len(before), len(lab.FEATURE_NAMES))
        self.assertEqual(len(before), 19)

    def test_baselines_never_use_later_readings(self):
        grid, values = synthetic()
        e1 = lab.build_examples(grid, values, 60)
        changed = values.copy()
        last_origin = int(e1["origin_s"][-1]) - grid[0]
        changed[last_origin + 1:, 1:] += 50.0  # change only future current and air
        e2 = lab.build_examples(grid, changed, 60)
        p1, p2 = lab.baseline_predictions(e1, 60), lab.baseline_predictions(e2, 60)
        for name in lab.BASELINES:
            self.assertEqual(p1[name][-1], p2[name][-1])

    def test_target_is_the_reading_at_origin_plus_horizon(self):
        grid, values = synthetic()
        e = lab.build_examples(grid, values, 120)
        i = 5
        origin = int(e["origin_s"][i])
        self.assertEqual(e["target_c"][i], values[origin - grid[0] + 120, 0])
        self.assertEqual(e["now_c"][i], values[origin - grid[0], 0])
        self.assertTrue(np.all(np.diff(e["origin_s"]) == lab.SPACING_S))

    def test_origins_touching_a_gap_are_skipped(self):
        grid, values = synthetic()
        values[250:260] = np.nan
        e = lab.build_examples(grid, values, 60)
        for origin in e["origin_s"]:
            index = int(origin) - grid[0]
            self.assertTrue(np.all(np.isfinite(values[index - 60:index + 1])))
            self.assertTrue(np.isfinite(values[index + 60, 0]))
        self.assertNotIn(grid[0] + 255, set(e["origin_s"].tolist()))

    def test_record_plan_keeps_the_held_record_out(self):
        plan = lab.record_plan(lab.RECORDS)
        self.assertEqual(len(plan), 3)
        for fold in plan:
            self.assertNotIn(fold["outer_test"], fold["outer_train"])
            self.assertEqual(len(fold["inner"]), 2)
            for inner in fold["inner"]:
                used = set(inner["train_groups"]) | set(inner["validation_groups"])
                self.assertNotIn(fold["outer_test"], used)
                self.assertFalse(set(inner["train_groups"]) & set(inner["validation_groups"]))

    def test_physics_baseline_matches_the_closed_form(self):
        e = {"now_c": np.array([26.0]), "current_a": np.array([-10.0]), "meansq_a2": np.array([64.0]),
             "air_c": np.array([25.0]), "temp_slope": np.array([0.001])}
        p = lab.baseline_predictions(e, 300)
        k = 1 - math.exp(-lab.B * 300)
        self.assertAlmostEqual(p["physics_hold_last"][0], 26 + (25 - 26 + lab.A * 100 / lab.B) * k, places=12)
        self.assertAlmostEqual(p["physics_hold_meansq"][0], 26 + (25 - 26 + lab.A * 64 / lab.B) * k, places=12)
        self.assertAlmostEqual(p["linear_trend"][0], 26.3, places=12)
        self.assertEqual(p["persistence"][0], 26.0)


if __name__ == "__main__":
    unittest.main()
