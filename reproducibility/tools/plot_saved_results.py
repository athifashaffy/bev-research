"""AI-assisted plotting wrapper for saved simulation/forecast results only.

Usage:
  python plot_saved_results.py --root /path/to/data/root --output /path/to/new/figures

Requires NumPy and Matplotlib (the reference render used NumPy 2.3.5 and
Matplotlib 3.10.7). The input directory must retain the relative layout in INPUTS.
No manuscript, document-authoring, equation-image, model-fitting or simulation code
is imported or executed. The three plot routines are adapted from the saved
build_revision.py plotting routines; the accompanying PLOT_INPUTS.json identifies
the source and exact baseline inputs. The code and validation are AI-assisted.

Only operations/thermal/forecast .png, .svg and .pdf are written, in --output.
Current input/output SHA256 hashes, versions and validation counts go to stdout.
The renderer uses the saved row values without refitting, interpolation or new
scientific calculations. Display transformations are time / 60 and temperature
minus 25 degrees C. thermal includes only within_common_window == 'True'; forecast
includes only case C100_RR03 and horizons 300/600 s, displayed at target_s.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INPUTS = {
    "operations": "APCOM_Study_2026-10-22/results/operations_comparison.csv",
    "thermal_summary": "APCOM_Draft_Experiments_2026-10-27/thermal/table2_common_window.csv",
    "thermal_traces": "APCOM_Draft_Experiments_2026-10-27/thermal/nominal_traces.csv",
    "predictions": "APCOM_Draft_Experiments_2026-10-27/experiment_a/predictions.csv.gz",
}
CAPACITIES = (283.2, 354.0, 424.8)
RESISTANCES = (2, 3, 4)
CASES = {f"C{scale:03d}_RR{rr:02d}" for scale in (80, 100, 120) for rr in RESISTANCES}
METHODS = ("persistence", "linear_trend", "physics_hold", "ridge", "hist_gradient_boosting")
COLORS = ["#007785", "#d4841c", "#7c4280"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path, excluded_numeric, required):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None, f"Empty CSV: {path}")
        require(set(required) <= set(reader.fieldnames), f"Missing columns in {path}")
        rows = list(reader)
    require(rows, f"No rows: {path}")
    for line_number, row in enumerate(rows, 2):
        require(None not in row, f"Malformed extra fields in {path}:{line_number}")
        for key, value in row.items():
            if key in excluded_numeric:
                continue
            try:
                number = float(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Non-numeric {key} in {path}:{line_number}") from exc
            require(math.isfinite(number), f"Non-finite {key} in {path}:{line_number}")
    return rows


def unique_cases(rows, label):
    require(len(rows) == 9, f"{label}: expected exactly nine rows")
    require(len({r['case'] for r in rows}) == 9, f"{label}: duplicate case")
    require({r['case'] for r in rows} == CASES, f"{label}: unexpected/missing cases")


def expected_configuration(row, resistance_key, label):
    case = row["case"]
    require(case in CASES, f"{label}: unknown case {case}")
    scale = int(case[1:4]) / 100
    rr = int(case[-2:])
    require(abs(float(row['capacity_kwh']) - 354 * scale) < 1e-8,
            f"{label}: capacity does not match case {case}")
    require(float(row[resistance_key]) == rr, f"{label}: resistance does not match case {case}")


def load_and_validate(root):
    paths = {key: root / relative for key, relative in INPUTS.items()}
    before = {key: sha256(path) for key, path in paths.items()}
    operations = read_csv(paths["operations"], {"case"},
                          {"case", "capacity_kwh", "rolling_resistance_pct",
                           "recurring_cycle_energy_kwh", "reserve_time_min", "reserve_completed_tonnes"})
    thermal = read_csv(paths["thermal_summary"], {"case", "window", "temperature_domain"},
                       {"case", "capacity_kwh", "rr_percent", "window_end_s", "air_c", "initial_temperature_c"})
    traces = read_csv(paths["thermal_traces"], {"case", "state", "within_common_window"},
                      {"case", "capacity_kwh", "rr_percent", "time_s", "temperature_c", "air_c",
                       "within_common_window", "own_reserve_endpoint_s"})
    predictions = read_csv(paths["predictions"], {"case", "method"},
                           {"case", "horizon_s", "origin_s", "target_s", "method",
                            "true_temperature_c", "predicted_temperature_c"})
    unique_cases(operations, "operations")
    unique_cases(thermal, "thermal summary")
    for row in operations:
        expected_configuration(row, "rolling_resistance_pct", "operations")
    for row in thermal:
        expected_configuration(row, "rr_percent", "thermal summary")
        require(row["window"] == "common", "Thermal summary must describe the common window")
        require(float(row['air_c']) == float(row['initial_temperature_c']) == 25,
                "Reference thermal plot requires 25 degree air and initial conditions")
    common_end = {r["case"]: float(r["window_end_s"]) for r in thermal}
    last_time = {}
    common_counts = collections.Counter()
    for row in traces:
        expected_configuration(row, "rr_percent", "thermal traces")
        case, time = row["case"], float(row["time_s"])
        require(case not in last_time or time > last_time[case],
                f"Trace times must be unique and strictly sorted within {case}")
        require(time >= 0 and time <= float(row['own_reserve_endpoint_s']) + 1e-7,
                f"Trace outside reserve interval for {case}")
        require(float(row['air_c']) == 25, "Reference thermal trace must have 25 degree air")
        require(row["within_common_window"] in ("True", "False"), "Invalid common-window flag")
        require((row["within_common_window"] == "True") == (time <= common_end[case] + 1e-7),
                f"Inconsistent common-window filter for {case}")
        if row["within_common_window"] == "True":
            common_counts[case] += 1
        last_time[case] = time
    require(set(last_time) == CASES and set(common_counts) == CASES, "Missing nominal/common-window cases")
    prediction_keys, prediction_cases = set(), set()
    last_target, origin_methods, truths = {}, collections.defaultdict(set), {}
    for row in predictions:
        case, method = row["case"], row["method"]
        h = float(row["horizon_s"])
        require(case in CASES and method in METHODS, "Unexpected prediction case/method")
        require(h in (60, 120, 300, 600), "Unexpected prediction horizon")
        origin, target = float(row["origin_s"]), float(row["target_s"])
        require(abs(target - origin - h) < 1e-8, "Prediction target does not equal origin plus horizon")
        key, series = (case, h, method, origin), (case, h, method)
        require(key not in prediction_keys, f"Duplicate prediction key {key}")
        require(series not in last_target or target > last_target[series],
                f"Prediction target times must be strictly sorted within {series}")
        prediction_keys.add(key)
        prediction_cases.add(case)
        last_target[series] = target
        origin_key = (case, h, origin)
        origin_methods[origin_key].add(method)
        truth = float(row["true_temperature_c"])
        require(origin_key not in truths or truths[origin_key] == truth,
                "Methods disagree on the saved generated target")
        truths[origin_key] = truth
    require(prediction_cases == CASES, "Predictions do not cover all nine cases")
    require(all(methods == set(METHODS) for methods in origin_methods.values()),
            "Missing expected methods at a prediction origin")
    selected = [r for r in predictions if r["case"] == "C100_RR03" and int(r["horizon_s"]) in (300, 600)]
    selected_counts = collections.Counter((int(r["horizon_s"]), r["method"]) for r in selected)
    require(set(selected_counts) == {(h, m) for h in (300, 600) for m in METHODS},
            "Central forecast plot must have five methods at both 300/600 second horizons")
    after = {key: sha256(path) for key, path in paths.items()}
    require(before == after, "An input changed while reading")
    return operations, traces, selected, {
        "inputs": [{"key": key, "relative_path": INPUTS[key], "sha256": before[key]} for key in INPUTS],
        "validation": {"operations_cases": len(operations), "thermal_summary_cases": len(thermal),
                       "nominal_trace_rows": len(traces), "common_window_rows_by_case": dict(common_counts),
                       "prediction_rows": len(predictions), "selected_prediction_rows": len(selected),
                       "selected_series_rows": {f"{h}:{m}": n for (h, m), n in sorted(selected_counts.items())},
                       "finite_numeric_values": True, "unique_sorted_times": True,
                       "all_expected_methods_per_origin": True, "inputs_unchanged": True}}


def savefig(fig, key, output):
    for ext in ("png", "pdf", "svg"):
        fig.savefig(output / f"{key}.{ext}", dpi=330, bbox_inches="tight", pad_inches=.05)
    plt.close(fig)


def plot_operations(operations, output):
    fig, axs = plt.subplots(1, 3, figsize=(6.4, 2.4), layout="constrained")
    keys = ["recurring_cycle_energy_kwh", "reserve_time_min", "reserve_completed_tonnes"]
    labels = ["Cycle energy (kWh)", "Time to reserve (min)", "Completed payload (t)"]
    lookup = {(float(r["capacity_kwh"]), int(r["rolling_resistance_pct"])): r for r in operations}
    for n, (ax, key, label) in enumerate(zip(axs, keys, labels)):
        vals = np.array([[float(lookup[(c, rr)][key]) for rr in RESISTANCES] for c in CAPACITIES])
        ax.imshow(vals, cmap="YlGnBu", aspect="auto", vmin=vals.min()-.2*(vals.max()-vals.min()),
                  vmax=vals.max()+.1*(vals.max()-vals.min()))
        ax.set_xticks(range(3), ["2", "3", "4"])
        ax.set_yticks(range(3), ["283.2", "354", "424.8"])
        ax.set_xlabel("Rolling resistance (%)")
        ax.set_ylabel("Nominal energy (kWh)" if n == 0 else "")
        ax.text(0, 1.16, f"({chr(97+n)})", transform=ax.transAxes, fontweight="bold")
        ax.text(.5, 1.04, label, transform=ax.transAxes, ha="center", fontsize=9)
        for i in range(3):
            for j in range(3):
                value = vals[i, j]
                ax.text(j, i, f"{value:.1f}" if n < 2 else f"{value:.0f}", ha="center", va="center",
                        fontsize=9, color="white" if value > vals.mean() else "#132d3c")
        ax.tick_params(length=0)
    savefig(fig, "operations", output)


def plot_thermal(traces, output):
    fig, axs = plt.subplots(1, 3, figsize=(6.4, 2.65), sharey=True, layout="constrained")
    for n, ax in enumerate(axs):
        for color, cap in zip(COLORS, CAPACITIES):
            rows = [r for r in traces if int(r["rr_percent"]) == n+2
                    and float(r["capacity_kwh"]) == cap and r["within_common_window"] == "True"]
            ax.plot([float(r["time_s"])/60 for r in rows], [float(r["temperature_c"])-25 for r in rows],
                    color=color, lw=1.25, label=f"{cap:g} kWh")
        ax.set_xlim(0, 68.04)
        ax.set_ylim(0, .105)
        ax.set_xticks([0, 20, 40, 60])
        ax.set_xlabel("Elapsed time (min)")
        ax.grid(alpha=.18)
        ax.text(.02, 1.04, f"({chr(97+n)})", transform=ax.transAxes, fontweight="bold")
        if n == 0:
            ax.set_ylabel("Cell-equivalent rise (°C)")
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, frameon=False)
    savefig(fig, "thermal", output)


def plot_forecast(predictions, output):
    fig, axs = plt.subplots(2, 1, figsize=(6.4, 3.8), sharex=True, sharey=True, layout="constrained")
    names = ["Persistence", "Linear trend", "Held-input model", "Ridge", "Boosting"]
    colors = ["#8a9098", "#bc9146", "#38799d", "#90679b", "#d45d28"]
    for ax, h, n in zip(axs, (300, 600), (0, 1)):
        rows = [r for r in predictions if int(r["horizon_s"]) == h and r["method"] == "persistence"]
        ax.plot([float(r["target_s"])/60 for r in rows], [float(r["true_temperature_c"])-25 for r in rows],
                color="#152d39", lw=1.9, label="Generated target", zorder=8)
        for method, name, color in zip(METHODS, names, colors):
            rows = [r for r in predictions if int(r["horizon_s"]) == h and r["method"] == method]
            ax.plot([float(r["target_s"])/60 for r in rows],
                    [float(r["predicted_temperature_c"])-25 for r in rows], color=color, lw=1.0,
                    label=name, alpha=.9, ls="--" if method in ("persistence", "ridge") else "-")
        ax.text(.015, .9, f"({chr(97+n)})", transform=ax.transAxes, fontweight="bold")
        ax.grid(alpha=.18)
        ax.set_ylabel("Cell-equivalent rise (°C)")
        ax.set_xlim(0, 86)
    axs[-1].set_xlabel("Forecast target time (min)")
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, frameon=False)
    savefig(fig, "forecast", output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, type=Path, help="Root containing the four relative input paths")
    parser.add_argument("--output", required=True, type=Path, help="Separate folder for nine plot files")
    args = parser.parse_args(argv)
    root, output = args.root.resolve(strict=True), args.output.resolve()
    protected = {root / Path(p).parent for p in INPUTS.values()}
    protected.add(root / "APCOM_Ezz_Revision_2026-10-28/figures")
    require(output != root and all(output != p and p not in output.parents for p in protected),
            "--output must be separate from the input and original figure directories")
    operations, traces, predictions, report = load_and_validate(root)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.labelsize": 9, "xtick.labelsize": 8,
                         "ytick.labelsize": 8, "legend.fontsize": 8, "svg.fonttype": "none",
                         "savefig.facecolor": "white"})
    plot_operations(operations, output)
    plot_thermal(traces, output)
    plot_forecast(predictions, output)
    report.update({"disclosure": "AI-assisted plotting and input-validation code; saved results only",
                   "versions": {"python": platform.python_version(), "numpy": np.__version__,
                                "matplotlib": matplotlib.__version__},
                   "filters": {"thermal": "within_common_window == True", "forecast_case": "C100_RR03",
                               "forecast_horizons_s": [300, 600], "forecast_alignment": "target_s",
                               "temperature_display": "temperature_c - 25", "time_display": "seconds / 60"},
                   "outputs": [{"name": f"{key}.{ext}", "sha256": sha256(output / f"{key}.{ext}")}
                               for key in ("operations", "thermal", "forecast") for ext in ("png", "svg", "pdf")]})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f"Input/output validation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
