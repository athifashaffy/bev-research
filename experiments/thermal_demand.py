"""Thermal demand and reserve windows for the nine configurations (Table 2).

Question
    Across three pack capacities and three rolling resistances, how much power
    and energy does the duty cycle demand, how long does the truck run before
    the energy reserve is reached, and how far does the modelled cell surface
    rise?

Protocol
    Each configuration is run to its own reserve endpoint, defined as 60 % of
    nominal capacity and representing an 80 % to 20 % state-of-charge
    excursion. The raw simulation may continue past that point; external
    analysis stops there. A common-window variant is also reported so the nine
    can be compared over identical elapsed time.

The result, stated plainly
    Peak rise is 0.043 to 0.093 degrees C and the margin to the declared
    60 degrees C screen is 34.907 to 34.957 degrees C. That is a spread of
    0.05 degrees C across all nine configurations, against a 35 degrees C
    margin, so there is no margin comparison to be drawn between them. The
    calculation produces a small normal response under its assumed parameters.
    It cannot exclude actual pack thermal risk or identify pack safety limits.

    Capacity, vehicle mass and available power vary together in the archived
    cases, so these compare whole vehicle configurations and do not isolate a
    pure battery-capacity effect.

Usage
    python experiments/thermal_demand.py [--out DIR]
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from bev_research import datasets  # noqa: E402
from bev_research.config import (DATASHEET_OPERATING_C, RESERVE_FRACTION,
                                 RESIDUAL_LO_C, STUDY_SCREEN_C, Z50,
                                 thermal_note)  # noqa: E402


def build_table() -> pd.DataFrame:
    """Combine trace temperatures with archived all-state energy accounting.

    Mean power and completed production use operations_comparison.csv, whose
    event-ledger totals include stationary consumption and the clipped reserve
    event. Samples at event boundaries carry the next event's power, so
    right-endpoint power quadrature is inappropriate. Complete recurring cycles
    exclude the initial delivery; completed tonnes must include that delivery.
    Common-window demand is labelled separately from each own-reserve window.
    """
    traces = datasets.nominal_traces()
    stored = datasets.reserve_summary().set_index("case")
    operations = datasets.operations_comparison().set_index("case")

    rows = []
    for case, sub in traces.groupby("case"):
        sub = sub.sort_values("time_s")
        peak_c = float(sub["temperature_c"].max())
        ref = stored.loc[case]
        operation = operations.loc[case]
        window_min = float(operation["reserve_time_min"])
        window_energy_kwh = float(operation["reserve_energy_kwh"])
        mean_power = 60.0 * window_energy_kwh / window_min

        rows.append(dict(
            case=case,
            capacity_kwh=float(ref["capacity_kwh"]),
            rr_percent=int(ref["rr_percent"]),
            window="own_reserve",
            window_min=window_min,
            window_energy_kwh=window_energy_kwh,
            mean_power_kw=mean_power,
            common_window_min=float(operation["common_window_min"]),
            common_window_mean_power_kw=(60.0 * float(operation["common_window_energy_kwh"])
                                         / float(operation["common_window_min"])),
            power_vs_rating_pct=100.0 * mean_power / Z50["continuous_power_kw"],
            energy_per_cycle_kwh=float(ref["energy_per_complete_cycle_kwh"]),
            complete_cycles=int(ref["complete_recurring_cycles"]),
            tonnes=float(operation["reserve_completed_tonnes"]),
            peak_rise_c=float(sub["rise_c"].max()),
            end_rise_c=float(sub["rise_c"].iloc[-1]),
            margin_to_60c=STUDY_SCREEN_C - peak_c,
            margin_to_55c=DATASHEET_OPERATING_C - peak_c,
        ))

    return pd.DataFrame(rows).sort_values(
        ["capacity_kwh", "rr_percent"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join("results", "thermal"))
    args = parser.parse_args()

    table = build_table()
    os.makedirs(args.out, exist_ok=True)
    table.to_csv(os.path.join(args.out, "thermal_demand.csv"), index=False)

    show = ["capacity_kwh", "rr_percent", "window_min", "mean_power_kw",
            "energy_per_cycle_kwh", "complete_cycles", "peak_rise_c",
            "margin_to_60c"]
    print("Reserve rule: analysis stops at %.0f %% of nominal capacity "
          "(80 %% to 20 %% SOC)" % (100 * RESERVE_FRACTION))
    print(table[show].to_string(
        index=False, float_format=lambda v: "%.4f" % v))

    print("\nown-reserve mean power %.2f to %.2f kW  (%.1f to %.1f %% of the "
          "%d kW continuous rating)"
          % (table.mean_power_kw.min(), table.mean_power_kw.max(),
             table.power_vs_rating_pct.min(), table.power_vs_rating_pct.max(),
             Z50["continuous_power_kw"]))
    print("common-window mean power %.2f to %.2f kW"
          % (table.common_window_mean_power_kw.min(),
             table.common_window_mean_power_kw.max()))
    print("energy per cycle    %.2f to %.2f kWh"
          % (table.energy_per_cycle_kwh.min(), table.energy_per_cycle_kwh.max()))
    print("reserve window      %.2f to %.2f min"
          % (table.window_min.min(), table.window_min.max()))
    print("peak rise           %.6f to %.6f C"
          % (table.peak_rise_c.min(), table.peak_rise_c.max()))
    print("margin to %.0f C      %.3f to %.3f C   (spread %.3f C)"
          % (STUDY_SCREEN_C, table.margin_to_60c.min(),
             table.margin_to_60c.max(),
             table.margin_to_60c.max() - table.margin_to_60c.min()))

    if table.peak_rise_c.max() < RESIDUAL_LO_C:
        print("\nEvery rise above is smaller than the %.3f C measured-cell "
              "residual error, so the ordering between configurations is not "
              "physically resolvable." % RESIDUAL_LO_C)
    print(thermal_note())
    print("\nwrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
