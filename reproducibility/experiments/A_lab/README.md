# Experiment A_lab: live-sensor forecasting on laboratory cell records

AI-written (Claude, 12 November 2026) at the author's request. This is a new
experiment. It does not reproduce or replace Experiment A or the
completed-report run, and nothing here is manuscript text.

## Scope

Three laboratory records of one A123 26650 cell (de Souza 2021,
doi:10.17632/p8kf893yv3.1), read from `data/raw/a123_csv/` at the repository
root. At each forecast time every method sees the measured current, surface
temperature and air temperature of the preceding minute. The answer key is
the measured surface temperature 1, 2, 5, 10 or 30 minutes later.

It is not truck-pack data and gives no evidence about thermal-runaway warning.

## Method

- Latest reading at or before each whole second; no interpolation or filtering.
- Seconds inside a source gap longer than 1.5 s carry no reading. A forecast
  time is used only if its 61 history seconds and its target second have readings.
- Baselines: persistence, linear trend, and the fitted heat equation holding
  either the latest current or the last minute's mean squared current.
- Learned models: the ridge and histogram gradient boosting estimators and
  grids of `experiments/A/train.py`.
- Leave one record out. The heat-equation coefficients were fitted on the
  pulse record, so the physics baselines are out-of-sample only on the two
  drive-cycle records; both poolings are reported.

## Run

From `reproducibility/`, with the pinned NumPy, SciPy and scikit-learn:

```text
python -m unittest discover -s experiments/A_lab/tests -v
python tools/run_with_proof.py --output results/NEW --script experiments/A_lab/train.py --script experiments/A/train.py --input ../data/raw/a123_csv/A002_PeriodicPulseData.csv --input ../data/raw/a123_csv/A002_UDDS_P25.csv --input ../data/raw/a123_csv/A002_UDDS_P35.csv -- python experiments/A_lab/train.py --output results/NEW
python tools/run_with_proof.py --verify results/NEW/PROOF.json
```

Run of 12 November 2026 (AI-executed, same machine, two processes with
identical outputs): `results/lab-forecast-2026-11-12/run-1` and `run-2`.
`pooled_metrics.csv` SHA-256
`4c755cd6112e582ae2be3a457cf70bbb671c824683936360580fcbc7eb67cb07`.
Numbers quoted in `LAB_FORECAST_NOTES.txt` are registered in
`tools/claims/claims_lab_forecast.json`.

## Limits

Three records of one cell; a held-out record is not an independent cell. The
loads are laboratory pulses and a car drive cycle, not mining duty. Source
units are not stored in the files; amperes, degrees Celsius and seconds are
assumed. Cross-platform reproduction and independent human verification have
not been done.
