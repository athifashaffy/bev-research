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
    Agreement checks the stated equation at matched event endpoints only. Saved
    traces stop at the reserve cutoff, so not every ledger event is compared.
    This is not a comparison of every temperature sample. It does NOT validate
    the equivalent-current assumption, the fitted coefficients, or the transfer
    from an A123 cell to a Sandvik Z50 pack. A pipeline can be perfectly
    reproducible and still rest on an assumption that does not hold physically.

What is still not reproducible from this repository
    The HAULSIM simulation that produced the event ledger needs a licensed copy
    of HAULSIM 3.8 build 585 and its configured model. Native result databases
    and A123 input records are archived under ``reproducibility/data/workspace``.
    The thermal coefficients a and b come from an A123 cell fit; the original
    fitting code in ``code/fit_thermal_model.py`` retains its original workspace
    paths and is not a standalone entry point for this layout. Coefficient
    provenance is in ``data/manifest/frozen_cell_model.json``.

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
    expected_cases = set(reference.index)
    actual_cases = set(ledger["case"])
    if (len(reference) != 9 or not reference.index.is_unique
            or actual_cases != expected_cases):
        print("CHECK: expected all nine reference configurations; "
              "missing=%s, unexpected=%s" % (
                  sorted(expected_cases - actual_cases),
                  sorted(actual_cases - expected_cases)))
        return 1
    print("Rebuilding %d events across %d configurations from the event "
          "ledger alone.\n" % (len(ledger), ledger["case"].nunique()))
    print("Checking matched event endpoints only; saved traces can stop "
          "at the reserve cutoff.\n")

    all_rows, worst_overall = [], 0.0
    all_passed, total_matched = True, 0
    for case, events in ledger.groupby("case"):
        capacity = float(reference.loc[case, "capacity_kwh"])
        rebuilt = rebuild_case(events, capacity)
        rebuilt.insert(0, "case", case)

        # Compare against the saved trace, matched on event end times.
        saved = datasets.nominal_traces(case)
        matched, deltas, comparison_error = 0, [], None
        try:
            if not np.isfinite(saved[["time_s", "temperature_c"]].to_numpy()).all():
                raise ValueError("saved times or temperatures contain nonfinite values")
            if not np.isfinite(rebuilt[["end_s", "rebuilt_temperature_c"]].to_numpy()).all():
                raise ValueError("rebuilt endpoints contain nonfinite values")
            for _, row in rebuilt.iterrows():
                hit = np.flatnonzero(np.isclose(
                    saved["time_s"], row["end_s"], atol=1e-6, rtol=0.0))
                if len(hit) > 1:
                    raise ValueError("ambiguous duplicate saved timestamp at %.9f s"
                                     % row["end_s"])
                if len(hit):
                    deltas.append(abs(float(saved.iloc[hit[0]]["temperature_c"])
                                      - row["rebuilt_temperature_c"]))
                    matched += 1
            if not matched:
                raise ValueError("no saved timestamps match event endpoints")
        except ValueError as error:
            comparison_error = str(error)

        worst = max(deltas) if deltas else float("nan")
        if np.isfinite(worst):
            worst_overall = max(worst_overall, worst)
        case_passed = comparison_error is None and bool(deltas) and worst < TOLERANCE_C
        all_passed = all_passed and case_passed
        total_matched += matched
        status = "OK  " if case_passed else "CHECK"
        print("  %s %-10s  %2d events  %2d matched to saved trace  "
              "max delta %.2e C" % (status, case, len(rebuilt), matched, worst))
        if comparison_error:
            print("       " + comparison_error)
        all_rows.append(rebuilt)

    combined = pd.concat(all_rows, ignore_index=True)
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "rebuilt_from_event_ledger.csv")
    combined.to_csv(out_path, index=False)

    print("\nLargest deviation across all configurations: %.3e C"
          % worst_overall)
    print("Partial endpoint comparison: %d of %d ledger event endpoints "
          "matched; unmatched times and interior samples were not compared."
          % (total_matched, len(ledger)))
    if all_passed:
        print("All nine configurations agree with the frozen equation at "
              "the matched event endpoints only.")
    else:
        print("MISMATCH. The saved traces do not follow from these inputs "
              "under the stated equation.")

    print("\nThis checks internal consistency only. It does not validate the "
          "equivalent-current assumption, the fitted coefficients, or the "
          "cell-to-pack transfer.")
    print(thermal_note())
    print("\nwrote", out_path)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
