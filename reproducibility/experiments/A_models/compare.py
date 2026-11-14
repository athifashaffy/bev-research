"""Compare HGB with other machine-learning models on the paper's forecasting task.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

Reuses, unchanged, everything that defines the Table 2 experiment
(experiments/A_live): the nine simulated 1 Hz sensor records, the 20 inputs,
the five horizons, the nested leave-one-configuration-out plan and the HGB
settings. Adds three other model families, each given the same treatment:
a small settings grid chosen on the four inner splits, a refit on the eight
training configurations, and a test on the held-out one.

    ridge                   linear: one weight per input, kept small by a penalty
    random_forest           many deep trees averaged (bagging), not boosted
    neural_network          small multilayer perceptron
    hist_gradient_boosting  the paper's model (recomputed; must equal Table 2)

Besides RMSE and MAE it reports R^2 (on temperature and on temperature change),
per-configuration wins, training time, time per single forecast and model size.

    python experiments/A_models/compare.py --output results/models-NEW [--check-table2 results/run-2026-11-13/live]
"""
from pathlib import Path
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
import argparse, csv, datetime, gzip, json, pickle, platform, sys, time, warnings  # noqa: E401

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "A_live"))

import numpy as np  # noqa: E402
import scipy  # noqa: E402
import sklearn  # noqa: E402
from sklearn.compose import TransformedTargetRegressor  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.exceptions import ConvergenceWarning  # noqa: E402
from sklearn.neural_network import MLPRegressor  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

import train as live  # noqa: E402  (A_live/train.py, unchanged)

original = live.original          # experiments/A/train.py, unchanged
SEED = original.SEED
BASELINES = ("persistence", "linear_trend", "physics_hold")
MODELS = ("ridge", "random_forest", "neural_network", "hist_gradient_boosting")
GRIDS = {
    "ridge": original.GRIDS["ridge"],                                   # alpha 1, 100, 10000 (as in Experiment A)
    "random_forest": [{"max_depth": d} for d in (8, None)],
    "neural_network": [{"alpha": a} for a in (1e-4, 1e-2)],
    "hist_gradient_boosting": original.GRIDS["hist_gradient_boosting"],  # 40 or 80 iterations (as in the paper)
}


def estimator(method, p):
    if method in ("ridge", "hist_gradient_boosting"):
        return original.estimator(method, p)                         # identical objects to the paper's code
    if method == "random_forest":
        return RandomForestRegressor(n_estimators=100, max_depth=p["max_depth"], min_samples_leaf=20,
                                     max_features=1.0, random_state=SEED, n_jobs=1)
    if method == "neural_network":
        net = MLPRegressor(hidden_layer_sizes=(32, 32), alpha=p["alpha"], learning_rate_init=1e-3,
                           max_iter=300, early_stopping=False, random_state=SEED)
        # Temperature changes are ~0.001 C, so inputs and target are both standardised.
        return TransformedTargetRegressor(Pipeline([("scale", StandardScaler()), ("model", net)]),
                                          transformer=StandardScaler())
    raise ValueError(method)


def fit_selected(method, x, delta, groups, fold):
    """Same selection rule as experiments/A/train.py fit_selected, for any method."""
    candidates, fits = [], 0
    for params in GRIDS[method]:
        mses = []
        for inner in fold["inner"]:
            train = np.isin(groups, inner["train_groups"]); valid = np.isin(groups, inner["validation_groups"])
            if set(groups[train]) & set(groups[valid]) or fold["outer_test"] in set(groups[train]) | set(groups[valid]):
                raise AssertionError("Group leakage")
            model = estimator(method, params); model.fit(x[train], delta[train]); fits += 1
            pred = model.predict(x[valid]); g = groups[valid]
            mses.extend(float(np.mean((pred[g == n] - delta[valid][g == n]) ** 2)) for n in inner["validation_groups"])
        candidates.append({"parameters": params, "mean_validation_mse_c2": float(np.mean(mses))})
    chosen = min(candidates, key=lambda c: c["mean_validation_mse_c2"])
    train = np.isin(groups, fold["outer_train"])
    if fold["outer_test"] in set(groups[train]):
        raise AssertionError("Outer test configuration in training data")
    start = time.perf_counter()
    model = estimator(method, chosen["parameters"]); model.fit(x[train], delta[train]); fits += 1
    return model, {"selected": chosen["parameters"], "candidates": candidates, "fits": fits,
                   "final_fit_s": time.perf_counter() - start}


