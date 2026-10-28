"""Experiment A: cross-configuration temperature forecasting benchmark.

Question
    Given 60 s of causal history on one vehicle configuration, how well can the
    temperature change over the next 1 to 10 minutes be predicted on a
    configuration the model has never seen?

Protocol
    Leave-one-configuration-out over the nine configurations. Within each
    training set, the last two configurations are held out again to select the
    ridge penalty, so no test fold influences any fitting decision. Four
    horizons, five methods.

What this does and does not establish
    The traces are the deterministic output of the frozen thermal model driven
    by an assumed equivalent current. A model that does well here has
    rediscovered that equation. It has not been validated against a measured
    vehicle pack, and every error in the resulting table lies below the
    measured-cell fit's own residual error.

Usage
    python experiments/experiment_a_forecasting.py [--out DIR] [--quick]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from bev_research import baselines, datasets, features, metrics, models  # noqa: E402
from bev_research.config import HISTORY_S, HORIZONS_S, RESIDUAL_LO_C, thermal_note  # noqa: E402


def prepare_grids(dt_s: float = 1.0) -> dict:
    """Put every configuration on a uniform 1 Hz grid."""
    from bev_research.thermal import resample_to_grid
    traces = datasets.nominal_traces()
    grids = {}
    for case, sub in traces.groupby("case"):
        sub = sub.sort_values("time_s")
        grid, temp, cur, air = resample_to_grid(
            sub["time_s"].to_numpy(float),
            sub["temperature_c"].to_numpy(float),
            sub["equivalent_current_a"].to_numpy(float),
            sub["air_c"].to_numpy(float), dt_s=dt_s)
        grids[case] = dict(
            t=grid, T=temp, I=cur, air=air,
            capacity_kwh=float(sub["capacity_kwh"].iloc[0]),
            rr_percent=float(sub["rr_percent"].iloc[0]))
    return grids


def run(out_dir: str, quick: bool = False) -> pd.DataFrame:
    grids = prepare_grids()
    cases = sorted(grids)
    horizons = (60, 600) if quick else HORIZONS_S
    print("configurations: %d   horizons: %s   history: %d s"
          % (len(cases), list(horizons), HISTORY_S))

    rows = []
    for horizon in horizons:
        built = {}
        for case in cases:
            g = grids[case]
            made = features.build_design(
                g["T"], g["I"], g["air"], horizon,
                g["capacity_kwh"], g["rr_percent"], HISTORY_S)
            if made is not None:
                built[case] = made

        usable = sorted(built)
        for test_case in usable:
            started = time.time()
            train = [c for c in usable if c != test_case]
            dev, core = train[-2:], train[:-2]

            core_x = np.vstack([built[c][0] for c in core])
            core_y = np.concatenate([built[c][1] for c in core])
            dev_x = np.vstack([built[c][0] for c in dev])
            dev_y = np.concatenate([built[c][1] for c in dev])
            lam = models.select_lambda(core_x, core_y, dev_x, dev_y)

            train_x = np.vstack([built[c][0] for c in train])
            train_y = np.concatenate([built[c][1] for c in train])
            ridge = models.ridge_fit(train_x, train_y, lam)
            gbt = models.gbt_fit(train_x, train_y)

            test_x, test_y, names, _ = built[test_case]
            predicted = baselines.all_baselines(test_x, names, horizon)
            predicted["ridge"] = models.ridge_predict(ridge, test_x)
            predicted["gradient_boosting"] = models.gbt_predict(gbt, test_x)

            for method, values in predicted.items():
                rows.append(dict(horizon_s=horizon, test_case=test_case,
                                 method=method, ridge_lambda=lam,
                                 **metrics.score(values, test_y)))
            print("  h=%4ds  holdout=%-10s lambda=%-7g  %.1fs"
                  % (horizon, test_case, lam, time.time() - started), flush=True)

    per_case = pd.DataFrame(rows)
    pooled = metrics.pool_by(per_case, ["horizon_s", "method"],
                             ["rmse_c", "mae_c"])

    os.makedirs(out_dir, exist_ok=True)
    per_case.to_csv(os.path.join(out_dir, "experiment_a_per_case.csv"),
                    index=False)
    pooled.to_csv(os.path.join(out_dir, "experiment_a_pooled.csv"), index=False)

    print("\nPooled RMSE (degrees C), mean over held-out configurations")
    table = pooled.pivot(index="horizon_s", columns="method",
                         values="rmse_c_mean")
    print(table.to_string(float_format=lambda v: "%.6f" % v))

    worst = float(pooled["rmse_c_max"].max())
    print("\nLargest single-fold RMSE: %.6f C" % worst)
    print(metrics.resolution_note(worst))
    if worst < RESIDUAL_LO_C:
        print("\nREAD THIS BEFORE QUOTING THE TABLE:")
        print("  " + thermal_note())
    print("\nwrote", out_dir)
    return pooled


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join("results", "experiment_a"))
    parser.add_argument("--quick", action="store_true",
                        help="two horizons instead of four, for a smoke test")
    args = parser.parse_args()
    run(args.out, quick=args.quick)
    return 0


if __name__ == "__main__":
    sys.exit(main())
