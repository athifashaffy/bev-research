# Archived Experiment B: warning rules and event admissibility

This directory archives the original analysis implementation, tests, protocol,
numerical results and figures. Its laboratory warning-rule scope is separate
from the haulage thermal-modelling and forecasting benchmark.

The analysis screens 27 Sheffield heating records and 16 TUM measurement files
(six temperature, five voltage, five vent-temperature channels from one module).
Strict temperature thresholds are 45/50/55/60 C; causal 60-second OLS rate
thresholds are 1/2/5 C per minute, each with five seconds of persistence. Stored
counts describe rule responses. They do not establish independently validated
thermal-runaway onset, confirmed misses, field false-alarm rates or physical
warning lead time. A measured <=0.1 V condition is an electrical condition, not
adjudicated thermal-runaway onset. Preserve UNAVAILABLE entries in the results.

## Actual archived files

- `code/`: original runner, rule implementation and unit tests, unchanged.
- `qa/independent_output_audit.py`: original separate numerical readback.
- `01_experiment_b_protocol.json`: original frozen configuration.
- `results/`: original CSV/JSON results and compressed causal features.
- `figures/`: original PNG, SVG and PDF figure exports.
- `README.txt`, `02_Results_and_Limitations.txt` and QA records: historical
  documentation/evidence, not a claim of a fresh run.
- `data/sheffield/`: all 27 original publisher CSVs, workbook and attribution.
- `legacy_inputs/`: the other small original inputs used by the runner, including
  prior saved laboratory predictions and three opaque joblib artifacts. The
  archived B runner hashes those models; it does not deserialize or fit them.

`COPY_MANIFEST.json` records every byte-identical copied artifact. Generated
packaging metadata is identified separately. The original source folders were
not edited and the analysis was not rerun for this release.

## Data provenance

Sheffield: Bugryniec and colleagues, *Experimental Temperature and Heat Flux
Data for Constant Power Over Heating Tests of 18650 and 26650 LFP Cells*,
[DOI 10.15131/shef.data.29836850.v1](https://doi.org/10.15131/shef.data.29836850.v1).
The archived publisher metadata explicitly specifies
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Every CSV and workbook
is unchanged. CSV provenance sidecars are new stable-URL metadata; expired signed
URLs were omitted. `data/sheffield/LICENSE_EVIDENCE.json` retains attribution and
the hash of the local publisher metadata. No Sheffield paper PDF or quoted paper
text is redistributed.

TUM: [DOI 10.14459/2023mp1717758](https://doi.org/10.14459/2023mp1717758).
Full LFP CSV exports are already in `../../data/tum/dataset/`; license evidence and
attribution are in `../../data/tum/`. The 16 files required by B are byte-identical
CSV copies of the publisher TXT exports. `REQUIRED_MEASUREMENT_INPUTS.json` maps
every original measurement path to its public repository path and SHA-256.
TUM is used by this historical B analysis, but not by the
Experiment A forecasting benchmark. Edited videos are not redistributed here.
Video-clock annotations retained as a required input do not establish numerical
sensor-clock synchronization.

## Execution status and exact layout alignment

**The original full runner is archived and is not directly portable as shipped.**
It derives an original BEV workspace layout from its location, adds a historical
local tools directory to `sys.path`, and writes into its own `results/` and
`figures/`. It also unconditionally hashes an excluded private `source_draft.txt`.
That manuscript dependency is not supplied or fabricated. A reviewed runtime
adapter must remove the private draft-hash dependency and accept explicit data
and output roots before a full public rerun can be claimed.

For a future reviewed adapter or an isolated legacy-layout investigation, create
an entirely new scratch workspace; keep this archive read only:

1. Copy this archived analysis to
   `SCRATCH/APCOM_Draft_Experiments_2026-10-27/experiment_b/`.
2. Copy `data/sheffield/*` to
   `SCRATCH/LFP_Data_Feasibility_2026-10-20/sources/sheffield/`. The rebuilt
   `*.csv.provenance.json` sidecars provide the SHA-256 field read by the runner.
3. For each row in `REQUIRED_MEASUREMENT_INPUTS.json`, copy the listed
   `public_repository_path` to `SCRATCH/original_workspace_path`. For TUM this
   changes only the filename back to `.txt`; bytes must remain identical. Do not
   resample, round or interpolate the measurements.
4. Copy the contents of `legacy_inputs/` into `SCRATCH/`, preserving every relative
   path. This supplies TUM inventories/checksums, Sheffield quality records,
   video annotations, saved forecast predictions, selection metadata and model
   hashes.
5. Provide NumPy and Matplotlib through a normal Python environment. The
   historical local dependency directory is not redistributed. No estimator is
   loaded by the B runner, so scikit-learn is not required for its hash-only
   forecast reuse step.
6. Resolve the excluded draft-hash dependency in a clearly identified adapter;
   do not invent a draft or claim an unchanged full rerun. Direct execution before
   this correction can write partial outputs and then fail.

The isolated standard-library rule tests do not need the measurement inputs:
`python -B -m unittest discover -s code -p test_rules.py -v` from this directory.
The test logs included here are archived originals, not new packaging test runs.

No new license grant is made for first-party code or other artifacts by this
archive. Source dataset terms remain applicable.
