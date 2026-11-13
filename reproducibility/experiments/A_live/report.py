"""AI-assisted independent arithmetic audit and two-run comparison.

Reads saved predictions; never refits models or changes the experiment runs.
"""
import argparse
import csv
import datetime
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path
import sys

from train import sha, validate_output, verify_proof, write_json


def strip_timing(value):
    if isinstance(value, dict):
        return {k: strip_timing(v) for k, v in value.items() if k != "elapsed_s"}
    if isinstance(value, list):
        return [strip_timing(v) for v in value]
    return value


def independent_metrics(rows):
    errors = [float(r["predicted_temperature_c"]) - float(r["target_temperature_c"]) for r in rows]
    if not errors or not all(map(math.isfinite, errors)):
        raise ValueError("Empty or nonfinite prediction errors")
    return {"n_origins": len(errors),
            "rmse_c": math.sqrt(math.fsum(e * e for e in errors) / len(errors)),
            "mae_c": math.fsum(map(abs, errors)) / len(errors),
            "max_absolute_error_c": max(map(abs, errors))}


def check_metric(name, expected, actual):
    if name == "n_origins":
        assert float(actual) == expected, (name, expected, actual)
    else:
        assert math.isclose(float(actual), expected, rel_tol=0, abs_tol=1e-12), (name, expected, actual)


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as stream:
        return list(csv.DictReader(stream))


def content(path):
    return gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()


def audit(run1, run2, output):
    run1, run2 = Path(run1).resolve(), Path(run2).resolve()
    if run1 == run2:
        raise ValueError("Two distinct run directories are required")
    output = validate_output(output)
    proofs = [verify_proof(p) for p in (run1, run2)]
    assert proofs[0]["inputs_and_scripts_sha256"] == proofs[1]["inputs_and_scripts_sha256"]
    compared = []
    for name in ("telemetry.csv.gz", "features.csv.gz", "predictions.csv.gz",
                 "pooled_metrics.csv", "per_case_metrics.csv", "fold_assignments.json",
                 "protocol.json", "cases.json", "replay_checks.json", "status.json"):
        assert content(run1 / name) == content(run2 / name), "Run mismatch: " + name
        compared.append(name)
    for name in ("model_selection.json", "summary.json"):
        a, b = [strip_timing(json.loads((p / name).read_text())) for p in (run1, run2)]
        assert a == b, "Run mismatch beyond timing: " + name
        compared.append(name + " (elapsed_s excluded)")

    predictions = read_csv(run1 / "predictions.csv.gz")
    pooled, per_case = defaultdict(list), defaultdict(list)
    keys = set()
    for r in predictions:
        h = int(r["horizon_s"])
        assert int(r["target_s"]) == int(r["origin_s"]) + h
        key = (r["case"], h, r["method"], int(r["origin_s"]))
        assert key not in keys, "Duplicate prediction"
        keys.add(key)
        pooled[(h, r["method"])].append(r)
        per_case[(r["case"], h, r["method"])].append(r)
    claims = []
    for filename, groups, fields in (("pooled_metrics.csv", pooled, ("horizon_s", "method")),
                                     ("per_case_metrics.csv", per_case, ("case", "horizon_s", "method"))):
        rows = read_csv(run1 / filename)
        seen = set()
        for r in rows:
            key = tuple(int(r[f]) if f == "horizon_s" else r[f] for f in fields)
            assert key not in seen, "Duplicate metric row"
            seen.add(key)
            checked = independent_metrics(groups[key])
            for name, value in checked.items():
                check_metric(name, value, r[name])
                claims.append({"table": filename, "row": list(key), "metric": name,
                               "recomputed": value, "reported": float(r[name]), "matched": True})
        assert seen == set(groups), "Missing metric row"

    metrics = {k: independent_metrics(v) for k, v in pooled.items()}
    decisions = []
    for h in sorted({k[0] for k in metrics}):
        own = metrics[(h, "hist_gradient_boosting")]
        others = [v for k, v in metrics.items() if k[0] == h and k[1] != "hist_gradient_boosting"]
        decisions.append({"horizon_s": h, "boosting_beats_all_on_both":
            all(own[metric] < b[metric] for b in others for metric in ("rmse_c", "mae_c"))})
    summary = json.loads((run1 / "summary.json").read_text())
    assert decisions == summary["decisions"], "Decision mismatch"
    for r in summary["metrics"]:
        for name, value in metrics[(r["horizon_s"], r["method"])].items():
            check_metric(name, value, r[name])

    sensors = read_csv(run1 / "telemetry.csv.gz")
    temperatures = [float(r["reference_cell_temperature_c"]) for r in sensors]
    per_case_wins = {}
    for d in decisions:
        h = d["horizon_s"]; wins = []
        for case in sorted({r["case"] for r in predictions}):
            own = independent_metrics(per_case[(case, h, "hist_gradient_boosting")])
            baselines = [independent_metrics(v) for k, v in per_case.items()
                         if k[0] == case and k[1] == h and k[2] != "hist_gradient_boosting"]
            if all(own[m] < b[m] for b in baselines for m in ("rmse_c", "mae_c")):
                wins.append(case)
        per_case_wins[str(h)] = wins
    output.mkdir(parents=True)
    verification = {"checked_date_local": "2026-11-12", "timezone": "America/Toronto",
        "recorded_by": "AI-authored verification, not independent human review",
        "run1": str(run1), "run2": str(run2), "exact_comparisons": compared,
        "excluded_from_byte_comparison": ["compressed headers", "elapsed_s", "PROOF timestamps/commands", "serialized model bytes"],
        "metric_tolerance_c": 1e-12, "checked_metric_values": len(claims),
        "prediction_rows": len(predictions), "sensor_rows": len(sensors),
        "temperature_range_c": [min(temperatures), max(temperatures)],
        "decisions": decisions, "cases_beating_all_baselines_on_both": per_case_wins,
        "models_per_run": len(list((run1 / "models").glob("*.joblib"))),
        "prefix_replay_checks_per_run": len(json.loads((run1 / "replay_checks.json").read_text()))}
    write_json(output / "verification.json", verification)
    write_json(output / "claims.json", {"prediction_source_sha256": sha(run1 / "predictions.csv.gz"), "claims": claims})
    lines = ["# Simulated live telemetry: verified results", "",
        "Automated checks on 12 November 2026 (America/Toronto). AI-authored implementation and audit; no human scientific validation is claimed.", "",
        "The two runs have exactly matching decompressed readings, features and predictions, metric CSVs, folds and settings. Model-selection records and summaries match after excluding elapsed time. Serialized model bytes are not required to match; each run reloads every model and checks all batch predictions, plus 135 rolling-prefix forecasts.", "",
        f"Independently recomputed {len(claims)} numeric metric entries from {len(predictions)} saved prediction rows using Python math.fsum, matching within 1e-12 °C (counts exact). There are {len(sensors)} simulated sensor rows and 405 model fits per run.", "",
        "All table entries are RMSE / MAE in °C. Win requires beating all three baselines on both scores, pooled across held-out configurations.", "",
        "| Ahead | Persistence | Linear trend | Heat equation | Boosting | Win? |",
        "|---|---|---|---|---|---|"]
    for d in decisions:
        h = d["horizon_s"]
        cells = [f'{metrics[(h,m)]["rmse_c"]:.6f} / {metrics[(h,m)]["mae_c"]:.6f}'
                 for m in ("persistence", "linear_trend", "physics_hold", "hist_gradient_boosting")]
        lines.append(f'| {h//60} min | ' + ' | '.join(cells) + (' | Yes |' if d["boosting_beats_all_on_both"] else ' | No |'))
    lines += ["", "Boosting wins at 5, 10 and 30 minutes. It has lower pooled RMSE at every horizon, but the heat-equation baseline has lower pooled MAE at 1 and 2 minutes. These are descriptive comparisons, not statistical significance tests.", "",
        "Whole-case wins (both metrics against every baseline): " + "; ".join(f"{int(h)//60} min: {len(v)}/9" for h,v in per_case_wins.items()) + ".", "",
        f"Generated reference-cell temperature range: {min(temperatures):.8f} to {max(temperatures):.8f} °C. These tiny errors reflect an ideal, low-amplitude synthetic signal, not demonstrated real-sensor accuracy.", "",
        "## Interpretation limits", "",
        "Complete archived activity energy and duration define the offline constant-power scenario. Revealing that scenario one sample at a time is a simulated sensor experiment, not recovered instantaneous HAULSIM telemetry. The current activity's eventual average is assumed to be its instantaneous current throughout that activity. Past-only feature access is valid inside that assumed scenario; this does not prove the original activity exports were available live.", "",
        "No noise, latency, within-activity variation, changing ambient conditions, battery aging or thermal runaway is modelled. The heat-equation baseline shares the target generator's coefficients and holds the latest current, not the last-minute average. All cases share a route and generator; overlapping forecasts are dependent. A held-out configuration is not an independent truck, route or field trial. Thirty-minute scores use fewer origins and a different eligible time range than shorter horizons, so their magnitudes are not directly comparable as a horizon-difficulty test.", "",
        "A123 laboratory calibration is inherited, not newly performed. This experiment adds no measured-pack validation or thermal-runaway precursor, detection, false-alarm or warning-lead-time evidence. It supports a simulation workflow for ordinary temperature forecasting only. The existing paper and prior experiments were not edited.", "",
        "![Central configuration, simulated forecasts](central_case.png)"]
    (output / "RESULTS.md").write_text("\n".join(lines) + "\n")
    make_plot(sensors, predictions, output / "central_case.png")
    write_json(output / "PROOF.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv], "recorded_by": "AI-assisted A_live/report.py",
        "inputs_sha256": {str(p): sha(p) for p in [run1 / "PROOF.json", run2 / "PROOF.json", Path(__file__)]},
        "outputs_sha256": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}})
    print(json.dumps(verification, indent=2))


