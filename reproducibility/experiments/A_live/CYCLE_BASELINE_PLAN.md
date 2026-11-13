# Cycle baseline design and execution plan

13 November 2026. AI-assisted analysis requested by the author. This records
implementation choices, not a preregistered experiment: earlier test results
and the repeating traces have already been inspected.

## Design

Add a separate seasonal-naive comparison without altering saved A_live runs.
Estimate each training recording's period from equivalent-current lag correlation
at integer lags 600–2400 seconds, retaining at least half the recording as overlap.
For each outer test configuration use the rounded median of the eight training
periods. No held-out readings or forecast errors choose that period. The lag range
is an analyst choice motivated by the already observed haul-cycle scale.

At origin t, horizon h, period L, use temperature at
`t + h - L * ceil(h / L)`. This is always at or before t. If that time precedes
the recording, fall back to persistence. Use only the revealed prefix of the
test stream. This is the usual seasonal-naive forecast, with a training-derived
period and explicit startup policy. It needs up to L seconds of test history,
unlike the existing methods' 60 seconds. The information budget is not identical.

Alternatives: a fixed 30-minute lag assumes a cycle length without estimating it;
online period estimation needs enough observed cycles and another warmup policy.
Use the training-derived median as a simple first comparison, not an optimized
cycle-aware predictor. A poor result will not rule out better adaptive methods.

## Tasks and checks

- [ ] Add tests for known periodic signals, constant/invalid inputs, train/test
  separation, long horizons, warmup fallback and future-prefix isolation.
- [ ] Add `cycle_baseline.py`, a standalone runner reading hash-verified saved
  telemetry, folds and predictions. Reject duplicates, mismatched targets and
  unequal method coverage. Save all predictions, period evidence and metrics.
- [ ] Score all original origins and the same subset for every method where
  previous-cycle readings are available. Report coverage, per-case metrics and
  both-score wins. Independently cross-check arithmetic with math.fsum.
- [ ] Run twice into new result directories and compare numerical files exactly
  after gzip decompression. Verify old inputs/outputs remain unchanged.
- [ ] Run A_live tests and repository-required checks; record date, actual scope,
  failures and AI assistance in README/CHECKS. No human verification claim.
- [ ] Make the two requested language edits to the supplied Google Doc draft.
  Report new baseline results separately before incorporating new scientific
  results into the manuscript. No image generation or model refitting needed.

Reference: Hyndman and Athanasopoulos, Forecasting: Principles and Practice,
seasonal-naive method, https://otexts.com/fpp3/simple-methods.html.
