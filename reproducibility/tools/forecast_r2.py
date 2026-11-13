"""RMSE, MAE and R² for the saved Experiment A predictions, plus an equation-to-code map.

AI-assisted tool (Claude, 13 November 2026). Reads saved files only; fits nothing.

Usage (from reproducibility/):
  python tools/forecast_r2.py --output results/r2-check-001

R² is reported two ways, because they answer different questions:
  r2_level   R² of the predicted temperature against the true temperature.
  r2_change  R² of the predicted temperature CHANGE (T(t+h) - T(t)) against the true change.
             This is what the models were trained to predict.
Both use R² = 1 - SSE / SST, with SST taken around the mean of the true values
in the same pool. The squared errors are identical in both; only SST differs.

Self-check: pooled RMSE and MAE must equal the archived Table 4 to 1e-12 °C,
otherwise the script stops without writing results.
"""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

PREDICTIONS = Path("experiments/A/reproduction_run_2026-10-28/predictions.csv.gz")
TABLE4 = Path("experiments/A/archived_reference/table_4_pooled_metrics.csv")
METHODS = ("persistence", "linear_trend", "physics_hold", "ridge", "hist_gradient_boosting")
HORIZONS = (60, 120, 300, 600)

# Equation numbers follow audits/physics/equation_audit.csv.
EQUATIONS = [
    (1, "P = 60 E / Δt (event power)", "data/workspace/APCOM_Study_2026-10-22/code/thermal_analysis.py", "prepare_events", "power_kw="),
    (2, "I_eq = 2.5 Ah × P / E_nom (equivalent current)", "data/workspace/APCOM_Study_2026-10-22/code/thermal_analysis.py", "equivalent_current", "return"),
    (2, "I_eq (portable copy)", "src/bev_research/thermal_model.py", "equivalent_current", "return"),
    (3, "dT/dt = a I² − b (T − T_air) (heat balance, used to fit a and b)", "data/workspace/APCOM_Coupled_Thermal_2026-10-16/code/fit_model.py", "predict", "eq=air"),
    (4, "Exact step solution of Eq. 3", "data/workspace/APCOM_Study_2026-10-22/code/thermal_analysis.py", "exact_step", "expm1"),
    (4, "Exact step (portable copy)", "src/bev_research/thermal_model.py", "step", "return"),
    (4, "Physics-hold forecast uses the same solution", "experiments/A/train.py", "physics_forecast", "expm1"),
    (5, "ΔT∞ = g a I² / b ; τ = 1 / b", "src/bev_research/thermal_model.py", "equilibrium_rise_c", "return"),
    (5, "τ = 1 / b", "src/bev_research/thermal_model.py", "time_constant_s", "return"),
]


def stats(pairs):
    """pairs: (true_level, pred_level, true_change, pred_change)."""
    n = len(pairs)
    err = [p[1] - p[0] for p in pairs]
    sse = math.fsum(e * e for e in err)
    out = {"n": n, "rmse_c": math.sqrt(sse / n), "mae_c": math.fsum(abs(e) for e in err) / n}
    for name, idx in (("r2_level", 0), ("r2_change", 2)):
        mean = math.fsum(p[idx] for p in pairs) / n
        sst = math.fsum((p[idx] - mean) ** 2 for p in pairs)
        out[name] = 1 - sse / sst if sst > 0 else float("nan")
    return out


