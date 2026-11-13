# Cycle-based baseline: executed comparison

13 November 2026 (America/Toronto). AI-assisted implementation and automated checks; not independent human validation.

The two executions produced identical numerical outputs. Existing boosting estimators and all four original methods were reused without refitting or changing their predictions. This post-hoc comparison adds one seasonal-naive baseline.

## Method

For each held-out configuration, estimate current repetition periods on the eight training configurations only, using Pearson lag correlation over 600–2400 seconds with at least half-record overlap. Round the median period to the nearest second (half up). The fitted fold periods are 1,472–1,482 seconds (24.53–24.70 minutes). Predict the last observed temperature at the same phase of that period; use persistence if the required earlier sample does not exist. No future test readings or event schedule enter predictions.

This comparator retains up to a cycle of past temperatures. The existing methods retain 60 seconds. It is a longer-history comparison, not an equal-history ablation. Lag bounds were chosen after earlier results and traces had been seen; this is not preregistered.

## Full matched-origin comparison

Root mean squared error / mean absolute error, in millidegrees Celsius (m°C). Lower is better.

| Horizon | Cycle baseline | Gradient boosting | Cycle available / all origins |
|---|---|---|---|
| 1 min | 12.547 / 6.406 | 1.525 / 0.732 | 3160 / 4388 |
| 2 min | 13.230 / 7.267 | 3.264 / 1.706 | 3160 / 4334 |
| 5 min | 16.555 / 9.728 | 6.717 / 4.084 | 3160 / 4172 |
| 10 min | 22.737 / 13.354 | 7.121 / 5.438 | 3160 / 3902 |
| 30 min | 23.116 / 16.675 | 6.384 / 4.247 | 1833 / 2822 |

Boosting has lower pooled RMSE and MAE than this cycle baseline at every horizon. With all four baselines included, boosting wins on both scores at 5, 10 and 30 minutes. The thermal baseline retains lower MAE at 1 and 2 minutes. The original headline conclusion therefore survives this particular additional comparison.

## Excluding fallback forecasts

All five methods are rescored on exactly the same cycle-available origins. This removes startup persistence from the cycle method, not from the other methods independently.

| Horizon | Cycle baseline | Gradient boosting |
|---|---|---|
| 1 min | 14.501 / 7.688 | 1.489 / 0.725 |
| 2 min | 14.501 / 7.688 | 3.220 / 1.712 |
| 5 min | 14.501 / 7.688 | 6.826 / 4.164 |
| 10 min | 14.501 / 7.688 | 6.808 / 5.065 |
| 30 min | 21.412 / 13.254 | 6.424 / 4.329 |

The same win pattern holds after excluding fallback origins. The cycle baseline has identical 1–10 minute errors on this subset because these horizons map to the same set of target/source time pairs, despite differing forecast origins. The 30-minute forecasts wrap over two periods and use a different target range.

## Limits and interpretation

Individual training-record periods range from 1,438 to 1,572 seconds (23.97–26.20 minutes); none hit a search boundary. A single median period can mismatch the held-out configuration and accumulate phase error. It also repeats the startup transient when that is the only observed corresponding phase. Its failure does not rule out adaptive or configuration-specific cycle models, and does not establish what boosting has learned. These remain noiseless surrogate temperatures, not measured pack temperatures or thermal-runaway detection.

## Artifacts and verification

The local `results/cycle-baseline-2026-11-13/run-1` and `run-2` directories contain predictions, pooled and per-case metrics, fitted periods, exact source times, settings and SHA-256 manifests. `verification.json` records the independent source-index and score checks. All 19,618 cycle predictions used an already revealed temperature. Original metric values agree within 1e-12 °C. No scientific figure was added or changed.

Repository checks: 25 A_live tests, 12 package tests with a canonical temporary directory, 9 ML audit tests and 6 TUM conversion tests pass. All 103 archived input hashes and all 17 TUM measurement tables verify. The historical physics/ML/plot audit completed successfully; it is separate from this new baseline analysis. The first package-test invocation needed PYTHONPATH=src; the default macOS temporary-path alias then triggered an existing containment-check failure. Re-running with TMPDIR=/private/tmp passed without changing existing code.

Reproduce the numerical outputs using the cycle-baseline commands in [README.md](README.md). Full run directories remain generated, git-ignored artifacts; this checked-in report publishes the comparison summary.