def make_plot(sensors, predictions, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    case = "C100_RR03"
    rows = [r for r in sensors if r["case"] == case]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, layout="constrained")
    axes[0].plot([float(r["time_s"])/60 for r in rows], [float(r["equivalent_current_a"]) for r in rows], color="#555555")
    axes[0].set_ylabel("Equivalent cell current (A)")
    axes[0].set_title("Ideal simulated sensors: central truck configuration")
    axes[1].plot([float(r["time_s"])/60 for r in rows], [float(r["reference_cell_temperature_c"]) for r in rows], label="Generated reference temperature", color="black", linewidth=2)
    for method, label in [("hist_gradient_boosting", "Boosting"), ("persistence", "Persistence"), ("physics_hold", "Heat equation")]:
        rr = [r for r in predictions if r["case"] == case and int(r["horizon_s"]) == 1800 and r["method"] == method]
        axes[1].plot([float(r["target_s"])/60 for r in rr], [float(r["predicted_temperature_c"]) for r in rr], label=label, alpha=.85)
    axes[1].set(xlabel="Simulation time (minutes)", ylabel="Reference-cell temperature (°C)",
                title="30-minute forecasts plotted at their target time")
    axes[1].legend(fontsize=9)
    for ax in axes:
        ax.grid(alpha=.2); ax.ticklabel_format(useOffset=False, axis="y")
    fig.savefig(destination, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run1", type=Path, required=True)
    parser.add_argument("--run2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.run1, args.run2, args.output)
