# Simulated live truck telemetry experiment

This separate experiment turns nine archived HAULSIM activity ledgers into an
**ideal simulated sensor stream** and evaluates temperature forecasts from the
readings revealed so far. It does not rerun HAULSIM or recover its instantaneous
telemetry. It does not change the paper, original Experiment A, the completed-event
correction, or the separate laboratory experiment.

## What is simulated

For each activity, constant pack power is assumed to equal its total battery
energy divided by duration. Equivalent reference-cell current is
`2.5 Ah * pack power (kW) / nominal capacity (kWh)`. This is an assumed mapping,
not measured pack current. Complete event aggregates define the offline scenario;
they are not reported as real-time data from HAULSIM.

The inherited A123-calibrated equation is `dT/dt = a I² - b(T - T_air)`, with
`a = 4.344635339312832e-05 K/(A² s)` and `b = 0.002655462788692412 s⁻¹`.
Its exact solution is integrated across activity boundaries, including fractional
seconds. A new temperature series is generated; it is not a replay of the old
paper's temperature CSV. Temperature starts at 25 °C and air stays at 25 °C.
Temperature is continuous; current changes immediately at each activity boundary.
Integer-second samples stop at the 20% energy reserve, starting from 80% SOC and
counting stationary energy. No noise, delay or within-activity variation is added.

There is an important distinction: a real sensor can reveal current during an
unfinished activity; an activity-summary export cannot yet reveal its eventual
average. Here that average defines an explicitly assumed constant-current scenario.
The prefix-access checks establish causality **within that scenario**. They do not
prove that event averages were available live in the original experiment.

## Forecasts and evaluation

- At each origin, predictors see only the last 61 sensor samples (60 seconds),
  plus nominal capacity and rolling resistance. No future schedule, remaining
  activity duration, future reading or reserve time is a feature.
- Twenty features summarize temperature, equivalent current and air temperature
  with last/mean/min/max/slope/latest difference, plus the two configuration values.
  Centered `math.fsum` arithmetic and 12-decimal rounding match the stabilized
  feature implementation in `A_causal/inputs.py`.
- Gradient boosting predicts the change from the current temperature at 1, 2, 5,
  10 and 30 minutes. Origins are 10 seconds apart and need complete history and
  a target before reserve cutoff.
- Three baselines: unchanged temperature, continuing the past temperature slope,
  and the heat equation with **latest current and air held constant**. This is not
  the last-minute-average-current baseline from the separate laboratory experiment.
- Nine outer folds each hold out a whole configuration. Four inner folds each
  use six training and two validation configurations from the remaining eight.
  Boosting selects 40 or 80 iterations by inner validation error. Seed 20261027;
  depth 3; at most 7 leaves; learning rate 0.08; minimum 20 samples per leaf;
  L2 0.0001; 64 bins; early stopping off. There are 405 fits and 45 saved models
  per run. These are newly fitted estimators, not historical models.
- A pooled win requires strictly smaller RMSE **and** MAE than each baseline.
  Case-wise results are saved too. Scores are descriptive, without significance
  claims. Overlapping forecasts and nine versions of one route are not independent
  physical experiments.

## Reproduce

Use Python 3.14.6 for the recorded environment. From the repository root, create
a separate environment and install the existing pinned Experiment A requirements:

```sh
python3.14 -m venv /tmp/bev-live-env
/tmp/bev-live-env/bin/python -m pip install -r reproducibility/experiments/A/requirements.txt
```

Activate that environment, then run from the repository root. Output directories
must be new and outside input data; replace example names if they already exist.

```sh
source /tmp/bev-live-env/bin/activate
python -B -m unittest discover -s reproducibility/experiments/A_live/tests -v
python -B reproducibility/experiments/A_live/train.py --output results/live-new/run-1
python -B reproducibility/experiments/A_live/train.py --output results/live-new/run-2
python -B reproducibility/experiments/A_live/report.py --run1 results/live-new/run-1 --run2 results/live-new/run-2 --output results/live-new/comparison
```

Recorded dependencies: NumPy 2.3.5, SciPy 1.16.3, scikit-learn 1.7.2,
matplotlib 3.10.7, threadpoolctl 3.6.0 and joblib 1.5.2. Native numerical execution
is limited to one thread. Other platforms or library versions may produce different
floating-point/model-fit results; repeatability here is checked in the recorded
environment, not claimed universally.

## Replay as a live stream

```sh
python -B reproducibility/experiments/A_live/replay.py --run results/live-new/run-1 --case C100_RR03 --from-s 1200 --to-s 1210 --speed 1
```

This prints one JSON reading per second, with forecasts every ten simulated
seconds from a rolling past-only window. `--speed 0` runs without wall-clock delay.
It loads the saved model that excluded the requested configuration. It does not
read future labels to make the forecast. At late origins it can forecast beyond
the available recording; such forecasts have no scored target in this experiment.
This is a command-line replay demonstration, not an edge-device deployment or
a measured latency benchmark.

