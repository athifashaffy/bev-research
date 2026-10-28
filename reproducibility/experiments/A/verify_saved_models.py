"""Reload NEW_REFIT estimators and check all saved learned predictions; no fits."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np


def verify(run_dir):
    run_dir = Path(run_dir).resolve()
    manifest = json.loads((run_dir / "fresh_model_manifest.json").read_text())
    audit = json.loads((run_dir / "pre_fit_audit.json").read_text())
    names = audit["feature_names"]
    with gzip.open(run_dir / "causal_features.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        features = {(r["case"], int(r["horizon_s"]), int(r["origin_s"])): [float(r[n]) for n in names]
                    for r in csv.DictReader(stream)}
    with gzip.open(run_dir / "predictions.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    checked, maximum = 0, 0.
    if len(manifest) != 72:
        raise ValueError("Expected 72 newly refitted outer estimators")
    for entry in manifest:
        path = (run_dir / entry["path"]).resolve()
        if not path.is_relative_to(run_dir) or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Model artifact path/hash mismatch")
        model = joblib.load(path)
        selected = [r for r in rows if r["case"] == entry["outer_test"] and int(r["horizon_s"]) == entry["horizon_s"] and r["method"] == entry["method"]]
        x = np.array([features[r["case"], int(r["horizon_s"]), int(r["origin_s"])] for r in selected])
        actual = np.array([float(r["origin_temperature_c"]) for r in selected]) + model.predict(x)
        expected = np.array([float(r["predicted_temperature_c"]) for r in selected])
        difference = float(np.max(np.abs(actual - expected)))
        if difference > 1e-12 or not np.all(np.isfinite(actual)):
            raise ValueError("Reloaded model predictions differ from saved values")
        maximum = max(maximum, difference)
        checked += len(selected)
    if checked != 33592:
        raise ValueError("Expected all 33,592 learned-method prediction rows")
    return {"passed": True, "fresh_estimators_reloaded": len(manifest), "learned_prediction_rows_checked": checked,
            "maximum_prediction_absolute_difference_c": maximum, "fits_executed_by_verification": 0,
            "scope": "NEW_REFIT artifacts from the portable reproduction run; not recovered archived estimators"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.run_dir), indent=2))
