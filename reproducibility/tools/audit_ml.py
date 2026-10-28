"""Independently audit saved Experiment A predictions, using only Python stdlib.

AI-assisted audit code. No scientific manuscript text is generated. No fitting,
imports of experiment code, or writes to the input tree occur. Python >= 3.10.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
import datetime
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys

HORIZONS = (60, 120, 300, 600)
METHODS = ("persistence", "linear_trend", "physics_hold", "ridge", "hist_gradient_boosting")
FEATURES = [f"{signal}_{stat}" for signal in ("temperature_c", "equivalent_current_a", "air_c")
            for stat in ("last", "mean", "minimum", "maximum", "slope_per_s", "last_difference")]
FEATURES += ["capacity_kwh", "rolling_resistance_pct"]
REQUIRED = ("forecasting.py", "test_forecasting.py", "protocol.json", "predictions.csv.gz",
            "table_4_pooled_metrics.csv", "per_case_metrics.csv", "fold_assignments.json",
            "per_fold_model_selection.json", "summary.json", "verification.json",
            "eligible_origins.csv", "causal_features.csv.gz")


class AuditError(ValueError):
    """Input does not satisfy a stated audit invariant."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def finite(value):
    result = float(value)
    require(math.isfinite(result), f"Non-finite numeric input: {value!r}")
    return result


def integer(value):
    result = finite(value)
    require(result.is_integer(), f"Expected integer: {value!r}")
    return int(result)


def near(a, b, label, *, atol=1e-12, rtol=0):
    a, b = finite(a), finite(b)
    require(math.isclose(a, b, abs_tol=atol, rel_tol=rtol), f"Mismatch {label}: {a!r} versus {b!r}")
    return abs(a - b)


