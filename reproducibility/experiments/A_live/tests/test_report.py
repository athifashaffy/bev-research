"""AI-assisted independent metric and repeatability verification tests."""
from pathlib import Path
import datetime
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report import independent_metrics, strip_timing, check_metric, audit_clock, comparison_narrative


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

    def test_audit_date_comes_from_one_instant_in_toronto(self):
        instant = datetime.datetime(2027, 1, 2, 2, 30, tzinfo=datetime.timezone.utc)
        clock = audit_clock(instant)
        self.assertEqual(clock["date_local"], "2027-01-01")
        self.assertEqual(clock["date_display"], "1 January 2027")
        self.assertEqual(clock["utc"], instant.isoformat())

    def test_conclusions_follow_changed_metrics_and_no_wins(self):
        methods = ["persistence", "linear_trend", "physics_hold", "hist_gradient_boosting"]
        metrics = {(h, m): {"rmse_c": 2., "mae_c": 2.} for h in (60, 120) for m in methods}
        metrics[(60, "hist_gradient_boosting")] = {"rmse_c": 1., "mae_c": 1.}
        metrics[(120, "hist_gradient_boosting")] = {"rmse_c": 3., "mae_c": 3.}
        decisions = [{"horizon_s": 60, "boosting_beats_all_on_both": True},
                     {"horizon_s": 120, "boosting_beats_all_on_both": False}]
        notes = comparison_narrative(metrics, decisions)
        self.assertIn("both pooled scores: 1 min.", notes)
        self.assertIn("lower pooled MAE than boosting: 2 min.", notes)
        metrics[(60, "hist_gradient_boosting")] = {"rmse_c": 3., "mae_c": 3.}
        decisions[0]["boosting_beats_all_on_both"] = False
        self.assertIn("both pooled scores: none.", comparison_narrative(metrics, decisions))


if __name__ == "__main__":
    unittest.main()
