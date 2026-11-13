"""Draw the figures for the laboratory live-sensor forecasting run from its saved outputs.

AI-written (Claude, 12 November 2026). Reads a finished run folder of
experiments/A_lab/train.py and the three source records; writes PNG figures and
the win grid as CSV to a new folder. It fits nothing and changes no input.

Usage (from reproducibility/):
  python experiments/A_lab/plot_results.py --run results/RUN --output results/NEW_FIGURES
"""
from pathlib import Path
import argparse
import csv
import gzip
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parents[2] / "data/raw/a123_csv"
RECORDS = {"pulse_25C": ("A002_PeriodicPulseData.csv", "SurfaceTemperature", "Pulse test, 25 °C"),
           "udds_25C": ("A002_UDDS_P25.csv", "Ts1", "Drive cycle, 25 °C"),
           "udds_35C": ("A002_UDDS_P35.csv", "Ts", "Drive cycle, 35 °C")}
METHODS = [("hist_gradient_boosting", "Boosting (learned)", "#2a78d6"),
           ("ridge", "Ridge (learned)", "#eb6834"),
           ("physics_hold_meansq", "Heat formula, last-minute current", "#1baf7a"),
           ("physics_hold_last", "Heat formula, latest current", "#eda100"),
           ("linear_trend", "Keep the slope", "#e87ba4"),
           ("persistence", "Stay the same", "#008300")]
BASELINES = ["persistence", "linear_trend", "physics_hold_last", "physics_hold_meansq"]
SCOPES = [("udds_records_only", "Two drive-cycle recordings"), ("all_three_records", "All three recordings")]
HORIZONS = [60, 120, 300, 600, 1800]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#fcfcfb"
GOOD, BAD = "#0ca30c", "#d03b3b"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left"})


def save(fig, path):
    fig.savefig(path, dpi=160, metadata={"Software": None})
    plt.close(fig)


def read_pooled(run):
    with open(run / "pooled_metrics.csv", encoding="utf-8") as stream:
        return [{**r, "horizon_s": int(r["horizon_s"]), "rmse_c": float(r["rmse_c"]), "mae_c": float(r["mae_c"])}
                for r in csv.DictReader(stream)]


def figure_records(data_dir, out):
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.2), sharex="col", constrained_layout=True)
    for j, (name, (file, temp_column, title)) in enumerate(RECORDS.items()):
        with open(data_dir / file, encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        hours = np.array([float(r["time"]) for r in rows]) / 3600
        axes[0, j].plot(hours, [float(r["current"]) for r in rows], color="#2a78d6", lw=0.5)
        axes[1, j].plot(hours, [float(r[temp_column]) for r in rows], color="#eb6834", lw=1.0)
        axes[0, j].set_title(title)
        axes[1, j].set_xlabel("hours since start of recording")
    axes[0, 0].set_ylabel("measured current (A)")
    axes[1, 0].set_ylabel("measured cell surface\ntemperature (°C)")
    for ax in axes.ravel():
        ax.grid(axis="y", color=GRID, lw=0.6)
    save(fig, out / "fig1_lab_records.png")


def figure_errors(pooled, out):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.4), constrained_layout=True)
    x = np.arange(len(HORIZONS))
    for i, (scope, scope_label) in enumerate(SCOPES):
        for j, (key, label) in enumerate((("rmse_c", "RMSE: big misses count extra"), ("mae_c", "MAE: plain average miss"))):
            ax = axes[i, j]
            for method, name, color in METHODS:
                y = [next(r[key] for r in pooled if r["scope"] == scope and r["horizon_s"] == h and r["method"] == method) for h in HORIZONS]
                learned = method in ("hist_gradient_boosting", "ridge")
                ax.plot(x, y, color=color, lw=2.4 if learned else 1.6, marker="o", ms=5.5 if learned else 4,
                        ls="-" if learned else "--", label=name)
            ax.set_yscale("log")
            ax.set_yticks([0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 4], ["0.02", "0.05", "0.1", "0.2", "0.5", "1", "2", "4"])
            ax.minorticks_off()
            ax.set_xticks(x, [f"{h // 60} min" for h in HORIZONS])
            ax.set_title(f"{scope_label}\n{label}")
            ax.set_ylabel("error (°C), log scale")
            ax.set_xlabel("how far ahead the guess is")
            ax.grid(axis="y", color=GRID, lw=0.6)
    axes[0, 0].legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.suptitle("Forecast error on measured lab-cell temperature. Lower is better. Solid = learned, dashed = simple.", x=0.01, ha="left", fontsize=11)
    save(fig, out / "fig2_error_by_distance.png")


