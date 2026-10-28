# Provenance

This file records who and what produced each part of this work. It exists so
that no reader has to guess, and so that the numerical claims can be separated
from the question of authorship.

Last updated: 28 October 2026.

## Summary

The **measurements and simulation outputs are genuine and reproducible**. The
**analysis code, figures and written explanations in this repository were
produced with AI assistance**, and the conference paper draft that this work
supports was substantially AI-generated. Those are different statements and
both are stated here deliberately.

## Who produced what

| Component | Produced by | Status |
|---|---|---|
| HAULSIM road and haulage simulations | Athif Shaffy, HAULSIM 3.8 build 585 under RPMGlobal licence | Native runs, archived with SHA-256 |
| Thermal model fitting and trace generation | OpenAI Codex, from the archived HAULSIM outputs | Executed code, outputs reproducible |
| Forecasting benchmark (Tables 3 and 4) | OpenAI Codex | Executed code, 792 model fits |
| Warning-rule screen (Table 5) | OpenAI Codex | Executed code |
| Conference paper draft text, structure, reference list | OpenAI Codex | AI-generated |
| Paper figures (in the manuscript) | OpenAI Codex | AI-generated |
| Figures in this repository (`figures/`) | Claude (Anthropic), via `code/make_figures.py` | AI-generated, reproducible from `data/derived/` |
| `code/make_figures.py`, `code/verify.py` | Claude (Anthropic) | AI-generated |
| Documentation in `docs/` | Claude (Anthropic) | AI-generated |
| Independent verification of headline numbers | Claude (Anthropic) | See below |

## What has been independently verified

An independent recomputation was performed on 27 and 28 October 2026 by Claude,
working from the source CSVs rather than from the reported tables. It is an
independent implementation, not a re-run of the original scripts.

| Quantity | Result |
|---|---|
| Worked thermal example, case C100_RR03 | Closed form reproduces the saved trace to 7.1e-14 degrees C |
| Closed form vs numerical integration | Agrees within forward-Euler truncation error |
| Table 2, nine-case demand | Matches to 4 to 5 significant figures |
| Table 4 baselines and ridge | Agrees within 1 to 2 percent; the residual gap is a weighting convention (per-case mean versus pooled origins) |
| Table 4 gradient boosting | Differs 5 to 19 percent, because the independent implementation is hand-written rather than scikit-learn |
| Operator energy comparison | 66.79 kWh is 18.87 percent of 354 kWh nominal, against an operator-reported 19 percent |

`code/verify.py` re-runs 22 of these checks on every invocation and exits
non-zero on any failure.

## One correction this verification produced

An earlier independent run reported that gradient boosting beat every baseline
at all four horizons. That was true on RMSE only. Checking MAE as well shows
the held-input physics baseline wins at the one-minute horizon
(4.317e-04 against 6.706e-04). The two-metric result is the correct one, and
it is what the paper states.

## Known limitations of the AI-generated analysis

These are properties of the study, not of the tooling, but they are the points
most likely to be challenged.

1. **Equation (2), the equivalent-current relation, is an assumption.** The pack
   voltage and series/parallel topology of the Sandvik Z50 are not identified,
   so `I = P / V` is not claimed. The study instead matches power per unit of
   configured energy onto a 2.5 Ah A123-equivalent cell. Every predicted
   temperature follows from this choice and it needs explicit justification and
   a sensitivity analysis.
2. **Only two ratios are identifiable** from the thermal fit, `a = R_eff/C_eff`
   and `b = K_eff/C_eff`. Scaling R, C and K by a common factor leaves the model
   unchanged, so individual physical parameters are not recovered.
3. **All modelled temperature rises (0.043 to 0.093 degrees C) fall below the
   measured-cell residual error (0.109 to 0.117 degrees C).** The rankings
   between configurations are therefore not physically resolvable.
4. **Table 4 measures agreement with a synthetic generator.** The traces are
   deterministic output of a known equation, so learned models recover that
   equation. On the measured cell in Table 3, persistence wins instead.
5. **No verified thermal-runaway onset reference exists** in either laboratory
   archive, so lead time, missed detections and field false-alarm rate are
   reported as `UNAVAILABLE` rather than estimated.

## Note on the experiment package readme

The `APCOM_Draft_Experiments_2026-10-27` package contains a section headed
"CLAUDE REVIEW" stating that no Claude review was received. That is accurate
about an automated command-line attempt that returned HTTP 401. It is not
accurate about the review itself, which was carried out interactively and is
recorded above.
