EXPERIMENT A: CONFIGURATION-HELD-OUT SURROGATE FORECASTING
27 October 2026

Target: self-generated A123-equivalent cell surface temperature, not measured pack temperature. The same fixed ODE and coefficients generated truth and define the hold-current physics baseline. This benchmark is not physical validation.

Completed nine outer whole-configuration holdouts. Each inner selection uses four group folds among the other eight cases. Twenty causal features summarize the preceding 60 seconds, with one origin every 10 seconds. Horizons are 60, 120, 300 and 600 seconds. No origin crosses an acquisition gap or the external reserve. Air is constant 25 C, so ambient features contain no variability.

Each final benchmark run performs 792 fits: 432 inner Ridge, 288 inner histogram boosting, and 36 final fits of each model. The final run completed in about 30 seconds after imports. All final selected Ridge alpha values are 1; all selected boosting max_iter values are 80. This is selection inside the fixed small grid, not a claim of globally optimal hyperparameters.

Primary reporting rule: a learned method qualifies only when BOTH pooled RMSE and pooled MAE are lower than ALL THREE baselines. RMSE-only skill is plotted separately and does not imply qualification. No statistical independence or significance is inferred from overlapping origins.

Findings: neither learned method qualifies at 60 s because the physics baseline has lower MAE. Histogram boosting qualifies at 120, 300 and 600 s, with 7/9, 9/9 and 9/9 individual-case all-baseline wins on both metrics. Ridge qualifies at 300 and 600 s, with 8/9 and 9/9 case wins. These findings describe predictable structure in this deterministic, low-variation surrogate. They establish no measured pack accuracy, thermal-runaway forecast, warning lead time, or field false-alarm rate.

TABLE 4: pooled errors and nine-case spread (C; at least 8 significant figures)
horizon_s method n pooled_RMSE pooled_MAE case_RMSE_min case_RMSE_max case_MAE_min case_MAE_max
60 persistence 4388 0.0049386423 0.0040107715 0.0032669667 0.0067073722 0.0027678287 0.0054802557
60 linear_trend 4388 0.0026559494 0.0013352749 0.0017612066 0.0036141848 0.00091539392 0.0018383263
60 physics_hold 4388 0.0017877129 0.00043173608 0.0011762121 0.0025134469 0.00029015159 0.0006324254
60 ridge 4388 0.0016703422 0.00085728859 0.0011437565 0.0023552618 0.00074086721 0.0010982903
60 hist_gradient_boosting 4388 0.0014807207 0.00067055824 0.0010906511 0.0020340717 0.00056278899 0.00088006136
120 persistence 4334 0.0095618302 0.007872174 0.0063338626 0.012950694 0.0054369487 0.010737885
120 linear_trend 4334 0.0063307154 0.0038361273 0.0042222994 0.0086308848 0.0026446171 0.0052762002
120 physics_hold 4334 0.0048057754 0.0016390783 0.0031867856 0.0067062074 0.0011094409 0.0023803479
120 ridge 4334 0.0041409487 0.002731208 0.0030000233 0.0058337759 0.0023481811 0.00356882
120 hist_gradient_boosting 4334 0.002910561 0.0014524202 0.0020739183 0.0040919219 0.0012188885 0.0020281438
300 persistence 4172 0.021506277 0.018260777 0.014334209 0.028641295 0.012645334 0.024651371
300 linear_trend 4172 0.021045269 0.016861802 0.014281394 0.027605524 0.011823184 0.022352093
300 physics_hold 4172 0.016308042 0.0089477291 0.010900415 0.021795016 0.006109545 0.012193734
300 ridge 4172 0.01035913 0.0082178035 0.0078268003 0.014158873 0.0065349608 0.01130237
300 hist_gradient_boosting 4172 0.0049314176 0.0034894322 0.0031181496 0.0073370519 0.0020582524 0.005730648
600 persistence 3902 0.035073348 0.030300248 0.023179057 0.048316132 0.020681261 0.042826177
600 linear_trend 3902 0.053933689 0.050635209 0.037628424 0.069785431 0.03624393 0.066713526
600 physics_hold 3902 0.036308739 0.029022031 0.02485123 0.04744851 0.020575675 0.037558595
600 ridge 3902 0.011511953 0.0079033058 0.0083091188 0.015762116 0.0055943636 0.01087751
600 hist_gradient_boosting 3902 0.0070139289 0.0053466646 0.0038589727 0.012951773 0.0030474093 0.010773973

Files:
protocol.json: frozen assumptions and grids before model fitting.
summary.json: full numerical findings, 180 per-case metric rows, 20 pooled cells, usefulness decisions, versions and hashes.
fold_assignments.json: all outer and inner whole-case assignments.
per_fold_model_selection.json: every candidate validation score, chosen parameter, train-only scaler mean/variance and timing.
pre_fit_audit.json, eligible_origins.csv, causal_features.csv.gz: causal inputs, source clocks, reserve endpoints and 20 features.
predictions.csv.gz: 83,980 per-method held-out predictions at identical origins.
per_case_metrics.csv and table_4_pooled_metrics.csv: numerical tables without rounding small errors to zero.
verification.json: independent stdlib readback, shared origin sets, groups, hashes and metric recomputation.
experiment_a_predictions and experiment_a_skill: PNG/SVG/PDF figures, visually inspected at 6.5-inch width.

Reproduction:
& 'C:/Users/athif/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'C:/Users/athif/Documents/ChatGPT/BEV/APCOM_Draft_Experiments_2026-10-27/experiment_a/forecasting.py'
& 'C:/Users/athif/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s APCOM_Draft_Experiments_2026-10-27/experiment_a -p test_forecasting.py -v
& 'C:/Users/athif/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' APCOM_Draft_Experiments_2026-10-27/experiment_a/verify_outputs.py

Source archive files and the Google Doc were not changed. Nine unit tests pass; independent readback matches pooled and case errors within 1.39e-17 C, and a complete repeated fit produced byte-identical metric CSV files.
