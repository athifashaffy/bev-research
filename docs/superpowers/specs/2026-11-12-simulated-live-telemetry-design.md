# Simulated live telemetry design
Date: 12 November 2026. AI-assisted implementation and verification.
The user confirmed simulated live truck telemetry after explicitly distinguishing it
from delayed completed reports and laboratory replay. This document records that
accepted direction; routine implementation choices below are the assistant's.

Build a separate experiment in reproducibility/experiments/A_live.
Use the nine native archived HAULSIM ledgers, read-only and hash checked.
Freeze an offline scenario: each activity has constant power equal to its recorded
energy divided by duration. This aggregate-derived assumption is not recovered
instantaneous HAULSIM telemetry. Map to a 2.5 Ah reference-cell current using P/E.
Integrate the existing frozen thermal model exactly across activity boundaries;
sample each integer second, starting at 25 C with air at 25 C. No noise or latency.
Stop scored data at the 80%-to-20% energy reserve using all activities.
Predictors see only the generated stream prefix, never ledger ends or future samples.
Current and temperature at the origin are observable ideal simulated sensors.

Reuse stable 20-feature arithmetic (61 samples), seed, boosting grid and nested
whole-configuration splits. Only boosting and three baselines, no ridge. Horizons:
60,120,300,600,1800 seconds; origin stride 10 seconds. Separate targets from prefix
features. Report all pooled and per-case scores; strict all-baseline RMSE/MAE rule.
Save telemetry, features, predictions, final held-out models, folds, selections,
protocol, hashes, versions and commands. Two independent processes must match
numerical outputs excluding timings and serialization metadata.
Provide a replay CLI that streams rows, computes predictions from its rolling
history and saved held-out models, and does not preload future targets.
Produce a figure from saved central-case predictions and compare at 30 minutes.
Archive a machine-checkable claims record and runnable commands.
The paper, original experiment, correction branch and lab experiment remain untouched.

Alternatives considered in the conversation: completed-report estimation and
measured laboratory replay do not implement the requested live simulated truck
setup. Noise/segment-based load modelling would require additional assumptions
and are deferred. No claim of measured pack temperature or fault detection.

