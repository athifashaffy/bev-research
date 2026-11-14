"""Draw the model-comparison figures from a saved compare.py run.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md. Reads only the
run's CSV files; run it through tools/run_with_proof.py to keep a proof record.

    python experiments/A_models/plot.py --run results/models-NEW --output results/models-NEW-figures
"""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LABELS = {"persistence": "Persistence", "linear_trend": "Linear trend", "physics_hold": "Thermal baseline",
          "ridge": "Ridge", "random_forest": "Random forest", "neural_network": "Neural network (MLP)",
          "hist_gradient_boosting": "HGB"}
STYLE = {"persistence": ("#9e9e9e", "--"), "linear_trend": ("#bdbdbd", ":"), "physics_hold": ("#616161", "-."),
         "ridge": ("#1f77b4", "-"), "random_forest": ("#2ca02c", "-"), "neural_network": ("#9467bd", "-"),
         "hist_gradient_boosting": ("#d62728", "-")}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    pooled = read(a.run / "pooled_metrics.csv")
    costs = read(a.run / "cost_summary.csv")
    horizons = sorted({int(r["horizon_s"]) for r in pooled})
    minutes = [h / 60 for h in horizons]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for m in LABELS:
        rows = sorted((r for r in pooled if r["method"] == m), key=lambda r: int(r["horizon_s"]))
        color, ls = STYLE[m]
        ax1.plot(minutes, [1000 * float(r["rmse_c"]) for r in rows], ls, color=color, marker="o", lw=2 if m == "hist_gradient_boosting" else 1.3, label=LABELS[m])
        ax2.plot(minutes, [float(r["r2_temperature"]) for r in rows], ls, color=color, marker="o", lw=2 if m == "hist_gradient_boosting" else 1.3)
    ax1.set(xscale="log", yscale="log", xlabel="Forecast horizon (min)", ylabel="Pooled RMSE (m°C), lower is better",
            title="(a) Forecast error")
    ax2.set(xscale="log", xlabel="Forecast horizon (min)", ylabel="R² on temperature, higher is better",
            title="(b) R² (1 = perfect, 0 = no better than the mean)", ylim=(-1, 1.02))
    ax2.axhline(0, color="black", lw=0.6)
    for ax in (ax1, ax2):
        ax.set_xticks(minutes, [f"{m:g}" for m in minutes]); ax.grid(alpha=0.3, which="both")
    fig.legend(loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(a.output / "models_rmse_r2.png", dpi=170, bbox_inches="tight")

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    names = [LABELS[r["method"]] for r in costs]
    colors = [STYLE[r["method"]][0] for r in costs]
    for ax, key, title in zip(axes, ("median_final_fit_s", "median_single_forecast_ms", "median_model_kb"),
                              ("Training time (s)", "Time per forecast (ms)", "Model size (KB)")):
        ax.barh(names, [float(r[key]) for r in costs], color=colors)
        ax.set_title(title); ax.grid(alpha=0.3, axis="x")
    fig.suptitle("Cost per model (median over the 45 held-out fits, one CPU thread)")
    fig.tight_layout()
    fig.savefig(a.output / "models_cost.png", dpi=170, bbox_inches="tight")
    print("wrote", a.output)


if __name__ == "__main__":
    main()
