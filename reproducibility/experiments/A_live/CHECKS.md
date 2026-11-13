# Executed verification record

Date: 12 November 2026, America/Toronto. AI-authored implementation, tests and
automated checks. This is not a human scientific review or field validation.

## Final numerical result

The final two runs used Python 3.14.6 and every direct dependency pinned in
`../A/requirements.txt`, including joblib 1.5.2. Each executed 405 fits and saved
45 newly fitted held-out models. Predictions also exactly match the preliminary
joblib-1.6.0 run, but the final pair is the reproduction reference.

`results/live-telemetry-2026-11-12/final-report/verification.json` records:

- 44,906 generated sensor rows; 19,618 forecast origins across five horizons;
  78,472 prediction rows across four methods.
- Exact two-run agreement on decompressed telemetry, features and predictions,
  metric CSVs, fold assignments, cases, protocol and replay checks.
- Exact model selection and summary agreement after removing elapsed time.
- All 800 entries in pooled and per-case metric tables independently recalculated
  from saved predictions: counts exact, errors within 1e-12 °C.
- Each run reloads all 45 models and compares every batch prediction exactly;
  135 selected rolling-prefix predictions per run also match.
- Separate replay CLI check: 11 sensor rows at seconds 1200–1210 and 40 forecast
  values at seconds 1200 and 1210 exactly match the scored outputs.
- Generated temperatures span 25.00000000 to 25.09317769 °C.

| Horizon | Boosting RMSE (°C) | Boosting MAE (°C) | Pooled strict win | Whole-case strict wins |
|---:|---:|---:|:---:|---:|
| 1 min | 0.001525 | 0.000732 | No | 0/9 |
| 2 min | 0.003264 | 0.001706 | No | 7/9 |
| 5 min | 0.006717 | 0.004084 | Yes | 8/9 |
| 10 min | 0.007121 | 0.005438 | Yes | 9/9 |
| 30 min | 0.006384 | 0.004247 | Yes | 9/9 |

Strict win means beating all three baselines on both RMSE and MAE. The heat-equation
baseline has lower pooled MAE at 1 and 2 minutes. Pooled and case-wise outcomes
need not agree because magnitudes and eligible sample counts differ. These are
descriptive results, not significance tests.

## Test commands and outcomes

Use the environment documented in README. Commands below were executed with its
Python interpreter. All exited successfully. `-B` suppressed bytecode writes.
The temporary directory was canonicalized as `/private/tmp` for the reproducibility
unit tests, avoiding the pre-existing macOS `/var` versus `/private/var` alias issue.

From repository root:

| Command | Outcome |
|---|---|
| `PYTHONPATH=src python -B -m pytest` | 46 tests and 27 subtests passed |
| `python -B -m unittest discover -s reproducibility/experiments/A_live/tests -v` | 18 tests passed after review fixes |

From `reproducibility/`:

| Command | Outcome |
|---|---|
| `TMPDIR=/private/tmp PYTHONPATH=src python -B -m unittest discover -s tests -v` | 12 tests passed |
| `python -B -m unittest discover -s tools -p test_audit_ml.py -v` | 9 tests passed |
| `python -B -m unittest discover -s data/tum -p test_prepare_tum_csv.py -v` | 6 tests passed |
| `python -B data/tum/verify_tum_csv.py --dataset data/tum/dataset` | All source hashes and previews matched; 747,524 rows preserved |
| `python -B -m unittest discover -s experiments/A/tests -p test_models.py -v` | 9 tests passed |
| `python -B -m unittest discover -s experiments/A_causal/tests -v` | 12 tests passed |
| `PYTHONPATH=src python -B -m bev_research.cli all --output ../results/live-telemetry-2026-11-12/checks/reconstruction` | Hashes, physics, ML reconstruction and plots completed; 103 input files checked |

The final command invokes the same `main` as `bev-reproduce all`, explicitly using
this checkout's `src` rather than an installed CLI from another checkout. It is
an archive reconstruction audit, not another model refit and not full Experiment B
execution. Experiment B remains outside this task and is not declared portable.

Run the two trainer commands, report comparison and replay command in README with
the recorded final paths to reproduce the remaining checks. All logs and a hashed
`VERIFICATION_RECORD.json` are in the local `results/live-telemetry-2026-11-12/checks/`
directory. `final-report/claims.json` contains the metric-by-metric cross-check.
The saved central-case plot was visually inspected for labels, units and alignment;
30-minute forecasts are drawn at target times, starting after minute 31.

## Review and scope

One fresh-context AI reviewer inspected the complete branch from `2a9a3fd` through
`4a87249`, the saved artifacts and relevant helper functions. The reviewer found
no critical issue and two important reporting defects, both fixed:

1. Future audits previously inherited the original execution date. Reports now
   capture one audit instant, convert it to Toronto time and use it consistently
   in the human report, verification record and UTC proof. A test covers the
   previous-local-day boundary on a future date.
2. Outcome-specific prose previously assumed the first run's winners. It now
   derives the stated wins and RMSE/MAE comparisons from the audited metrics.
   A test covers different winners and no winning horizons.

The new tests failed before the fixes and the full A_live suite then passed 18/18.
The finalized report was regenerated into `final-report`, preserving the earlier
`final-comparison` artifact. Training code and predictions did not change; both
training manifests still verify. No additional minor findings were deferred.

The review's scope exclusions were accepted explicitly:

- Physical calibration adequacy, pack accuracy and runaway performance remain
  unvalidated. Treating this check as evidence for them would overstate the result.
- Noise, delay, changing ambient conditions and unseen routes remain deferred.
  Predictions under those conditions may differ substantially.
- The frozen boosting grid remains 40/80; all 45 selections reached 80. This limits
  conclusions about tuning and is documented without retuning to test outcomes.
- Prior A/A_causal/B code was reviewed only where helpers are used here, with
  regression checks; this does not establish unrelated implementation correctness.
- AI review does not constitute independent human scientific approval.

Automated
verification establishes internal reproducibility and the implemented information
boundary, not real-world accuracy, calibration adequacy or thermal-runaway detection.
The manuscript, original experiment, prior correction branch and lab experiment
remain unchanged. Results are local artifacts and have not been published.
