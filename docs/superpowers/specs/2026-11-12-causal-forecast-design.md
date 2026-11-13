# Causal event-ledger forecasting correction

The user requested fixing future-information use and numerical reproducibility,
rerunning the study and checking its conclusions. This is AI-assisted analysis,
not manuscript text. Preserve the original experiments and input bytes.

## Approach and assumptions

Use completed-event information at the original ten-second forecast origins.
An event's energy and duration become available at its recorded end, with zero
extra reporting latency assumed. Reconstruct the synthetic temperature history
from completed events. From the last completed event to the forecast origin,
hold its equivalent current; before any completed event, assume zero current
and the known initial/ambient temperature of 25 C. These are estimates, not
measurements. No incomplete-event energy, duration or mean current enters
features or baseline forecasts. Future temperatures remain evaluation targets.
The existing generated targets and eligibility windows are retained, so this
is a delayed-information simulation benchmark, not a new physical experiment.

Alternatives considered: forecasting only at event ends would substantially
change sampling; simply lagging current leaves temperature-history dependence;
real-time telemetry is unavailable. Completed-event estimation preserves the
comparison schedule and explicitly models the available information. This is
an implementation choice under the user's requested correction, not a claimed
user-selected scientific protocol. The revised protocol is frozen before fitting.

Replace backend-dependent dot products with centered scalar math.fsum slopes;
canonicalize numerical histories and derived features to 12 decimal places,
far below the source's meaningful precision. Exactly constant histories must
produce exactly zero slopes. Preserve the original grids, splits and seed.

## Outputs and checks

New implementation: reproducibility/experiments/A_causal/{inputs,train}.py.
Save protocol, provenance hashes, estimated features, input-availability audit,
predictions, metrics, selection records and comparisons in fresh result folders.
Use unchanged laboratory coefficients and original generated target CSV;
read native SQLite event archives read-only and verify their manifest hashes.
Run a stabilized retrospective control and two corrected independent process
runs. Compare numerical outputs, not wall-clock timings or gzip timestamps.
Cross-platform numerical identity is not claimed without a second platform.

Regression tests cover unfinished/future-event mutation, exact completion
boundaries, cold start, constant-input thermal evolution, invalid records,
constant slopes, hand-computed slopes, and harmless last-bit perturbations.
Run existing project checks and a fresh code review before reporting results.

No source edits, manuscript changes, merge, push or publication are included.
