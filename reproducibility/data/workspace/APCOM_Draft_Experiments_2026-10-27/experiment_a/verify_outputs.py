"""Independent stdlib-only readback checks for Experiment A output files."""
from pathlib import Path
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    summary = json.loads((HERE / "summary.json").read_text())
    groups = defaultdict(list)
    with gzip.open(HERE / "predictions.csv.gz", "rt", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (row["case"], int(row["horizon_s"]), row["method"])
            groups[key].append(row)
    methods = summary["methods"]
    cases = sorted({key[0] for key in groups})
    largest_metric_difference = 0.
    for horizon in summary["horizons_s"]:
        for case in cases:
            origin_sets = [{int(r["origin_s"]) for r in groups[case, horizon, method]} for method in methods]
            assert all(origins == origin_sets[0] for origins in origin_sets)
            for method in methods:
                rows = groups[case, horizon, method]
                assert len(rows) == len(origin_sets[0])
                assert all(int(r["target_s"]) - int(r["origin_s"]) == horizon for r in rows)
                errors = [float(r["predicted_temperature_c"]) - float(r["true_temperature_c"]) for r in rows]
                rmse = math.sqrt(math.fsum(e * e for e in errors) / len(errors))
                mae = math.fsum(abs(e) for e in errors) / len(errors)
                recorded = next(r for r in summary["per_case_metrics"] if r["case"] == case and r["horizon_s"] == horizon and r["method"] == method)
                largest_metric_difference = max(largest_metric_difference, abs(recorded["rmse_c"] - rmse), abs(recorded["mae_c"] - mae))
                assert math.isclose(rmse, recorded["rmse_c"], abs_tol=1e-14, rel_tol=0)
                assert math.isclose(mae, recorded["mae_c"], abs_tol=1e-14, rel_tol=0)
    for cell in summary["pooled_metrics"]:
        rows = [row for (case, h, method), case_rows in groups.items() if h == cell["horizon_s"] and method == cell["method"] for row in case_rows]
        errors = [float(r["predicted_temperature_c"]) - float(r["true_temperature_c"]) for r in rows]
        rmse = math.sqrt(math.fsum(e * e for e in errors) / len(errors))
        mae = math.fsum(abs(e) for e in errors) / len(errors)
        largest_metric_difference = max(largest_metric_difference, abs(cell["rmse_c"] - rmse), abs(cell["mae_c"] - mae))
        assert math.isclose(rmse, cell["rmse_c"], abs_tol=1e-14, rel_tol=0)
        assert math.isclose(mae, cell["mae_c"], abs_tol=1e-14, rel_tol=0)
    choices = json.loads((HERE / "per_fold_model_selection.json").read_text())
    assert len(choices) == 72 and sum(r["fit_count"] for r in choices) == 792
    for outer in choices:
        held = outer["outer_test"]
        assert held not in outer["outer_train"] and len(outer["outer_train"]) == 8
        for candidate in outer["candidates"]:
            for inner in candidate["inner_folds"]:
                a, b = set(inner["train_groups"]), set(inner["validation_groups"])
                assert not a & b and held not in a | b and a | b == set(outer["outer_train"])
                assert inner["scaler_fitted_groups"] is None or set(inner["scaler_fitted_groups"]) == a
    with (HERE / "eligible_origins.csv").open() as stream:
        eligibility = list(csv.DictReader(stream))
    assert all(float(row["latest_input_source_s"]) <= int(row["origin_s"]) for row in eligibility)
    assert all(int(row["target_s"]) <= float(row["reserve_endpoint_s"]) for row in eligibility)
    for relative, expected in summary["input_and_protocol_hashes"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    for relative, expected in summary["code_hashes"].items():
        assert hashlib.sha256((HERE / relative).read_bytes()).hexdigest() == expected
    first = json.loads((HERE / "first_run_metric_sha256.json").read_text())
    repeated_identical = {
        "pooled_table": hashlib.sha256((HERE / "table_4_pooled_metrics.csv").read_bytes()).hexdigest() == first["table_4_sha256"],
        "per_case_metrics": hashlib.sha256((HERE / "per_case_metrics.csv").read_bytes()).hexdigest() == first["per_case_sha256"],
    }
    assert all(repeated_identical.values())
    result = {"passed": True, "case_horizon_method_groups": len(groups), "per_case_metric_rows": 180,
              "pooled_metric_cells": 20, "nested_model_fits": 792, "same_origin_sets_for_every_method": True,
              "no_outer_case_in_inner_or_final_training": True, "all_source_and_code_hashes_match": True,
              "independent_math_fsum_max_metric_difference_c": largest_metric_difference,
              "final_repeated_fit_metric_files_byte_identical": repeated_identical,
              "all_inputs_causal_and_all_targets_within_reserve": True,
              "threadpools_all_one_thread": all(p["num_threads"] == 1 for p in summary["threadpools_during_fit"]),
              "reproduction": "python experiment_a/verify_outputs.py"}
    (HERE / "verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
