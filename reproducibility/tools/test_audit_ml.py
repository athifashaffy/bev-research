"""Small analytic and adversarial tests; no model training or source writes."""
import copy
import math
import unittest

from audit_ml import AuditError, causal_features, error_metrics, index_predictions, validate_folds


class MetricTests(unittest.TestCase):
    def test_known_errors(self):
        result = error_metrics([1, -2, 3])
        self.assertEqual(result["n_origins"], 3)
        self.assertEqual(result["mae_c"], 2)
        self.assertAlmostEqual(result["rmse_c"], math.sqrt(14 / 3))
        self.assertEqual(result["max_absolute_error_c"], 3)

    def test_small_nonzero_errors_are_preserved(self):
        result = error_metrics([1e-9, -2e-9])
        self.assertAlmostEqual(result["mae_c"], 1.5e-9, delta=1e-24)
        self.assertGreater(result["rmse_c"], 0)

    def test_empty_and_nonfinite_rejected(self):
        for values in ([], [float("nan")], [float("inf")]):
            with self.assertRaises(AuditError):
                error_metrics(values)


class IntegrityTests(unittest.TestCase):
    def test_duplicate_prediction_origin_rejected(self):
        row = {"case": "A", "horizon_s": "60", "origin_s": "100",
               "target_s": "160", "method": "ridge", "origin_temperature_c": "25",
               "true_temperature_c": "26", "predicted_temperature_c": "25.5", "error_c": "-0.5"}
        with self.assertRaisesRegex(AuditError, "Duplicate prediction"):
            index_predictions([row, dict(row)])

    @staticmethod
    def valid_plan():
        cases = list("ABCDEFGHI")
        plan = []
        for held in cases:
            train = [c for c in cases if c != held]
            inner = []
            for i in range(4):
                valid = train[i::4]
                inner.append({"inner_fold": i, "train_groups": [c for c in train if c not in valid],
                              "validation_groups": valid})
            plan.append({"outer_test": held, "outer_train": train, "inner": inner})
        return cases, plan

    def test_valid_fold_plan(self):
        cases, plan = self.valid_plan()
        self.assertEqual(len(validate_folds(plan, cases)), 9)

    def test_heldout_case_in_inner_training_rejected(self):
        cases, plan = self.valid_plan()
        broken = copy.deepcopy(plan)
        broken[0]["inner"][0]["train_groups"][0] = "A"
        with self.assertRaisesRegex(AuditError, "held-out|leak"):
            validate_folds(broken, cases)

    def test_heldout_case_in_outer_training_rejected(self):
        cases, plan = self.valid_plan()
        plan[0]["outer_train"][0] = "A"
        with self.assertRaisesRegex(AuditError, "held-out|leak"):
            validate_folds(plan, cases)

    def test_future_changes_do_not_change_causal_features(self):
        grid = {t: (25 + t / 100, t / 10, 25) for t in range(121)}
        expected = causal_features(grid, 60, 100, 3)
        for t in range(61, 121):
            grid[t] = (10000, -999, 42)
        self.assertEqual(causal_features(grid, 60, 100, 3), expected)

    def test_missing_history_point_is_rejected(self):
        grid = {t: (25, 1, 25) for t in range(61) if t != 30}
        with self.assertRaisesRegex(AuditError, "Missing causal history"):
            causal_features(grid, 60, 100, 3)


if __name__ == "__main__":
    unittest.main()
