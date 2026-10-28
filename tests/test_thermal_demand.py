"""Demand-table regression checks against independently audited native ledgers."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("thermal_demand_under_test", ROOT / "experiments/thermal_demand.py")
demand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demand)

# Independently reconstructed native SQLite event ledgers, 2026-10-28 audit:
# case, own-reserve energy (kWh), own-reserve time (min), completed tonnes,
# common-window mean power (kW). Common window is 68.03897261395167 min.
NATIVE = [
    ("C080_RR02", 169.92, 72.36691651810074, 90, 133.26071793692395),
    ("C080_RR03", 169.92, 70.05596363778325, 90, 141.72802374421096),
    ("C080_RR04", 169.92, 68.03897261395167, 90, 149.84353243907498),
    ("C100_RR02", 212.4, 88.34161317289522, 135, 149.44453002626267),
    ("C100_RR03", 212.4, 85.5989351257934, 135, 159.3908162579688),
    ("C100_RR04", 212.4, 71.88331196125137, 90, 168.80477414350383),
    ("C120_RR02", 254.88, 108.08589338172511, 180, 150.8009788905915),
    ("C120_RR03", 254.88, 93.35031312083146, 135, 160.73079974249657),
    ("C120_RR04", 254.88, 90.62932934508058, 135, 170.2583418061959),
]


class ThermalDemandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = demand.build_table().set_index("case")

    def test_own_reserve_mean_uses_all_state_energy_not_right_endpoint_power(self):
        for case, energy, minutes, _, _ in NATIVE:
            with self.subTest(case=case):
                self.assertAlmostEqual(self.table.loc[case, "mean_power_kw"], energy * 60.0 / minutes, places=9)

    def test_completed_tonnes_include_startup_delivery(self):
        self.assertEqual(self.table.loc["C100_RR03", "tonnes"], 135)
        for case, _, _, tonnes, _ in NATIVE:
            with self.subTest(case=case):
                self.assertEqual(self.table.loc[case, "tonnes"], tonnes)

    def test_common_and_own_reserve_windows_are_explicit_and_distinct(self):
        self.assertEqual(set(self.table["window"]), {"own_reserve"})
        for case, energy, minutes, _, common_power in NATIVE:
            with self.subTest(case=case):
                self.assertAlmostEqual(self.table.loc[case, "window_min"], minutes, places=9)
                self.assertAlmostEqual(self.table.loc[case, "window_energy_kwh"], energy, places=9)
                self.assertAlmostEqual(self.table.loc[case, "common_window_mean_power_kw"], common_power, places=9)


if __name__ == "__main__":
    unittest.main()