def load(base: Path):
    pooled, per_case = defaultdict(list), defaultdict(list)
    with gzip.open(base / PREDICTIONS, "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            origin = float(row["origin_temperature_c"])
            true, pred = float(row["true_temperature_c"]), float(row["predicted_temperature_c"])
            item = (true, pred, true - origin, pred - origin)
            key = (row["method"], int(row["horizon_s"]))
            pooled[key].append(item)
            per_case[key + (row["case"],)].append(item)
    return pooled, per_case


def self_check(base: Path, results: dict):
    worst = 0.0
    for row in csv.DictReader(open(base / TABLE4, newline="", encoding="utf-8")):
        mine = results[(row["method"], int(row["horizon_s"]))]
        worst = max(worst, abs(mine["rmse_c"] - float(row["rmse_c"])), abs(mine["mae_c"] - float(row["mae_c"])))
        if int(row["n_origins"]) != mine["n"]:
            raise SystemExit(f"Origin count differs from Table 4 for {row['method']} {row['horizon_s']}")
    if worst > 1e-12:
        raise SystemExit(f"RMSE/MAE differ from archived Table 4 by {worst:.3e} °C; no results written")
    return worst


def find_line(path: Path, func: str | None, needle: str):
    lines = path.read_text(encoding="utf-8").splitlines()
    if func is None:
        for i, line in enumerate(lines, 1):
            if "a*" in line.replace(" ", "") and "b*" in line.replace(" ", "") and "**2" in line.replace(" ", ""):
                return i, i, line.strip()
        raise SystemExit(f"Heat-balance line not found in {path}")
    tree = ast.parse("\n".join(lines))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            for i in range(node.lineno, node.end_lineno + 1):
                if needle in lines[i - 1]:
                    return node.lineno, i, lines[i - 1].strip()
            return node.lineno, node.lineno, lines[node.lineno - 1].strip()
    raise SystemExit(f"Function {func} not found in {path}")


def plot(results: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = {"persistence": "Persistence", "linear_trend": "Linear trend", "physics_hold": "Physics hold",
             "ridge": "Ridge", "hist_gradient_boosting": "Gradient boosting"}
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), layout="constrained")
    x = range(len(HORIZONS))
    for method in METHODS:
        axes[0].plot(x, [results[(method, h)]["rmse_c"] * 1000 for h in HORIZONS], marker="o", label=names[method])
        axes[1].plot(x, [results[(method, h)]["r2_change"] for h in HORIZONS], marker="o", label=names[method])
    for ax, label in zip(axes, ("RMSE (thousandths of °C)", "R² on temperature change")):
        ax.set_xticks(list(x), [f"{h // 60} min" for h in HORIZONS])
        ax.set_xlabel("Forecast horizon")
        ax.set_ylabel(label)
        ax.grid(alpha=.25)
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].axhline(1, color="grey", lw=0.6, ls="--")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center", ncol=5, frameon=False, fontsize=8)
    fig.savefig(path, dpi=200)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output folder already exists: {args.output}")
    pooled, per_case = load(args.base)
    results = {key: stats(rows) for key, rows in pooled.items()}
    worst = self_check(args.base, results)
    args.output.mkdir(parents=True)
    with open(args.output / "forecast_metrics.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["horizon_s", "method", "n_origins", "rmse_c", "mae_c", "r2_level", "r2_change",
                         "case_r2_change_min", "case_r2_change_max", "case_r2_level_min", "case_r2_level_max"])
        for h in HORIZONS:
            for m in METHODS:
                r = results[(m, h)]
                cases = [stats(v) for k, v in per_case.items() if k[0] == m and k[1] == h]
                writer.writerow([h, m, r["n"], r["rmse_c"], r["mae_c"], r["r2_level"], r["r2_change"],
                                 min(c["r2_change"] for c in cases), max(c["r2_change"] for c in cases),
                                 min(c["r2_level"] for c in cases), max(c["r2_level"] for c in cases)])
    eq = []
    for number, name, file, func, needle in EQUATIONS:
        start, line, code = find_line(args.base / file, func, needle)
        eq.append({"equation": number, "name": name, "file": file, "function": func,
                   "function_line": start, "line": line, "code": code})
    (args.output / "equation_code_map.json").write_text(json.dumps(eq, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    plot(results, args.output / "forecast_rmse_r2.png")
    print(f"Self-check passed: RMSE/MAE match archived Table 4 (max difference {worst:.1e} °C).")
    print(f"Wrote forecast_metrics.csv, equation_code_map.json, forecast_rmse_r2.png to {args.output}")


if __name__ == "__main__":
    main()
