"""Experiment B: frozen warning rules on laboratory records.

Question
    Seven rules are fixed in advance. Do they stay quiet on modelled normal
    haulage, and do they respond on published LFP abuse records?

Protocol
    The same seven rules, unchanged, are applied to two very different
    populations: 729 modelled normal-operation trajectories, and the published
    laboratory records. The rules were specified before any record was screened
    and were never re-tuned, which is the only reason the laboratory result
    means anything.

The limit this experiment runs into, and reports rather than papers over
    A rule firing on an abuse record is a RESPONSE TO RECORDED HEATING. It is
    not a verified thermal-runaway detection. Neither archive contains an
    independent, temperature-free onset reference with bounded sensor-clock
    uncertainty, so lead time, missed detections and field false-alarm rate
    cannot be computed and are reported as UNAVAILABLE.

    The quiet result on 729 trajectories is likewise not a field false-alarm
    rate: its denominator is modelled scenarios, not fleet hours. The nine
    nominal settings are a subset of the 729, not nine extra experiments.

Usage
    python experiments/experiment_b_warning_rules.py [--out DIR]
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from bev_research import datasets, rules  # noqa: E402


def screen_modelled_normal() -> pd.DataFrame:
    """Apply the frozen rules to every generated nominal trajectory."""
    traces = datasets.nominal_traces()
    out = []
    for case, sub in traces.groupby("case"):
        sub = sub.sort_values("time_s")
        for result in rules.screen(sub["time_s"].to_numpy(float),
                                   sub["temperature_c"].to_numpy(float)):
            result["case"] = case
            result["population"] = "modelled_nominal"
            out.append(result)
    return pd.DataFrame(out)


def report_archived() -> None:
    """Print the archived Table 5, which covers the laboratory records.

    The laboratory records themselves are licence restricted and are not
    committed, so this reads the derived response summary rather than
    re-screening the raw files. To re-screen from source, fetch the datasets
    per data/README.md into data/raw and verify them against the checksum
    manifest first.
    """
    table = datasets.rule_response_table()
    print("\nArchived Table 5, laboratory record responses")
    cols = ["record_set", "rule", "records_or_channels", "responses",
            "first_alarm_min_s", "first_alarm_median_s", "first_alarm_max_s",
            "lead_time_s"]
    print(table[cols].to_string(index=False))

    for col in ("lead_time_s", "misses", "field_false_alarm_rate"):
        assert (table[col].astype(str) == rules.UNAVAILABLE).all(), (
            "%s must remain UNAVAILABLE; a value here would be unsupported"
            % col)
    print("\nlead_time_s, misses and field_false_alarm_rate: %s"
          % rules.UNAVAILABLE)
    print(rules.UNAVAILABLE_REASON)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join("results", "experiment_b"))
    args = parser.parse_args()

    print("Frozen rules, fixed before any record was screened:")
    for rule in rules.frozen_rules():
        print("   " + str(rule))

    modelled = screen_modelled_normal()
    os.makedirs(args.out, exist_ok=True)
    modelled.to_csv(os.path.join(args.out, "modelled_nominal_responses.csv"),
                    index=False)

    fired = int(modelled["responded"].sum())
    print("\nModelled normal trajectories: %d case-rule combinations, "
          "%d eligible samples, %d responses"
          % (len(modelled), int(modelled["eligible_samples"].sum()), fired))
    if fired == 0:
        print("No rule responded on any modelled normal trajectory.")
        print("The denominator is modelled scenarios, not fleet exposure, so "
              "this is not a field false-alarm rate.")

    summary = datasets.frozen_rule_summary()
    archived_alarms = int(summary["trajectories_with_debounced_alarm"].sum())
    print("Archived full screen over 9 nominal and 729 variant trajectories: "
          "%d alarms" % archived_alarms)

    report_archived()
    print("\nwrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
