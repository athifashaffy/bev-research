"""Tests for the model comparison. AI-assisted (Claude, 13 November 2026)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare  # noqa: E402


class Setup(unittest.TestCase):
    def test_paper_models_are_unchanged(self):
        self.assertEqual(compare.GRIDS["hist_gradient_boosting"], [{"max_iter": 40}, {"max_iter": 80}])
        hgb = compare.estimator("hist_gradient_boosting", {"max_iter": 80}).get_params()
        self.assertEqual(hgb, compare.original.estimator("hist_gradient_boosting", {"max_iter": 80}).get_params())
        self.assertEqual((hgb["learning_rate"], hgb["max_depth"], hgb["max_leaf_nodes"], hgb["min_samples_leaf"]),
                         (.08, 3, 7, 20))

    def test_every_model_selects_and_fits_without_leakage(self):
        rng = np.random.default_rng(0)
        names = [f"C{i}" for i in range(9)]
        groups = np.repeat(names, 40)
        x = rng.normal(size=(len(groups), 20)); y = 1e-3 * x[:, 0] + 1e-4 * rng.normal(size=len(groups))
        fold = compare.original.nested_group_plan(names)[0]
        for method in compare.MODELS:
            model, sel = compare.fit_selected(method, x, y, groups, fold)
            self.assertIn(sel["selected"], compare.GRIDS[method])
            self.assertEqual(sel["fits"], 4 * len(compare.GRIDS[method]) + 1)
            self.assertEqual(model.predict(x[:3]).shape, (3,))

    def test_leakage_is_refused(self):
        names = [f"C{i}" for i in range(9)]
        fold = compare.original.nested_group_plan(names)[0]
        bad = {**fold, "inner": [{**fold["inner"][0], "train_groups": fold["inner"][0]["train_groups"] + [fold["outer_test"]]}]}
        x = np.zeros((90, 20)); groups = np.repeat(names, 10)
        with self.assertRaises(AssertionError):
            compare.fit_selected("ridge", x, np.zeros(90), groups, bad)

    def test_r2(self):
        self.assertEqual(compare.r2([1, 2, 3], [1, 2, 3]), 1.)
        self.assertEqual(compare.r2([1, 2, 3], [2, 2, 2]), 0.)


if __name__ == "__main__":
    unittest.main()