Only load models from your own trusted runs. Hashes detect changes against a
manifest; they do not establish the authenticity of a manifest supplied by someone
else. Proof files refer to the source checkout by absolute path. After moving the
checkout, create fresh runs to establish valid local proofs rather than editing
old manifests to make them pass.

## Saved results and checks

### Technical details supporting Section 2.3

The two final runs used Python 3.14.6, NumPy 2.3.5, SciPy 1.16.3,
scikit-learn 1.7.2 and joblib 1.5.2, with single-thread numerical execution.
SHA-256 manifests identify the inputs, scripts and outputs. Every saved estimator
was reloaded and its predictions compared with the scored outputs. A rolling-window
replay computed forecasts from the revealed sensor history, with future readings
excluded from predictor inputs. These details accompany the shortened
reproducibility statement in the document; exact commands and the full dependency
pins appear above, and the check records are described below.

The finalized runs are in `results/live-telemetry-2026-11-12/final-run-1` and
`final-run-2`; the checked tables and plot are in `final-report`. These local
result folders are git-ignored. Run the commands above to regenerate them.

Each run saves input and script SHA-256 hashes, all output hashes, sensor readings,
features, individual predictions, pooled/per-case metrics, folds, tuning records,
protocol, versions, and 45 models. It checks every model's batch predictions after
serialization and 135 selected rolling-prefix predictions against batch output.
`report.py` verifies the manifests, compares both runs, independently recomputes
all metric table entries using `math.fsum`, and generates `claims.json`,
`verification.json`, `RESULTS.md` and `central_case.png` from saved predictions.

Compressed CSV content is compared after decompression. Run times, proof timestamps,
commands and serialized model bytes need not match; the numerical outputs and model
selection must match exactly. The independent metric arithmetic uses a 1e-12 °C
absolute tolerance, with exact counts. This is an automated internal cross-check,
not independent human scientific review.

Initial `run-1` and `run-2` used joblib 1.6.0 despite the existing requirements
pinning 1.5.2. They are retained as preliminary artifacts. The final pair was
rerun in a fresh environment with all six direct dependencies pinned as above.

## Interpretation

### Temperature R² reporting, 14 November 2026

The AI-assisted `report.py --predictions` mode regenerates RMSE, MAE and
temperature R² directly from saved forecasts, without retraining. It pools
prediction rows before calculating R²; it does not average configuration scores.
The denominator uses the mean of the scored target temperatures. Constant targets
have undefined R² (NaN). This differs from the temperature-change R² also recorded
by `A_models`; the paper table uses temperature R².

From the repository root, using the pinned Python environment:

```bash
python reproducibility/experiments/A_live/report.py \
  --predictions reproducibility/results/models-2026-11-13/predictions.csv.gz \
  --output results/r2-report-NEW
```

Use the prediction path from a newly reproduced `A_models` run if the dated local
run is unavailable (see its README for the training command). The original
`results/live-telemetry-2026-11-12/final-run-1/predictions.csv.gz` is also accepted
and reproduces the same four-method table. No existing run is overwritten.

Outputs include `pooled_metrics.csv`, `per_case_metrics.csv`, `r2_ranges.csv`
(with the configurations at the endpoints), `comparison_checks.json`, the
four-method table in `METRICS.md`, and a SHA-256 `PROOF.json`. All methods supplied
in the input are retained in the CSVs, including ridge, random forest and MLP
when using `A_models`. The report rejects duplicate predictions, unequal forecast
times or targets across methods, and inconsistent horizon timestamps. This mode
checks arithmetic and pairing; it does not establish training provenance or
replace the original two-run audit.

The committed numerical snapshot is in
[`../../docs/forecast_metrics_2026-11-14`](../../docs/forecast_metrics_2026-11-14).
All 1,050 RMSE/MAE/R² values (35 pooled and 315 case-level rows) were independently
checked against scikit-learn and the saved `A_models` outputs within 1e-12.
HGB's lowest R² at every horizon is for `C120_RR02` (424.8 kWh, 2% rolling
resistance), including −0.236474 at five minutes and −0.015675 at thirty minutes.
It nevertheless beats each of the three original baselines on both errors in
all nine configurations at ten and thirty minutes. These are descriptive,
simulation-only results, not statistical significance or pack validation.

The full comparison remains available in the snapshot: MLP has lower pooled RMSE
than HGB at all five horizons. Keeping HGB as the main paper method does not
establish it as the best learned model tested.

The final tables describe **generated reference-cell temperature**, not real truck
pack temperature. The inherited lab calibration is unchanged; this adds no new
thermal calibration evidence. The same heat equation generates the targets and
the physics baseline, while all truck configurations share a route and scenario
construction. Ideal noiseless readings and small temperature excursions make the
errors much smaller than should be assumed for real sensors.

A lower error at 30 minutes than at 10 minutes does not imply longer forecasting
is generally easier: the eligible origins differ, and the deterministic cycle can
create recurring patterns. Generalization to new routes, trucks, workloads, sensors,
aging or ambient conditions remains untested.

