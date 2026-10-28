# TUM LFP measurement CSV package

This folder prepares and verifies a CSV distribution of the locally available LFP measurement tables from [TUM dataset DOI 10.14459/2023mp1717758](https://doi.org/10.14459/2023mp1717758). This is a historical external experimental dataset, separate from the generated targets used in the conference forecasting benchmark.

Open [`dataset/README.md`](dataset/README.md) for the data guide and [`dataset/csv_manifest.csv`](dataset/csv_manifest.csv) for every part, source path, row range and hash. Experimental values are the original publisher data.

## Portable preparation

Python 3.10 or newer is sufficient; no third-party dependencies are required. `--source` points to the existing downloaded `sources/tum` directory, containing the publisher tree, `inventory.json` and `checksums.sha512`. It is read only. `--output` must be a new directory outside the source tree.

```text
python -B prepare_tum_csv.py --source /path/to/sources/tum --output /path/to/new_tum_csv_dataset --license-record license_evidence.json
python -B verify_tum_csv.py --dataset /path/to/new_tum_csv_dataset
python -B -m unittest discover -s . -p test_prepare_tum_csv.py -v
```

The preparation script checks all 68 original LFP/NMC measurement representations against both the prior local SHA-256 inventory and the publisher SHA-512 manifest. It validates the known numeric CSV schemas, copies the LFP publisher TXT exports as CSV, and splits the surface table at data-row boundaries. A new MATLAB or Excel schema causes an explicit failure; there is no guessed conversion or table decoding.

The publisher TXT files are already UTF-8 CSV with comma delimiters and CRLF row endings. Sixteen exports become byte-identical descriptive `.csv` files. The 99,489,781-byte LFP surface export becomes five parts, each below 20,000,000 bytes, with the exact header repeated. Joining the first part and the data rows of later parts reconstructs the entire original TXT file byte for byte. `verify_tum_csv.py` proves that using the source SHA-256 recorded in the manifest; originals are not needed for this verification.

All 17 LFP MATLAB counterparts are inventoried, including their original hashes and sizes. Inspection with SciPy identifies MATLAB opaque MCOS table objects. They are not decoded or converted. The publisher's TXT exports provide all 17 measurement tables; **no claim of exact MATLAB-versus-TXT numeric equivalence or recovery of additional MATLAB precision is made**. There are no locally available Excel sources in this TUM measurement tree.

NMC-811 has another 17 TXT and 17 MAT measurement files. Their dimensions, source clocks and hashes are inventoried in `dataset/nmc_inventory_ONLY.json`; their measurement values are not duplicated into this LFP CSV package. NMC surface measurements have 83 channels, whereas LFP surface measurements have 89.

## License evidence

The data license is **CC BY 4.0**, based on the explicit prior local provenance that records verification on the primary mediaTUM page in a normal browser on 2026-10-20. The local record is `LFP_Data_Feasibility_2026-10-20/00_READ_ME.txt`, lines 65–68, with a second license field in `tum_audit.json`. The complete evidence distinction is recorded in `license_evidence.json`.

On 2026-10-28, the primary DataCite API supplied title/author/publisher metadata, saved as `primary_datacite_metadata.json`. Its `rightsList` is empty. A normal browser read of the publisher's [mediaTUM record](https://mediatum.ub.tum.de/1717758) confirmed the explicit CC BY 4.0 rights field; see `current_publisher_license_check.json`. The earlier automated-request challenge is retained in the dated evidence trail. See the dataset attribution notice before reusing the data.

## Verification evidence

- 17 LFP tables, 105 measurement channels across those tables, 747,524 original data rows, and 21 output CSV files.
- Surface table: 124,487 data rows, 90 columns including the original time column; all 89 measurement channels are retained in every part.
- Maximum output part size: 19,999,793 bytes. No individual data CSV exceeds 20 MB.
- All 17 logical source reconstructions and their data-row digests match. All 17 previews match exactly the first 200 source rows.
- Six unit tests check exact split reconstruction, a byte-identical single part, source preservation, preview separation, known NMC surface dimensions, unknown schema/license rejection and an overlarge individual row.
- All source data remain unchanged. No synchronization, onset annotation, resampling, interpolation, rounding, filtering, model fitting or warning scoring is performed.

`test_evidence.json` and `dataset/verification_readback.json` record the final local verification. Original videos and third-party paper PDFs are excluded.

## Publisher licence recheck on 28 October 2026

A normal browser read of the [current mediaTUM record](https://mediatum.ub.tum.de/1717758) displayed the explicit Rights field `by, http://creativecommons.org/licenses/by/4.0`. This independently confirms CC BY 4.0. Earlier automated-request challenges and the empty DataCite rightsList are recorded above for chronology; they do not override the publisher's displayed licence. See [the current check](current_publisher_license_check.json) for the recorded method.
