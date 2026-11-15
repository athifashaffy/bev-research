# Temperature forecasting metrics

AI-assisted arithmetic report from saved predictions; no models refitted.
R2 uses the scored temperature mean, not temperature change. Constant targets have undefined R2.
All supplied methods remain in the CSV outputs. Case R2 is not averaged to obtain pooled R2.

| Horizon (min) | Metric | Persistence | Linear trend | Thermal baseline | HGB |
|---|---|---:|---:|---:|---:|
| 1 | RMSE (mC) | 4.939 | 2.656 | 1.788 | **1.525** |
| 1 | MAE (mC) | 4.011 | 1.335 | **0.432** | 0.732 |
| 1 | R2 | 0.949 | 0.985 | 0.993 | **0.995** |
| 2 | RMSE (mC) | 9.562 | 6.331 | 4.806 | **3.264** |
| 2 | MAE (mC) | 7.872 | 3.836 | **1.639** | 1.706 |
| 2 | R2 | 0.807 | 0.916 | 0.951 | **0.978** |
| 5 | RMSE (mC) | 21.506 | 21.045 | 16.308 | **6.717** |
| 5 | MAE (mC) | 18.261 | 16.862 | 8.948 | **4.084** |
| 5 | R2 | -0.017 | 0.026 | 0.415 | **0.901** |
| 10 | RMSE (mC) | 35.073 | 53.934 | 36.309 | **7.121** |
| 10 | MAE (mC) | 30.300 | 50.635 | 29.022 | **5.438** |
| 10 | R2 | -1.984 | -6.056 | -2.198 | **0.877** |
| 30 | RMSE (mC) | 22.904 | 130.781 | 23.896 | **6.384** |
| 30 | MAE (mC) | 20.314 | 107.596 | 21.056 | **4.247** |
| 30 | R2 | -0.374 | -43.806 | -0.496 | **0.893** |

## HGB per-configuration R2

| Horizon (min) | Lowest R2 | Configuration | Highest R2 | Configuration |
|---|---:|---|---:|---|
| 1 | 0.986285 | C120_RR02 | 0.996315 | C080_RR03 |
| 2 | 0.868476 | C120_RR02 | 0.986806 | C080_RR03 |
| 5 | -0.236474 | C120_RR02 | 0.975198 | C100_RR03 |
| 10 | 0.154227 | C120_RR02 | 0.953500 | C100_RR03 |
| 30 | -0.015675 | C120_RR02 | 0.975739 | C080_RR03 |

HGB cases beating each of the three original baselines on both RMSE and MAE:
- 1 min: 0; none
- 2 min: 7; C080_RR02, C080_RR03, C080_RR04, C100_RR02, C100_RR03, C100_RR04, C120_RR03
- 5 min: 8; C080_RR02, C080_RR03, C080_RR04, C100_RR02, C100_RR03, C100_RR04, C120_RR03, C120_RR04
- 10 min: 9; C080_RR02, C080_RR03, C080_RR04, C100_RR02, C100_RR03, C100_RR04, C120_RR02, C120_RR03, C120_RR04
- 30 min: 9; C080_RR02, C080_RR03, C080_RR04, C100_RR02, C100_RR03, C100_RR04, C120_RR02, C120_RR03, C120_RR04
