# Repository working instructions

## Scope

Use this repository to inspect, reproduce and verify BEV simulation and battery
data analyses. Do not generate scientific manuscript text for the author.
Language suggestions may improve a draft supplied by the author. Record AI
assistance accurately in the provenance documentation and commit description.

## Implementations

- `reconstruction/` contains the NumPy reconstruction and figure workflow added
  on 28 October 2026 (moved there from the repository root on 13 November 2026;
  its package is `bev_reconstruction`).
- `edge/` contains the standalone on-vehicle forecaster (`bev_edge`) added on
  13 November 2026. It must reproduce the saved A_live forecasts exactly.
- `reproducibility/experiments/A` retains the original scikit-learn algorithms
  in a portable trainer, with a separately dated fresh model refit.
- `reproducibility/experiments/B` contains the archived LFP analysis and its
  documented execution gaps. Its scope differs from the narrowed paper.
- `reproducibility/experiments/haulage` and `thermal` index native records,
  accounting functions, coefficient provenance and thermal sensitivities.
- `reproducibility/data/tum` contains publisher LFP measurements in CSV form.
  TUM is not training or validation data for Experiment A.

Preserve both implementations. They are not interchangeable merely because
their experiment names resemble each other.

## Data integrity

Preserve source bytes, values, units, channel clocks and provenance. Open SQLite
archives read-only. Write new results to a new directory outside input data.
Do not silently resample, filter, interpolate, infer event times or replace
measurements. Clearly separate viewing previews from full analysis inputs.

Respect `.gitattributes` and the SHA-256 manifests. Run integrity checks after
moving or repackaging files. Never commit credentials, private correspondence,
manuscript drafts or local software installations in a new data release.

## Checks

From `reproducibility/`, install the pinned requirements and run:

```text
bev-reproduce all --output results/check-new
python -m unittest discover -s tests -v
python -m unittest discover -s tools -p test_audit_ml.py -v
python -m unittest discover -s data/tum -p test_prepare_tum_csv.py -v
python data/tum/verify_tum_csv.py --dataset data/tum/dataset
```

`python scripts/check_all.py` (from the repository root) runs all of these plus
the experiment, reconstruction and edge suites; GitHub Actions runs it on each
push. The edge replay test must keep reproducing the saved Table 2 forecasts
exactly. Follow each Experiment A/B README for its own commands. Archive B is not
declared fully portable. A model newly refitted today must not be labelled an
original historical estimator.

## Interpretation and reporting

Equivalent current is an assumed reference-cell mapping. Numerical agreement
does not establish actual pack current, temperature or thermal-runaway warning
performance. Distinguish simulation, generated temperatures and laboratory
measurements. Report unsuccessful comparisons and missing evidence.

State the date and scope of each check. Do not attribute an automated check or
AI-authored code to personal human verification. Commit dates record uploads
and changes, not the execution date or independent authorship of older results.

## Figures, evidence and AI-written statements

These rules apply to every figure, table, screenshot and statement prepared for
the author, in study notes as well as anything meant for the paper.

1. **Brainstorm first.** Before producing anything, write out the plan: what
   will be made, which script and which input files it comes from, every
   assumption involved, and how each number will be checked. Agree it with the
   author before building.
2. **Figures come only from code run on actual outputs.** Every figure, chart
   or screenshot of a result must be produced by a Python script in this
   repository from saved HAULSIM, thermal or model outputs. No hand-drawn,
   AI-drawn or illustrative charts of results. A screenshot of code shows the
   file exactly as it is in the repository, with its path.
3. **Keep proof for every figure and table.** Save a proof record next to the
   output: date, exact command, script path and SHA-256, every input file path
   and SHA-256, output SHA-256, and Python and library versions. A figure without
   a proof record is not used.
4. **The author runs it.** Give the commands so the author regenerates each
   figure and table on their own machine and compares hashes. Do not describe
   a figure as the author's own work; record who wrote the code (AI-assisted
   code stays labelled as such).
5. **Cross-check every AI-written sentence.** Any sentence containing a number,
   result or factual claim written by an AI is checked against the generated
   output or the cited source before it is given to the author. List each
   claim with its source file and value, and mark it matched, mismatched or
   unverified. Unverified claims are flagged, never presented as fact.
6. **No AI text in the manuscript.** These rules govern study material and
   evidence. Manuscript wording remains the author's own, as stated in Scope.

Tools (from `reproducibility/`, both AI-assisted):

```text
python tools/run_with_proof.py --output results/NEW --script SCRIPT --input FILE ... -- COMMAND
python tools/run_with_proof.py --verify results/NEW/PROOF.json
python tools/check_claims.py --text NOTES.txt --claims tools/claims/claims_study_notes.json --output results/NEW
python -m unittest discover -s tools -p "test_*proof*.py"
python -m unittest discover -s tools -p "test_check_claims.py"
```

Register a claim in a claims file before relying on a number; give it
`anchors` so a wrong value is reported as mismatched, not just unverified.
