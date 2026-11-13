"""Live-sensor forecasting contest on measured A123 laboratory-cell records.

AI-written (Claude, 12 November 2026) at the author's request. New experiment;
it does not reproduce or replace Experiment A or the completed-report run.

Scope: three laboratory records of ONE A123 26650 cell (de Souza 2021,
doi:10.17632/p8kf893yv3.1). Inputs at each forecast time are the measured
current, surface temperature and air temperature of the preceding minute.
The scoring target is the MEASURED surface temperature at the target time.
This is not truck-pack data and gives no thermal-runaway warning evidence.

Usage (from reproducibility/):
  python experiments/A_lab/train.py --output results/NEW_FOLDER
"""
from pathlib import Path
import os
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import platform
import sys

import numpy as np
import scipy
import sklearn
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
_spec = importlib.util.spec_from_file_location("original_experiment_a", HERE.parent / "A/train.py")
original = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(original)

A, B, SEED = original.A, original.B, original.SEED
DEFAULT_DATA = REPO / "data/raw/a123_csv"
# record name -> (file, surface-temperature column, air-temperature column); mapping as in the fit script.
RECORDS = {"pulse_25C": ("A002_PeriodicPulseData.csv", "SurfaceTemperature", "AirTemperature"),
           "udds_25C": ("A002_UDDS_P25.csv", "Ts1", "Tf"),
           "udds_35C": ("A002_UDDS_P35.csv", "Ts", "Tf")}
EXPECTED_SHA256 = {"A002_PeriodicPulseData.csv": "aee455a44a97cd5960612e57d8b49f4c18ccd700e586723a875e457111e165e7",
                   "A002_UDDS_P25.csv": "8b27f24f0239dd8cc8f21e823207e23b18a0b67be5ec46703a6ff7e1af957b50",
                   "A002_UDDS_P35.csv": "2ef19e7709ac3f31fed8694c02d442ae927a6d48dacf6cb3a6d200c0b21ec248"}
