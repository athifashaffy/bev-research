# Thermal Modelling and Temperature Forecasting for Underground Mining BEVs

Code and data behind the APCOM 2027 paper *Thermal Modelling and Temperature
Forecasting for Underground Mining Battery Electric Vehicles* (Shaffy, Bakhtavar,
Ben-Awuah).

The study takes nine HAULSIM haulage simulations, converts each activity's battery
energy into the current of a 2.5 Ah reference cell, computes that cell's surface
temperature with a fitted heat balance, and compares temperature forecasts 1–30
minutes ahead from histogram gradient boosting against persistence, linear-trend
and thermal baselines.

> The temperatures are modelled for a laboratory reference cell, not measured on a
> truck battery. See [Limits](#limits).

---

## Repository layout

| Folder | What is in it |
| --- | --- |
| `reproducibility/` | **The main package for the paper.** Everything below is inside it unless noted. |
| `reproducibility/data/workspace/` | Original study inputs and code: HAULSIM results, the a/b fit, thermal traces (read-only) |
| `reproducibility/experiments/` | Experiments; **`A_live/` produced the paper's Table 2 and Figure 2**. See its [README](reproducibility/experiments/README.md) for the others |
| `reproducibility/results/run-2026-11-13/live/` | The saved run behind Table 2 (predictions, models, metrics, proof record) |
| `reproducibility/src/bev_research/` | Reusable energy/reserve and thermal functions; `bev-reproduce` command |
| `reproducibility/tools/` | Audits, plotting, equation walkthrough, proof recorder, claim checker; claim lists in `tools/claims/` |
| `reproducibility/audits/`, `figures/` | Saved audit tables and figures |
| `src/`, `experiments/`, `code/`, `tests/` (top level) | A separate NumPy reconstruction of the study (no scikit-learn). Kept for comparison; not the source of the paper's numbers |
| `data/` (top level) | Raw A123 cell records and derived tables used by the top-level reconstruction |
| `docs/`, `archive/`, `walkthroughs/` | Guides and provenance, the 16 Oct 2026 transfer archive, and a recorded walkthrough |

---

## Quick start

From a terminal, one time:

```bash
python3 -m venv ~/bev-env
~/bev-env/bin/pip install -r ~/Documents/bev-research/reproducibility/experiments/A/requirements.txt
cd ~/Documents/bev-research/reproducibility
```

Pinned versions: numpy 2.3.5, scipy 1.16.3, scikit-learn 1.7.2, matplotlib 3.10.7,
threadpoolctl 3.6.0, joblib 1.5.2. None of the commands below modify project files.

---

## 1. The raw HAULSIM data

```bash
sqlite3 -readonly data/workspace/New_Afton_Experiments_2026-10-20/results/C100_RR03/native_run.hsmdb \
  "select State, SimulationTime, ElapsedTime, ElectricityFromBatteryConsumed from HS_EquipmentState where EquipmentClass='Truck' limit 8;"
```

Each line is one truck activity from HAULSIM's own result file for the 354 kWh,
3% rolling-resistance configuration: activity, start time (min), duration (min) and
battery energy used (kWh). There are nine such files, one per configuration
(283.2 / 354 / 424.8 kWh × 2 / 3 / 4% rolling resistance).

---

## 2. Equations (1)–(5) and Table 1, step by step

```bash
~/bev-env/bin/python tools/walkthrough_equations.py
~/bev-env/bin/python tools/walkthrough_equations.py --case C080_RR04   # any configuration
```

The script uses only the Python standard library and opens the HAULSIM files read-only.

### Reading the output

**Activity table: Equations (1) and (2).** One row per activity.

| Column | Meaning |
| --- | --- |
| start min / dur min | start time and duration of the activity |
| state | TravelEmpty (down-ramp, empty), SpottingAtLoader / SpottingAtDump (positioning), Loading, TravelLoaded (up-ramp, loaded), Unloading, Idle |
| E kWh | battery energy used in the activity |
| P kW | Equation (1): P = 60 E / Δt |
| I_eq A | Equation (2): I_eq = 2.5 Ah × P / E_nom |
| used kWh | cumulative energy |

The loaded climb is the highest-demand activity (312.44 kW → 2.207 A for 354 kWh).
Stationary activities draw the 20 kW auxiliary load. The final row is a climb cut off
by the 120-minute simulation end, after the reserve, and is not used.

**Energy reserve.** Budget = (0.80 − 0.20) × E_nom (212.40 kWh for 354 kWh). The time
the cumulative energy reaches it is the reserve time (85.60 min for C100_RR03);
deliveries count only if unloading finishes before then (3 × 45 t = 135 t). The
earliest reserve time of all nine configurations, 68.04 min, is the common
comparison period for mean power and peak temperature rise. Cycle energy is measured
between successive completed unloads.

**Equations (3)–(5).** a and b are the fitted coefficients. 1/b = 376.6 s is the time
constant (63.2% of a change completed). The steady rise a·I²/b is the maximum
temperature rise above air at a constant current. The script also steps Equation (4)
numerically in 0.01 s steps and compares it with Equation (5) as a check of the
solution, then reports the peak rise and the effect of doubling the heating term (g = 2).

**Table 1 check.** For each configuration, "calc" is recomputed from the HAULSIM data
and "doc" is the value in the paper. The paper values are stored in the script
(`PAPER_TABLE1`), typed from the manuscript on 12 Nov 2026; update them if Table 1 changes.

---

## 3. Table 2 source

```bash
cat results/run-2026-11-13/live/pooled_metrics.csv
```

Columns: horizon in seconds (60 = 1 min … 1800 = 30 min), method, number of scored
forecasts, RMSE (°C), MAE (°C), maximum absolute error (°C). Table 2 reports RMSE and
MAE × 1000 (m°C). `physics_hold` is the thermal baseline; `hist_gradient_boosting` is HGB.

---

## 4. One forecast from a saved model

```bash
~/bev-env/bin/python -c "
import joblib, gzip, csv
run = 'results/run-2026-11-13/live/'
row = next(r for r in csv.DictReader(gzip.open(run + 'features.csv.gz', 'rt')) if r['case'] == 'C100_RR03' and r['horizon_s'] == '1800' and r['origin_s'] == '2400')
x = [[float(v) for k, v in row.items() if k not in ('case', 'horizon_s', 'origin_s', 'max_input_time_s')]]
model = joblib.load(run + 'models/C100_RR03_h1800.joblib')
print('Now (minute 40):', round(x[0][0], 6), 'C   HGB forecast for minute 70:', round(x[0][0] + model.predict(x)[0], 6), 'C')
"
```

Loads the HGB model trained without configuration C100_RR03, gives it the 20 inputs
from the previous minute at 2,400 s, and forecasts 30 minutes ahead.
Expected output: 25.042392 °C now, forecast 25.064848 °C (generated value 25.064647 °C).

---

## 5. Rerun the forecasting experiment (about 16 s)

The forecasting code is in `reproducibility/experiments/A_live/`:

```bash
cd ~/Documents/bev-research
~/bev-env/bin/python reproducibility/experiments/A_live/train.py --output /tmp/apcom-rerun
cat /tmp/apcom-rerun/pooled_metrics.csv
```

It regenerates the 1 Hz simulated sensor record from the HAULSIM activity data, builds
the 20 inputs every 10 s, trains 45 HGB models (9 held-out configurations × 5
horizons) and scores all four methods. The output matches Table 2. Use a new output
folder each time; the script will not overwrite an existing one.

---

## Methods summary

Paths below are under `reproducibility/experiments/`.

| Step | Equation / method | Where in the code |
| --- | --- | --- |
| Activity power | (1) P = 60 E / Δt | `A_live/telemetry.py` → `generate()` |
| Reference-cell current | (2) I_eq = 2.5 Ah × P / E_nom | `A_live/telemetry.py` → `generate()` |
| Heat balance | (3) C dT/dt = I²R − K(T − Tₐ); (4) dT/dt = g a I² − b(T − Tₐ) | coefficients fitted in `reproducibility/data/workspace/APCOM_Coupled_Thermal_2026-10-16/code/fit_model.py` |
| Exact step solution | (5) T(t+Δt) = Tₐ + (T − Tₐ)e^(−bΔt) + (g a I²/b)(1 − e^(−bΔt)) | `A_causal/inputs.py` → `advance()` |
| 20% reserve | budget = 0.6 × E_nom | `A_live/telemetry.py` → `reserve_cutoff()` |
| Inputs | last 61 one-second samples → 20 features | `A_live/telemetry.py` → `history_features()` |
| Baselines | persistence, linear trend, thermal (Eq. 5, current held) | `A_live/telemetry.py` → `predict_history()`; `A/train.py` → `physics_forecast()` |
| HGB | HistGradientBoostingRegressor, lr 0.08, depth 3, ≤7 leaves, ≥20 per leaf, 40 or 80 iterations | `A/train.py` → `estimator()` |
| Evaluation | hold out each configuration; 4 inner splits of the other 8 | `A/train.py` → `nested_group_plan()` |

Fitted coefficients: a = 4.344635339 × 10⁻⁵ K A⁻² s⁻¹, b = 2.655462789 × 10⁻³ s⁻¹
(`frozen_cell_model.json`).

## Data

| Data | Source | Location |
| --- | --- | --- |
| HAULSIM results, 9 configurations | HAULSIM 3.8 (RPMGlobal), run by the author | `reproducibility/data/workspace/New_Afton_Experiments_2026-10-20/` |
| A123 LiFePO₄ cell records (pulse test, two drive cycles) | de Souza (2021), Mendeley Data, doi:10.17632/p8kf893yv3.1 | `data/raw/a123/`, `data/raw/a123_csv/` |
| Saved forecasting run behind Table 2 | generated by `A_live/train.py`, 13 Nov 2026 | `reproducibility/results/run-2026-11-13/live/` |

## Limits

- Temperatures are the modelled surface temperature of a 2.5 Ah A123 reference cell,
  not Z50 pack temperatures. The simulated rise is 0.043–0.093 °C; the model's error on
  separate laboratory records is 0.109 and 0.117 °C.
- Equation (2) assumes nominal pack voltage and equal current sharing.
- One route, one set of coefficients, ideal sensor readings (no noise or delay).
- Battery capacity, mass and power vary together across configurations.

## Provenance

Code, checks and this README were prepared with AI assistance (Codex and Claude);
file headers state where code is AI-assisted or AI-written, and
[`docs/PROVENANCE.md`](docs/PROVENANCE.md) records the project-wide disclosure. The
HAULSIM simulations and the published laboratory dataset are the study's inputs.
