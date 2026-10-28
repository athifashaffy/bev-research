# TUM LFP module measurements

Schöberl, Jan; Ank, Manuel; Schreiber, Markus; Wassiliadis, Nikolaos; Lienkamp, Markus (2023). **Thermal runaway propagation data set of lithium-ion batteries with NMC-811 and LFP cathodes.** Technical University of Munich. [Dataset DOI](https://doi.org/10.14459/2023mp1717758), [publisher record](https://mediatum.ub.tum.de/1717758). Licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); evidence and its verification limits are in [`license_evidence.json`](license_evidence.json).

Modification notice: the publisher's comma-separated UTF-8 `.txt` exports were given descriptive `.csv` filenames. The large surface table was split at row boundaries with the exact source header repeated. Raw data-row bytes, decimal field strings, clocks, signs, channel ordering, units and source rows were preserved. No values were estimated or replaced.

This is historical module thermal-runaway propagation data. It is separate from the conference experiment's self-generated temperature forecasting target. A channel filename identifies a sensor or table, not an independent experiment or a thermal-runaway onset.

## Browse the data

For quick viewing, use [`previews_first_200_rows_NOT_ANALYSIS_INPUT`](previews_first_200_rows_NOT_ANALYSIS_INPUT). Every file there contains only its source's first 200 data rows and is labelled as a viewing preview. Use the full files under [`lfp`](lfp) for data access. Previews must not be concatenated into analysis inputs.

| Measurement | Full-data location | Source tables | Measurement channels | Columns per source table |
|---|---|---:|---:|---:|
| Cell temperature T1–T6 | [`lfp/cell_temperatures`](lfp/cell_temperatures) | 6 | 6 | 2 |
| Cell voltage U1–U5 | [`lfp/cell_voltages`](lfp/cell_voltages) | 5 | 5 | 2 |
| Vent temperature T1vent–T5vent | [`lfp/venting_temperatures`](lfp/venting_temperatures) | 5 | 5 | 2 |
| Module surface temperature | [`lfp/surface_temperatures`](lfp/surface_temperatures) | 1, split into 5 CSV parts | 89 | 90 |

Every original `Time [s]` field is preserved. Temperatures are degrees Celsius, and voltages are volts, as stated in the original headers. [`column_dictionary.csv`](column_dictionary.csv) lists all 122 source columns across the 17 tables, including the 17 clock columns.

## Counts and surface parts

T1 has 1,970 rows. T2–T6 each have 41,405 rows. U1–U5 each have 41,404 rows. Vent T1/T2 each have 41,405 rows and vent T3–T5 each have 41,404 rows. The surface table has 124,487 rows. The total across separate tables is 747,524 rows; this is not a count of independent experiments or aligned multi-sensor samples.

| Surface part | Original data-row start | Original data-row end | Rows | Bytes |
|---:|---:|---:|---:|---:|
| 001 | 1 | 25,098 | 25,098 | 19,999,214 |
| 002 | 25,099 | 50,095 | 24,997 | 19,999,664 |
| 003 | 50,096 | 75,099 | 25,004 | 19,999,793 |
| 004 | 75,100 | 100,110 | 25,011 | 19,999,437 |
| 005 | 100,111 | 124,487 | 24,377 | 19,499,153 |

Row ranges are one-based data-row positions, excluding the header. Each part repeats the original header and contains all 89 surface channels. To reconstruct the original file, retain the first header and concatenate only the data rows of parts 001–005 in order. To read parts as tables, read each with its header and concatenate the resulting rows in that same order.

## Provenance and integrity

[`csv_manifest.csv`](csv_manifest.csv) maps every output to its original publisher path. It records byte size, part SHA-256, source SHA-256, original dimensions, source clock endpoints as exact strings, contiguous row ranges, and a digest of all original data rows. [`transformation_log.json`](transformation_log.json) records byte-for-byte logical reconstruction and source preservation checks. [`integrity.json`](integrity.json) records totals and the preparation-code hash.

[`source_measurement_inventory.json`](source_measurement_inventory.json) inventories all 68 locally available measurement representations across the two chemistries: 34 LFP and 34 NMC-811 files, each chemistry consisting of 17 TXT and 17 MAT files. The original local SHA-256 and publisher SHA-512 hashes were checked. Only the publisher's LFP TXT numeric exports are copied into the CSV dataset. MATLAB counterparts are opaque MCOS table containers and remain unconverted; exact TXT/MAT numerical equivalence and additional MATLAB precision are not claimed. [`nmc_inventory_ONLY.json`](nmc_inventory_ONLY.json) provides NMC dimensions and provenance without redistributing its measurement values here.

Reproduction code and commands are in the parent directory's [`README.md`](../README.md). `verify_tum_csv.py` verifies all parts, row ranges, source reconstruction digests and previews using this package alone.

## Limits on interpretation

Independent sensor-clock thermal-runaway onset labels are not supplied by this package. There is no new onset inference. Original negative clock values remain negative; time zero is not newly interpreted as failure onset. Separate channel clocks and endpoints are preserved without synchronization. Different file lengths are retained, including the shorter T1 record; no missing tail is filled.

The tables are not a healthy-operation current/temperature training corpus. Multiple channels from a module do not create multiple independent module tests. These copied measurements do not establish warning lead time, prospective alarm performance, a false-alarm rate, or pack-level generalization. No such scores are calculated here.

No video, video-derived event label, third-party paper PDF, or manuscript text is included.

## Publisher licence recheck on 28 October 2026

A normal browser read of the [current mediaTUM record](https://mediatum.ub.tum.de/1717758) displayed the explicit Rights field `by, http://creativecommons.org/licenses/by/4.0`. This independently confirms CC BY 4.0. Earlier automated-request challenges and the empty DataCite rightsList are recorded above for chronology; they do not override the publisher's displayed licence. See [the current check](../current_publisher_license_check.json) for the recorded method.
