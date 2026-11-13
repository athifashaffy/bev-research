# Executed verification record

Date: 12 November 2026, America/Toronto. AI-authored implementation, tests and
automated checks. This is not a human scientific review or field validation.

## Final numerical result

The final two runs used Python 3.14.6 and every direct dependency pinned in
`../A/requirements.txt`, including joblib 1.5.2. Each executed 405 fits and saved
45 newly fitted held-out models. Predictions also exactly match the preliminary
joblib-1.6.0 run, but the final pair is the reproduction reference.

`results/live-telemetry-2026-11-12/final-report/verification.json` records:

- 44,906 generated sensor rows; 19,618 forecast origins across five horizons;
  78,472 prediction rows across four methods.
- Exact two-run agreement on decompressed telemetry, features and predictions,
  metric CSVs, fold assignments, cases, protocol and replay checks.
- Exact model selection and summary agreement after removing elapsed time.
- All 800 entries in pooled and per-case metric tables independently recalculated
  from saved predictions: counts exact, errors within 1e-12 °C.
- Each run reloads all 45 models and compares every batch prediction exactly;
  135 selected rolling-prefix predictions per run also match.
- Separate replay CLI check: 11 sensor rows at seconds 1200–1210 and 40 forecast
  values at seconds 1200 and 1210 exactly match the scored outputs.
- Generated temperatures span 25.00000000 to 25.09317769 °C.

| Horizon | Boosting RMSE (°C) | Boosting MAE (°C) | Pooled strict win | Whole-case strict wins |
|---:|---:|---:|:---:|---:|
| 1 min | 0.001525 | 0.000732 | No | 0/9 |
| 2 min | 0.003264 | 0.001706 | No | 7/9 |
| 5 min | 0.006717 | 0.004084 | Yes | 8/9 |
| 10 min | 0.007121 | 0.005438 | Yes | 9/9 |
| 30 min | 0.006384 | 0.004247 | Yes | 9/9 |

Strict win means beating all three baselines on both RMSE and MAE. The heat-equation
baseline has lower pooled MAE at 1 and 2 minutes. Pooled and case-wise outcomes
need not agree because magnitudes and eligible sample counts differ. These are
descriptive results, not significance tests.

## Test commands and outcomes

Use the environment documented in README. Commands below were executed with its
Python interpreter. All exited successfully. `-B` suppressed bytecode writes.
The temporary directory was canonicalized as `/private/tmp` for the reproducibility
unit tests, avoiding the pre-existing macOS `/var` versus `/private/var` alias issue.

From repository root:

| Command | Outcome |
|---|---|
| `PYTHONPATH=src python -B -m pytest` | 46 tests and 27 subtests passed |
| `python -B -m unittest discover -s reproducibility/experiments/A_live/tests -v` | 18 tests passed after review fixes |

From `reproducibility/`:

| Command | Outcome |
|---|---|
| `TMPDIR=/private/tmp PYTHONPATH=src python -B -m unittest discover -s tests -v` | 12 tests passed |
| `python -B -m unittest discover -s tools -p test_audit_ml.py -v` | 9 tests passed |
| `python -B -m unittest discover -s data/tum -p test_prepare_tum_csv.py -v` | 6 tests passed |
| `python -B data/tum/verify_tum_csv.py --dataset data/tum/dataset` | All source hashes and previews matched; 747,524 rows preserved |
| `python -B -m unittest discover -s experiments/A/tests -p test_models.py -v` | 9 tests passed |
| `python -B -m unittest discover -s experiments/A_causal/tests -v` | 12 tests passed |
| `PYTHONPATH=src python -B -m bev_research.cli all --output ../results/live-telemetry-2026-11-12/checks/reconstruction` | Hashes, physics, ML reconstruction and plots completed; 103 input files checked |

The final command invokes the same `main` as `bev-reproduce all`, explicitly using
this checkout's `src` rather than an installed CLI from another checkout. It is
an archive reconstruction audit, not another model refit and not full Experiment B
execution. Experiment B remains outside this task and is not declared portable.

