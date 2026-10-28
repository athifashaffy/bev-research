"""Nested configuration-held-out forecasting of a self-generated cell surrogate.

This is a benchmark against the archived fixed generator, not measured pack
temperature forecasting or external physical validation. All writes stay here.
"""
from pathlib import Path
import os
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
import argparse
import csv
import datetime
import gzip
import hashlib
import json
import math
import platform
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "dependencies"))
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits, threadpool_info
import sklearn
import scipy

A = 4.344635339312832e-05
B = .002655462788692412
SEED = 20261027
HORIZONS = (60, 120, 300, 600)
METHODS = ("persistence", "linear_trend", "physics_hold", "ridge", "hist_gradient_boosting")
FEATURE_NAMES = [f"{signal}_{stat}" for signal in ("temperature_c", "equivalent_current_a", "air_c")
                 for stat in ("last", "mean", "minimum", "maximum", "slope_per_s", "last_difference")]
FEATURE_NAMES += ["capacity_kwh", "rolling_resistance_pct"]
GRIDS = {"ridge": [{"alpha": x} for x in (1, 100, 10000)],
         "hist_gradient_boosting": [{"max_iter": x} for x in (40, 80)]}


def nested_group_plan(group_names):
    names = sorted(set(map(str, group_names)))
    if len(names) != 9:
        raise ValueError("Exactly nine distinct whole configurations are required")
    result = []
    for held in names:
        train = [name for name in names if name != held]
        inner = []
        for i in range(4):
            validation = train[i::4]
            inner.append({"inner_fold": i, "validation_groups": validation,
                          "train_groups": [x for x in train if x not in validation]})
        result.append({"outer_test": held, "outer_train": train, "inner": inner})
    return result


def resample_past_held(time_s, values, maximum_gap_s=1.5):
    """Past hold on integer seconds within acquisition segments only.

    The interior of a missing acquisition interval is left NaN. Values after
    an origin never enter that origin's features; no linear interpolation is
    used. Segment availability is a retrospective eligibility check only.
    """
    t = np.asarray(time_s, dtype=float)
    y = np.asarray(values, dtype=float)
    if y.ndim == 1:
        y = y.reshape(-1, 1)
    if len(t) != len(y) or not len(t) or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError("Source time must be finite, aligned and strictly increasing")
    grid = np.arange(math.ceil(t[0]), math.floor(t[-1]) + 1, dtype=int)
    result = np.full((len(grid), y.shape[1]), np.nan)
    breaks = np.r_[0, np.flatnonzero(np.diff(t) > maximum_gap_s) + 1, len(t)]
    for start, stop in zip(breaks, breaks[1:]):
        use = (grid >= t[start]) & (grid <= t[stop - 1])
        indices = np.searchsorted(t[start:stop], grid[use], side="right") - 1 + start
        result[use] = y[indices]
    return grid, result


def features_at(values, index, capacity_kwh, rr_pct):
    if index < 60:
        return None
    past = np.asarray(values[index - 60:index + 1], dtype=float)
    if past.shape != (61, 3) or not np.all(np.isfinite(past)):
        return None
    x = np.arange(-60., 1.)
    centered = x - x.mean()
    slopes = centered @ past / (centered @ centered)
    row = []
    for j in range(3):
        col = past[:, j]
        row.extend((col[-1], col.mean(), col.min(), col.max(), slopes[j], col[-1] - col[-2]))
    row.extend((capacity_kwh, rr_pct))
    return np.asarray(row, dtype=float)


def build_examples(case, grid_s, values, capacity_kwh, rr_pct, horizon_s, spacing_s=10):
    grid = np.asarray(grid_s, dtype=int)
    if len(grid) != len(values) or np.any(np.diff(grid) != 1):
        raise ValueError("Expected a contiguous one-second grid with NaN acquisition gaps")
    rows, origin, truth, current_t, delta, now_i, now_air = [], [], [], [], [], [], []
    earliest = int(math.ceil((grid[0] + 60) / spacing_s) * spacing_s)
    for ti in range(earliest, int(grid[-1] - horizon_s) + 1, spacing_s):
        index = ti - grid[0]
        # Every method receives the same origins. Future values are read only
        # for target/availability, never for the feature or held-input baseline.
        if not np.all(np.isfinite(values[index - 60:index + horizon_s + 1])):
            continue
        features = features_at(values, index, capacity_kwh, rr_pct)
        if features is None:
            continue
        target = values[index + horizon_s, 0]
        temp = values[index, 0]
        rows.append(features); origin.append(ti); truth.append(target)
        current_t.append(temp); delta.append(target - temp)
        now_i.append(values[index, 1]); now_air.append(values[index, 2])
    return {"case": case, "origin_s": np.asarray(origin, dtype=int), "x": np.asarray(rows),
            "target_c": np.asarray(truth), "origin_temperature_c": np.asarray(current_t),
            "delta_c": np.asarray(delta), "current_a": np.asarray(now_i), "air_c": np.asarray(now_air)}