def sha(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def read_json(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def read_csv(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    require(bool(rows), "Refusing to write an empty result table")
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def error_metrics(errors):
    """Recompute MAE/RMSE with compensated sums; never round small errors."""
    errors = [finite(e) for e in errors]
    require(bool(errors), "No errors available for metric computation")
    return {"n_origins": len(errors),
            "rmse_c": math.sqrt(math.fsum(e * e for e in errors) / len(errors)),
            "mae_c": math.fsum(abs(e) for e in errors) / len(errors),
            "max_absolute_error_c": max(map(abs, errors))}


def index_predictions(rows):
    result = {}
    for row in rows:
        case, h, origin, method = row["case"], integer(row["horizon_s"]), integer(row["origin_s"]), row["method"]
        key = case, h, origin, method
        require(key not in result, f"Duplicate prediction origin: {key}")
        require(integer(row["target_s"]) == origin + h, f"Incorrect target time: {key}")
        true, pred = finite(row["true_temperature_c"]), finite(row["predicted_temperature_c"])
        finite(row["origin_temperature_c"])
        near(row["error_c"], pred - true, f"saved error {key}")
        result[key] = row
    require(bool(result), "No saved predictions")
    return result


def validate_folds(plan, cases):
    """Validate complete nested whole-case separation and declared deterministic plan."""
    cases = sorted(cases)
    require(len(cases) == len(set(cases)) == 9, "Exactly nine distinct configurations required")
    result = {}
    for fold in plan:
        held = fold["outer_test"]
        require(held not in result and held in cases, "Duplicate or unknown outer held-out group")
        train = fold["outer_train"]
        require(held not in train, f"Outer held-out group leak: {held}")
        require(train == [c for c in cases if c != held], f"Outer training group mismatch: {held}")
        require(len(fold["inner"]) == 4, "Expected four inner folds")
        validations = []
        for i, inner in enumerate(fold["inner"]):
            a, b = inner["train_groups"], inner["validation_groups"]
            require(held not in a + b, f"Inner held-out group leak: {held}")
            require(not set(a) & set(b), "Inner training/validation group leak")
            require(inner["inner_fold"] == i and b == train[i::4], "Deterministic inner fold mismatch")
            require(a == [c for c in train if c not in b], "Inner training group mismatch")
            require(len(a) == 6 and len(b) == 2, "Expected six training/two validation cases")
            validations.extend(b)
        require(Counter(validations) == Counter(train), "Each outer-training case must validate once")
        result[held] = fold
    require(set(result) == set(cases), "Outer folds do not cover all cases")
    return result


def keyed_rows(rows, fields):
    result = {}
    for row in rows:
        key = tuple(integer(row[f]) if f in ("horizon_s", "origin_s") else row[f] for f in fields)
        require(key not in result, f"Duplicate row {fields}: {key}")
        result[key] = row
    return result


def compare_metrics(recomputed, recorded, fields):
    expected = keyed_rows(recorded, fields)
    actual = keyed_rows(recomputed, fields)
    require(set(actual) == set(expected), "Metric table keys mismatch")
    differences = []
    for key, row in actual.items():
        for field in row:
            if field in fields:
                continue
            if field == "n_origins":
                require(integer(expected[key][field]) == row[field], f"Count mismatch {key}")
            else:
                differences.append(near(row[field], expected[key][field], f"metric {key} {field}", atol=1e-14))
    return max(differences, default=0)


def recompute_metrics(predictions, cases):
    per_case, pooled = [], []
    errors = defaultdict(list)
    for (case, h, origin, method), row in predictions.items():
        require(h in HORIZONS and method in METHODS, f"Unknown horizon/method: {(h, method)}")
        errors[case, h, method].append(finite(row["predicted_temperature_c"]) - finite(row["true_temperature_c"]))
    for h in HORIZONS:
        for case in cases:
            for method in METHODS:
                per_case.append({"case": case, "horizon_s": h, "method": method,
                                 **error_metrics(errors[case, h, method])})
        for method in METHODS:
            scores = [r for r in per_case if r["horizon_s"] == h and r["method"] == method]
            pooled.append({"horizon_s": h, "method": method,
                           **error_metrics([e for case in cases for e in errors[case, h, method]]),
                           "case_rmse_min_c": min(r["rmse_c"] for r in scores),
                           "case_rmse_max_c": max(r["rmse_c"] for r in scores),
                           "case_mae_min_c": min(r["mae_c"] for r in scores),
                           "case_mae_max_c": max(r["mae_c"] for r in scores)})
    return per_case, pooled


def audit_hashes(input_dir, source_root, summary):
    results = []
    recorded_paths = {PurePosixPath(p.replace("\\", "/")).as_posix() for p in summary["input_and_protocol_hashes"]}
    required_paths = {"APCOM_Study_2026-10-22/results/thermal_nominal_traces.csv",
                      "APCOM_Study_2026-10-22/results/thermal_audit.json",
                      "APCOM_Study_2026-10-22/results/operations_audit.json",
                      "APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json"}
    require(required_paths <= recorded_paths, "Scientific-source hash record is incomplete")
    require(set(summary["code_hashes"]) == {"forecasting.py", "test_forecasting.py"}, "Experiment code hash record is incomplete")
    for relative, expected in summary["input_and_protocol_hashes"].items():
        relative = PurePosixPath(relative.replace("\\", "/"))
        # Private drafting provenance is irrelevant to prediction arithmetic and
        # deliberately excluded. Its contents and digest are never published.
        if relative.name == "source_draft.txt":
            continue
        path = (source_root / relative).resolve()
        require(path.is_relative_to(source_root), "Source hash path escapes source root")
        if relative.name == "protocol.json":
            path = input_dir / "protocol.json"
        require(path.is_file(), f"Required scientific source missing: {relative}")
        observed = sha(path)
        require(observed == expected, f"Source SHA-256 mismatch: {relative}")
        results.append({"path": relative.as_posix(), "sha256": observed, "matches_recorded": True})
    for relative, expected in summary["code_hashes"].items():
        path = (input_dir / relative).resolve()
        require(path.is_relative_to(input_dir) and path.is_file(), f"Required experiment code missing: {relative}")
        observed = sha(path)
        require(observed == expected, f"Experiment code SHA-256 mismatch: {relative}")
        results.append({"path": f"experiment_a/{relative}", "sha256": observed, "matches_recorded": True})
    return results


def load_source_traces(path):
    cases = defaultdict(list)
    for row in read_csv(path):
        cases[row["case"]].append(row)
    result = {}
    for name, rows in cases.items():
        ts = [finite(r["time_s"]) for r in rows]
        require(all(b > a for a, b in zip(ts, ts[1:])), f"Source time not strictly increasing: {name}")
        values = [(finite(r["temperature_c"]), finite(r["equivalent_current_a"]),
                   finite(r["temperature_c"]) - finite(r["rise_c"])) for r in rows]
        grid = {}
        # A grid point in the interior of a source gap > 1.5 s is unavailable.
        for t in range(math.ceil(ts[0]), math.floor(ts[-1]) + 1):
            i = bisect_right(ts, t) - 1
            if ts[i] == t or i == len(ts) - 1 or ts[i + 1] - ts[i] <= 1.5:
                grid[t] = values[i]
        capacity, rr = finite(rows[0]["capacity_kwh"]), finite(rows[0]["rr_percent"])
        require(all(finite(r["capacity_kwh"]) == capacity and finite(r["rr_percent"]) == rr for r in rows),
                f"Configuration metadata varies within case: {name}")
        result[name] = {"times": ts, "values": values, "grid": grid, "capacity": capacity, "rr": rr}
    return result


def causal_features(grid, origin, capacity, rr):
    require(all(t in grid for t in range(origin - 60, origin + 1)), "Missing causal history grid point")
    columns = list(zip(*(grid[t] for t in range(origin - 60, origin + 1))))
    features = []
    denominator = math.fsum(x * x for x in range(-30, 31))
    for col in columns:
        features.extend([col[-1], math.fsum(col) / 61, min(col), max(col),
                         math.fsum(x * y for x, y in zip(range(-30, 31), col)) / denominator,
                         col[-1] - col[-2]])
    return features + [capacity, rr]


def audit_causality(input_dir, source_root, predictions):
    traces = load_source_traces(source_root / "APCOM_Study_2026-10-22/results/thermal_nominal_traces.csv")
    operations = read_json(source_root / "APCOM_Study_2026-10-22/results/operations_audit.json")
    reserve = {r["case"]: finite(r["reserve_time_min"]) * 60 for r in operations["comparison"]}
    expected = {}
    for case, trace in traces.items():
        near(trace["times"][-1], reserve[case], f"reserve trace endpoint {case}", atol=1e-7)
        grid = trace["grid"]
        earliest = math.ceil((math.ceil(trace["times"][0]) + 60) / 10) * 10
        for h in HORIZONS:
            for origin in range(earliest, math.floor(trace["times"][-1]) - h + 1, 10):
                if all(t in grid for t in range(origin - 60, origin + h + 1)):
                    expected[case, h, origin] = causal_features(grid, origin, trace["capacity"], trace["rr"])
    eligible = keyed_rows(read_csv(input_dir / "eligible_origins.csv"), ("case", "horizon_s", "origin_s"))
    features = keyed_rows(read_csv(input_dir / "causal_features.csv.gz"), ("case", "horizon_s", "origin_s"))
    require(set(expected) == set(eligible) == set(features), "Saved eligibility/features differ from independently rebuilt origins")
    feature_difference = baseline_difference = 0.
    for (case, h, origin), vector in expected.items():
        trace, key = traces[case], (case, h, origin)
        latest = trace["times"][bisect_right(trace["times"], origin) - 1]
        require(latest <= origin, "Source input after prediction origin")
        for row in (eligible[key], features[key]):
            require(integer(row["history_start_s"]) == origin - 60, "Incorrect history start")
            require(integer(row["target_s"]) == origin + h <= reserve[case], "Target beyond reserve endpoint")
            near(row["reserve_endpoint_s"], reserve[case], "recorded reserve endpoint", atol=1e-7)
            near(row["latest_input_source_s"], latest, "latest past-held input timestamp")
        for name, value in zip(FEATURES, vector):
            feature_difference = max(feature_difference, near(features[key][name], value, f"feature {key} {name}", atol=2e-11, rtol=1e-12))
        temp, current, air = trace["grid"][origin]
        truth = trace["grid"][origin + h][0]
        physics = temp + (air - temp + 4.344635339312832e-05 * current ** 2 / .002655462788692412) * (-math.expm1(-.002655462788692412 * h))
        baselines = {"persistence": temp, "linear_trend": temp + vector[4] * h, "physics_hold": physics}
        for method in METHODS:
            predkey = case, h, origin, method
            require(predkey in predictions, f"Missing prediction origin/method {predkey}")
            row = predictions[predkey]
            near(row["origin_temperature_c"], temp, "saved origin temperature")
            near(row["true_temperature_c"], truth, "saved target from generated source")
            if method in baselines:
                baseline_difference = max(baseline_difference, near(row["predicted_temperature_c"], baselines[method], f"baseline {predkey}", atol=2e-11))
    require(len(predictions) == len(expected) * len(METHODS), "Extra predictions outside rebuilt eligible origins")
    temperature = [v[0] for trace in traces.values() for v in trace["values"]]
    air = [v[2] for trace in traces.values() for v in trace["values"]]
    return {"eligible_origin_rows": len(expected), "same_origins_for_all_five_methods": True,
            "past_held_features_independently_rebuilt": True, "all_targets_within_verified_reserve": True,
            "maximum_feature_difference": feature_difference, "maximum_baseline_difference_c": baseline_difference,
            "source_temperature_range_c": [min(temperature), max(temperature)], "source_air_range_c": [min(air), max(air)]}, expected


def audit_selections(choices, folds, features, protocol):
    cases = sorted(folds)
    count = Counter((case, h) for case, h, origin in features)
    expected_keys = {(case, h, m) for case in cases for h in HORIZONS for m in METHODS[3:]}
    observed, fits, selected_rows = set(), 0, []
    largest_scaler_difference = 0.
    grids = {"ridge": [{"alpha": v} for v in protocol["ridge"]["alpha_grid"]],
             "hist_gradient_boosting": [{"max_iter": v} for v in protocol["hist_gradient_boosting"]["max_iter_grid"]]}
    for choice in choices:
        case, h, method = choice["outer_test"], integer(choice["horizon_s"]), choice["method"]
        key = case, h, method
        require(key in expected_keys and key not in observed, f"Unexpected/duplicate selection {key}")
        observed.add(key)
        fold = folds[case]
        require(choice["outer_train"] == fold["outer_train"], "Selection outer training groups mismatch")
        require(choice["n_outer_train_origins"] == sum(count[c, h] for c in fold["outer_train"]), "Outer training row count mismatch")
        require([c["parameters"] for c in choice["candidates"]] == grids[method], "Hyperparameter grid mismatch")
        for candidate in choice["candidates"]:
            require(len(candidate["inner_folds"]) == 4, "Missing inner candidate folds")
            scores = []
            for inner, expected in zip(candidate["inner_folds"], fold["inner"]):
                for field in ("inner_fold", "train_groups", "validation_groups"):
                    require(inner[field] == expected[field], f"Selection inner group leak/mismatch: {key} {field}")
                require(inner["n_train_origins"] == sum(count[c, h] for c in expected["train_groups"]), "Inner training row count mismatch")
                require(inner["n_validation_origins"] == sum(count[c, h] for c in expected["validation_groups"]), "Inner validation row count mismatch")
                require(set(inner["validation_case_mse_c2"]) == set(expected["validation_groups"]), "Validation MSE case mismatch")
                values = [finite(v) for v in inner["validation_case_mse_c2"].values()]
                require(all(v >= 0 for v in values), "Negative validation MSE")
                scores.extend(values)
                require(inner["scaler_fitted_groups"] == (expected["train_groups"] if method == "ridge" else None), "Inner scaler groups leak/mismatch")
            near(candidate["equal_case_mean_validation_mse_c2"], math.fsum(scores) / 8, "equal-case candidate mean", atol=1e-14)
        best = min(choice["candidates"], key=lambda c: c["equal_case_mean_validation_mse_c2"])
        require(choice["selected_parameters"] == best["parameters"], "Choice does not minimize declared inner score/tie rule")
        near(choice["selection_score_c2"], best["equal_case_mean_validation_mse_c2"], "selected inner score", atol=1e-14)
        require(choice["scaler_fitted_groups"] == (fold["outer_train"] if method == "ridge" else None), "Outer scaler groups leak/mismatch")
        if method == "ridge":
            train = [v for (c, hh, origin), v in features.items() if hh == h and c in fold["outer_train"]]
            require(len(choice["outer_training_scaler_mean"]) == len(choice["outer_training_scaler_variance"]) == 20, "Scaler dimension mismatch")
            for j in range(20):
                mean = math.fsum(v[j] for v in train) / len(train)
                var = math.fsum((v[j] - mean) ** 2 for v in train) / len(train)
                for field, actual in (("outer_training_scaler_mean", mean), ("outer_training_scaler_variance", var)):
                    largest_scaler_difference = max(largest_scaler_difference, near(choice[field][j], actual, f"training-only scaler {key} {j}", atol=1e-9, rtol=1e-10))
        declared_fits = len(grids[method]) * 4 + 1
        require(choice["fit_count"] == declared_fits, "Declared fit-count mismatch")
        fits += declared_fits
        selected_rows.append({"case": case, "horizon_s": h, "method": method,
                              "selected_parameters": json.dumps(choice["selected_parameters"], sort_keys=True),
                              "inner_equal_case_mse_c2": finite(choice["selection_score_c2"]), "recorded_fit_count": declared_fits})
    require(observed == expected_keys and fits == 792, "Incomplete selections or recorded fit total")
    return {"outer_folds": len(folds), "selection_records": len(observed), "recorded_fit_count": fits,
            "nested_group_and_scaler_records_consistent": True,
            "selection_scores_reaggregated_from_saved_case_mses": True,
            "maximum_training_scaler_numeric_difference": largest_scaler_difference,
            "fits_executed_by_this_audit": 0,
            "scope_limit": "Saved inner predictions and fitted estimators are unavailable; validation MSEs and learned predictions were not regenerated by fitting."}, selected_rows


def usefulness_rows(per_case, pooled, cases):
    cp = keyed_rows(per_case, ("case", "horizon_s", "method"))
    pp = keyed_rows(pooled, ("horizon_s", "method"))
    result = []
    for h in HORIZONS:
        for method in METHODS[3:]:
            def beats(own, baselines):
                return all(own[m] < base[m] for base in baselines for m in ("rmse_c", "mae_c"))
            wins = [case for case in cases if beats(cp[case, h, method], [cp[case, h, b] for b in METHODS[:3]])]
            result.append({"horizon_s": h, "method": method,
                           "beats_all_three_baselines_on_both_pooled_metrics": beats(pp[h, method], [pp[h, b] for b in METHODS[:3]]),
                           "case_count_beating_all_on_both_metrics": len(wins), "cases_beating_all": wins})
    return result


def run(input_dir, output_dir, source_root=None):
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    require(input_dir.is_dir(), "Input experiment directory does not exist")
    require(not output_dir.exists(), "Output directory must be new; refusing overwrite")
    require(not output_dir.is_relative_to(input_dir), "Output directory cannot be inside read-only input tree")
    source_root = Path(source_root).resolve() if source_root else input_dir.parents[1]
    for name in REQUIRED:
        require((input_dir / name).is_file(), f"Required experiment artifact missing: {name}")
    initial = {name: sha(input_dir / name) for name in REQUIRED}
    summary, protocol = read_json(input_dir / "summary.json"), read_json(input_dir / "protocol.json")
    require(tuple(summary["methods"]) == METHODS and tuple(summary["horizons_s"]) == HORIZONS, "Unexpected declared benchmark methods/horizons")
    require(tuple(protocol["horizons_s"]) == HORIZONS and protocol["history_s"] == 60 and protocol["origin_spacing_s"] == 10, "Unexpected causal window protocol")
    hashes = audit_hashes(input_dir, source_root, summary)
    predictions = index_predictions(read_csv(input_dir / "predictions.csv.gz"))
    require(len(predictions) == 83980 == summary["prediction_rows"], "Expected 83,980 saved predictions")
    cases = sorted({k[0] for k in predictions})
    folds = validate_folds(read_json(input_dir / "fold_assignments.json"), cases)
    per_case, pooled = recompute_metrics(predictions, cases)
    differences = [compare_metrics(per_case, read_csv(input_dir / "per_case_metrics.csv"), ("case", "horizon_s", "method")),
                   compare_metrics(pooled, read_csv(input_dir / "table_4_pooled_metrics.csv"), ("horizon_s", "method")),
                   compare_metrics(per_case, summary["per_case_metrics"], ("case", "horizon_s", "method")),
                   compare_metrics(pooled, summary["pooled_metrics"], ("horizon_s", "method"))]
    require(len(per_case) == 180 and len(pooled) == 20, "Metric cell count mismatch")
    causal, features = audit_causality(input_dir, source_root, predictions)
    selection, selected_rows = audit_selections(read_json(input_dir / "per_fold_model_selection.json"), folds, features, protocol)
    useful = usefulness_rows(per_case, pooled, cases)
    require(useful == summary["usefulness"], "Usefulness rule readback mismatch")
    artifacts = sorted(p.relative_to(input_dir).as_posix() for p in input_dir.rglob("*")
                       if p.is_file() and "dependencies" not in p.relative_to(input_dir).parts and
                       p.suffix.lower() in (".pkl", ".pickle", ".joblib", ".onnx", ".pt", ".pth", ".h5", ".keras", ".ubj", ".cbm", ".skops", ".xgb", ".bin"))
    require(all(sha(input_dir / name) == digest for name, digest in initial.items()), "Experiment artifact changed during audit")
    require(audit_hashes(input_dir, source_root, summary) == hashes, "Scientific source changed during audit")
    result = {"audit_completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "passed": True, "ai_assistance": "Audit code and records were generated with AI assistance; no manuscript drafting is included.",
              "domain": "Self-generated A123-equivalent laboratory-cell surface-temperature surrogate; not measured battery or pack temperatures.",
              "target_generator_relation": "Physics-hold baseline uses the target generator's fixed ODE coefficients; future current and air are held at origin values.",
              "prediction_rows": len(predictions), "per_case_metric_rows": len(per_case), "pooled_metric_cells": len(pooled),
              "maximum_recomputed_metric_difference_c": max(differences), "causality": causal, "selection": selection,
              "saved_predictions_present": True, "serialized_model_artifacts_found": artifacts,
              "artifact_search_scope": "Experiment folder recursively, excluding dependencies; common estimator serialization suffixes only.",
              "trained_model_artifact_assessment": "No standard serialized estimators found; source constructs estimators in memory and saves predictions/selection records." if not artifacts else "Candidate serialized artifacts found; inspect before claiming reusability.",
              "prior_verification_record_passed": read_json(input_dir / "verification.json")["passed"],
              "prior_verification_is_independent_evidence": False,
              "source_hashes_verified": hashes,
              "private_documentary_provenance_excluded": True,
              "read_only_input_hashes_unchanged": True,
              "input_artifact_sha256": initial,
              "auditor_sha256": sha(Path(__file__)),
              "limitations": ["No refits were performed; saved learned predictions and inner validation MSEs cannot establish model-training reproducibility alone.",
                              "No serialized learned estimators or inner validation predictions were found in the named saved outputs.",
                              "Protocol says recorded before fitting, but chronology is not independently established by mutable local files.",
                              "Overlapping rows are dependent; nine deterministic cases are not independent physical experiments.",
                              "Constant nominal air and common generator provide no measured-battery, pack, field-alarm or thermal-runaway validation."]}
    output_dir.mkdir(parents=True)
    write_json(output_dir / "audit_ml.json", result)
    write_csv(output_dir / "recomputed_pooled_metrics.csv", pooled)
    write_csv(output_dir / "recomputed_per_case_metrics.csv", per_case)
    write_csv(output_dir / "selected_hyperparameters.csv", selected_rows)
    write_json(output_dir / "recomputed_usefulness.json", useful)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Existing experiment_a directory (read only)")
    parser.add_argument("--output", required=True, type=Path, help="New output directory; existing directories are rejected")
    parser.add_argument("--source-root", type=Path, help="Root holding the original scientific source subdirectories; defaults to input/../..")
    args = parser.parse_args()
    try:
        result = run(args.input, args.output, args.source_root)
    except (AuditError, OSError, KeyError, ValueError, TypeError) as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": result["passed"], "prediction_rows": result["prediction_rows"],
                      "pooled_metric_cells": result["pooled_metric_cells"], "per_case_metric_rows": result["per_case_metric_rows"],
                      "maximum_metric_difference_c": result["maximum_recomputed_metric_difference_c"],
                      "fits_executed": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