Run the two trainer commands, report comparison and replay command in README with
the recorded final paths to reproduce the remaining checks. All logs and a hashed
`VERIFICATION_RECORD.json` are in the local `results/live-telemetry-2026-11-12/checks/`
directory. `final-report/claims.json` contains the metric-by-metric cross-check.
The saved central-case plot was visually inspected for labels, units and alignment;
30-minute forecasts are drawn at target times, starting after minute 31.

## Review and scope

One fresh-context AI reviewer inspected the complete branch from `2a9a3fd` through
`4a87249`, the saved artifacts and relevant helper functions. The reviewer found
no critical issue and two important reporting defects, both fixed:

1. Future audits previously inherited the original execution date. Reports now
   capture one audit instant, convert it to Toronto time and use it consistently
   in the human report, verification record and UTC proof. A test covers the
   previous-local-day boundary on a future date.
2. Outcome-specific prose previously assumed the first run's winners. It now
   derives the stated wins and RMSE/MAE comparisons from the audited metrics.
   A test covers different winners and no winning horizons.

The new tests failed before the fixes and the full A_live suite then passed 18/18.
The finalized report was regenerated into `final-report`, preserving the earlier
`final-comparison` artifact. Training code and predictions did not change; both
training manifests still verify. No additional minor findings were deferred.

The review's scope exclusions were accepted explicitly:

- Physical calibration adequacy, pack accuracy and runaway performance remain
  unvalidated. Treating this check as evidence for them would overstate the result.
- Noise, delay, changing ambient conditions and unseen routes remain deferred.
  Predictions under those conditions may differ substantially.
- The frozen boosting grid remains 40/80; all 45 selections reached 80. This limits
  conclusions about tuning and is documented without retuning to test outcomes.
- Prior A/A_causal/B code was reviewed only where helpers are used here, with
  regression checks; this does not establish unrelated implementation correctness.
- AI review does not constitute independent human scientific approval.

Automated
verification establishes internal reproducibility and the implemented information
boundary, not real-world accuracy, calibration adequacy or thermal-runaway detection.
At the implementation-review checkpoint, the manuscript, original experiment,
prior correction branch and lab experiment remained unchanged. Subsequent
authorized document edits are recorded below. Results are local artifacts and
have not been published.

## Whole-document consistency review

Date: 12 November 2026, America/Toronto. This AI-assisted automated audit compared
the current Google Doc with saved results and implementation. It is not independent
human scientific review. The document ID is
`1Lh_NBFdk2zKvXd8NM9vxwErwL84WUWYJjuPqL3EZbsc`.

- All 63 numeric values in Table 1 and all 40 error values plus five horizon
  labels in Table 2 matched their sources and displayed rounding.
- The report audit rechecked both saved forecasting runs, manifests and all 800
  metric entries. This was not another model refit or HAULSIM execution.
- A fresh physics reconstruction checked nine configurations and 729 sensitivity
  assignments; archived thermal agreement was within 7.11e-15 degrees Celsius.
- Both figure source PNGs regenerated byte-identically from code and saved data.
  Google Docs resizes Figure 1 on embedding, so embedded pixel identity is not
  asserted. Figure 2's exported pixels matched its source. The nine-page PDF
  export was inspected for equations, tables, captions and figure layout.
- Methods, abstract and conclusions consistently report pooled strict wins at
  five, ten and thirty minutes, and lower thermal-baseline MAE at one and two
  minutes. Forecast counts, 20 features, 405 fits and 45 saved models agree.
- Small document edits clarified the heating multiplier, the central sensitivity
  configuration, exact sensitivity endpoints versus integer-second forecast
  samples, held-out scoring labels, and forecasting executions versus native
  simulator runs. Numerical results did not change. Five equations and 23
  reference hyperlinks were preserved.

Local detailed evidence is in `results/document-audit-2026-11-12/`, including
`document_checks.json`, `forecast/`, `physics/` and `figures/`. Manuscript exports
were kept outside the repository.

