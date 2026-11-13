"""Tests for check_claims.py (AI-assisted). Uses temporary folders only."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from check_claims import agrees, check, find_numbers, main, resolve_all, safe_eval, ClaimError


class NumberTests(unittest.TestCase):
    def test_rounding_to_written_decimals(self):
        self.assertTrue(agrees(85.6, 1, 85.5989))
        self.assertTrue(agrees(86, 0, 85.5989))
        self.assertFalse(agrees(85.7, 1, 85.5989))

    def test_finds_plain_comma_negative_and_scientific(self):
        found = {v for _, v, _ in find_numbers("Uses 1,500 m, −12% and a = 4.3446 × 10⁻⁵ K.")}
        self.assertIn(1500, found)
        self.assertIn(-12, found)
        self.assertTrue(any(abs(v - 4.3446e-5) < 1e-12 for v in found))

    def test_skips_identifiers_refs_dates_and_sections(self):
        found = [t for t, _, _ in find_numbers("C100_RR03 in Section 5.1, ref [23], on 9 Nov 2026, see Table 4 and Z50.")]
        self.assertEqual(found, [])

    def test_safe_eval_rejects_code(self):
        self.assertAlmostEqual(safe_eval("2 * x + sqrt(4)", {"x": 3}), 8)
        with self.assertRaises(ClaimError):
            safe_eval("__import__('os')", {})


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        Path("cases.csv").write_text("case,reserve_min\nA,85.5989\nB,71.8833\n")
        Path("model.json").write_text(json.dumps({"b": 0.0026554, "folds": [{"a": 1}, {"a": 1}, {"a": 2}]}))
        con = sqlite3.connect("db.sqlite")
        con.execute("create table t(x real)")
        con.execute("insert into t values (58.9278)")
        con.commit()
        con.close()
        self.claims = [
            {"id": "res_a", "keywords": ["reserve"], "anchors": ["case A", "reserve"],
             "source": {"kind": "csv", "file": "cases.csv", "where": {"case": "A"}, "column": "reserve_min"}},
            {"id": "tau", "keywords": ["tau", "τ"], "source": {"kind": "json", "file": "model.json", "path": ["b"]}},
            {"id": "tau_s", "keywords": ["τ"], "source": {"kind": "expr", "expr": "1 / tau"}},
            {"id": "a_one", "keywords": ["folds"], "source": {"kind": "json", "file": "model.json", "path": ["folds"], "count_where": {"a": 1}}},
            {"id": "climb", "keywords": ["kWh"], "source": {"kind": "sqlite", "file": "db.sqlite", "sql": "select x from t"}},
            {"id": "spec", "keywords": ["spec"], "value": 354, "source": {"kind": "external", "url": "https://example.com"}}]

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_statuses(self):
        values = resolve_all(self.claims, Path("."))["values"]
        rows, mism = check("Case A reaches the reserve at 85.6 min. τ = 376.6 s. Used 58.93 kWh. Spec says 354. "
                           "It took 2 folds. Mystery 42 units.", self.claims, values)
        status = {r["number"]: r["status"] for r in rows}
        self.assertEqual(status["85.6"], "matched")
        self.assertEqual(status["376.6"], "matched")
        self.assertEqual(status["58.93"], "matched")
        self.assertEqual(status["354"], "external")
        self.assertEqual(status["2"], "matched")
        self.assertEqual(status["42"], "unverified")
        self.assertEqual(mism, [])

    def test_mismatch_detected(self):
        values = resolve_all(self.claims, Path("."))["values"]
        _, mism = check("Case A reaches the reserve at 90.1 min.", self.claims, values)
        self.assertEqual([m["claim"] for m in mism], ["res_a"])

    def test_cli_writes_report_and_fails_on_mismatch(self):
        Path("claims.json").write_text(json.dumps({"claims": self.claims}))
        Path("ok.txt").write_text("Case A reaches the reserve at 85.6 min.")
        Path("bad.txt").write_text("Case A reaches the reserve at 90 min.")
        self.assertEqual(main(["--text", "ok.txt", "--claims", "claims.json", "--output", "r1"]), 0)
        self.assertTrue(Path("r1/CLAIMS_REPORT.md").is_file())
        self.assertEqual(main(["--text", "bad.txt", "--claims", "claims.json", "--output", "r2"]), 1)


if __name__ == "__main__":
    unittest.main()
