# Repository working instructions

## Scope

Use this repository to inspect, reproduce and verify BEV simulation and battery
data analyses. Do not generate scientific manuscript text for the author.
Language suggestions may improve a draft supplied by the author. Record AI
assistance accurately in the provenance documentation and commit description.

## Implementations

- `src/`, `experiments/` and `code/` at the repository root contain the NumPy
  reconstruction and figure workflow added on 28 October 2026.
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

Follow each Experiment A/B README for its own commands. Archive B is not
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