HORIZONS = (60, 120, 300, 600, 1800)
HISTORY_S, SPACING_S = 60, 10
BASELINES = ("persistence", "linear_trend", "physics_hold_last", "physics_hold_meansq")
LEARNED = ("ridge", "hist_gradient_boosting")
METHODS = BASELINES + LEARNED
STATS = ("last", "mean", "minimum", "maximum", "slope_per_s", "last_difference")
FEATURE_NAMES = [f"{signal}_{stat}" for signal in ("rise_above_air_c", "current_a", "air_c") for stat in STATS]
FEATURE_NAMES.append("current_squared_mean_a2")


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_record(path, temp_column, air_column):
    """Read time, current, surface temperature and air temperature exactly as stored."""
    with open(path, encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    time_s = np.array([float(r["time"]) for r in rows])
    values = np.array([[float(r[temp_column]), float(r["current"]), float(r[air_column])] for r in rows])
    order_ok = np.diff(time_s) > 0
    if not np.all(order_ok):
        raise ValueError(f"{path.name}: time is not strictly increasing")
    return time_s, values


def features_at(grid_values, index):
    """19 inputs from the 61 one-second readings ending at `index`. Never reads later rows."""
    if index < HISTORY_S:
        return None
    past = np.asarray(grid_values[index - HISTORY_S:index + 1], dtype=float)
    if past.shape != (HISTORY_S + 1, 3) or not np.all(np.isfinite(past)):
        return None
    channels = np.column_stack([past[:, 0] - past[:, 2], past[:, 1], past[:, 2]])
    x = np.arange(-float(HISTORY_S), 1.)
    centered = x - x.mean()
    slopes = centered @ channels / (centered @ centered)
    row = []
    for j in range(3):
        col = channels[:, j]
        row.extend((col[-1], col.mean(), col.min(), col.max(), slopes[j], col[-1] - col[-2]))
    row.append(float(np.mean(past[:, 1] ** 2)))
    return np.asarray(row, dtype=float)


def build_examples(grid_s, grid_values, horizon_s):
    """Forecast origins every SPACING_S seconds. The target row is read only as the answer."""
    grid = np.asarray(grid_s, dtype=int)
    out = {k: [] for k in ("origin_s", "x", "now_c", "target_c", "current_a", "meansq_a2", "air_c", "temp_slope")}
    first = int(math.ceil((grid[0] + HISTORY_S) / SPACING_S) * SPACING_S)
    for origin in range(first, int(grid[-1] - horizon_s) + 1, SPACING_S):
        index = origin - grid[0]
        target = grid_values[index + horizon_s, 0]
        features = features_at(grid_values, index)
        if features is None or not np.isfinite(target):
            continue
        past_temp = grid_values[index - HISTORY_S:index + 1, 0]
        x = np.arange(-float(HISTORY_S), 1.)
        centered = x - x.mean()
        out["origin_s"].append(origin); out["x"].append(features)
        out["now_c"].append(grid_values[index, 0]); out["target_c"].append(target)
        out["current_a"].append(grid_values[index, 1]); out["meansq_a2"].append(features[-1])
        out["air_c"].append(grid_values[index, 2])
        out["temp_slope"].append(float(centered @ past_temp / (centered @ centered)))
    return {k: np.asarray(v) for k, v in out.items()}


def baseline_predictions(e, horizon_s):
    now = e["now_c"]
    return {"persistence": now,
            "linear_trend": now + e["temp_slope"] * horizon_s,
            "physics_hold_last": original.physics_forecast(now, e["current_a"], e["air_c"], horizon_s, A, B),
            "physics_hold_meansq": original.physics_forecast(now, np.sqrt(e["meansq_a2"]), e["air_c"], horizon_s, A, B)}


def record_plan(names):
    """Leave one record out; inside, each remaining record validates once."""
    names = sorted(names)
    plan = []
    for held in names:
        train = [n for n in names if n != held]
        inner = [{"inner_fold": i, "validation_groups": [v], "train_groups": [n for n in train if n != v]}
                 for i, v in enumerate(train)]
        plan.append({"outer_test": held, "outer_train": train, "inner": inner})
    return plan


def fit_selected(method, x, delta, groups, fold):
    candidates = []
    fits = 0
    for params in original.GRIDS[method]:
        scores = []
        for inner in fold["inner"]:
            train, valid = np.isin(groups, inner["train_groups"]), np.isin(groups, inner["validation_groups"])
            if fold["outer_test"] in set(groups[train]) | set(groups[valid]):
                raise AssertionError("held-out record leaked into selection")
            model = original.estimator(method, params)
            model.fit(x[train], delta[train]); fits += 1
            scores.append(float(np.mean((model.predict(x[valid]) - delta[valid]) ** 2)))
        candidates.append({"parameters": params, "validation_mse_c2_by_fold": scores,
                           "mean_validation_mse_c2": float(np.mean(scores))})
    chosen = min(candidates, key=lambda c: c["mean_validation_mse_c2"])
    train = np.isin(groups, fold["outer_train"])
    model = original.estimator(method, chosen["parameters"])
    model.fit(x[train], delta[train]); fits += 1
    return model, {"method": method, "outer_test": fold["outer_test"], "selected_parameters": chosen["parameters"],
                   "candidates": candidates, "n_outer_train_origins": int(train.sum()), "fit_count": fits}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    data = text.getvalue().encode("utf-8")
    if str(path).endswith(".gz"):
        with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as stream:
            stream.write(data)
    else:
        Path(path).write_bytes(data)


def run(data_dir, output_dir):
    data_dir, out = Path(data_dir).resolve(), Path(output_dir).resolve()
    if out.exists():
        raise FileExistsError("Output directory already exists; refusing to overwrite")
    if out.is_relative_to(data_dir):
        raise ValueError("Output must be outside the input data folder")
    hashes = {}
    for file in sorted(EXPECTED_SHA256):
        hashes[file] = sha(data_dir / file)
        if hashes[file] != EXPECTED_SHA256[file]:
            raise ValueError(f"Input hash mismatch: {file}")
    cases, record_rows = {}, []
    for name, (file, temp_column, air_column) in RECORDS.items():
        time_s, values = load_record(data_dir / file, temp_column, air_column)
        grid_s, grid_values = original.resample_past_held(time_s, values)
        cases[name] = (grid_s, grid_values)
        gaps = np.diff(time_s)
        record_rows.append({"record": name, "file": file, "source_rows": len(time_s),
                            "time_first_s": float(time_s[0]), "time_last_s": float(time_s[-1]),
                            "duration_h": float((time_s[-1] - time_s[0]) / 3600),
                            "median_step_s": float(np.median(gaps)), "gaps_over_1p5_s": int(np.sum(gaps > 1.5)),
                            "largest_gap_s": float(gaps.max()), "grid_seconds_with_reading": int(np.isfinite(grid_values[:, 0]).sum()),
                            "surface_min_c": float(values[:, 0].min()), "surface_max_c": float(values[:, 0].max()),
                            "surface_swing_c": float(values[:, 0].max() - values[:, 0].min()),
                            "current_min_a": float(values[:, 1].min()), "current_max_a": float(values[:, 1].max()),
                            "air_min_c": float(values[:, 2].min()), "air_max_c": float(values[:, 2].max())})
    out.mkdir(parents=True)
    plan = record_plan(cases)
    protocol = {"name": "lab-live-sensor-forecast-v1", "written_by": "Claude (AI), 12 November 2026",
                "scope": "ONE A123 26650 laboratory cell, three records; measured targets; not truck-pack validation",
                "inputs": "Measured current, surface temperature and air temperature of the preceding 60 s, latest reading at or before each whole second (past hold, no interpolation, no filtering)",
                "target": "Measured surface temperature at origin + horizon (latest reading at or before that second)",
                "gap_rule": "Seconds inside a source gap longer than 1.5 s carry no reading; an origin is used only if its 61 history seconds and its target second all carry readings",
                "history_s": HISTORY_S, "spacing_s": SPACING_S, "horizons_s": list(HORIZONS),
                "feature_names": FEATURE_NAMES, "methods": list(METHODS),
                "baselines": {"persistence": "temperature stays at the latest measured value",
                              "linear_trend": "latest value plus the 60 s least-squares slope times the horizon",
                              "physics_hold_last": "fitted heat equation, latest measured current and air temperature held",
                              "physics_hold_meansq": "fitted heat equation, mean squared current of the last 60 s and latest air temperature held"},
                "thermal_coefficients": {"a_K_per_A2_s": A, "b_per_s": B,
                                         "caution": "a and b were fitted on the pulse record; physics baselines are out-of-sample only on the two UDDS records"},
                "learned_models": "Same estimators and grids as experiments/A/train.py; target is future minus current measured temperature",
                "model_grids": original.GRIDS, "seed": SEED,
                "validation": "Leave one record out (3 outer folds); inside, each of the two training records validates once",
                "success_rule": "Strictly beat all four baselines on pooled RMSE and MAE separately at each horizon",
                "units_assumption": "current in A, temperatures in degrees C, time in s; units are not stored in the source files",
                "limitations": ["Three records of one cell; a held-out record is not an independent cell",
                                "Laboratory pulse and drive-cycle loads, not mining duty",
                                "Sampling is about 1.007 to 1.014 s; some whole seconds reuse the previous reading",
                                "No truck-pack, cooling-system or fault data"]}
    write_json(out / "protocol.json", protocol)
    write_json(out / "fold_assignments.json", plan)
    write_csv(out / "record_summary.csv", record_rows)

    predictions, per_record, selections, fit_total = [], [], [], 0
    with threadpool_limits(limits=1):
        for h in HORIZONS:
            ex = {name: build_examples(g, v, h) for name, (g, v) in cases.items()}
            x = np.vstack([e["x"] for e in ex.values()])
            delta = np.concatenate([e["target_c"] - e["now_c"] for e in ex.values()])
            groups = np.concatenate([np.repeat(name, len(e["origin_s"])) for name, e in ex.items()])
            for fold in plan:
                held, e = fold["outer_test"], ex[fold["outer_test"]]
                pred = baseline_predictions(e, h)
                for method in LEARNED:
                    model, selection = fit_selected(method, x, delta, groups, fold)
                    pred[method] = e["now_c"] + model.predict(e["x"])
                    fit_total += selection["fit_count"]
                    selections.append({"horizon_s": h, **selection})
                for method in METHODS:
                    per_record.append({"record": held, "horizon_s": h, "method": method,
                                       **original.error_metrics(e["target_c"], pred[method])})
                    for i, origin in enumerate(e["origin_s"]):
                        predictions.append({"record": held, "horizon_s": h, "origin_s": int(origin), "target_s": int(origin + h),
                                            "method": method, "origin_temperature_c": float(e["now_c"][i]),
                                            "true_temperature_c": float(e["target_c"][i]),
                                            "predicted_temperature_c": float(pred[method][i])})
                print(json.dumps({"horizon_s": h, "held_record": held, "n_origins": int(len(e["origin_s"]))}), flush=True)

    def pooled_for(records, label):
        rows = []
        for h in HORIZONS:
            for method in METHODS:
                use = [p for p in predictions if p["horizon_s"] == h and p["method"] == method and p["record"] in records]
                rows.append({"scope": label, "horizon_s": h, "method": method,
                             **original.error_metrics([p["true_temperature_c"] for p in use],
                                                      [p["predicted_temperature_c"] for p in use])})
        return rows

    def decisions(rows):
        result = []
        for h in HORIZONS:
            at = {r["method"]: r for r in rows if r["horizon_s"] == h}
            for method in LEARNED:
                wins = all(at[method][k] < at[b][k] for b in BASELINES for k in ("rmse_c", "mae_c"))
                result.append({"horizon_s": h, "method": method, "beats_all_baselines_on_both": bool(wins)})
        return result

    pooled_all = pooled_for(set(RECORDS), "all_three_records")
    pooled_udds = pooled_for({"udds_25C", "udds_35C"}, "udds_records_only")
    write_csv(out / "pooled_metrics.csv", pooled_all + pooled_udds)
    write_csv(out / "per_record_metrics.csv", per_record)
    write_csv(out / "predictions.csv.gz", predictions)
    write_json(out / "model_selection.json", selections)
    write_json(out / "summary.json", {
        "scope": "NEW EXPERIMENT ON LABORATORY CELL RECORDS; NOT TRUCK VALIDATION; AI-WRITTEN CODE",
        "input_sha256": hashes, "script_sha256": sha(__file__), "original_trainer_sha256": sha(HERE.parent / "A/train.py"),
        "model_fit_count": fit_total,
        "origins_by_horizon": {str(h): int(sum(1 for p in predictions if p["horizon_s"] == h and p["method"] == "persistence")) for h in HORIZONS},
        "decisions_all_three_records": decisions(pooled_all), "decisions_udds_records_only": decisions(pooled_udds),
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                     "sklearn": sklearn.__version__, "platform": platform.platform()}})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Folder holding the three A123 CSV records (read only)")
    parser.add_argument("--output", type=Path, required=True, help="New output folder outside the input data")
    args = parser.parse_args(argv)
    out = run(args.data, args.output)
    print(f"Results written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
