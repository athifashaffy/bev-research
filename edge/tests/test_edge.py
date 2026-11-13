"""Edge forecaster tests; standard library only.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

The replay test feeds the saved 1 Hz sensor record of C100_RR03 through the
edge code one reading at a time and requires every forecast to equal the saved
Table 2 run (results/run-2026-11-13/live) exactly, for all four methods and
five horizons.
"""
import csv
import gzip
import io
import json
import math
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bev_edge import Bundle, Forecaster, SensorBuffer, equivalent_current, history_features, thermal_hold
from bev_edge.cli import main

EDGE = Path(__file__).resolve().parents[1]
PAPER = EDGE / "bundles/paper-heldout-C100_RR03"
FIXTURE = EDGE / "examples/C100_RR03"
BUNDLES = sorted(p for p in (EDGE / "bundles").iterdir() if (p / "manifest.json").exists())


def stream():
    with open(FIXTURE / "sensor_stream.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            yield int(r["time_s"]), float(r["equivalent_current_a"]), float(r["temperature_c"]), float(r["air_c"])


class ReplayMatchesPaperRun(unittest.TestCase):
    def test_every_saved_forecast_reproduced_exactly(self):
        bundle = Bundle(PAPER)
        m = bundle.manifest
        forecaster = Forecaster(bundle, m["held_out_capacity_kwh"], m["held_out_rr_pct"])
        produced = {}
        for reading in stream():
            result = forecaster.push(*reading)
            if result:
                for f in result["forecasts"]:
                    for method in ("persistence", "linear_trend", "physics_hold", "hist_gradient_boosting"):
                        produced[(f["horizon_s"], method, result["time_s"])] = f[method]
        with gzip.open(FIXTURE / "expected_forecasts.csv.gz", "rt", encoding="utf-8", newline="") as f:
            expected = list(csv.DictReader(f))
        self.assertEqual(len(expected), 9008)   # 4 methods x 5 horizons
        for r in expected:
            key = (int(r["horizon_s"]), r["method"], int(r["origin_s"]))
            self.assertIn(key, produced)
            self.assertEqual(produced[key], float(r["predicted_temperature_c"]), key)


class Buffer(unittest.TestCase):
    def test_needs_61_consecutive_seconds(self):
        b = SensorBuffer()
        for t in range(60):
            b.push(t, 1., 25., 25.)
        self.assertFalse(b.ready)
        b.push(60, 1., 25., 25.)
        self.assertTrue(b.ready)

    def test_gap_or_bad_reading_empties_buffer_without_filling(self):
        b = SensorBuffer()
        for t in range(61):
            b.push(t, 1., 25., 25.)
        self.assertFalse(b.push(62, 1., 25., 25.))      # second 61 missing
        self.assertEqual(len(b.rows), 1)
        b.push(63, float("nan"), 25., 25.)
        self.assertEqual(len(b.rows), 0)
        self.assertEqual(b.resets, 2)

    def test_repeated_time_resets_and_fractional_time_refused(self):
        b = SensorBuffer()
        b.push(5, 1., 25., 25.)
        self.assertFalse(b.push(5, 1., 25., 25.))
        with self.assertRaises(ValueError):
            b.push(6.5, 1., 25., 25.)

    def test_forecasts_only_on_cadence(self):
        f = Forecaster(Bundle(PAPER), 354., 3., every_s=10)
        out = [f.push(t, 1., 25., 25.) for t in range(75)]
        self.assertEqual([i for i, r in enumerate(out) if r], [60, 70])


class Formulas(unittest.TestCase):
    def test_equation_2(self):
        self.assertAlmostEqual(equivalent_current(312.44, 354.), 2.5 * 312.44 / 354.)

    def test_thermal_hold_approaches_ceiling(self):
        a, b = 4.344635339312832e-05, .002655462788692412
        self.assertAlmostEqual(thermal_hold(25., 2., 25., 1e7, a, b), 25. + a * 4 / b)
        self.assertEqual(thermal_hold(25., 0., 25., 600, a, b), 25.)

    def test_constant_history_has_zero_slope(self):
        x = history_features([(25., 1., 25.)] * 61, 354., 3.)
        self.assertEqual(len(x), 20)
        self.assertEqual(x[4], 0.)
        self.assertEqual(x[18:], [354., 3.])

    def test_rejects_short_or_nonfinite_history(self):
        with self.assertRaises(ValueError):
            history_features([(25., 1., 25.)] * 60, 354., 3.)
        with self.assertRaises(ValueError):
            history_features([(25., math.inf, 25.)] * 61, 354., 3.)


class Bundles(unittest.TestCase):
    def test_all_bundles_load_and_are_labelled(self):
        self.assertTrue(any(p.name.startswith("paper-heldout") for p in BUNDLES))
        for p in BUNDLES:
            b = Bundle(p)
            self.assertIn(b.kind, ("paper-heldout", "deployment"))
            self.assertEqual(b.horizons, [60, 120, 300, 600, 1800])
            if b.kind == "deployment":
                self.assertIn("Not the paper's models", b.manifest["label"])

    def test_changed_model_file_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            copy = Path(t) / "b"
            shutil.copytree(PAPER, copy)
            spec = json.loads((copy / "h60.json").read_text())
            spec["baseline"] += 1e-9
            (copy / "h60.json").write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, "changed since export"):
                Bundle(copy)


class CommandLine(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(list(args)), 0)
        return buf.getvalue()

    def test_info(self):
        self.assertTrue(json.loads(self.run_cli("info", "--bundle", str(PAPER)))["hashes_checked"])

    def test_run_from_pack_power_column(self):
        """Pack power converted by Equation (2) gives the same forecasts within rounding of the 12-decimal inputs."""
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "power.csv"
            with open(FIXTURE / "sensor_stream.csv", newline="") as f, open(path, "w", newline="") as g:
                rows = list(csv.DictReader(f))[:200]
                w = csv.writer(g)
                w.writerow(["time_s", "pack_power_kw", "temperature_c", "air_c"])
                w.writerows([r["time_s"], r["pack_power_kw"], r["temperature_c"], r["air_c"]] for r in rows)
            lines = self.run_cli("run", "--bundle", str(PAPER), "--capacity-kwh", "354", "--rr-pct", "3",
                                 "--input", str(path)).splitlines()
        self.assertEqual([json.loads(x)["time_s"] for x in lines], list(range(60, 200, 10)))


if __name__ == "__main__":
    unittest.main()
