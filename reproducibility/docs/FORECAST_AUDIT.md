# Experiment A saved-output audit

This saved-output audit checks archived predictions without fitting models or changing its inputs. A separate fresh refit is documented in [Experiment A](../experiments/A).

The independent audit recalculated every saved prediction error using Python's standard library and compensated sums. All 20 pooled rows and 180 case rows agree with both saved CSV tables and the saved summary within **1.3877787807814457e-17 °C**. It used **83,980 prediction rows**, covering **16,796 distinct case/horizon/origin combinations** for five methods.

## Reproduce

Use Python 3.10 or newer; no pip installation is required. Keep the scientific source folders under a common source root. The experiment directory may be anywhere; pass its path explicitly. `--source-root` defaults to the experiment folder's grandparent. The output path must not exist and must be outside the experiment folder.

```text
python -B ml/audit_ml.py --input /path/to/experiment_a --source-root /path/to/source_root --output /path/to/new_audit_results
python -B -m unittest discover -s ml -p test_audit_ml.py -v
```

From this audit directory's parent, replace `ml` with the appropriate relative path if needed. PowerShell accepts the same arguments; use a Python executable available on that computer. Paths containing spaces must be quoted.

Required experiment files: `forecasting.py`, `test_forecasting.py`, `protocol.json`, `predictions.csv.gz`, `table_4_pooled_metrics.csv`, `per_case_metrics.csv`, `fold_assignments.json`, `per_fold_model_selection.json`, `summary.json`, `verification.json`, `eligible_origins.csv`, `causal_features.csv.gz`.

Required source-root files:

```text
APCOM_Study_2026-10-22/results/thermal_nominal_traces.csv
APCOM_Study_2026-10-22/results/thermal_audit.json
APCOM_Study_2026-10-22/results/operations_audit.json
APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json
```

Missing inputs, duplicate origins, unexpected group membership, nonfinite numbers, mismatched hashes or metrics, invalid source timing, and an existing output directory cause a nonzero exit. Original experiment Python modules are not imported. The private drafting-provenance entry in the original hash record is deliberately excluded; its content and digest are not reproduced. Its absence does not affect this audit.

## What was independently checked

| Check | Observed result | Original source location |
|---|---|---|
| Pooled and per-case RMSE, MAE, maximum absolute error, counts, and case extrema | 20 pooled plus 180 case rows reproduced; maximum difference 1.39e-17 °C | `forecasting.py:133–136, 293–315`; compared directly with both CSV tables and `summary.json` |
| Prediction identity and coverage | Every eligible case/horizon/origin has exactly one row for each of the five methods; no duplicate method/origin keys | `forecasting.py:296–302` |
| Past-held source resampling and feature construction | Rebuilt all 16,796 eligible origins and all 20 feature columns from original traces; maximum feature difference 1.42e-14 | `forecasting.py:61–123, 209–224, 249–265`; `protocol.json:11–13` |
| Forecast targets and reserve endpoint | Saved origin temperatures/targets match the independently resampled source; all target intervals fit within the source trace and operations reserve endpoint | `forecasting.py:242–261`; `protocol.json:12` |
| Persistence, trend, and ODE baselines | Recomputed all baseline predictions from causal features/current/air; maximum difference 3.09e-13 °C | `forecasting.py:126–130, 287–288` |
| Whole-case outer/inner separation | Nine outer folds; four inner folds per outer; six training and two validation cases per inner fold; held-out outer case absent throughout | `forecasting.py:45–58, 150–180`; `protocol.json:15–16` |
| Hyperparameter choice and recorded training counts | All 72 selection records match declared grids, equal-case score aggregation, first-in-grid tie rule, fold counts and training memberships; 792 recorded fits | `forecasting.py:41–42, 156–190`; `protocol.json:17–23` |
| Ridge preprocessing | All saved outer-training scaler means and population variances reproduced from the eight permitted cases; max numerical difference 3.57e-10 across variables of different units | `forecasting.py:139–146, 181–189`; `protocol.json:17` |
| Original-source and experiment-code SHA-256 | Four scientific source files, protocol and two code files match saved digests; rechecked after audit; required input artifact hashes unchanged | `forecasting.py:230–238, 332, 349` |
| Decision rule | Recomputed all eight learned-method/horizon decisions and all-baseline case win counts | `forecasting.py:316–329`; `protocol.json:26` |

Source references use one-based lines in the original `APCOM_Draft_Experiments_2026-10-27/experiment_a` files. SHA-256 values identify the versions audited, not external authenticity or registration time.

## Evidence limits

| Distinction | Audit conclusion | Source location |
|---|---|---|
| Target versus measured battery data | The targets are self-generated A123-equivalent laboratory-cell surface-temperature surrogates. No measured pack-temperature accuracy is established. | `forecasting.py:1–4, 338–351`; `protocol.json:5–7` |
| ODE baseline independence | Target source and hold-input baseline share the fixed generator coefficients. The baseline holds present current and air; this is a generator benchmark. | `forecasting.py:33–34, 126–130, 287–288, 339`; `protocol.json:7, 19` |
| Saved predictions versus saved trained models | Predictions, selection records, and ridge scaler moments exist. No common serialized estimator formats were found outside dependencies. The code creates model objects in memory and saves predictions/records. | `forecasting.py:181–191, 289–292, 333–354` |
| Training reproduction versus output verification | This audit rechecks saved outputs. No estimators were refit. Inner-validation per-origin predictions are not saved in the named outputs, so recorded validation case MSEs are reaggregated, not independently regenerated. | `forecasting.py:166–176, 184–191`; selection records |
| Causal predictors versus retrospective eligibility | Feature values use source times no later than the origin. Future availability is used to decide which origins have complete forecast intervals. | `forecasting.py:61–66, 109–116` |
| Generalization | Nine deterministic configurations and overlapping windows do not supply independent physical experiments or row-level significance. Ambient is always 25 °C; the full source temperature range is 25–25.093186885353067 °C. | `forecasting.py:344–351`; `protocol.json:27` |
| Protocol chronology | A local flag records an intention to specify the protocol before fitting. Mutable files and their current hashes do not independently establish when that happened. | `protocol.json:2`; `forecasting.py:266–272` |
| Prior verification record | The saved `verification.json` is treated as a prior local record. Its `passed` value is not substituted for this audit's calculations. | `verification.json`; `verify_outputs.py:13–85` |

No temperature-warning lead time, thermal-runaway prediction, field false-alarm rate, or deployment suitability follows from this audit.

## Recomputed all-baseline decisions

Both pooled RMSE and pooled MAE must be strictly lower than all three baselines. Case wins apply the same two-metric rule within each case.

| Horizon (s) | Ridge pooled win | Ridge case wins / 9 | Histogram boosting pooled win | Boosting case wins / 9 |
|---:|:---:|---:|:---:|---:|
| 60 | No | 0 | No | 0 |
| 120 | No | 0 | Yes | 7 |
| 300 | Yes | 8 | Yes | 9 |
| 600 | Yes | 9 | Yes | 9 |

## Outputs and tests

`results_verified/audit_ml.json` holds numerical checks, input hashes, source hashes, audit-code hash, evidence scope and limitations. The adjacent CSV files contain independently recomputed pooled/case metrics and selected hyperparameters; `recomputed_usefulness.json` contains the decision-rule readback.

Nine analytic/adversarial unit tests cover known MAE/RMSE, retention of small errors, empty/nonfinite rejection, duplicate prediction origins, valid whole-case folds, outer/inner held-out-case leaks, future-invariant causal features, and missing-history rejection. Tests never train estimators. `test_evidence.json` records the final local execution result.