def physics_forecast(temperature_c, current_a, air_c, horizon_s, a=A, b=B):
    temp, amps, air = np.asarray(temperature_c), np.asarray(current_a), np.asarray(air_c)
    if b == 0:
        return temp + a * amps ** 2 * horizon_s
    return temp + (air - temp + a * amps ** 2 / b) * (-math.expm1(-b * horizon_s))


def error_metrics(target, predicted):
    error = np.asarray(predicted) - np.asarray(target)
    return {"n_origins": len(error), "rmse_c": float(np.sqrt(np.mean(error ** 2))),
            "mae_c": float(np.mean(np.abs(error))), "max_absolute_error_c": float(np.max(np.abs(error)))}


def estimator(method, parameters):
    if method == "ridge":
        return Pipeline([("scale", StandardScaler()),
                         ("model", Ridge(alpha=parameters["alpha"], fit_intercept=True))])
    if method == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(max_iter=parameters["max_iter"], learning_rate=.08,
                    max_depth=3, max_leaf_nodes=7, min_samples_leaf=20, l2_regularization=.0001,
                    max_bins=64, early_stopping=False, random_state=SEED)
    raise ValueError(method)


def fit_selected(method, x, delta, groups, fold, deadline=None):
    """Inner selection and final preprocessing never see the outer test case."""
    start = time.perf_counter()
    groups = np.asarray(groups)
    candidates = []
    fit_count = 0
    for params in GRIDS[method]:
        case_mses, inner_audits = [], []
        for inner in fold["inner"]:
            if deadline is not None and time.perf_counter() > deadline:
                raise TimeoutError("Prespecified 1200 s fit budget exceeded")
            train = np.isin(groups, inner["train_groups"])
            valid = np.isin(groups, inner["validation_groups"])
            if set(groups[train]) & set(groups[valid]) or fold["outer_test"] in set(groups[train]) | set(groups[valid]):
                raise AssertionError("Group leakage")
            model = estimator(method, params)
            model.fit(x[train], delta[train]); fit_count += 1
            pred = model.predict(x[valid])
            valid_groups = groups[valid]
            mses = {name: float(np.mean((pred[valid_groups == name] - delta[valid][valid_groups == name]) ** 2))
                    for name in inner["validation_groups"]}
            case_mses.extend(mses.values())
            inner_audits.append({**inner, "n_train_origins": int(train.sum()), "n_validation_origins": int(valid.sum()),
                                 "validation_case_mse_c2": mses,
                                 "scaler_fitted_groups": inner["train_groups"] if method == "ridge" else None})
        candidates.append({"parameters": params, "equal_case_mean_validation_mse_c2": float(np.mean(case_mses)),
                           "inner_folds": inner_audits})
    chosen = min(candidates, key=lambda c: c["equal_case_mean_validation_mse_c2"])
    train = np.isin(groups, fold["outer_train"])
    if fold["outer_test"] in set(groups[train]) or set(groups[train]) != set(fold["outer_train"]):
        raise AssertionError("Outer training groups inconsistent")
    model = estimator(method, chosen["parameters"])
    model.fit(x[train], delta[train]); fit_count += 1
    scale = model.named_steps["scale"] if method == "ridge" else None
    audit = {"method": method, "outer_test": fold["outer_test"], "outer_train": fold["outer_train"],
             "selected_parameters": chosen["parameters"], "selection_score_c2": chosen["equal_case_mean_validation_mse_c2"],
             "candidates": candidates, "n_outer_train_origins": int(train.sum()), "fit_count": fit_count,
             "scaler_fitted_groups": fold["outer_train"] if scale is not None else None,
             "outer_training_scaler_mean": scale.mean_.tolist() if scale is not None else None,
             "outer_training_scaler_variance": scale.var_.tolist() if scale is not None else None,
             "elapsed_s": time.perf_counter() - start}
    return model, audit


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def write_csv(path, rows):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def load_cases(source):
    cases = {}
    with source.open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            name = row["case"]
            if name not in cases:
                cases[name] = {"time_s": [], "values": [], "capacity_kwh": float(row["capacity_kwh"]),
                               "rr_pct": float(row["rr_percent"])}
            c = cases[name]
            c["time_s"].append(float(row["time_s"]))
            temp, rise = float(row["temperature_c"]), float(row["rise_c"])
            c["values"].append([temp, float(row["equivalent_current_a"]), temp - rise])
    for name, c in cases.items():
        c["grid_s"], c["grid_values"] = resample_past_held(c["time_s"], c["values"])
    if len(cases) != 9:
        raise ValueError("Nine archived nominal traces required")
    return cases


