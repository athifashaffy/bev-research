# Data

Three directories, with different rules attached to each.

```
data/
  derived/    committed    outputs computed in this study
  manifest/   committed    checksums and metadata describing the sources
  raw/        NOT committed  licence-restricted third-party source data
```

## `derived/` — computed outputs, safe to redistribute

These are research outputs of this study, not third-party data. Every figure in
`figures/` is generated from these files alone, so the repository is
self-contained for reproduction of the figures.

| File | Contents |
|---|---|
| `table2_nominal_reserve.csv` | Nine configurations, each run to its own reserve endpoint |
| `table2_common_window.csv` | The same nine on one shared 68.0389726 min window |
| `table4_pooled_metrics.csv` | Pooled RMSE and MAE, 5 methods x 4 horizons |
| `table5_rule_response.csv` | Frozen-rule response summary on laboratory records |
| `frozen_rule_summary.csv` | The same rules applied to modelled normal trajectories |
| `trace_C100_RR03.csv` | One full case trace, used for the worked example figure |

Temperatures in these files are **A123-equivalent cell surface** values from a
fitted lumped model. They are not measured, and they are not validated Sandvik
Z50 pack, core or hotspot temperatures.

## `manifest/` — how to confirm you have the same inputs

| File | Contents |
|---|---|
| `source_checksums.json` | SHA-256 and byte size for all 43 Sheffield and TUM source files |
| `tum_channel_index.csv` | Per-channel metadata: source file, SHA-256, sample count, time range, temperature range, sensor location, quality flags |
| `tum_datacite.json` | The TUM DataCite record as retrieved |
| `event_register.csv` | Per-record event qualification, and why each onset time is unavailable |
| `clock_alignment_audit.csv` | Sensor clock alignment checks |

If you obtain the raw datasets yourself, verify them against
`source_checksums.json` before reproducing anything. Byte-identical inputs are
the only way to confirm you are reproducing rather than approximating.

## `raw/` — not in this repository, and why

### TUM thermal runaway propagation dataset

- DOI: [10.14459/2023mp1717758](https://doi.org/10.14459/2023mp1717758)
- Schöberl, Ank, Schreiber, Wassiliadis, Lienkamp (2023), Technical University of Munich
- Hosted at <https://mediatum.ub.tum.de/1717758>

**The DataCite record carries an empty `rightsList`, meaning no licence is
declared.** Without a declared licence there is no permission to redistribute,
so these files are not included here. Download them from the DOI above and
place them under `data/raw/tum/`.

Six temperature channels from this dataset are used. They come from **one
module experiment** and are dependent channels, not six independent
experiments. `tum_channel_index.csv` records this in its quality flags.

### Sheffield LFP abuse records

- Hosted at the University of Sheffield research data repository (ORDA)
- 27 records across 8 date groups, split 15 / 5 / 7 by date into train,
  development and test

All 28 SHA-256 and MD5 values were checked against the publisher's published
checksums and matched. Confirm the current licence terms at the source before
redistributing any of it. Download to `data/raw/sheffield/`.

### A123 ANR26650M1-B

Datasheet values only. The operating range is -30 to +55 degrees C and the
storage range is -40 to +60 degrees C. The 60 degrees C figure used throughout
this study is a **declared study screen**, not a Z50 pack or BMS limit, and
55 degrees C margins are reported alongside it.

### HAULSIM

HAULSIM 3.8 build 585, used under licence from RPMGlobal. No licence, software
or native model file is included in this repository.

## Attribution

Third-party rights remain with their owners. Derived summary tables and
computed metrics in `derived/` are research outputs of this study. Including
derived metrics here is not a redistribution of the underlying datasets and
does not grant any right to redistribute them.
