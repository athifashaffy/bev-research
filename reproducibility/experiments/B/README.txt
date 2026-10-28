EXPERIMENT B: WARNING RULES AND EVENT ADMISSIBILITY
27 October 2026

The protocol was frozen before this scoring pass. It is a sensitivity exercise
on historically inspected data, not an optimized or blinded detector validation.
All prior files remain unchanged.

Reproduce with the bundled Python runtime:
  python -m unittest discover -s code -p "test*.py" -v
  python code/run_experiment_b.py
Run from this folder, or pass absolute paths from another working directory.
The script uses standard-library analysis plus the existing NumPy/Matplotlib
packages under New_Afton_Experiments_2026-10-20/tools. No package installation,
model training, native HAULSIM execution or new measurement download is needed.

Inputs: 27 Sheffield CSVs, 6 TUM cell-temperature TXT files, 5 TUM voltage TXT
files and 5 TUM vent-temperature TXT files: 43 measurement files in total.
Each matches its archived SHA256; the 16 TUM files also match publisher SHA512.
The optional forecast screen verifies the prior prediction file, saved model
selection and three frozen model files against the Oct25 artifact manifest.
It reuses saved predictions, without loading or fitting an estimator.

Rules: strict temperature >45, >50, >55 or >60 C; separately, strict causal
60-second OLS rate >1, >2 or >5 C/min. Each predicate must remain true for
5 elapsed seconds. Rate processing requires 61 valid one-second points covering
60 elapsed seconds. Values are the latest native measurements available at the
grid instant, never future interpolation. Missing/stale values and acquisition
segments interrupt persistence/history. See the JSON protocol for exact limits.

Sheffield has 27 screening records, not 35 ARC/oven tests. Its 15 training,
5 development and 7 held-out test records retain date groups; the seven test
records share two dates. These roles preserve the earlier forecasting split;
no warning threshold was tuned. All six TUM temperature channels belong to one
five-cell module experiment and are not independent trials.

Main files:
  results/table5.csv: population/split rule counts and descriptive alarm times.
  results/rule_responses.csv: every record/channel and threshold, including
    first point crossing, first persistent alarm and eligible sample coverage.
  results/coverage.csv and causal_features.csv.gz: native-to-grid audit trail.
  results/native_channel_audit.csv and source_hashes.json: all 43 source files.
  results/event_register.csv/json and event_admissibility.json: reference gate.
  results/voltage_condition_audit.csv/json: the preregistered electrical condition.
  results/module_alarm_to_voltage_condition.csv: conditional arithmetic intervals
    from the first module alarm to the first qualified voltage condition only.
  results/clock_alignment_audit.csv: observed native phase offsets and limits.
  results/forecast_threshold_responses.csv and forecast_threshold_summary.csv:
    saved laboratory-model threshold responses on matched available origins.
  results/summary.json: machine-readable complete summary.
  02_Results_and_Limitations.txt: plain-language results.

The main Table 5 lead time is UNAVAILABLE. Voltage is a separate measured signal,
but a study-defined <=0.1 V condition is not independently adjudicated TR onset.
The record does not independently exclude a sensing-wire/contact fault or bound
absolute interchannel clock error. A voltage sampling bracket is not a bound on
total event uncertainty. Vent thermocouple temperature is not a vent-opening
switch. Edited video remains unsynchronized to the numerical clock.

No verified TR lead time, confirmed misses, population sensitivity, field
false-alarm rate or evacuation time is reported. Heater-driven temperature
alarms naturally preceding a later electrical condition are not proof of
predictive warning. Numerical differences for frozen forecast thresholds are
relative response times on the forecast-origin clock, not physical lead times.

Figures are PNG/SVG/PDF, native width 6.6 inches, with readable print labels.
Synthetic red/green logs and final verification are in qa/.
