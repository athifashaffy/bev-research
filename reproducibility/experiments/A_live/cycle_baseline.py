"""AI-assisted post-hoc seasonal-naive comparison; existing runs are read-only."""
import argparse
from collections import defaultdict
import datetime
import json
import math
from pathlib import Path
import platform
import sys

from train import original, sha, validate_output, verify_proof, write_json
from report import read_csv, independent_metrics, check_metric
import numpy as np

METHOD = "seasonal_naive"
LAG_MIN, LAG_MAX = 600, 2400


def estimate_period(current, lag_min=LAG_MIN, lag_max=LAG_MAX):
    """Strongest Pearson lag correlation, with >= half-record overlap; no labels."""
    x = np.asarray(current, dtype=float)
    if (x.ndim != 1 or not np.isfinite(x).all() or len(x) < 2 * lag_min
            or not isinstance(lag_min, int) or not isinstance(lag_max, int)
            or lag_min < 1 or lag_max < lag_min):
        raise ValueError("Invalid current recording or lag bounds")
    candidates = []
    for lag in range(lag_min, min(lag_max, len(x) // 2) + 1):
        left, right = x[:-lag], x[lag:]
        left, right = left - left.mean(), right - right.mean()
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        if denominator > 0:
            candidates.append((float(np.dot(left, right) / denominator), lag))
    if not candidates:
        raise ValueError("No identifiable period in constant current")
    # On ties select the shorter lag; the lag is never chosen by forecast error.
    correlation, lag = max(candidates, key=lambda item: (item[0], -item[1]))
    return {"period_s": lag, "correlation": correlation,
            "overlap_samples": len(x) - lag,
            "at_search_boundary": lag in (lag_min, min(lag_max, len(x) // 2))}


def fit_period(currents, training_names, test_name, lag_min=LAG_MIN, lag_max=LAG_MAX):
    if (not training_names or test_name in training_names
            or len(set(training_names)) != len(training_names)):
        raise ValueError("Training configurations must be distinct and exclude test")
    estimates = {name: estimate_period(currents[name], lag_min, lag_max)
                 for name in sorted(training_names)}
    median = float(np.median([value["period_s"] for value in estimates.values()]))
    return {"period_s": int(math.floor(median + .5)), "training_estimates": estimates}


def predict_prefix(temperatures, horizon, period):
    """Accept only revealed 1-Hz temperatures starting at t=0; return source index."""
    values = np.asarray(temperatures, dtype=float)
    if (values.ndim != 1 or not len(values) or not np.isfinite(values).all()
            or not isinstance(horizon, int) or not isinstance(period, int)
            or horizon < 1 or period < 1):
        raise ValueError("Invalid temperatures, horizon or period")
    origin = len(values) - 1
    source = origin + horizon - period * ((horizon + period - 1) // period)
    fallback = source < 0
    if fallback:
        source = origin
    return {"prediction_c": float(values[source]), "source_s": source, "fallback": fallback}


def run(source, output):
    source, output = Path(source).resolve(), validate_output(output)
    verify_proof(source)
    input_files = [source / name for name in ("telemetry.csv.gz", "predictions.csv.gz",
        "fold_assignments.json", "pooled_metrics.csv", "PROOF.json")]
    scripts = [Path(__file__), Path(__file__).with_name("CYCLE_BASELINE_PLAN.md"),
               Path(__file__).with_name("report.py"), Path(__file__).with_name("train.py"),
               Path(original.__file__)]
    hashes = {str(path): sha(path) for path in input_files + scripts}
    sensors = defaultdict(list)
    for row in read_csv(source / "telemetry.csv.gz"):
        sensors[row["case"]].append(row)
    temperatures, currents = {}, {}
    for name, rows in sensors.items():
        if [int(r["time_s"]) for r in rows] != list(range(len(rows))):
            raise ValueError("Telemetry must retain its original contiguous 1-Hz clock")
        temperatures[name] = np.array([float(r["reference_cell_temperature_c"]) for r in rows])
        currents[name] = np.array([float(r["equivalent_current_a"]) for r in rows])
    periods = {}
    for fold in json.loads((source / "fold_assignments.json").read_text()):
        name = fold["outer_test"]
        if name in periods or set(fold["outer_train"]) != set(sensors) - {name}:
            raise ValueError("Invalid outer split")
        periods[name] = fit_period(currents, fold["outer_train"], name)
    if set(periods) != set(sensors):
        raise ValueError("Missing outer test configuration")
    rows = read_csv(source / "predictions.csv.gz")
    origins, by_key = defaultdict(dict), {}
    for row in rows:
        name, h, t = row["case"], int(row["horizon_s"]), int(row["origin_s"])
        key = name, h, t
        if (row["method"] in origins[key] or int(row["target_s"]) != t + h
                or float(row["target_temperature_c"]) != temperatures[name][t + h]
                or abs(float(row["origin_temperature_c"]) - temperatures[name][t]) > 1e-11):
            raise ValueError("Duplicate or inconsistent saved prediction")
        origins[key][row["method"]] = row
    expected_methods = {"persistence", "linear_trend", "physics_hold", "hist_gradient_boosting"}
    if any(set(values) != expected_methods for values in origins.values()):
        raise ValueError("Methods do not share identical origins")
    for (name, h, t), values in sorted(origins.items()):
        predicted = predict_prefix(temperatures[name][:t + 1], h, periods[name]["period_s"])
        row = dict(values["persistence"])
        row.update(method=METHOD, predicted_temperature_c=predicted["prediction_c"])
        by_key[(name, h, t)] = predicted
        rows.append(row)
    groups, per_case = defaultdict(list), defaultdict(list)
    for row in rows:
        name, h, t = row["case"], int(row["horizon_s"]), int(row["origin_s"])
        subsets = ["all_origins"]
        if not by_key[(name, h, t)]["fallback"]:
            subsets.append("cycle_available")
        for subset in subsets:
            groups[(subset, h, row["method"])].append(row)
            per_case[(subset, name, h, row["method"])].append(row)
    pooled_rows, case_rows = [], []
    for mapping, dest, fields in ((groups, pooled_rows, ("subset", "horizon_s", "method")),
                                  (per_case, case_rows, ("subset", "case", "horizon_s", "method"))):
        for key, group in sorted(mapping.items()):
            result = original.error_metrics([float(r["target_temperature_c"]) for r in group],
                                            [float(r["predicted_temperature_c"]) for r in group])
            for metric, value in independent_metrics(group).items():
                check_metric(metric, value, result[metric])
            dest.append({**dict(zip(fields, key)), **result})
    metrics = {(r["subset"], r["horizon_s"], r["method"]): r for r in pooled_rows}
    for old in read_csv(source / "pooled_metrics.csv"):
        current = metrics[("all_origins", int(old["horizon_s"]), old["method"])]
        for metric in ("n_origins", "rmse_c", "mae_c", "max_absolute_error_c"):
            check_metric(metric, float(old[metric]), current[metric])
    decisions, coverage = [], []
    horizons = sorted({key[1] for key in origins})
    for h in horizons:
        selected = [v for (name, horizon, t), v in by_key.items() if horizon == h]
        coverage.append({"horizon_s": h, "all_origins": len(selected),
                         "cycle_available": sum(not v["fallback"] for v in selected),
                         "fallback_origins": sum(v["fallback"] for v in selected)})
        for subset in ("all_origins", "cycle_available"):
            own = metrics[(subset, h, "hist_gradient_boosting")]
            competitors = [metrics[(subset, h, m)] for m in expected_methods - {"hist_gradient_boosting"} | {METHOD}]
            decisions.append({"subset": subset, "horizon_s": h,
                "boosting_beats_all_four_on_both": all(own[k] < other[k]
                    for other in competitors for k in ("rmse_c", "mae_c")),
                "boosting_beats_cycle_on_both": all(own[k] < metrics[(subset, h, METHOD)][k]
                                                    for k in ("rmse_c", "mae_c"))})
    output.mkdir(parents=True)
    write_json(output / "protocol.json", {"date_local": "2026-11-13", "post_hoc": True,
        "period_fit": "Median training-only current lag-correlation periods; half-up rounding to integer seconds",
        "lag_range_s": [LAG_MIN, LAG_MAX], "minimum_overlap": "half the recording",
        "forecast": "T[t+h-L*ceil(h/L)]", "startup": "persistence if referenced time is before zero",
        "history": "Up to a whole cycle; other methods retain their original 60-second window",
        "comparison": "Saved held-out predictions unchanged; identical origins within each subset",
        "limitations": ["Period search bounds informed by previously seen traces; not preregistered",
            "Fixed training-median period does not adapt to configuration-specific timing",
            "Synthetic reference cell only; no new thermal calibration or pack validation"],
        "reference": "https://otexts.com/fpp3/simple-methods.html"})
    write_json(output / "periods.json", periods)
    write_json(output / "summary.json", {"coverage": coverage, "decisions": decisions,
        "original_metrics_match": True, "arithmetic_crosscheck_tolerance_c": 1e-12})
    for filename, values in (("predictions.csv.gz", rows), ("pooled_metrics.csv", pooled_rows),
                              ("per_case_metrics.csv", case_rows)):
        original.write_csv(output / filename, values)
    original.write_csv(output / "source_times.csv", [dict(case=name, horizon_s=h, origin_s=t,
        period_s=periods[name]["period_s"], **values) for (name, h, t), values in sorted(by_key.items())])
    verify_proof(source)
    if any(sha(path) != digest for path, digest in hashes.items()):
        raise AssertionError("Input or script changed during analysis")
    write_json(output / "PROOF.json", {"recorded_by": "AI-assisted automated analysis; not human verification",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv], "python": platform.python_version(),
        "numpy": np.__version__, "inputs_and_scripts_sha256": hashes,
        "outputs_sha256": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}})
    print(json.dumps({"periods_s": {name: p["period_s"] for name, p in periods.items()},
                      "coverage": coverage, "decisions": decisions}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.run, args.output)