def single_forecast_seconds(model, row, repeats=200):
    """Median wall time of one predict() call on one input row (what an edge device does every 10 s)."""
    row = row.reshape(1, -1); times = []
    for _ in range(repeats):
        t = time.perf_counter(); model.predict(row); times.append(time.perf_counter() - t)
    return float(np.median(times))


def r2(target, predicted):
    target, predicted = np.asarray(target), np.asarray(predicted)
    return float(1 - np.sum((target - predicted) ** 2) / np.sum((target - target.mean()) ** 2))


def scores(rows):
    y = np.array([r["target_temperature_c"] for r in rows]); p = np.array([r["predicted_temperature_c"] for r in rows])
    now = np.array([r["origin_temperature_c"] for r in rows])
    return {**original.error_metrics(y, p), "r2_temperature": r2(y, p), "r2_change": r2(y - now, p - now)}


def run(output, check_table2=None):
    output = live.validate_output(output)
    if (np.__version__, scipy.__version__, sklearn.__version__) != ("2.3.5", "1.16.3", "1.7.2"):
        raise RuntimeError("Use experiments/A/requirements.txt")
    cases, streams, source_hashes = live.load_scenarios()
    plan = original.nested_group_plan(cases)
    output.mkdir(parents=True)
    original.write_json(output / "status.json", {"state": "RUNNING"})
    original.write_json(output / "protocol.json", {
        "based_on": "experiments/A_live (Table 2): same sensor records, inputs, horizons, folds and HGB settings",
        "models": MODELS, "baselines": BASELINES, "grids": GRIDS, "seed": SEED,
        "selection": "lowest equal-configuration mean validation MSE over the 4 inner splits, then refit on 8",
        "scores": "pooled RMSE, MAE, R^2 on temperature and on temperature change; per-configuration wins",
        "timing": "single-thread; final-fit seconds and median single-row predict seconds on this machine",
        "domain": "Generated reference-cell temperatures from ideal simulated sensors; not measured pack data."})
    predictions, per_case, selections, costs = [], [], [], []
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    with live.threadpool_limits(limits=1):
        for h in live.HORIZONS:
            ex = {n: live.build_examples(s, cases[n]["capacity_kwh"], cases[n]["rr_pct"], h) for n, s in streams.items()}
            x = np.vstack([e["x"] for e in ex.values()]); delta = np.concatenate([e["delta_c"] for e in ex.values()])
            groups = np.concatenate([np.repeat(n, len(e["origin_s"])) for n, e in ex.items()])
            for fold in plan:
                name = fold["outer_test"]; e = ex[name]; now = e["x"][:, 0]
                pred = {"persistence": now, "linear_trend": now + e["x"][:, 4] * h,
                        "physics_hold": original.physics_forecast(now, e["x"][:, 6], e["x"][:, 12], h)}
                for method in MODELS:
                    model, sel = fit_selected(method, x, delta, groups, fold)
                    pred[method] = now + model.predict(e["x"])
                    selections.append({"horizon_s": h, "outer_test": name, "method": method, **sel})
                    costs.append({"horizon_s": h, "outer_test": name, "method": method, "final_fit_s": sel["final_fit_s"],
                                  "single_forecast_s": single_forecast_seconds(model, e["x"][0]),
                                  "model_bytes": len(pickle.dumps(model))})
                for method in BASELINES + MODELS:
                    rows = [dict(case=name, horizon_s=h, method=method, origin_s=int(t), target_s=int(t + h),
                                 origin_temperature_c=float(now[i]), target_temperature_c=float(e["target_c"][i]),
                                 predicted_temperature_c=float(pred[method][i])) for i, t in enumerate(e["origin_s"])]
                    predictions.extend(rows)
                    per_case.append({"case": name, "horizon_s": h, "method": method, **scores(rows)})
            print(json.dumps({"horizon_s": h, "finished": True}), flush=True)

    pooled = []
    for h in live.HORIZONS:
        for method in BASELINES + MODELS:
            rows = [r for r in predictions if r["horizon_s"] == h and r["method"] == method]
            wins = sum(1 for n in cases if all(
                next(c for c in per_case if c["case"] == n and c["horizon_s"] == h and c["method"] == method)[k]
                < next(c for c in per_case if c["case"] == n and c["horizon_s"] == h and c["method"] == o)[k]
                for o in BASELINES + MODELS if o != method for k in ("rmse_c", "mae_c")))
            pooled.append({"horizon_s": h, "method": method, **scores(rows), "configurations_best_on_both": wins})
    summary_costs = []
    for method in MODELS:
        c = [r for r in costs if r["method"] == method]
        summary_costs.append({"method": method, "median_final_fit_s": float(np.median([r["final_fit_s"] for r in c])),
                              "median_single_forecast_ms": 1000 * float(np.median([r["single_forecast_s"] for r in c])),
                              "median_model_kb": float(np.median([r["model_bytes"] for r in c])) / 1024})

    table2 = None
    if check_table2:
        saved = {}
        with gzip.open(Path(check_table2) / "predictions.csv.gz", "rt", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["method"] == "hist_gradient_boosting":
                    saved[(r["case"], int(r["horizon_s"]), int(r["origin_s"]))] = float(r["predicted_temperature_c"])
        mine = {(r["case"], r["horizon_s"], r["origin_s"]): r["predicted_temperature_c"]
                for r in predictions if r["method"] == "hist_gradient_boosting"}
        table2 = {"saved_run": str(check_table2), "hgb_forecasts_compared": len(saved),
                  "all_identical": saved == mine}
        if not table2["all_identical"]:
            raise AssertionError("Recomputed HGB differs from the saved Table 2 run")

    for file, rows in [("predictions.csv.gz", predictions), ("pooled_metrics.csv", pooled),
                       ("per_case_metrics.csv", per_case), ("costs.csv", costs), ("cost_summary.csv", summary_costs)]:
        original.write_csv(output / file, rows)
    original.write_json(output / "model_selection.json", selections)
    versions = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "sklearn": sklearn.__version__, "platform": platform.platform()}
    original.write_json(output / "summary.json", {"versions": versions, "table2_hgb_check": table2,
                                                  "metrics": pooled, "costs": summary_costs})
    scripts = [Path(__file__), HERE.parent / "A_live/train.py", HERE.parent / "A_live/telemetry.py",
               HERE.parent / "A/train.py", HERE.parent / "A_causal/inputs.py"]
    for p, digest in source_hashes.items():
        if original.sha(p) != digest:
            raise AssertionError("Source changed during run")
    original.write_json(output / "status.json", {"state": "COMPLETE"})
    original.write_json(output / "PROOF.json", {
        "recorded_by": "AI-assisted experiments/A_models/compare.py",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "command": [Path(sys.executable).name, *sys.argv], "versions": versions,
        "inputs_and_scripts_sha256": {**source_hashes, **{str(p): original.sha(p) for p in scripts}},
        "outputs_sha256": {p.name: original.sha(p) for p in sorted(output.iterdir()) if p.name != "PROOF.json"}})
    print(json.dumps({"complete": True, "table2_hgb_check": table2}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check-table2", type=Path, help="saved A_live run; recomputed HGB must match it exactly")
    a = parser.parse_args()
    run(a.output, a.check_table2)
