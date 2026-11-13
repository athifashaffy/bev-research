# Simulated live telemetry Implementation Plan
> **For agentic workers:** Use superpowers:executing-plans in this session.
**Goal:** Generate and replay ideal simulated live telemetry with up-to-30-minute forecasts.
**Architecture:** Native ledger -> fixed scenario generator -> streaming prefix features -> held-out boosting.
**Tech Stack:** Python; original pinned NumPy/SciPy/scikit-learn/matplotlib.
**Spec:** docs/superpowers/specs/2026-11-12-simulated-live-telemetry-design.md

## Global Constraints
New A_live files only. Immutable inputs; exact event integration; explicit aggregate
assumption; no manuscript edits; separate models and results; AI provenance.

## Review Focus
- Events crossing one-second boundaries must conserve thermal integration.
- A later event or sensor row must not alter earlier predictor inputs.
- Invalid ledger, grid, capacity or short stream must fail clearly.
- Model selection must exclude the complete test configuration.
- Replay must match scored predictions and verify model hashes before loading.

### Task 1: Generator and stream boundary
Files: A_live/telemetry.py, A_live/tests/test_live.py.
Interfaces: generate(events,capacity,cutoff_s,a,b) -> array [time,power,current,temp,air];
history_features(prefix,capacity,rr) -> 20 floats.
- [ ] Add tests for fractional boundaries, reserve, future independence and malformed data.
- [ ] Observe failure, implement and pass tests.

### Task 2: Trainer and replay
Files: A_live/train.py, A_live/replay.py.
Interfaces: build_examples(stream,capacity,rr,horizon) -> origins/features/targets;
predict_history(history,capacity,rr,models) -> horizon/method predictions.
- [ ] Test future-row mutation, 30-minute eligibility and baseline calculations.
- [ ] Run nested boosting fits using the original selection helper.
- [ ] Save and reload held-out models; test exact replay equality against scores.
- [ ] Record proof hashes and fail on overwrite or data-directory output.

### Task 3: Verification and delivery
Files: A_live/report.py, A_live/README.md.
- [ ] Independently recompute metrics and decisions from prediction CSV.
- [ ] Compare two runs including prefixes, folds, selections without timing.
- [ ] Plot saved central-case forecasts with clearly labelled simulated temperatures.
- [ ] Run relevant experiment tests and repository-required checks.
- [ ] Fresh whole-branch review, fix material issues, commit only this experiment.
- [ ] Report verified results and reproduction commands; leave paper unchanged.