def run():
    start = time.perf_counter()
    protocol_path = HERE / "protocol.json"
    protocol_hash = sha(protocol_path)
    source = ROOT / "APCOM_Study_2026-10-22/results/thermal_nominal_traces.csv"
    audit_source = ROOT / "APCOM_Study_2026-10-22/results/thermal_audit.json"
    ops_source = ROOT / "APCOM_Study_2026-10-22/results/operations_audit.json"
    model_source = ROOT / "APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json"
    source_draft = HERE.parent / "source_draft.txt"
    inputs = [source, audit_source, ops_source, model_source, source_draft, protocol_path]
    before_hashes = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    cases = load_cases(source)
    plan = nested_group_plan(cases)
    write_json(HERE / "fold_assignments.json", plan)
    thermal = json.loads(audit_source.read_text())
    reserve = {r["case"]: r["reserve_time_min"] * 60 for r in json.loads(ops_source.read_text())["comparison"]}
    for name, c in cases.items():
        if not math.isclose(c["time_s"][-1], reserve[name], abs_tol=1e-7):
            raise ValueError("Archived trace is not clipped at the verified reserve")
        if not np.allclose(np.asarray(c["values"])[:, 2], 25., rtol=0, atol=1e-12):
            raise ValueError("Unexpected nominal air boundary")
    examples = {h: {name: build_examples(name, c["grid_s"], c["grid_values"], c["capacity_kwh"], c["rr_pct"], h)
                    for name, c in cases.items()} for h in HORIZONS}
    feature_rows, eligible = [], []
    for h, bycase in examples.items():
        for name, e in bycase.items():
            c = cases[name]
            raw_times = np.asarray(c["time_s"])
            for i, origin in enumerate(e["origin_s"]):
                latest_raw = raw_times[np.searchsorted(raw_times, origin, side="right") - 1]
                assert latest_raw <= origin
                row = {"case": name, "horizon_s": h, "origin_s": int(origin), "history_start_s": int(origin - 60),
                       "latest_input_source_s": float(latest_raw), "target_s": int(origin + h),
                       "reserve_endpoint_s": c["time_s"][-1]}
                eligible.append(row)
                feature_rows.append({**row, **dict(zip(FEATURE_NAMES, map(float, e["x"][i])))})
    write_csv(HERE / "eligible_origins.csv", eligible)
    write_csv(HERE / "causal_features.csv.gz", feature_rows)
    write_json(HERE / "pre_fit_audit.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol_sha256": protocol_hash, "input_hashes": before_hashes, "feature_names": FEATURE_NAMES,
        "planned_fit_count": 792, "origin_count_by_horizon_case": {str(h): {n: len(e["origin_s"]) for n,e in bycase.items()} for h,bycase in examples.items()},
        "maximum_latest_input_minus_origin_s": max(r["latest_input_source_s"] - r["origin_s"] for r in eligible),
        "air_feature_variances": {str(h): np.var(np.vstack([e["x"] for e in bycase.values()]), axis=0)[12:18].tolist() for h,bycase in examples.items()},
        "raw_source_gap_count": {n: int(np.sum(np.diff(c["time_s"]) > 1.5)) for n,c in cases.items()},
        "reserve_endpoints_verified": True, "resampling_future_interpolation": False})
    print(json.dumps({"phase": "pre-fit audit saved", "fit_count": 792,
                      "eligible_origins": {h: sum(len(e["origin_s"]) for e in bycase.values()) for h,bycase in examples.items()}}), flush=True)
    predictions, per_case, selections = [], [], []
    deadline = start + 1200
    with threadpool_limits(limits=1):
        actual_threadpools = threadpool_info()
        for h, bycase in examples.items():
            x = np.vstack([e["x"] for e in bycase.values()])
            delta = np.concatenate([e["delta_c"] for e in bycase.values()])
            groups = np.concatenate([np.repeat(name, len(e["origin_s"])) for name,e in bycase.items()])
            for fold in plan:
                held = fold["outer_test"]
                e = bycase[held]
                now = e["origin_temperature_c"]
                pred = {"persistence": now, "linear_trend": now + e["x"][:, 4] * h,
                        "physics_hold": physics_forecast(now, e["current_a"], e["air_c"], h)}
                for method in ("ridge", "hist_gradient_boosting"):
                    model, selection = fit_selected(method, x, delta, groups, fold, deadline)
                    pred[method] = now + model.predict(e["x"])
                    selections.append({"horizon_s": h, **selection})
                for method in METHODS:
                    per_case.append({"case": held, "horizon_s": h, "method": method,
                                     **error_metrics(e["target_c"], pred[method])})
                for i, origin in enumerate(e["origin_s"]):
                    for method in METHODS:
                        predictions.append({"case": held, "horizon_s": h, "origin_s": int(origin),
                                            "target_s": int(origin + h), "method": method,
                                            "origin_temperature_c": float(now[i]), "true_temperature_c": float(e["target_c"][i]),
                                            "predicted_temperature_c": float(pred[method][i]),
                                            "error_c": float(pred[method][i] - e["target_c"][i])})
                print(json.dumps({"phase": "outer fold complete", "horizon_s": h, "held_case": held,
                                  "n_origins": len(now), "elapsed_s": round(time.perf_counter() - start, 2)}), flush=True)
    pooled = []
    for h in HORIZONS:
        for method in METHODS:
            rows = [r for r in predictions if r["horizon_s"] == h and r["method"] == method]
            metric = error_metrics([r["true_temperature_c"] for r in rows], [r["predicted_temperature_c"] for r in rows])
            casescores = [r for r in per_case if r["horizon_s"] == h and r["method"] == method]
            pooled.append({"horizon_s": h, "method": method, **metric,
                           "case_rmse_min_c": min(r["rmse_c"] for r in casescores),
                           "case_rmse_max_c": max(r["rmse_c"] for r in casescores),
                           "case_mae_min_c": min(r["mae_c"] for r in casescores),
                           "case_mae_max_c": max(r["mae_c"] for r in casescores)})
    usefulness = []
    for h in HORIZONS:
        for method in ("ridge", "hist_gradient_boosting"):
            own = next(r for r in pooled if r["horizon_s"] == h and r["method"] == method)
            baselines = [r for r in pooled if r["horizon_s"] == h and r["method"] in METHODS[:3]]
            wins = []
            for name in cases:
                a = next(r for r in per_case if r["horizon_s"] == h and r["method"] == method and r["case"] == name)
                bs = [r for r in per_case if r["horizon_s"] == h and r["method"] in METHODS[:3] and r["case"] == name]
                if all(a["rmse_c"] < b["rmse_c"] and a["mae_c"] < b["mae_c"] for b in bs):
                    wins.append(name)
            usefulness.append({"horizon_s": h, "method": method,
                               "beats_all_three_baselines_on_both_pooled_metrics": all(own["rmse_c"] < b["rmse_c"] and own["mae_c"] < b["mae_c"] for b in baselines),
                               "case_count_beating_all_on_both_metrics": len(wins), "cases_beating_all": wins})
    assert len(per_case) == 180 and len(pooled) == 20 and len(selections) == 72
    assert sum(s["fit_count"] for s in selections) == 792
    assert all(sha(ROOT / relative) == digest for relative,digest in before_hashes.items())
    write_csv(HERE / "predictions.csv.gz", predictions)
    write_csv(HERE / "per_case_metrics.csv", per_case)
    write_csv(HERE / "table_4_pooled_metrics.csv", pooled)
    write_json(HERE / "per_fold_model_selection.json", selections)
    summary = {"completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "completed": True,
        "domain": "SELF_GENERATED_A123_EQUIVALENT_SURFACE_TEMPERATURE; NOT MEASURED PACK; NOT PHYSICAL VALIDATION",
        "physics_baseline_relation_to_target": "Truth was generated by the same frozen ODE and coefficients used by physics_hold. Future current is held constant in that baseline, rather than supplied from the generator. This is not an independent physics-model validation.",
        "model_coefficients": {"a_K_per_A2_s": A, "b_per_s": B}, "outer_folds": 9,
        "inner_group_folds_per_outer": 4, "horizons_s": HORIZONS, "methods": METHODS,
        "model_fit_count": 792, "per_case_metric_rows": len(per_case), "pooled_metric_cells": len(pooled),
        "prediction_rows": len(predictions), "eligible_origin_rows": len(eligible), "feature_count": 20,
        "origin_spacing_s": 10, "history_s": 60, "temperature_range_c": [min(v[0] for c in cases.values() for v in c["values"]), max(v[0] for c in cases.values() for v in c["values"])],
        "air_range_c": [25,25], "air_features_constant": True,
        "elapsed_total_s_before_figures": time.perf_counter() - start,
        "fit_elapsed_s_sum": sum(s["elapsed_s"] for s in selections), "threadpools_during_fit": actual_threadpools,
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__},
        "input_and_protocol_hashes": before_hashes, "code_hashes": {p.name: sha(p) for p in (Path(__file__), HERE / "test_forecasting.py")},
        "test_first_evidence": "Nine tests were executed red before implementation, including group disjointness, gap/no-future processing, outer test perturbation, horizon/current units, and preservation of small errors.",
        "limitations": ["Deterministic self-generated target from the same fixed ODE as one baseline.", "Constant 25 C air gives no ambient-generalization evidence.", "Capacity, pack mass and available power vary together in the archived configurations.", "Overlapping histories and horizons yield dependent rows; no row-level confidence intervals or significance tests.", "Outer temperature/current histories are causal inputs, but outer targets never enter preprocessing, tuning or fitting.", "No thermal-runaway forecasting, warning lead time, field false-alarm rate or pack-temperature validation follows from these scores."],
        "pooled_metrics": pooled, "per_case_metrics": per_case, "usefulness": usefulness,
        "reproduction": "& 'C:/Users/athif/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'C:/Users/athif/Documents/ChatGPT/BEV/APCOM_Draft_Experiments_2026-10-27/experiment_a/forecasting.py'"}
    write_json(HERE / "summary.json", summary)
    make_figures(predictions, pooled)
    print(json.dumps({"complete": True, "elapsed_s": time.perf_counter() - start, "usefulness": usefulness}), flush=True)


