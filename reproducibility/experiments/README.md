# Experiments

**The current APCOM paper's forecasting results (Table 2, Figure 2) come from
[A_live](A_live).** The other folders are earlier or separate experiments, kept so
their results stay reproducible.

| Folder | What it is | Used by the current paper? |
| --- | --- | --- |
| [A_live](A_live) | Simulated live-sensor forecasting: 1 Hz sensor record from the HAULSIM activities, HGB vs persistence, linear-trend and thermal baselines at 1, 2, 5, 10 and 30 min. Saved run: `../results/run-2026-11-13/live/` | **Yes**: Table 2, Figure 2 |
| [A_models](A_models) | HGB compared with ridge, random forest and a neural network on the A_live task (same data, inputs, folds; HGB recomputed identical to Table 2). Accuracy, R², training time, forecast time and model size | No (added 13 Nov 2026, after the draft) |
| [A_causal](A_causal) | Completed-event forecasting correction and the stable feature arithmetic (`inputs.py`) that A_live imports | Indirectly: A_live uses its `inputs.py` |
| [A](A) | Original Experiment A: scikit-learn ridge and HGB at 1, 2, 5 and 10 min, with a byte-identical 792-fit reproduction | No (earlier draft's Table 4). A_live reuses its `estimator()`, `fit_selected()`, `nested_group_plan()` and `physics_forecast()` |
| [A_lab](A_lab) | Forecasting on measured A123 laboratory-cell records | No (separate experiment) |
| [B](B) | Archived LFP warning-rule analysis on Sheffield and TUM records | No (removed from the paper) |
| [haulage](haulage) | Index: nine HAULSIM result databases, settings and energy/reserve functions | Yes: Table 1 |
| [thermal](thermal) | Index: reference-cell model, fitted ratios, generated traces and sensitivities | Yes: Equations (2)–(5), Figure 1 |

Run any experiment from `reproducibility/` in an environment with
`experiments/A/requirements.txt` installed; each folder's README has its commands.

TUM module measurements are separately available as [CSV data](../data/tum/dataset).
They are not inputs to Experiments A or A_live.