All 45 outer models selected 80 iterations, the upper edge of the frozen 40/80
grid. Wider tuning could change the results. The grid was preserved for this
comparison rather than expanded after inspecting the test scores.

**No thermal-runaway event, precursor, fault response, alarm threshold, false-alarm
rate or warning lead time is evaluated.** The result cannot substantiate a claim
of thermal-runaway prediction or early warning. It is a simulated normal-operation
temperature forecasting experiment that may inform later monitoring research.

## Assistance and scope

### Additional cycle-based baseline, 13 November 2026

`cycle_baseline.py` adds a separate, post-hoc seasonal-naive comparison. It does
not refit boosting, alter original predictions or replace the four-method run.
For each outer test case, the median current repetition period is estimated
using only the eight training cases. Integer lag candidates span 600–2400 seconds
and retain at least half of each recording as overlap. Pearson correlation
chooses each training period; forecast errors do not choose periods. The median
is rounded to seconds, with halves rounded up. See `CYCLE_BASELINE_PLAN.md` for
the decisions recorded before executing this additional comparison.

At origin `t`, horizon `h` and fitted period `L`, the prediction is the observed
temperature at `t + h - L * ceil(h/L)`. If that index is negative, persistence
is used. The function receives only the revealed temperature prefix. This is
the [seasonal-naive method](https://otexts.com/fpp3/simple-methods.html), with an
explicit period estimator and startup rule. It retains up to a cycle of test
history, whereas the original methods use 60 seconds. It is not an equal-history
comparison. The range was chosen with knowledge of earlier traces, so the new
experiment is explicitly post-hoc.

From the repository root with the pinned environment active:

```sh
python -B -m unittest discover -s reproducibility/experiments/A_live/tests -v
python -B reproducibility/experiments/A_live/cycle_baseline.py --run results/live-telemetry-2026-11-12/final-run-1 --output results/cycle-new/run-1
python -B reproducibility/experiments/A_live/cycle_baseline.py --run results/live-telemetry-2026-11-12/final-run-2 --output results/cycle-new/run-2
```

The source runs must first exist and pass their original hash manifests; use
the reproduction commands above if regenerating them. Each new output includes
all five methods' predictions, per-case and pooled scores, the training period
estimates, source-sample times, fallback flags, protocol and a SHA-256 proof.
Two subsets are reported: all original origins, and only origins with an available
same-phase reading, with all methods scored on the same subset. Existing method
scores are checked against the source run, and all new scores are cross-checked
with `math.fsum` arithmetic to 1e-12 °C. Use new output directories for each run.

Executed outputs: `results/cycle-baseline-2026-11-13/run-1` and `run-2`.
The checked-in [results report](CYCLE_RESULTS.md) includes both comparison tables
and the interpretation limits; full generated run directories remain git-ignored.
Seven numerical/protocol files match exactly after gzip decompression; proof
timestamps and source-run paths differ. The adjacent `RESULTS.md` and
`verification.json` record results and the separate source-index/metric check.
All 19,618 seasonal predictions referenced times at or before their forecast
origin. Fold periods were 1,472–1,482 seconds. Individual training-record periods
ranged from 1,438 to 1,572 seconds, with no search-boundary selections.

Boosting beat this cycle baseline on pooled RMSE and MAE at every horizon.
Against all four baselines it won on both metrics at 5, 10 and 30 minutes;
the thermal baseline retained lower MAE at 1 and 2 minutes. The same pattern
held after excluding fallback origins. This supports the existing descriptive
conclusion against this particular comparator. It does not rule out adaptive
cycle predictors, prove that boosting learned the cycle, or validate real pack
temperatures. A fixed median period can mismatch configuration-specific timing
and repeat the startup transient. No new calibration or runaway detection was run.

### Forecasting-only document update, 12 November 2026

After the experiment was completed, the author requested that the existing Google
Doc be updated using the forecasting results only, with no Experiment B addition.
The earlier statements that the paper was unchanged describe the implementation
stage; the subsequent document revision adopts the simulated-sensor protocol and
verified 1/2/5/10/30-minute results. Thermal runaway remains motivation and an
explicitly unvalidated future application.

Both document figures are generated by this codebase from the verified numerical
outputs, using Matplotlib. No generative-image model is used. Regenerate them with:

```sh
python -B reproducibility/experiments/A_live/figures.py --run results/live-telemetry-2026-11-12/final-run-1 --output results/live-new/document-figures
```

`figure1.png` plots all nine reference-cell traces over the common reserve-limited
period; `peak_rises.json` supplies Table 1's sampled peak rises. `figure2.png`
plots the central configuration's current and saved 30-minute forecasts, using
the same plotting function as `report.py`. Forecast errors are read from the
unchanged final-run metric files, not extracted from images. The generated
`PROOF.json` records source and figure hashes. The initial repository-generated
figures were byte-identical to the images inserted in the document.

Code, tests, documentation and automated verification were produced with AI
assistance on 12 November 2026 (America/Toronto; UTC records may show 13 November).
No automated check is attributed to human verification. See `CHECKS.md` for the
executed verification commands, outcomes and final review disposition.
