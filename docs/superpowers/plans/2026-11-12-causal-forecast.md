# Causal Forecast Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with a final fresh review.

**Goal:** Remove unfinished-event information from predictors, stabilize features and rerun conclusions.
**Architecture:** A separate experiment reuses original model selection and group splits, with an as-of-origin completed-event state estimate and stable feature arithmetic.
**Tech Stack:** Python and existing pinned NumPy/SciPy/scikit-learn environment.
**Spec:** ../specs/2026-11-12-causal-forecast-design.md

## Constraints and review focus

- Original targets are labels only; every input's source event must end by origin.
- Initial state is assumed, not measured. Do not silently relabel estimates as observations.
- Completed event boundary is inclusive; unfinished final events remain unavailable.
- Target/eligibility accesses may use future records, feature construction may not.
- Numerical tests compare deterministic data outputs, not timestamps or compressed-container bytes.

## Tasks

- [x] Write failing tests in experiments/A_causal/tests/test_inputs.py for completed-event causality and numerical stability.
- [x] Implement inputs.py: history_as_of(events, origin_s, capacity_kwh, a, b) returns estimated history and availability metadata; stable_features(history, capacity_kwh, rr_pct) returns the existing twenty-feature layout.
- [x] Implement train.py with unchanged estimator fitting/splits, explicit revised protocol and non-destructive new output directories. Test common-origin target/feature separation and repeatability.
- [x] Run stabilized retrospective control and corrected experiment twice. Record exact inputs, scripts, commands, versions and hashes; recompute all pass/fail conclusions from the saved outputs.
- [x] Run repository checks, obtain a fresh review, address material findings, and deliver findings with limitations and reproduction commands.

## Execution ledger

Ruling: execute the user-authorized fix without another permission round; the conservative event-completion assumption is stated in chat and this spec.
Ruling: native worktree creation did not return or create a checkout; use a separate Git worktree on codex/causal-forecast-correction.
Baseline: the original forecasting tests passed in the previous audit; rerunning in the new worktree before implementation.

Input task: eight new regression tests observed failing before implementation, then passed.
Training task: three example-construction tests observed failing before implementation, then passed.
Final review: fresh read-only reviewer found no causal-input or baseline defect; one Important finding concerned causal wording in retrospective-control metadata.
Final fix: added a mode-specific protocol test, observed it fail, fixed the metadata and reran all twelve corrected tests successfully. Fresh final outputs preserve the earlier provenance records rather than editing them.
Verification: original forecasting tests, root pytest (46 tests and 27 subtests), ML audit tests, TUM preparation/integrity and full source reproduction passed.
Ruling: reproducibility/tests/test_cli.py::IntegrityTests::test_hash_match_and_tamper_failure initially failed because macOS temporary paths resolve through a symlink. Re-running the unchanged twelve-test suite with a canonical TMPDIR passed; this environment workaround does not change science or suppress a test.
Results: final-corrected-1 and final-corrected-2 match exactly on data outputs and selections excluding timings. Corrected ridge/boosting pass at every horizon. Stabilized retrospective ridge/boosting pass only at five and ten minutes; original two-minute boosting superiority is not numerically robust.
Ruling: retain the conservative completed-report protocol explicitly; this changes the experiment and does not recover unrecorded telemetry. Its cost is weaker current-state information for every method.
Ruling: claim same-environment repeatability only; independent platform execution and physical/field validation are outside this completed correction.
No minor review findings were deferred. Keep the local branch and results; no merge, push or manuscript change.
