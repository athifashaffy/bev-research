# Experiments

Three entry points, each self-contained and runnable from the repository root.
All of them read from `data/derived`, which is committed, so none requires the
licence-restricted raw datasets.

```bash
python experiments/thermal_demand.py              # Table 2
python experiments/experiment_a_forecasting.py    # Tables 3 and 4
python experiments/experiment_b_warning_rules.py  # Table 5
```

Results are written under `results/`, which is not committed, so a run never
overwrites the archived reference values in `data/derived`.

---

## `thermal_demand.py` — Table 2

**Asks:** across three pack capacities and three rolling resistances, how much
power and energy does the duty cycle demand, how long does the truck run before
the energy reserve is reached, and how far does the modelled cell surface rise?

**Method:** each configuration is run to its own reserve endpoint, defined as
60 % of nominal capacity and representing an 80 % to 20 % state-of-charge
excursion. The raw simulation may continue past that point; external analysis
stops there.

**Finds:** mean power 140.9 to 177.4 kW, energy 60.6 to 73.7 kWh per cycle,
reserve windows 68.0 to 108.1 minutes, peak rise 0.043 to 0.093 °C.

**The honest reading:** the margin to the declared 60 °C screen is 34.907 to
34.957 °C, a spread of 0.05 °C across all nine configurations. There is no
margin comparison to be drawn between them. The useful result is the negative
one: under these parameters normal haulage duty cycle is not a thermal risk
pathway. Capacity, vehicle mass and available power vary together in the
archived cases, so these compare whole vehicle configurations and do not
isolate a pure capacity effect.

Runtime: a few seconds.

---

## `experiment_a_forecasting.py` — Tables 3 and 4

**Asks:** given 60 s of causal history, how well can the temperature change over
the next 1 to 10 minutes be predicted on a configuration the model has never
seen?

**Method:** leave-one-configuration-out over the nine configurations. Within
each training set, the last two configurations are held out again to choose the
ridge penalty, so no test fold influences any fitting decision. Four horizons,
five methods: persistence, 60 s linear trend, held-input physics, ridge, and
gradient boosted trees.

**Finds:** gradient boosting leads on both RMSE and MAE at 2, 5 and 10 minutes.
At 1 minute it leads on RMSE only; the held-input physics baseline wins on MAE
(4.317 × 10⁻⁴ against 6.706 × 10⁻⁴ °C). At 10 minutes both the trend and the
physics baselines become worse than persistence.

**The honest reading, and this matters more than the ranking:** these traces are
the deterministic output of the frozen thermal model driven by an assumed
equivalent current. A model that does well here has rediscovered that equation.
Every error in the resulting table is smaller than the measured-cell fit's own
0.109 to 0.117 °C residual, so the differences between methods are not
physically resolvable. On the measured A123 cell the ranking reverses and
persistence wins from 2 to 10 minutes. That reversal is the informative result.

`--quick` runs two horizons instead of four for a smoke test.

Runtime: a few minutes for the full grid, since the tree ensemble is fitted in
numpy rather than imported.

---

## `experiment_b_warning_rules.py` — Table 5

**Asks:** do seven rules fixed in advance stay quiet on modelled normal haulage,
and do they respond on published LFP abuse records?

**Method:** the same seven rules, unchanged, applied to two very different
populations. Four fixed-temperature rules at 45, 50, 55 and 60 °C, and three
causal 60 s rate-of-rise rules at 1, 2 and 5 °C/min, each requiring 5 s of
elapsed record. The rules were specified before any laboratory record was
screened and were never re-tuned, which is the only reason the laboratory result
carries any weight.

**Finds:** no rule responds on any of the 729 modelled normal trajectories. The
same rules respond on 26 of 27 Sheffield records, all 7 test records and all
6 TUM channels. First response is 13 to 45 s on Sheffield and 10 to 1943 s on
TUM.

**The honest reading:** a rule firing on an abuse record is a *response to
recorded heating*, not a verified thermal-runaway detection, and the time it
fires is not a lead time. Neither archive contains an independent,
temperature-free onset reference with bounded sensor-clock uncertainty, so lead
time, missed detections and field false-alarm rate cannot be computed and are
reported as `UNAVAILABLE`. The script asserts this rather than trusting it: if
any of those three columns ever carries a number, the run fails.

The quiet result on 729 trajectories is likewise not a field false-alarm rate.
Its denominator is modelled scenarios, not fleet hours, and the nine nominal
settings are a subset of the 729 rather than nine additional experiments.

The laboratory records themselves are licence restricted and not committed, so
this reads the derived response summary. To re-screen from source, fetch the
datasets per `data/README.md` into `data/raw` and verify them against the
checksum manifest first.

Runtime: under a minute.

---

## Checking a run

`python code/verify.py` recomputes the headline numbers from the source CSVs
rather than reading the reported tables, and exits non-zero on any mismatch.
`python -m pytest tests/` runs 37 unit tests on the model, the rules, the
baselines, the learned models and the feature construction.
