"""AI-assisted independent metric and repeatability verification tests."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report import independent_metrics, strip_timing, check_metric


class ReportTests(unittest.TestCase):
    def test_metrics_use_signed_prediction_errors(self):
        rows = [dict(target_temperature_c="10", predicted_temperature_c="13"),
                dict(target_temperature_c="8", predicted_temperature_c="4")]
        result = independent_metrics(rows)
        self.assertEqual(result["n_origins"], 2)
        self.assertEqual(result["mae_c"], 3.5)
        self.assertEqual(result["max_absolute_error_c"], 4)
        self.assertAlmostEqual(result["rmse_c"], (25 / 2) ** .5)

    def test_bad_reported_score_is_rejected(self):
        with self.assertRaises(AssertionError):
            check_metric("rmse_c", .1, .1001)
        with self.assertRaises(AssertionError):
            check_metric("rmse_c", .1, float("nan"))

    def test_only_timing_is_ignored(self):
        a = {"elapsed_s": 1, "folds": [{"elapsed_s": 2, "score": 3}]}
        b = {"elapsed_s": 8, "folds": [{"elapsed_s": 9, "score": 3}]}
        self.assertEqual(strip_timing(a), strip_timing(b))
        b["folds"][0]["score"] = 4
        self.assertNotEqual(strip_timing(a), strip_timing(b))


if __name__ == "__main__":
    unittest.main()
