"""Render five teaching figures from frozen archived experiment outputs.

No model execution or source modification. Install the repository plotting requirements first.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = REPO
if not (REPO / "data/derived").is_dir():
    raise RuntimeError("Run this script from its walkthroughs/2026-11-07/charts location inside the repository.")
os.environ.setdefault("MPLCONFIGDIR", str(HERE / ".mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import numpy as np

WORKSPACE = REPO / "reproducibility/data/workspace"
SOURCES = {
    "operations": REPO / "data/derived/thermal/operations_comparison.csv",
    "temperature": REPO / "data/derived/thermal/trace_C100_RR03.csv",
    "predictions": REPO / "data/derived/experiment_a/predictions.csv.gz",
    "metrics": WORKSPACE / "APCOM_Draft_Experiments_2026-10-27/experiment_a/table_4_pooled_metrics.csv",
    "thermal_protocol": WORKSPACE / "APCOM_Draft_Experiments_2026-10-27/thermal/protocol.json",
    "forecast_readme": WORKSPACE / "APCOM_Draft_Experiments_2026-10-27/experiment_a/RESULTS_README.txt",
    "operations_definitions": WORKSPACE / "APCOM_Study_2026-10-22/code/operations.py",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows, fields=None):
    path = HERE / name
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path.name


def finite(rows, fields):
    assert all(math.isfinite(float(row[field])) for row in rows for field in fields)


plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 23,
    "axes.labelsize": 25,
    "xtick.labelsize": 23,
    "ytick.labelsize": 23,
    "legend.fontsize": 22,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#5B6470",
    "axes.labelcolor": "#182C3D",
    "xtick.color": "#334657",
    "ytick.color": "#334657",
    "axes.linewidth": 1.5,
    "lines.linewidth": 3.3,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.formatter.useoffset": False,
})
BLUE, ORANGE, GREEN, DARK = "#1261A0", "#C65D11", "#008269", "#182C3D"
CAPACITIES = [283.2, 354.0, 424.8]
COLORS = [BLUE, ORANGE, GREEN]


def canvas():
    fig, ax = plt.subplots(figsize=(16, 8.5), dpi=100)
    fig.subplots_adjust(left=.115, right=.975, bottom=.16, top=.95)
    ax.grid(axis="y", color="#DCE3E9", linewidth=1.1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=6, width=1.25, pad=9)
    return fig, ax


def legend(ax, **kwargs):
    return ax.legend(frameon=False, handlelength=2.3, **kwargs)


def save(fig, name):
    for suffix in ("png", "svg"):
        fig.savefig(HERE / f"{name}.{suffix}", dpi=100)
    plt.close(fig)


def main():
    before = {key: digest(path) for key, path in SOURCES.items()}
    operations = read_csv(SOURCES["operations"])
    assert len(operations) == 9
    assert len({r["case"] for r in operations}) == 9
    assert {(float(r["capacity_kwh"]), int(r["rolling_resistance_pct"])) for r in operations} == {
        (capacity, rr) for capacity in CAPACITIES for rr in (2, 3, 4)}
    finite(operations, ["capacity_kwh", "rolling_resistance_pct", "recurring_cycle_energy_kwh",
                        "reserve_completed_loads", "reserve_completed_tonnes", "reserve_energy_kwh"])
    for row in operations:
        assert math.isclose(float(row["reserve_energy_kwh"]), .6 * float(row["capacity_kwh"]), abs_tol=1e-10)
        assert float(row["reserve_completed_tonnes"]) == 45 * int(row["reserve_completed_loads"])
        assert int(row["reserve_completed_loads"]) == int(row["complete_recurring_cycles_before_reserve"]) + 1
    ops_copy = write_csv("operations_9_cases.csv", operations)

    fig, ax = canvas()
    for capacity, color, marker in zip(CAPACITIES, COLORS, ["o", "s", "^"]):
        rows = sorted([r for r in operations if float(r["capacity_kwh"]) == capacity], key=lambda r: int(r["rolling_resistance_pct"]))
        ax.plot([float(r["rolling_resistance_pct"]) for r in rows],
                [float(r["recurring_cycle_energy_kwh"]) for r in rows],
                color=color, marker=marker, markersize=12, label=f"{capacity:g} kWh", zorder=3)
    ax.set(xlim=(1.9, 4.1), ylim=(55, 78), xticks=[2, 3, 4], yticks=[55, 60, 65, 70, 75],
           xlabel="Rolling resistance (%)", ylabel="Energy per recurring cycle (kWh)")
    legend(ax, loc="upper left", title="Nominal pack capacity", title_fontsize=23)
    save(fig, "01_cycle_energy")

    fig, ax = canvas()
    xx = np.arange(3)
    for j, (capacity, color) in enumerate(zip(CAPACITIES, COLORS)):
        rows = sorted([r for r in operations if float(r["capacity_kwh"]) == capacity], key=lambda r: int(r["rolling_resistance_pct"]))
        vals = [float(r["reserve_completed_tonnes"]) for r in rows]
        bars = ax.bar(xx + (j - 1) * .24, vals, width=.22, color=color, label=f"{capacity:g} kWh", zorder=3)
        ax.bar_label(bars, labels=[f"{v:g}" for v in vals], padding=7, fontsize=22, color=DARK)
    ax.set(xlim=(-.58, 2.58), ylim=(0, 245), xticks=xx, xticklabels=["2", "3", "4"],
           yticks=[0, 45, 90, 135, 180], xlabel="Rolling resistance (%)",
           ylabel="Completed tonnes before reserve")
    legend(ax, loc="upper center", ncol=3, title="Nominal pack capacity", title_fontsize=23)
    save(fig, "02_reserve_tonnes")

    temperature = read_csv(SOURCES["temperature"])
    finite(temperature, ["time_s", "temperature_c"])
    times = np.array([float(r["time_s"]) for r in temperature])
    temps = np.array([float(r["temperature_c"]) for r in temperature])
    assert np.all(np.diff(times) > 0)
    assert temps[0] == 25 and times[0] == 0
    reserve_c100 = next(float(r["reserve_time_min"]) for r in operations if r["case"] == "C100_RR03")
    assert math.isclose(times[-1] / 60, reserve_c100, abs_tol=1e-10)
    temperature_copy = write_csv("temperature_C100_RR03.csv", temperature)
    fig, ax = canvas()
    ax.plot(times / 60, temps, color=BLUE, label="A123-equivalent cell model", zorder=3)
    ax.axhline(25, color="#6C7680", linestyle="--", linewidth=2.4, label="Air: 25 °C", zorder=2)
    ax.set(xlim=(0, 86), ylim=(24.995, 25.089), xticks=[0, 20, 40, 60, 80],
           yticks=[25, 25.02, 25.04, 25.06, 25.08], xlabel="Elapsed time (min)",
           ylabel="Generated cell temperature (°C)")
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    legend(ax, loc="upper left", ncol=2)
    save(fig, "03_generated_temperature")

    predictions = read_csv(SOURCES["predictions"])
    methods = ["persistence", "ridge", "hist_gradient_boosting"]
    selected = [r for r in predictions if r["case"] == "C100_RR03" and int(r["horizon_s"]) == 300
                and r["method"] in ["persistence", "hist_gradient_boosting"]]
    finite(selected, ["origin_s", "target_s", "true_temperature_c", "predicted_temperature_c", "error_c"])
    series = {}
    for row in selected:
        target = float(row["target_s"])
        assert target - float(row["origin_s"]) == 300
        item = series.setdefault(target, {"origin_s": row["origin_s"], "target_s": row["target_s"],
                                           "generated_target_c": row["true_temperature_c"]})
        assert item["generated_target_c"] == row["true_temperature_c"]
        assert row["method"] + "_c" not in item
        item[row["method"] + "_c"] = row["predicted_temperature_c"]
        assert math.isclose(float(row["predicted_temperature_c"]) - float(row["true_temperature_c"]),
                            float(row["error_c"]), abs_tol=1e-12)
    forecast = [series[k] for k in sorted(series)]
    assert len(forecast) == 478
    assert all(len(r) == 5 for r in forecast)
    assert max(float(r["target_s"]) for r in forecast) <= times[-1]
    for row in forecast:
        assert math.isclose(float(row["generated_target_c"]),
                            np.interp(float(row["target_s"]), times, temps), abs_tol=1e-10)
    forecast_copy = write_csv("forecast_5min_C100_RR03.csv", forecast)
    fig, ax = canvas()
    target_min = np.array([float(r["target_s"]) for r in forecast]) / 60
    ax.plot(target_min, [float(r["generated_target_c"]) for r in forecast], color=DARK,
            linewidth=3.8, label="Generated target", zorder=4)
    ax.plot(target_min, [float(r["hist_gradient_boosting_c"]) for r in forecast], color=GREEN,
            linewidth=2.8, label="Boosting (5 min)", zorder=5)
    ax.plot(target_min, [float(r["persistence_c"]) for r in forecast], color=ORANGE,
            linestyle="--", linewidth=3, label="Persistence (5 min)", zorder=3)
    ax.set(xlim=(0, 86), ylim=(24.995, 25.089), xticks=[0, 20, 40, 60, 80],
           yticks=[25, 25.02, 25.04, 25.06, 25.08], xlabel="Target time (min)",
           ylabel="Generated cell temperature (°C)")
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    legend(ax, loc="upper center", ncol=3, columnspacing=1.5)
    save(fig, "04_forecast_5min")

    metrics = [r for r in read_csv(SOURCES["metrics"]) if int(r["horizon_s"]) in (300, 600) and r["method"] in methods]
    assert len(metrics) == 6
    finite(metrics, ["rmse_c", "mae_c", "n_origins"])
    recomputation = []
    for row in metrics:
        subset = [r for r in predictions if r["horizon_s"] == row["horizon_s"] and r["method"] == row["method"]]
        assert len(subset) == int(row["n_origins"])
        assert len({r["case"] for r in subset}) == 9
        finite(subset, ["true_temperature_c", "predicted_temperature_c"])
        rmse = math.sqrt(math.fsum((float(r["predicted_temperature_c"]) - float(r["true_temperature_c"])) ** 2 for r in subset) / len(subset))
        assert math.isclose(rmse, float(row["rmse_c"]), abs_tol=1e-12)
        recomputation.append({"horizon_s": int(row["horizon_s"]), "method": row["method"],
                              "n_origins": len(subset), "archived_rmse_c": float(row["rmse_c"]),
                              "recomputed_rmse_c": rmse})
    metrics_copy = write_csv("pooled_rmse_5_10min.csv", metrics)
    fig, ax = canvas()
    xx = np.arange(2)
    for j, (method, color, label) in enumerate(zip(methods, [ORANGE, BLUE, GREEN], ["Persistence", "Ridge", "Boosting"])):
        rows = sorted([r for r in metrics if r["method"] == method], key=lambda r: int(r["horizon_s"]))
        vals = [float(r["rmse_c"]) for r in rows]
        bars = ax.bar(xx + (j - 1) * .24, vals, width=.22, color=color, label=label, zorder=3)
        ax.bar_label(bars, labels=[f"{v:.4f}" for v in vals], padding=8, fontsize=22, color=DARK)
    ax.set(xlim=(-.55, 1.55), ylim=(0, .044), xticks=xx, xticklabels=["5 min", "10 min"],
           yticks=[0, .01, .02, .03, .04], xlabel="Forecast horizon",
           ylabel="Pooled RMSE on generated target (°C)")
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    legend(ax, loc="upper center", ncol=3)
    save(fig, "05_pooled_rmse")

    charts = [
        {"file": "01_cycle_energy.png", "sources": ["operations", "operations_definitions"], "data_copy": ops_copy,
         "teaching_claim": "Recurring-cycle energy increases with rolling resistance in all three archived configurations.",
         "definition": "Completed recurring unload-end to unload-end intervals; initialization-to-first-unload is excluded.",
         "scope": "Nine saved HAULSIM cases; capacity, mass and rating vary jointly across configuration scales."},
        {"file": "02_reserve_tonnes.png", "sources": ["operations", "operations_definitions"], "data_copy": ops_copy,
         "teaching_claim": "Reserve-completed output ranges from 90 to 180 tonnes in the nine saved cases.",
         "definition": "Fully completed 45-tonne deliveries before the external all-state 80% to 20% reserve cutoff, including the initial completed load.",
         "scope": "Uses reserve_completed_tonnes, not complete_recurring_cycles multiplied by payload."},
        {"file": "03_generated_temperature.png", "sources": ["temperature", "thermal_protocol"], "data_copy": temperature_copy,
         "teaching_claim": f"C100_RR03 generated cell-model temperature peaks at {max(temps):.5f} °C with 25 °C air.",
         "definition": "A123-equivalent cell surface model, from time zero to the case's external reserve endpoint.",
         "scope": "Generated cell scenario; not measured or validated Z50 pack temperature."},
        {"file": "04_forecast_5min.png", "sources": ["predictions", "temperature", "forecast_readme"], "data_copy": forecast_copy,
         "teaching_claim": "The held-out C100_RR03 series compares five-minute predictions at the same generated target times.",
         "definition": "All 478 eligible C100_RR03 origins at a 300-second horizon, plotted at target_s / 60. true_temperature_c is the generated target.",
         "scope": "Whole-configuration held-out surrogate forecast; no measured-pack accuracy claim."},
        {"file": "05_pooled_rmse.png", "sources": ["metrics", "predictions", "forecast_readme"], "data_copy": metrics_copy,
         "teaching_claim": "Boosting has lower pooled RMSE than ridge and persistence at both five and ten minutes in the archived generated-target benchmark.",
         "definition": "Exact archived pooled rmse_c values; displayed bar labels round to four decimal places. Six values independently checked against archived predictions.",
         "scope": "Nine configuration holdouts; overlapping forecast origins do not imply independent statistical replicates."},
    ]
    metadata = {
        "purpose": "Educational video charts; no new experiments or model changes",
        "dimensions_px": [1600, 850], "font": "Segoe UI with DejaVu Sans fallback",
        "renderer": {"python": sys.version, "matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "sources": {key: {"path": str(path), "relative_to_repository": path.relative_to(REPO).as_posix(),
                           "sha256": before[key]} for key, path in SOURCES.items()},
        "charts": charts,
        "validation": {"nine_cases": True, "factorial_3_by_3": True, "finite_plotted_values": True,
                       "reserve_energy_equals_60pct_capacity": True, "reserve_counts_include_initial_load": True,
                       "temperature_points": len(temperature), "forecast_target_count": len(forecast),
                       "forecast_exact_300s_alignment": True, "forecast_targets_match_temperature_trace": True,
                       "pooled_metric_recomputation": recomputation,
                       "source_hashes_unchanged_after_render": all(digest(path) == before[key] for key, path in SOURCES.items())},
    }
    assert metadata["validation"]["source_hashes_unchanged_after_render"]
    for chart in charts:
        chart["png_sha256"] = digest(HERE / chart["file"])
        chart["csv_sha256"] = digest(HERE / chart["data_copy"])
    (HERE / "sources.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"charts": [c["file"] for c in charts], "validation": metadata["validation"]}, indent=2))


if __name__ == "__main__":
    main()
