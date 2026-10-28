"""Independent stdlib readback of Experiment B counts and causal timing.

Does not import shared rule code and writes only this qa folder.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import bisect
import datetime
import gzip
import hashlib
import json
import math
import statistics

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
RESULT = EXPERIMENT / "results"
BEV = EXPERIMENT.parents[1]


def rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(value):
    return float(value) if value not in (None, "", "None") else None


def finite(value):
    return value is not None and math.isfinite(value)


def independent_response(time, values, segments, threshold, is_rate=False):
    first = alarm = start = previous_time = previous_segment = None
    eligible = exceedances = 0
    for t, value, segment in zip(time, values, segments):
        if previous_time is not None and (t - previous_time > 1.000001 or segment != previous_segment):
            start = None
        valid = finite(value)
        eligible += int(valid)
        predicate = valid and value > threshold + (1e-10 if is_rate else 0.)
        exceedances += int(predicate)
        if not predicate:
            start = None
        else:
            if first is None:
                first = t
            if start is None:
                start = t
            if alarm is None and t - start >= 5:
                alarm = t
        previous_time, previous_segment = t, segment
    return dict(first_crossing_s=first, alarm_s=alarm, eligible_samples=eligible,
                exceedance_samples=exceedances, debounce_s=5.)


def main():
    failures = []
    checks = []
    protocol_path = EXPERIMENT / "01_experiment_b_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    summary = json.loads((RESULT / "summary.json").read_text())
    response = rows(RESULT / "rule_responses.csv")
    table = rows(RESULT / "table5.csv")
    native = rows(RESULT / "native_channel_audit.csv")
    rule_ids = [f"fixed_{v}C" for v in protocol["fixed_thresholds_c"]] + [f"rate_{v}C_min" for v in protocol["rate_thresholds_c_min"]]
    def check(name, ok, detail=None):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)
    def equal(a, b):
        if a is None:
            return b in (None, "", "None")
        return math.isclose(float(a), float(b), abs_tol=1e-9, rel_tol=0)
    check("protocol_hash_matches_summary", hashlib.sha256(protocol_path.read_bytes()).hexdigest() == summary["protocol_sha256"])
    check("rule_code_hash_matches_summary", hashlib.sha256((EXPERIMENT / "code/rules.py").read_bytes()).hexdigest() == summary["rules_sha256"])
    check("seven_rules_match_protocol", len(rule_ids) == 7 and set(rule_ids) == {r["rule"] for r in response})
    check("protocol_uses_60s_past_rate_5s_debounce", protocol["rate_window_s"] == 60 and protocol["debounce_s"] == 5)
    identities = {(r["dataset"], r["record"]) for r in response}
    sheffield = {r["record"]: r for r in response if r["dataset"] == "Sheffield"}
    tum = {r["record"]: r for r in response if r["dataset"] == "TUM"}
    split_records = Counter(r["split"] for r in sheffield.values())
    check("33_unique_temperature_trajectories", len(identities) == 33 and len(sheffield) == 27 and len(tum) == 6)
    check("exactly_seven_unique_responses_per_trajectory", len(response) == 231 and all(
        len([r for r in response if (r["dataset"], r["record"]) == key]) == 7 and
        {r["rule"] for r in response if (r["dataset"], r["record"]) == key} == set(rule_ids) for key in identities))
    expected_split = dict(zip(("train", "development", "test"), protocol["splits"]["expected_sheffield_records"]))
    check("date_grouped_split_counts_match_protocol", dict(split_records) == expected_split)
    for split in expected_split:
        dates = {r["record"][:6] for r in sheffield.values() if r["split"] == split}
        check(f"{split}_date_assignments_match_protocol", dates == set(protocol["splits"][split + "_dates"]))
    check("one_dependent_TUM_module", {r["independence_group"] for r in tum.values()} == {"TUM_LFP_MODULE_1"})
    native_counts = Counter((r["dataset"], r["kind"]) for r in native)
    check("43_measurement_channel_inventory", native_counts == Counter({("Sheffield", "cell_temperature"): 27,
        ("TUM", "cell_temperature"): 6, ("TUM", "cell_voltage"): 5, ("TUM", "vent_temperature"): 5}))
    thresholds = {r["rule"]: (float(r["threshold"]), r["family"] == "rate") for r in response}
    computed_rules = {}
    groups = defaultdict(list)
    for row in rows(RESULT / "causal_features.csv.gz"):
        groups[row["dataset"], row["record"]].append(row)
    max_rate_difference = 0.
    for identity, data in groups.items():
        t = [float(r["time_s"]) for r in data]
        temp = [number(r["temperature_c"]) for r in data]
        seg = [int(r["segment"]) for r in data]
        rate = []
        check(f"causal_source_times_{identity[0]}_{identity[1]}", all(float(r["measurement_time_s"]) <= float(r["time_s"]) for r in data))
        source_info = next(r for r in native if r["dataset"] == identity[0] and r["record"] == identity[1] and r["kind"] == "cell_temperature")
        source_rows = rows(BEV / source_info["path"])
        if identity[0] == "Sheffield":
            raw_t = [float(r["Time (s)"]) for r in source_rows]
            raw_y = [float(r["Cell Temperature (degC)"]) for r in source_rows]
        else:
            headers = list(source_rows[0])
            raw_t = [float(r[headers[0]]) for r in source_rows]
            raw_y = [float(r[headers[1]]) for r in source_rows]
        previous_source = None
        raw_match = True
        for index, grid_time in enumerate(t):
            source_index = bisect.bisect_right(raw_t, grid_time) - 1
            expected = raw_y[source_index] if grid_time - raw_t[source_index] <= 1.01 and source_index != previous_source else None
            previous_source = source_index
            if not finite(expected):
                expected = None
            if expected is None:
                raw_match = raw_match and temp[index] is None
            else:
                raw_match = raw_match and equal(expected, temp[index])
            raw_match = raw_match and equal(raw_t[source_index], data[index]["measurement_time_s"])
        check(f"native_past_held_values_reconstructed_{identity[0]}_{identity[1]}", raw_match)
        for i in range(len(t)):
            value = None
            if i >= 60 and seg[i] == seg[i - 60] and all(finite(x) for x in temp[i - 60:i + 1]):
                x = t[i - 60:i + 1]
                y = temp[i - 60:i + 1]
                mx, my = statistics.fmean(x), statistics.fmean(y)
                value = 60 * math.fsum((a - mx) * (b - my) for a, b in zip(x, y)) / math.fsum((a - mx) ** 2 for a in x)
            rate.append(value)
            recorded = number(data[i]["rate60_c_min"])
            if value is None or recorded is None:
                if value != recorded:
                    failures.append(f"rate_availability_{identity}_{t[i]}")
            else:
                max_rate_difference = max(max_rate_difference, abs(value - recorded))
        for rule in rule_ids:
            threshold, is_rate = thresholds[rule]
            actual = independent_response(t, rate if is_rate else temp, seg, threshold, is_rate)
            computed_rules[identity[0], identity[1], rule] = actual
            recorded = next(r for r in response if (r["dataset"], r["record"], r["rule"]) == (identity[0], identity[1], rule))
            check(f"independent_response_{identity[0]}_{identity[1]}_{rule}", all(equal(v, recorded[k]) for k, v in actual.items()))
    check("independent_centered_OLS_matches_saved_rates", max_rate_difference < 1e-9, max_rate_difference)
    recomputed_table = []
    for cell in table:
        title, rule = cell["record_set"], cell["rule"]
        selected = [r for r in response if r["rule"] == rule and
                    (r["dataset"] == "TUM" if title == "TUM_channels" else r["dataset"] == "Sheffield") and
                    (title in ("TUM_channels", "Sheffield_all") or r["split"] == title.removeprefix("Sheffield_"))]
        times = [number(r["alarm_s"]) for r in selected if r["alarm_s"]]
        computed = dict(record_set=title, rule=rule, records_or_channels=len(selected), responses=len(times),
            date_groups=len({r["independence_group"] for r in selected}) if title != "TUM_channels" else None,
            independent_module_experiments=1 if title == "TUM_channels" else None,
            first_crossing_records=sum(bool(r["first_crossing_s"]) for r in selected),
            total_eligible_samples=sum(int(r["eligible_samples"]) for r in selected),
            first_alarm_min_s=min(times) if times else None,
            first_alarm_median_s=statistics.median(times) if times else None,
            first_alarm_max_s=max(times) if times else None)
        recomputed_table.append(computed)
        check(f"Table5_{title}_{rule}", all(equal(v, cell[k]) for k,v in computed.items() if k not in ("record_set", "rule")))
        check(f"Table5_withholds_unsupported_endpoints_{title}_{rule}", all(cell[k] == "UNAVAILABLE" for k in
            ("lead_time_s", "misses", "field_false_alarm_rate")) and int(cell["verified_independent_reference_events"]) == 0)
    check("35_Table5_rows", len(table) == 35 and len({(r["record_set"], r["rule"]) for r in table}) == 35)
    compact = rows(RESULT / "table5_compact.csv")
    for record, title in zip(compact, ("Sheffield_all", "Sheffield_test", "TUM_channels")):
        for rule in rule_ids:
            cell = next(r for r in recomputed_table if r["record_set"] == title and r["rule"] == rule)
            check(f"compact_{title}_{rule}", record[rule + "_responses"] == f"{cell['responses']}/{cell['records_or_channels']}")
    event = json.loads((RESULT / "event_register.json").read_text())
    check("zero_admitted_independent_physical_events", sum(bool(r["verified_independent_physical_event"]) for r in event) == 0)
    check("rule_rows_do_not_claim_event_lead_time", all(r["lead_time_s"] == "UNAVAILABLE" and not r["independent_reference_s"] for r in response))
    voltages = json.loads((RESULT / "voltage_condition_audit.json").read_text())
    check("five_descriptive_voltage_conditions", len(voltages) == 5 and all(r["condition_start_s"] is not None and r["physical_origin_unverified"] for r in voltages))
    relative = rows(RESULT / "module_alarm_to_voltage_condition.csv")
    first = min(voltages, key=lambda r: r["condition_start_s"])
    for record in relative:
        alarm = min(number(r["alarm_s"]) for r in response if r["dataset"] == "TUM" and r["rule"] == record["rule"] and r["alarm_s"])
        check("conditional_voltage_interval_" + record["rule"], equal(first["bracket_s"][0] - alarm, record["conditional_condition_minus_alarm_lower_s"]) and
              equal(first["bracket_s"][1] - alarm, record["conditional_condition_minus_alarm_upper_s"]) and record["physical_tr_lead_time_s"] == "UNAVAILABLE")
    source_hashes = json.loads((RESULT / "source_hashes.json").read_text())
    check("all_43_source_hashes_recomputed", len(source_hashes) == 43 and all(hashlib.sha256((BEV / r["path"]).read_bytes()).hexdigest() == r["sha256"] for r in source_hashes))
    forecast = rows(RESULT / "forecast_threshold_responses.csv")
    forecast_summary = rows(RESULT / "forecast_threshold_summary.csv")
    check("forecast_origin_counts_have_no_missing_forecast_values", all(int(r["available_origins"]) == int(r["n_origins"]) for r in forecast))
    check("forecast_screen_156_rows", len(forecast) == 156)
    for cell in forecast_summary:
        selected = [r for r in forecast if all(r[k] == cell[k] for k in ("dataset", "horizon_s", "threshold_c"))]
        differences = [number(r["matched_current_minus_forecast_response_origin_s"]) for r in selected
                       if r["matched_current_minus_forecast_response_origin_s"]]
        counts = dict(records_or_channels=len(selected),
            forecast_responses=sum(bool(r["forecast_5s_response_origin_s"]) for r in selected),
            matched_current_responses=sum(bool(r["matched_current_5s_response_origin_s"]) for r in selected),
            earlier_forecast_response_count=sum(v > 0 for v in differences), tied_forecast_response_count=sum(v == 0 for v in differences),
            later_forecast_response_count=sum(v < 0 for v in differences),
            median_current_minus_forecast_origin_s=statistics.median(differences) if differences else None)
        check("forecast_summary_" + "_".join(cell[k] for k in ("dataset", "horizon_s", "threshold_c")), all(equal(v, cell[k]) for k,v in counts.items()))
    outcome = {"completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "independent_readback_passed": not failures,
        "auditor": "Independent operations agent; no shared rule-code imports and no analysis/Google Doc edits",
        "counts_recomputed": {"Sheffield_records": len(sheffield), "Sheffield_split_records": dict(split_records),
            "Sheffield_date_groups": len({r['independence_group'] for r in sheffield.values()}),
            "Sheffield_test_dates": sorted({r['record'][:6] for r in sheffield.values() if r['split']=='test'}),
            "TUM_temperature_channels": len(tum), "TUM_module_experiments": 1,
            "TUM_voltage_channels": native_counts['TUM', 'cell_voltage'], "TUM_vent_temperature_channels": native_counts['TUM', 'vent_temperature'],
            "measurement_files": len(native), "seven_rule_response_rows": len(response), "Table5_rows": len(table)},
        "maximum_independent_rate_difference_C_min": max_rate_difference,
        "recomputed_Table5": recomputed_table, "check_count": len(checks), "failures": failures, "checks": checks,
        "timing_review": {"causal": "Latest native sample never exceeds evaluation time; full 61-point trailing OLS; independent recomputation reproduces all 231 first crossings/alarms and sample counts.",
            "debounce": "Five elapsed seconds; false/missing predicate, clock gaps and segment changes reset persistence; alarm uses first confirmation sample.",
            "rate_availability": "Sheffield rates first eligible at 60 s and alarms at 65 s. TUM pretrigger samples permit an earlier first full window and 55 s earliest rate alarm; no future samples are used.",
            "event_gate": "No independently verified physical onset enters Table5. Voltage-condition start is retrospectively confirmed for5s and separately bracketed; only conditional electrical timing is reported, with unknown offset/fault origin explicitly retained.",
            "forecast_screen": "Saved forecasts reused without fitting; actual available-origin counts match. Forecast-origin persistence is not presented as verified future physical-temperature persistence or TR lead time."},
        "conclusion": "No material count, Table5, protocol, causal-timing or unsupported physical-onset claim discrepancy found." if not failures else "See failures; do not treat the table as independently verified."}
    (HERE / "independent_output_audit.json").write_text(json.dumps(outcome, indent=2, allow_nan=False), encoding="utf-8")
    concise = {k: outcome[k] for k in ("completed_utc", "independent_readback_passed", "counts_recomputed", "check_count", "failures", "maximum_independent_rate_difference_C_min", "conclusion")}
    concise["seven_rule_counts"] = [{k: row[k] for k in ("record_set", "rule", "records_or_channels", "responses", "first_alarm_median_s")}
                                    for row in recomputed_table if row["record_set"] in ("Sheffield_all", "Sheffield_test", "TUM_channels")]
    concise["timing_review"] = outcome["timing_review"]
    concise["full_audit"] = "independent_output_audit.json"
    (HERE / "independent_output_audit_summary.json").write_text(json.dumps(concise, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: outcome[k] for k in ("independent_readback_passed", "counts_recomputed", "check_count", "failures", "maximum_independent_rate_difference_C_min", "conclusion")}, indent=2))


if __name__ == "__main__":
    main()
