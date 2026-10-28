"""Rebuild the thermal traces from the haulage event ledger.

Why this exists
    A fair criticism of this repository is that its experiments read from
    ``data/derived`` and therefore check saved outputs rather than reproduce
    the pipeline that produced them. This script closes that gap for the
    thermal chain. It starts from the per-event haulage ledger, which is the
    actual input, and rebuilds the temperature traces end to end:

        event duration and energy
            -> event-average power
            -> assumed equivalent cell current
            -> frozen thermal model, replayed across events
            -> surface temperature

    Nothing here reads the saved traces except at the very end, to compare.

What this does and does not demonstrate
    Agreement proves the published traces follow from the stated inputs and the
    stated equation, with no undocumented step in between. It does NOT validate
    the equivalent-current assumption, the fitted coefficients, or the transfer
    from an A123 cell to a Sandvik Z50 pack. A pipeline can be perfectly
    reproducible and still rest on an assumption that does not hold physically.

What is still not reproducible from this repository
    The HAULSIM simulation that produced the event ledger needs a licensed copy
    of HAULSIM 3.8 build 585 and the native model files, which are not
    included. The thermal coefficients a and b come from a fit to A123 cell
    records; the fitting code is in ``code/fit_thermal_model.py`` and its
    provenance in ``data/manifest/frozen_cell_model.json``, but the ``.mat``
    records themselves are third party and must be fetched from their DOI.
    So this reproduces the middle of the pipeline, not its two ends.

Usage
    python experiments/reproduce_thermal_chain.py
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from bev_research import datasets, thermal  # noqa: E402
from bev_research.config import THERMAL_DIR, thermal_note  # noqa: E402

TOLERANCE_C = 1e-6


def load_event_ledger() -> pd.DataFrame:
    path = os.path.join(THERMAL_DIR, "operations_event_ledger.csv")
    return pd.read_csv(path, encoding="utf-8-sig")


def rebuild_case(events: pd.DataFrame, capacity_kwh: float,
                 air_c: float = 25.0) -> pd.DataFrame:
    """Replay one configuration from its events alone."""
    events = events.sort_values("event_index")
    temp = air_c
    rows = []
    for _, ev in events.iterrows():
        duration_s = float(ev["duration_min"]) * 60.0
        energy_kwh = float(ev["battery_energy_kwh"])
        hours = duration_s / 3600.0
        power_kw = energy_kwh / hours if hours > 0 else 0.0
        current_a = thermal.equivalent_current(power_kw, capacity_kwh)
        temp = float(thermal.step(temp, current_a, duration_s, air_c))
        rows.append(dict(
            event_index=int(ev["event_index"]),
            state=ev["state"],
            end_s=float(ev["end_min"]) * 60.0,
            duration_s=duration_s,
            mean_power_kw=power_kw,
            equivalent_current_a=current_a,
            rebuilt_temperature_c=temp,
        ))
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join("results", "thermal"))
    args = parser.parse_args()

    ledger = load_event_ledger()
    reference = datasets.reserve_summary().set_index("case")
    print("Rebuilding %d events across %d configurations from the event "
          "ledger alone.\n" % (len(ledger), ledger["case"].nunique()))

    all_rows, worst_overall = [], 0.0
    for case, events in ledger.groupby("case"):
        capacity = float(reference.loc[case, "capacity_kwh"])
        rebuilt = rebuild_case(events, capacity)
        rebuilt.insert(0, "case", case)

        # Compare against the saved trace, matched on event end times.
        saved = datasets.nominal_traces(case)
        matched, deltas = 0, []
        for _, row in rebuilt.iterrows():
            hit = saved.index[np.isclose(saved["time_s"], row["end_s"],
                                         atol=1e-6)]
            if len(hit):
                deltas.append(abs(float(saved.loc[hit[0], "temperature_c"])
                                  - row["rebuilt_temperature_c"]))
                matched += 1

        worst = max(deltas) if deltas else float("nan")
        worst_overall = max(worst_overall, worst if deltas else 0.0)
        status = "OK  " if deltas and worst < TOLERANCE_C else "CHECK"
        print("  %s %-10s  %2d events  %2d matched to saved trace  "
              "max delta %.2e C" % (status, case, len(rebuilt), matched, worst))
        all_rows.append(rebuilt)

    combined = pd.concat(all_rows, ignore_index=True)
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "rebuilt_from_event_ledger.csv")
    combined.to_csv(out_path, index=False)

    print("\nLargest deviation across all configurations: %.3e C"
          % worst_overall)
    if worst_overall < TOLERANCE_C:
        print("The published traces follow from the event ledger and the "
              "frozen equation, with no undocumented step in between.")
    else:
        print("MISMATCH. The saved traces do not follow from these inputs "
              "under the stated equation.")

    print("\nThis checks internal consistency only. It does not validate the "
          "equivalent-current assumption, the fitted coefficients, or the "
          "cell-to-pack transfer.")
    print(thermal_note())
    print("\nwrote", out_path)
    return 0 if worst_overall < TOLERANCE_C else 1


if __name__ == "__main__":
    sys.exit(main())
