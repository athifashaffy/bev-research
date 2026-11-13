# Data

The root analysis reads `derived/`, which contains archived simulation-derived
tables, generated temperature traces, forecasting scores and laboratory rule
response summaries. `manifest/` records source checksums and channel metadata.
New results are written outside these input directories.

| Input | Meaning |
|---|---|
| `derived/table2_nominal_reserve.csv` | Nine configurations at their own external reserve cutoffs |
| `derived/table2_common_window.csv` | The same configurations over the shared 68.039-minute window |
| `derived/table4_pooled_metrics.csv` | Pooled forecast scores for five methods and four horizons |
| `derived/table5_rule_response.csv` | Archived laboratory rule-response summary, not independently verified onset times |
| `derived/frozen_rule_summary.csv` | Rule responses on generated normal-temperature scenarios |
| `derived/trace_C100_RR03.csv` | Generated reference-cell temperature trace, not measured pack temperature |

## Source archives and full measurements

The separate [`reproducibility/data`](../reproducibility/data) tree retains nine
HAULSIM result databases, source event/thermal tables, frozen coefficients and
recorded forecasting inputs. Its `SOURCE_MANIFEST.json` lists file sizes and
SHA-256 hashes. HAULSIM software and licence credentials are not distributed;
rerunning the native simulation requires the licensed application.

TUM LFP measurements are available as
[`reproducibility/data/tum/dataset/`](../reproducibility/data/tum/dataset).
The publisher's [mediaTUM record](https://mediatum.ub.tum.de/1717758),
[DOI 10.14459/2023mp1717758](https://doi.org/10.14459/2023mp1717758), explicitly
declares CC BY 4.0, confirmed on 28 October 2026. The empty DataCite `rightsList`
does not negate that publisher declaration. CSV values, clocks and channel order
are preserved; the largest table is split at source-row boundaries. Multiple
channels from one module are not independent module experiments.

The 27 Sheffield LFP source CSVs and workbook are in
[`reproducibility/experiments/B/data/sheffield/`](../reproducibility/experiments/B/data/sheffield),
with attribution and CC BY 4.0 evidence for
[DOI 10.15131/shef.data.29836850.v1](https://doi.org/10.15131/shef.data.29836850.v1).
The archive's published checksums identify the source bytes used.

## Interpretation

Generated temperatures are A123-equivalent cell-surface model outputs. They are
not measured or validated Z50 pack, core or hotspot temperatures. The 60 °C
screen is a declared study threshold, not a Z50 battery-management-system limit;
the A123 datasheet lists operation up to 55 °C and storage up to 60 °C.

Third-party sources retain their original attribution and licence terms. Hash
agreement checks input identity, not physical validity or warning performance.