This review establishes internal consistency only. It does not establish pack
calibration, sensor accuracy, unseen-route generalization, thermal-runaway warning
performance, or comprehensive reference correctness. Cycle-aware baselines remain
untested; whether they match or outperform boosting is unknown. A citable location
for the reproducibility materials remains a submission documentation gap.

### Author-requested structural editing pass

On 12 November 2026, the author requested a clearer argument, less audit-log prose
and a consolidated limitations discussion in the existing Google Doc. AI-assisted
editing shortened the introduction and methods, added interpretation of the
reserve-limited payload comparison, and described cycle learning as a hypothesis
rather than a demonstrated cause. A cycle-based baseline remains future work.

Main-text coefficients now display three significant figures; Appendix A retains
full precision, implementation settings, execution counts and repeatability checks.
The appendix also accurately records AI assistance. The manuscript's methods point
to that appendix. The local experiment README and results remain the detailed
execution record; the branch and result artifacts have not been newly published.

Native readback verified identical table contents, all five equations, both figure
object IDs and all 23 reference hyperlinks. No numerical experiment, model, input
or figure source was changed. The revised PDF was checked for layout. This was
editing of an existing author-supplied draft, not independent scientific approval.

### Terminology, calibration context and figure review

Completed 13 November 2026, America/Toronto, following author feedback received
on 12 November. The current document no longer contained Appendix A, so its
dangling reference was removed rather than restoring the deleted appendix.
The edit defined BEV and surrogate temperature, distinguished a configuration
from a simulation and an activity, standardized thermal-baseline naming, and
ordered Future Work as calibration, edge evaluation, then the author's approved
sensor-fusion proposal. An explicit AI-assistance note was restored.

The Equation (2) explanation now describes preservation of nominal C-rate and
its voltage/current-sharing assumptions. This is algebraic justification for
the assumed mapping, not measured confirmation of the Z50 cell arrangement or
thermal transfer. No personal author verification is claimed.

Frozen-coefficient evaluation of the original laboratory files reproduced
time-weighted RMSE of 0.10902085611793273 and 0.11714816495692625 degrees Celsius
on the two separate driving-cycle records from the same cell. Input SHA-256
values matched the earlier audit. These errors are discussed as laboratory
comparison scales exceeding the simulated rise, not truck uncertainty bounds
or independent-cell validation. The pulse-record fit residual also reproduced.

The code-generated figures now use surrogate-temperature and thermal-baseline
labels. Figure 2's two caption-like internal headings were removed; Figure 1
retains its three rolling-resistance panel labels. Figures were regenerated from
the unchanged final-run inputs, and every peak-rise value matched the prior
figure output exactly. Numerical tables and equations were unchanged. PDF
inspection caught an image-upload ordering mismatch; replacing each image in a
separate guarded request corrected it. Both final embedded figures were then
visually verified with their captions and labels.

Evidence is under `results/document-feedback-2026-11-12/`: plotting began before
midnight, and `thermal_residual_check.json` records the 13 November check date.
The figure proof records source/output hashes. These are AI-assisted automated
and visual checks, not author or independent human scientific approval.

### Final consistency and repetition pass

On 13 November 2026, the current Google Doc was reread after the forecasting
method explanations were added. All 63 Table 1 numbers matched the operational
audit and integer-second figure peaks at displayed precision; all 40 Table 2
error values matched the saved forecasting metrics after conversion to mC.
The five equations and all numerical table contents were preserved. The textual
steady-state expression was aligned with the defined equivalent-current symbol.

Redundant method explanations, the Table 2 baseline footnote, repeated row-value
prose and repeated target-time explanations were trimmed. The abstract and
conclusions retain necessary summaries. No duplicate nonempty paragraphs or
dangling appendix references were found after editing. All references 1–23 are
cited, all 23 reference hyperlinks remain, and the full reference 4 title was
checked against the publisher-hosted PDF at
https://papers.acg.uwa.edu.au/d/2435_M-01/M-01.pdf.

