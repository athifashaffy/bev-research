"""Reproduce document figures directly from verified A_live outputs.

AI-assisted plotting code; every plotted value comes from the recorded numerical
experiment. No generative-image model, invented readings or fitted new model.
"""
import argparse
import datetime
import json
from pathlib import Path
import sys

from report import read_csv, make_plot
from train import validate_output, verify_proof, sha, write_json


def render(run, output):
    run = Path(run).resolve()
    output = validate_output(output)
    verify_proof(run)
    cases = json.loads((run / "cases.json").read_text())
    sensors = read_csv(run / "telemetry.csv.gz")
    predictions = read_csv(run / "predictions.csv.gz")
    cutoff = min(c["reserve_cutoff_s"] for c in cases.values())
    traces = {name: [r for r in sensors if r["case"] == name and float(r["time_s"]) <= cutoff]
              for name in sorted(cases)}
    peaks = {name: max(float(r["reference_cell_temperature_c"]) - 25 for r in rows)
             for name, rows in traces.items()}
    output.mkdir(parents=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(10.8, 4.4), sharey=True, layout="constrained")
    for ax, rr in zip(axes, [2, 3, 4]):
        for cap, color in zip(["080", "100", "120"], ["#2166ac", "#d6604d", "#1b7837"]):
            name = f"C{cap}_RR0{rr}"
            rows = traces[name]
            ax.plot([float(r["time_s"])/60 for r in rows],
                    [float(r["reference_cell_temperature_c"])-25 for r in rows],
                    label=f"{cases[name]['capacity_kwh']:g} kWh", color=color)
        ax.set_title(f"({chr(95+rr)}) {rr}% rolling resistance", fontsize=10)
        ax.set_xlabel("Simulation time (min)")
        ax.grid(alpha=.2)
    axes[0].set_ylabel("Surrogate temperature rise (°C)")
    axes[-1].legend(fontsize=8)
    fig.savefig(output / "figure1.png", dpi=200)
    plt.close(fig)
    make_plot(sensors, predictions, output / "figure2.png")
    write_json(output / "peak_rises.json", {"common_cutoff_s": cutoff, "peak_rise_c": peaks})
    sources = [run / "PROOF.json", run / "cases.json", run / "telemetry.csv.gz",
               run / "predictions.csv.gz", Path(__file__), Path(__file__).with_name("report.py")]
    write_json(output / "PROOF.json", {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv],
        "method": "Matplotlib plots of saved numerical outputs; no image generation model",
        "assistance": "AI-assisted code and automated verification, not human scientific validation",
        "matplotlib_version": matplotlib.__version__,
        "inputs_sha256": {str(p): sha(p) for p in sources},
        "outputs_sha256": {p.name: sha(p) for p in output.iterdir() if p.is_file()}})
    print(json.dumps({"output": str(output), "peak_rise_c": peaks}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.run, args.output)
