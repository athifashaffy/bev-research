# A_models: HGB compared with other machine-learning models

AI-assisted code (Claude, 13 November 2026). Results below are from the run of
13 November 2026 (`results/models-2026-11-13`, not in git) and were checked
automatically against its CSV files. This is not personal human verification.

## What it does

It answers the question "why HGB and not another model?" on exactly the paper's
task. Everything that defines the Table 2 experiment is reused unchanged from
[`A_live`](../A_live):

- the nine simulated 1 Hz sensor records;
- the 20 inputs and the five horizons;
- the nested hold-one-configuration-out test;
- the HGB settings.

Three other model families are added, and each gets the same treatment: a small
settings grid chosen on the four inner splits, a refit on the eight training
configurations, and a test on the held-out one.

| Model | In plain words | Settings tried |
| --- | --- | --- |
| Ridge | one weight per input, added up; a penalty keeps weights small | α = 1, 100, 10000 (as in Experiment A) |
| Random forest | 100 deep trees each fitted on a random resample, averaged (bagging) | max depth 8 or unlimited; ≥ 20 samples per leaf |
| Neural network (MLP) | two layers of 32 neurons; inputs and target standardised | α = 0.0001 or 0.01; 300 iterations |
| **HGB (paper)** | 40 or 80 small trees added one after another, each fixing the last one's errors (boosting) | as in the paper |

**Safety check:** HGB is recomputed inside this run. Its 19,618 forecasts are
identical to the saved Table 2 run (`--check-table2`), so the comparison is on
the paper's own HGB.

```bash
cd reproducibility                       # pinned: experiments/A/requirements.txt
python experiments/A_models/compare.py --output results/models-NEW --check-table2 results/run-2026-11-13/live   # ~7 min
python tools/run_with_proof.py --output results/models-NEW-figures --script experiments/A_models/plot.py \
  --input results/models-NEW/pooled_metrics.csv --input results/models-NEW/cost_summary.csv \
  -- python experiments/A_models/plot.py --run results/models-NEW --output results/models-NEW-figures/figs
python -m unittest discover -s experiments/A_models/tests -v
```

## Results (13 November 2026 run)

Pooled RMSE in m°C (lower is better), then R² on temperature (1 = perfect,
0 = no better than always guessing the mean, below 0 = worse than that):

| Horizon | Thermal baseline | Ridge | Random forest | Neural network | **HGB** |
| --- | --- | --- | --- | --- | --- |
| 1 min | 1.788 / 0.993 | 1.670 / 0.994 | 1.504 / 0.995 | **1.206 / 0.997** | 1.525 / 0.995 |
| 2 min | 4.806 / 0.951 | 4.141 / 0.964 | 3.246 / 0.978 | **2.338 / 0.988** | 3.264 / 0.978 |
| 5 min | 16.308 / 0.415 | 10.359 / 0.764 | 5.699 / 0.929 | **3.581 / 0.972** | 6.717 / 0.901 |
| 10 min | 36.309 / −2.198 | 11.512 / 0.679 | 10.802 / 0.717 | **5.834 / 0.917** | 7.121 / 0.877 |
| 30 min | 23.896 / −0.496 | 9.476 / 0.765 | 6.814 / 0.878 | **5.442 / 0.922** | 6.384 / 0.893 |

Persistence and linear trend are in `pooled_metrics.csv` (same values as
Table 2). At 5 minutes their R² is −0.017 and 0.026, and at 10 and 30 minutes it is below zero.

Cost per model (median over the 45 held-out fits, one CPU thread, this laptop):

| | Ridge | Random forest | Neural network | HGB |
| --- | --- | --- | --- | --- |
| Training time | 0.001 s | 0.72 s | 0.37 s | 0.045 s |
| Time per forecast | 0.06 ms | 1.34 ms | 0.11 ms | 0.26 ms |
| Model size | 1.4 KB | 1252 KB | 66 KB | 73 KB |

## What the numbers show

1. **Learning models beat the simple baselines.** Every model has lower pooled
   RMSE than the thermal baseline at every horizon. From 5 minutes on, every
   model keeps R² at 0.679 or higher, while the thermal baseline drops to 0.415
   at 5 minutes and below zero at 10 and 30 minutes.
2. **Tree models beat the straight-line model.** HGB and random forest have
   lower RMSE than ridge at every horizon. The relationship between recent
   readings and the coming temperature change is not a straight line.
3. **HGB is not the most accurate model here.** The neural network has the
   lowest pooled RMSE and highest R² at every horizon. Random forest is ahead of
   HGB at 1, 2 and 5 minutes and behind it at 10 and 30 minutes.
4. **Where HGB stands out is cost.** Among the models that beat ridge, it
   trains fastest (about 8× faster than the network, 16× faster than the
   forest). It is 17× smaller than the forest, and it needs no input scaling.
   Its trees run exactly in plain Python on the [edge device](../../../edge).
   At 30 minutes, it is best on both RMSE and MAE in 5 of the 9 held-out
   configurations, the most of any model (`configurations_best_on_both`),
   even though its pooled RMSE is second.

## Subset chosen for the paper (author's decision, 14 November 2026)

The author chose to present the two tree **ensemble** methods (random forest:
trees averaged, called bagging; HGB: trees added in sequence, called boosting),
ridge as a linear reference, and the three baselines. The neural network is
left out of the paper's comparison. Its results above stay in this record and in
`results/models-2026-11-13`; they were not deleted or rerun.

Context for that choice, from this run:

- **The data are small.** There are 2,822–4,388 forecast rows per horizon, from
  only nine simulated configurations of one route. Neighbouring rows overlap
  (a 61-second window every 10 s), so far fewer of them are independent.
- **Tree ensembles are the usual choice for small tabular data.** See
  Grinsztajn, L., Oyallon, E., & Varoquaux, G. (2022), *Why do tree-based
  models still outperform deep learning on tabular data?*, NeurIPS Datasets and
  Benchmarks, arXiv:2207.08815.
- **Caution:** in this run, the neural network was still the most accurate at
  every horizon. Small data is a reason the author scoped the comparison to
  ensembles; it is not a finding that neural networks did worse here.

Subset figures (same run, drawn with `--methods`, with a proof record):
`results/models-2026-11-14-paper-subset/figs/`.

## Limits of this comparison

- **One run, one seed, small grids.** The network had a single architecture
  and 300 iterations (convergence warnings were suppressed, not fixed).
- **HGB is held back by its fixed 80-iteration upper limit.** It picked 80 in
  all 45 fits, so it may be under-tuned. A wider HGB grid was not tried here,
  and it would need to be set before looking at the results.
- **The data are generated, not measured.** Generated reference-cell
  temperatures from ideal sensors, one route. Which model is best on real pack
  data is unknown.
- **Timings depend on the machine.**
