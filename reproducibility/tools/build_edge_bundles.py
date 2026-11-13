"""Build model bundles for the edge forecaster (edge/).

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

Two kinds of bundle, kept apart by name and by their manifest's "kind":

  paper   Converts the saved HGB models of ONE held-out configuration from the
          A_live run behind Table 2 (results/run-2026-11-13/live) to the edge
          format, and writes a replay fixture (that configuration's 1 Hz sensor
          record and its saved forecasts). No model is trained.

  deploy  NEWLY trains five HGB models (one per horizon) on all nine simulated
          configurations, with the paper's settings and inner selection of 40
          or 80 iterations. These are new models, not the paper's models, and
          have no held-out score because no configuration is left out.

Every exported model is checked to give exactly scikit-learn's prediction on
every saved input row before it is written. Run from reproducibility/ with the
pinned requirements in experiments/A/requirements.txt:

    python tools/build_edge_bundles.py paper  --run results/run-2026-11-13/live --case C100_RR03 \
        --out ../edge/bundles/paper-heldout-C100_RR03 --fixture ../edge/examples/C100_RR03
    python tools/build_edge_bundles.py deploy --out ../edge/bundles/deploy-all9-2026-11-13
"""
import argparse
import csv
import datetime
import gzip
import hashlib
import json
import platform
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parents[1]
ROOT = REPRO.parent
sys.path.insert(0, str(REPRO / "experiments/A_live"))
sys.path.insert(0, str(ROOT / "edge/src"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import sklearn  # noqa: E402
import train as live  # noqa: E402  (A_live/train.py; unchanged)
from bev_edge.features import FEATURE_NAMES  # noqa: E402
from bev_edge.trees import FORMAT as MODEL_FORMAT, BoostedTrees  # noqa: E402

BUNDLE_FORMAT = "bev-edge-bundle-v1"
original = live.original
sha = original.sha


def new_folder(path):
    path = Path(path).resolve()
    if path.exists():
        raise SystemExit(f"Output exists; choose a new folder: {path}")
    if any(path.is_relative_to(p) for p in (REPRO / "data", ROOT / "reconstruction/data")):
        raise SystemExit("Output must be outside input data")
    return path


def export_hgb(model):
    if model.n_trees_per_iteration_ != 1:
        raise ValueError("Expected single-output regression")
    trees = []
    for (predictor,) in model._predictors:
        n = predictor.nodes
        if n["is_categorical"].any():
            raise ValueError("Categorical splits are not supported")
        trees.append({"feature": n["feature_idx"].tolist(), "threshold": n["num_threshold"].tolist(),
                      "missing_left": n["missing_go_to_left"].astype(bool).tolist(),
                      "left": n["left"].tolist(), "right": n["right"].tolist(),
                      "leaf": n["is_leaf"].astype(bool).tolist(), "value": n["value"].tolist()})
    return {"format": MODEL_FORMAT, "n_features": int(model.n_features_in_),
            "baseline": float(model._baseline_prediction[0, 0]), "n_iter": int(model.n_iter_),
            "sklearn_version": sklearn.__version__, "trees": trees}


def check_exact(model, spec, x):
    """The exported trees must reproduce scikit-learn bit for bit on every row."""
    trees = BoostedTrees(json.loads(json.dumps(spec)))
    expected = model.predict(np.asarray(x, float))
    got = [trees.predict(list(row)) for row in np.asarray(x, float).tolist()]
    mismatches = int(np.sum(np.asarray(got) != expected))
    if mismatches:
        raise AssertionError(f"{mismatches} exported predictions differ from scikit-learn")
    return len(got)


def write_model(folder, horizon, spec):
    data = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    name = f"h{horizon}.json"
    (folder / name).write_bytes(data)
    return {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "n_iter": spec["n_iter"]}


def versions():
    return {"python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
            "joblib": joblib.__version__, "platform": platform.platform()}


def manifest(name, kind, label, models, extra):
    return {"format": BUNDLE_FORMAT, "name": name, "kind": kind, "label": label,
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "created_by": "AI-assisted reproducibility/tools/build_edge_bundles.py",
            "command": [Path(sys.executable).name, *sys.argv],
            "horizons_s": list(live.HORIZONS), "feature_names": FEATURE_NAMES,
            "history_s": 60, "origin_spacing_s": 10,
            "thermal": {"a_K_per_A2_s": live.A, "b_per_s": live.B},
            "inputs": "1 Hz reference-cell surface temperature (C), equivalent current of a 2.5 Ah reference cell (A), "
                      "air temperature (C); plus pack capacity (kWh) and rolling resistance (%)",
            "domain": "Trained on simulated A123 reference-cell temperatures generated from HAULSIM activity energy "
                      "(ideal, noiseless sensors). Not trained or validated on measured truck pack data.",
            "models": {str(h): m for h, m in models.items()}, "versions": versions(), **extra}


def verify_run(run):
    """Check the run is complete and that its outputs and recorded inputs are unchanged.

    The proof stores absolute paths from the machine and folder it ran in; each is
    mapped to the same path under this repository's reproducibility/ folder.
    """
    proof = json.loads((run / "PROOF.json").read_text())
    if json.loads((run / "status.json").read_text())["state"] != "COMPLETE":
        raise SystemExit("Run incomplete")
    for name, digest in proof["outputs_sha256"].items():
        if sha(run / name) != digest:
            raise SystemExit(f"Changed run output: {name}")
    for recorded, digest in proof["inputs_and_scripts_sha256"].items():
        parts = Path(recorded).parts
        here = REPRO.joinpath(*parts[len(parts) - parts[::-1].index("reproducibility"):])
        if sha(here) != digest:
            raise SystemExit(f"Input or script differs from the run: {here}")
    return proof


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def paper(args):
    run = Path(args.run).resolve()
    proof = verify_run(run)
    out, fixture = new_folder(args.out), new_folder(args.fixture)
    cases = json.loads((run / "cases.json").read_text())
    if args.case not in cases:
        raise SystemExit(f"Unknown case {args.case}")
    features = read_gz(run / "features.csv.gz")
    out.mkdir(parents=True)
    models, checked = {}, {}
    for h in live.HORIZONS:
        path = run / "models" / f"{args.case}_h{h}.joblib"
        model = joblib.load(path)
        spec = export_hgb(model)
        x = [[float(r[k]) for k in FEATURE_NAMES] for r in features if int(r["horizon_s"]) == h]
        checked[str(h)] = check_exact(model, spec, x)
        models[h] = {**write_model(out, h, spec), "source": path.name, "source_sha256": sha(path)}
    c = cases[args.case]
    m = manifest(out.name, "paper-heldout",
                 f"Paper models (A_live run of 2026-11-13, Table 2) trained WITHOUT configuration {args.case}. "
                 "Converted, not retrained. Use for exact-match testing against the saved run.",
                 models, {"held_out_case": args.case, "held_out_capacity_kwh": c["capacity_kwh"],
                          "held_out_rr_pct": c["rr_pct"], "source_run": str(run.relative_to(REPRO)),
                          "source_run_proof_utc": proof["utc"],
                          "exact_match_rows_checked_per_horizon": checked})
    (out / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")

    fixture.mkdir(parents=True)
    with gzip.open(run / "telemetry.csv.gz", "rt", encoding="utf-8", newline="") as f, \
            open(fixture / "sensor_stream.csv", "w", encoding="utf-8", newline="") as g:
        w = csv.writer(g)
        w.writerow(["time_s", "equivalent_current_a", "temperature_c", "air_c", "pack_power_kw"])
        for r in csv.DictReader(f):     # values copied as text, so no digits change
            if r["case"] == args.case:
                w.writerow([r["time_s"], r["equivalent_current_a"], r["reference_cell_temperature_c"],
                            r["air_c"], r["pack_power_kw"]])
    rows = [r for r in read_gz(run / "predictions.csv.gz") if r["case"] == args.case]
    with gzip.open(fixture / "expected_forecasts.csv.gz", "wt", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(g, fieldnames=["horizon_s", "method", "origin_s", "origin_temperature_c",
                                          "target_temperature_c", "predicted_temperature_c"])
        w.writeheader()
        w.writerows({k: r[k] for k in w.fieldnames} for r in rows)
    (fixture / "README.md").write_text(
        f"# Replay fixture: {args.case}\n\nCopied as text on "
        f"{datetime.date.today().isoformat()} by `reproducibility/tools/build_edge_bundles.py` from the saved run "
        f"`{run.relative_to(REPRO)}` (Table 2).\n\n"
        "- `sensor_stream.csv`: the simulated 1 Hz sensor record of this configuration up to the 20% reserve "
        "(generated reference-cell temperatures, not measurements).\n"
        "- `expected_forecasts.csv.gz`: the run's saved forecasts for this configuration (all four methods, "
        "five horizons). `target_temperature_c` is the generated value the forecast is scored against.\n\n"
        f"Capacity {c['capacity_kwh']} kWh, rolling resistance {c['rr_pct']}%.\n")
    print(json.dumps({"bundle": str(out), "fixture": str(fixture), "exact_rows_checked": checked}, indent=2))


def deploy(args):
    if (np.__version__, sklearn.__version__) != ("2.3.5", "1.7.2"):
        raise SystemExit("Use experiments/A/requirements.txt (numpy 2.3.5, scikit-learn 1.7.2)")
    out = new_folder(args.out)
    cases, streams, source_hashes = live.load_scenarios()
    names = sorted(cases)
    # Same inner selection as the paper, but over all nine: four validation groups (every 4th name).
    fold = {"outer_test": None, "outer_train": names,
            "inner": [{"inner_fold": i, "validation_groups": names[i::4],
                       "train_groups": [n for n in names if n not in names[i::4]]} for i in range(4)]}
    out.mkdir(parents=True)
    models, selection = {}, {}
    with live.threadpool_limits(limits=1):
        for h in live.HORIZONS:
            ex = {n: live.build_examples(s, cases[n]["capacity_kwh"], cases[n]["rr_pct"], h) for n, s in streams.items()}
            x = np.vstack([ex[n]["x"] for n in names])
            delta = np.concatenate([ex[n]["delta_c"] for n in names])
            groups = np.concatenate([np.repeat(n, len(ex[n]["origin_s"])) for n in names])
            model, audit = original.fit_selected("hist_gradient_boosting", x, delta, groups, fold)
            spec = export_hgb(model)
            rows = check_exact(model, spec, x)
            models[h] = write_model(out, h, spec)
            selection[str(h)] = {"selected": audit["selected_parameters"], "training_rows": rows,
                                 "candidates": [{"parameters": c["parameters"],
                                                 "mean_validation_mse_c2": c["equal_case_mean_validation_mse_c2"]}
                                                for c in audit["candidates"]]}
            print(json.dumps({"horizon_s": h, **selection[str(h)]["selected"]}), flush=True)
    for p, digest in source_hashes.items():
        if sha(p) != digest:
            raise AssertionError("Source changed during run")
    scripts = [Path(__file__), REPRO / "experiments/A_live/train.py", REPRO / "experiments/A_live/telemetry.py",
               REPRO / "experiments/A/train.py", REPRO / "experiments/A_causal/inputs.py"]
    m = manifest(out.name, "deployment",
                 f"NEW models trained {datetime.date.today().isoformat()} on all nine simulated configurations "
                 "with the paper's HGB settings. Not the paper's models; no configuration was held out, so these "
                 "models have no test score of their own.",
                 models, {"training_cases": {n: {k: cases[n][k] for k in ("capacity_kwh", "rr_pct", "reserve_cutoff_s")}
                                             for n in names},
                          "inner_selection": fold["inner"], "selection": selection, "seed": original.SEED,
                          "hgb_settings": "learning_rate 0.08, max_depth 3, max_leaf_nodes 7, min_samples_leaf 20, "
                                          "l2_regularization 1e-4, max_bins 64, max_iter 40 or 80, no early stopping",
                          "sources_sha256": {str(Path(p).relative_to(ROOT)): d for p, d in source_hashes.items()
                                             if Path(p).is_relative_to(ROOT)}
                                            | {str(p.relative_to(ROOT)): sha(p) for p in scripts}})
    (out / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
    print(json.dumps({"bundle": str(out)}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("paper", help="convert one held-out configuration's saved models")
    p.add_argument("--run", required=True)
    p.add_argument("--case", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fixture", required=True)
    d = sub.add_parser("deploy", help="train new all-nine deployment models")
    d.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    (paper if args.command == "paper" else deploy)(args)


if __name__ == "__main__":
    main()
