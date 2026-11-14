"""Figure 2 with panels labelled (a) and (b), plus each panel as its own image.

AI-assisted plotting code (Claude, 13 November 2026). Same data and same curves
as make_plot() in report.py (unchanged): configuration C100_RR03 from the saved
A_live run; 30-minute forecasts plotted at their target times. Only panel
labels and titles are added. Every plotted value is read from the run's files.

    python tools/run_with_proof.py --output results/figure2-NEW --script experiments/A_live/figure2_labelled.py \
      --input results/run-2026-11-13/live/telemetry.csv.gz --input results/run-2026-11-13/live/predictions.csv.gz \
      -- python experiments/A_live/figure2_labelled.py --run results/run-2026-11-13/live --output results/figure2-NEW/figs
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CASE = "C100_RR03"
TITLE_A = "(a) Equivalent current of the 2.5 Ah reference cell"
TITLE_B = "(b) Surrogate temperature and 30-minute forecasts"
METHODS = [("hist_gradient_boosting", "Gradient boosting"), ("persistence", "Persistence"),
           ("physics_hold", "Thermal baseline")]


def read(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def check_run(run):
    """Refuse a run whose saved outputs differ from its proof record."""
    proof = json.loads((run / "PROOF.json").read_text())
    for name in ("telemetry.csv.gz", "predictions.csv.gz"):
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != proof["outputs_sha256"][name]:
            raise SystemExit(f"{name} differs from the run's proof record")


def panel_a(ax, sensors):
    ax.plot([float(r["time_s"]) / 60 for r in sensors], [float(r["equivalent_current_a"]) for r in sensors], color="#555555")
    ax.set_ylabel("Equivalent cell current (A)")
    ax.set_title(TITLE_A, loc="left", fontsize=11)


def panel_b(ax, sensors, predictions):
    ax.plot([float(r["time_s"]) / 60 for r in sensors], [float(r["reference_cell_temperature_c"]) for r in sensors],
            label="Surrogate temperature", color="black", linewidth=2)
    for method, label in METHODS:
        rr = [r for r in predictions if r["method"] == method]
        ax.plot([float(r["target_s"]) / 60 for r in rr], [float(r["predicted_temperature_c"]) for r in rr],
                label=label, alpha=.85)
    ax.set(xlabel="Simulation time (min)", ylabel="Surrogate temperature (°C)")
    ax.set_title(TITLE_B, loc="left", fontsize=11)
    ax.legend(fontsize=9)


def tidy(ax):
    ax.grid(alpha=.2)
    ax.ticklabel_format(useOffset=False, axis="y")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    check_run(a.run)
    a.output.mkdir(parents=True, exist_ok=False)
    sensors = [r for r in read(a.run / "telemetry.csv.gz") if r["case"] == CASE]
    predictions = [r for r in read(a.run / "predictions.csv.gz")
                   if r["case"] == CASE and int(r["horizon_s"]) == 1800]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7.4), sharex=True, layout="constrained")
    panel_a(ax1, sensors); panel_b(ax2, sensors, predictions)
    for ax in (ax1, ax2):
        tidy(ax)
    fig.savefig(a.output / "figure2_labelled.png", dpi=180)
    plt.close(fig)

    for name, draw in (("figure2a_current.png", lambda ax: panel_a(ax, sensors)),
                       ("figure2b_forecasts.png", lambda ax: panel_b(ax, sensors, predictions))):
        fig, ax = plt.subplots(figsize=(10, 3.9), layout="constrained")
        draw(ax); tidy(ax)
        if name.startswith("figure2a"):
            ax.set_xlabel("Simulation time (min)")
        fig.savefig(a.output / name, dpi=180)
        plt.close(fig)
    print(json.dumps({"case": CASE, "sensor_rows": len(sensors), "forecasts_per_method": sum(r["method"] == METHODS[0][0] for r in predictions),
                      "output": str(a.output)}))


if __name__ == "__main__":
    main()
