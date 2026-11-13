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

Code, tests, documentation and automated verification were produced with AI
assistance on 12 November 2026 (America/Toronto; UTC records may show 13 November).
No automated check is attributed to human verification. See `CHECKS.md` for the
executed verification commands, outcomes and final review disposition.