The eight-page export was visually reviewed for table/figure placement, captions
and section flow. Both figures remain generated from the numerical codebase.
The title page still has the affiliation without an author-name line; author
names were not inferred. This pass did not rerun HAULSIM, refit models, perform
a comprehensive source-publication audit, or establish pack-level validity.
During this final pass, a concurrent document edit removed the AI-assistance note.
That live edit was preserved; AI provenance remains recorded in this repository.

On 13 November, a further author-approved wording pass clarified Figure 2's
three plotted methods, the nominal 576 kW record versus the retained 480 kW
electrical curve and 391 kW wheel limit, sensitivity sampling times, unchanged
fitted coefficients, and the forecasting experiment's constant 25 C air input.
Table 1 peak rises were rounded to three decimal places for presentation only.
Native readback verified all nine rounded values; other Table 1 cells and all
Table 2 cells were unchanged. No calculations or figure data changed.

On 13 November, reference 17 was reconfirmed through the journal publisher's
article listing and matching ScienceDirect record: Muhammed Kahraman and
H. Sebnem Duzgun, Journal of Industrial Safety, available online 15 July 2026,
DOI 10.1016/j.jinse.2026.06.001. Publisher listing:
https://www.keaipublishing.com/en/journals/journal-of-industrial-safety/recent-articles/
The existing experiment still contains only persistence, linear trend,
constant-current thermal baseline and histogram gradient boosting. A cycle-based
baseline has not been executed. Equation (2)'s algebra supports the stated
nominal C-rate assumption; the cited datasheets support capacities, not empirical
validation of cell-to-pack transfer. Author-list order was requested rather than
inferred from email recipients.

On 13 November, the user supplied the author order and affiliation explicitly.
AI-assisted document editing inserted that exact author list and affiliation
under the manuscript title; native readback confirmed the text. This is an
authorship metadata edit, not additional scientific verification.

## Cycle baseline, 13 November 2026

At the user's request, added a separate seasonal-naive comparator with
training-only period estimation and past-only test temperature access.
Implementation decisions were recorded in `CYCLE_BASELINE_PLAN.md` before runs;
the analysis is post-hoc because earlier results and traces were already seen.
Seven new tests initially failed because the implementation was absent, then
passed. The complete A_live suite passes (25 tests).

Executed `cycle_baseline.py` against final-run-1 and final-run-2 into new
`results/cycle-baseline-2026-11-13/run-1` and `run-2` directories. Seven output
files match exactly (gzip content decompressed); original proofs verify before
and after, with no refitting or changed source data. An independent modulo
calculation verifies all 19,618 seasonal source indices against stored telemetry,
and math.fsum recalculates pooled errors from 98,090 five-method prediction rows.
The report and verification JSON are in the parent results folder.

All-origin seasonal RMSE/MAE in m°C by 1/2/5/10/30-minute horizon:
12.547/6.406, 13.230/7.267, 16.555/9.728, 22.737/13.354, 23.116/16.675.
Boosting remains lower on both scores at all five horizons against this baseline,
and beats all four baselines on both scores at 5/10/30 minutes. This pattern also
holds on identical cycle-available subsets, excluding fallback origins.
Do not generalize this outcome to adaptive cycle models or measured pack data.

Required broader verification: `python -m bev_research.cli all` with PYTHONPATH=src
completed (103/103 archived input hashes, physics, saved-ML and plots audits).
This checks historical artifacts separately from the new cycle experiment.
ML audit tests: 9 passed. TUM conversion tests: 6 passed; TUM verification passed
for 17 measurement tables, 21 CSV parts and 747,524 rows. Package tests initially
failed import because this temporary environment lacked the editable package;
PYTHONPATH=src resolved imports. One existing test then exposed a macOS temporary
directory alias issue in the containment check. Re-running all 12 package tests
with TMPDIR=/private/tmp passed. No unrelated code was changed to conceal it.

Google Doc language edits removed the unused thermal-response definition and
added energy use and completed payload before reserve to the existing introduction
objective. Native readback confirmed both edits. New cycle results are documented
separately; the manuscript's original four-method table remains unchanged.
Code, tests, documentation and verification were AI-assisted; none is attributed
to independent human scientific review. No AI-generated images were used.
