# Completed-event forecasting correction

This AI-assisted experiment preserves Experiment A and its data. It tests a
different information-availability protocol and creates new model fits. It is
not a recovery of actual within-event telemetry or a truck-temperature validation.

At each original forecast origin, activity energy and duration are available
only after that activity ends. The cell temperature history is reconstructed
from completed activities, then extrapolated using the last completed current.
Before the first report, current is assumed zero. Initial and ambient temperature
are 25 C. This assumes no extra reporting latency after event completion.
All methods use the same estimated current state. The targets remain the original
generated temperatures. Target/availability checks may use future data; predictors
may not. Earlier historical estimates can be revised using reports available by
the current origin, which is explicitly part of this protocol.

The alternative `retrospective_control` mode retains the old information access
but uses stable numerical features. It is intentionally not an online protocol.

Feature arithmetic uses scalar `math.fsum` after centering each channel and
canonicalizes histories/features to twelve decimal places. Constant channels
have exactly zero slope. This suppresses irrelevant last-bit feature artifacts;
it does not prove cross-platform identity of native-library estimators.

## Reproduce

Install `../A/requirements.txt` in a dedicated environment. From `reproducibility/`:

```sh
python -B -m unittest discover -s experiments/A_causal/tests -v
python -B experiments/A_causal/train.py --output results/causal-new-1
python -B experiments/A_causal/train.py --output results/causal-new-2
python -B experiments/A_causal/train.py --mode retrospective_control --output results/stable-control-new
python -B experiments/A_causal/compare_runs.py --first results/causal-new-1 --second results/causal-new-2 --control results/stable-control-new --output results/causal-comparison-new
```

Output folders must be new. Source databases open read-only. Each run records
the input/script hashes, exact command, versions, protocol, features, predictions,
fold selections and metrics. The comparison verifies those hashes and exact
same-environment data-output repeatability, ignoring run times and gzip metadata.
No estimator binaries are saved; the full fitting protocol and selections are.

Read the generated `report.txt`, `comparison.csv` and `comparison.json` together.
The original all-baseline RMSE-and-MAE criterion is retained, but a positive result
under the corrected protocol is not the original result unchanged. The numerical
control is essential to separate feature-rounding effects from input availability.
Review the new assumptions and run the checks independently before submission.