def figure_win_grid(pooled, out):
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), constrained_layout=True)
    names = {m: n for m, n, _ in METHODS}
    for ax, (scope, scope_label) in zip(axes, SCOPES):
        cols = [(b, k) for b in BASELINES for k in ("rmse_c", "mae_c")]
        for yi, h in enumerate(HORIZONS):
            at = {r["method"]: r for r in pooled if r["scope"] == scope and r["horizon_s"] == h}
            all_win = True
            for xi, (b, k) in enumerate(cols):
                win = at["hist_gradient_boosting"][k] < at[b][k]
                all_win &= win
                rows.append({"scope": scope, "horizon_s": h, "baseline": b, "score": k, "boosting": at["hist_gradient_boosting"][k],
                             "baseline_value": at[b][k], "boosting_lower": win})
                ax.add_patch(plt.Rectangle((xi + 0.04, yi + 0.06), 0.92, 0.88, color=GOOD if win else BAD, alpha=0.9))
                ax.text(xi + 0.5, yi + 0.5, "better" if win else "worse", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
            ax.text(len(cols) + 0.15, yi + 0.5, "WIN" if all_win else "no win", va="center", fontsize=9,
                    fontweight="bold" if all_win else "normal", color=INK if all_win else MUTED)
        ax.set_xlim(0, len(cols) + 1.3); ax.set_ylim(len(HORIZONS), 0)
        ax.set_xticks([i + 0.5 for i in range(len(cols))], ["RMSE" if k == "rmse_c" else "MAE" for _, k in cols], fontsize=8)
        ax.set_yticks([i + 0.5 for i in range(len(HORIZONS))], [f"{h // 60} min" for h in HORIZONS])
        for bi, b in enumerate(BASELINES):
            ax.text(bi * 2 + 1, -0.12, names[b].replace(", ", ",\n"), ha="center", va="bottom", fontsize=7.5, color=MUTED)
        ax.set_title(f"Boosting versus each simple method\n{scope_label}", pad=30)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
    save(fig, out / "fig3_boosting_win_grid.png")
    with open(out / "win_grid.csv", "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def figure_trace(run, out, record="udds_25C"):
    with gzip.open(run / "predictions.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["record"] == record and r["horizon_s"] in ("600", "1800")]
    show = [("persistence", "Stay the same", "#008300"), ("physics_hold_meansq", "Heat formula, last-minute current", "#1baf7a"),
            ("hist_gradient_boosting", "Boosting (learned)", "#2a78d6")]
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.6), sharex=True, constrained_layout=True)
    for ax, h in zip(axes, ("600", "1800")):
        sub = [r for r in rows if r["horizon_s"] == h]
        truth = sorted({(int(r["target_s"]), float(r["true_temperature_c"])) for r in sub})
        ax.plot([t / 3600 for t, _ in truth], [v for _, v in truth], color=INK, lw=2.2, label="Measured (answer key)")
        for method, name, color in show:
            pts = sorted((int(r["target_s"]), float(r["predicted_temperature_c"])) for r in sub if r["method"] == method)
            ax.plot([t / 3600 for t, _ in pts], [v for _, v in pts], color=color, lw=1.3, label=name)
        ax.set_title(f"Guesses made {int(h) // 60} minutes earlier, drawn at the time they were aiming for")
        ax.set_ylabel("cell surface temperature (°C)")
        ax.grid(axis="y", color=GRID, lw=0.6)
    axes[0].legend(frameon=False, fontsize=8.5, ncols=2, loc="upper left")
    axes[1].set_xlabel("hours since start of the 25 °C drive-cycle recording (this recording was held out of training)")
    save(fig, out / "fig4_example_forecasts.png")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True, help="Finished run folder of experiments/A_lab/train.py")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Folder holding the three A123 CSV records (read only)")
    parser.add_argument("--output", type=Path, required=True, help="New folder for the figures")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output folder already exists: {args.output}")
    pooled = read_pooled(args.run)
    args.output.mkdir(parents=True)
    figure_records(args.data, args.output)
    figure_errors(pooled, args.output)
    figure_win_grid(pooled, args.output)
    figure_trace(args.run, args.output)
    print(f"Figures written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