def make_figures(predictions, pooled):
    sys.path.insert(0, str(ROOT / "New_Afton_Experiments_2026-10-20/tools"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 9.5,
                         "axes.labelsize": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    colors = {"persistence": "#888888", "linear_trend": "#b09b25", "physics_hold": "#734d99",
              "ridge": "#166c9c", "hist_gradient_boosting": "#d16a24"}
    labels = {"persistence": "Persistence", "linear_trend": "60 s trend", "physics_hold": "ODE hold input",
              "ridge": "Ridge", "hist_gradient_boosting": "Histogram boosting"}
    fig, axes = plt.subplots(2, 1, figsize=(6.5, 5.2), sharex=True, layout="constrained")
    for ax, h in zip(axes, (60, 600)):
        rows = [r for r in predictions if r["case"] == "C100_RR03" and r["horizon_s"] == h]
        actual = [r for r in rows if r["method"] == "persistence"]
        ax.plot([r["target_s"] / 60 for r in actual], [r["true_temperature_c"] - 25 for r in actual],
                color="#222222", lw=1.8, label="Surrogate truth")
        for method in METHODS:
            use = [r for r in rows if r["method"] == method]
            ax.plot([r["target_s"] / 60 for r in use], [r["predicted_temperature_c"] - 25 for r in use],
                    color=colors[method], lw=1.0, alpha=.9, label=labels[method], linestyle=":" if method == "persistence" else "-")
        ax.set(title=f"C100_RR03 held out: {h} s horizon", ylabel="A123-equivalent rise (°C)")
        ax.grid(alpha=.18)
    axes[-1].set_xlabel("Target time in reserve-limited record (min)")
    handles, legends = axes[0].get_legend_handles_labels()
    fig.legend(handles, legends, loc="outside lower center", ncol=3, fontsize=8)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(HERE / f"experiment_a_predictions.{ext}", dpi=250)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(6.5, 3.0), sharey=True, layout="constrained")
    fig.suptitle("Self-generated target. Usefulness requires both RMSE and MAE improvement.", fontsize=8.5)
    for ax, baseline in zip(axes, METHODS[:3]):
        for method in METHODS[3:]:
            skill = []
            for h in HORIZONS:
                own = next(r for r in pooled if r["horizon_s"] == h and r["method"] == method)
                base = next(r for r in pooled if r["horizon_s"] == h and r["method"] == baseline)
                skill.append(1 - own["rmse_c"] / base["rmse_c"])
            ax.plot(np.array(HORIZONS) / 60, skill, "-o", color=colors[method], label=labels[method], ms=4)
        ax.axhline(0, color="#555555", lw=.8)
        ax.set(title="Relative to " + labels[baseline], xlabel="Horizon (min)", xticks=[1,2,5,10])
        ax.grid(alpha=.15)
    axes[0].set_ylabel("RMSE skill: 1 - model / baseline")
    handles, legends = axes[0].get_legend_handles_labels()
    fig.legend(handles, legends, loc="outside lower center", ncol=2, fontsize=8)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(HERE / f"experiment_a_skill.{ext}", dpi=250)
    plt.close(fig)


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
