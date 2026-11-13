"""Regression checks for the event-ledger comparison's data contract."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location(
    "thermal_chain_under_test", ROOT / "experiments/reproduce_thermal_chain.py")
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)

CASES = [f"C{size}_RR{road}" for size in ("080", "100", "120")
         for road in ("02", "03", "04")]


class ThermalChainContractTests(unittest.TestCase):
    def setUp(self):
        self.reference = pd.DataFrame({"case": CASES, "capacity_kwh": [354.] * 9})
        self.ledger = pd.DataFrame([
            {"case": case, "event_index": 1, "state": "Hauling",
             "duration_min": 1., "battery_energy_kwh": 1., "end_min": 1.}
            for case in CASES
        ])
        expected = float(chain.thermal.step(
            25., chain.thermal.equivalent_current(60., 354.), 60., 25.))
        self.saved = {case: pd.DataFrame({"time_s": [60.],
                                        "temperature_c": [expected]})
                      for case in CASES}

    def run_main(self):
        stream = io.StringIO()
        with tempfile.TemporaryDirectory() as output:
            with patch.object(chain, "load_event_ledger", return_value=self.ledger), \
                    patch.object(chain.datasets, "reserve_summary", return_value=self.reference), \
                    patch.object(chain.datasets, "nominal_traces",
                                 side_effect=lambda case: self.saved[case]), \
                    patch.object(sys, "argv", ["reproduce_thermal_chain.py", "--out", output]), \
                    redirect_stdout(stream):
                status = chain.main()
        return status, stream.getvalue()

    def test_missing_configuration_cannot_report_success(self):
        self.ledger = self.ledger[self.ledger["case"] != CASES[0]]
        status, _ = self.run_main()
        self.assertNotEqual(status, 0)

    def test_no_matching_timestamps_cannot_report_success(self):
        self.saved[CASES[0]]["time_s"] = 61.
        status, _ = self.run_main()
        self.assertNotEqual(status, 0)

    def test_timestamp_matching_has_no_relative_tolerance(self):
        self.saved[CASES[0]]["time_s"] = 60.0001
        status, _ = self.run_main()
        self.assertNotEqual(status, 0)

    def test_duplicate_saved_timestamps_cannot_be_silently_selected(self):
        self.saved[CASES[0]] = pd.concat([
            self.saved[CASES[0]], self.saved[CASES[0]].assign(temperature_c=90.)
        ], ignore_index=True)
        status, _ = self.run_main()
        self.assertNotEqual(status, 0)

    def test_nonfinite_saved_temperature_cannot_report_success(self):
        self.saved[CASES[0]]["temperature_c"] = np.nan
        status, _ = self.run_main()
        self.assertNotEqual(status, 0)

    def test_partial_endpoint_comparison_is_identified_as_such(self):
        later = self.ledger.assign(event_index=2, end_min=2.)
        self.ledger = pd.concat([self.ledger, later], ignore_index=True)
        status, output = self.run_main()
        self.assertEqual(status, 0)
        self.assertIn("matched event endpoints only", output)
        self.assertIn("Partial endpoint comparison", output)


if __name__ == "__main__":
    unittest.main()
