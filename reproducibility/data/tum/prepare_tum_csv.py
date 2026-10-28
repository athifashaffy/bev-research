"""Prepare lossless CSV copies of publisher TXT exports. Standard library only.

AI-assisted packaging code. Never decode MATLAB MCOS tables, infer event labels,
resample, synchronize clocks, round values, or edit original downloaded data.
"""
from __future__ import annotations
import argparse
import csv
import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import sys

BASE = Path("thermal runaway propagation data set/measurement data")
EXPECTED = {
    **{f"cell temperatures/T{i}": f"cell_temperature_t{i}" for i in range(1, 7)},
    **{f"cell voltages/U{i}": f"cell_voltage_u{i}" for i in range(1, 6)},
    **{f"venting temperatures/T{i}vent": f"vent_temperature_t{i}" for i in range(1, 6)},
    "surface temperatures/T_surf": "module_surface_temperatures_89_channels",
}


class DatasetError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DatasetError(message)


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def csv_write(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def inspect_csv(path, surface=False):
    """Validate the known publisher schema; preserve the bytes separately."""
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        surface_count = 83 if Path(path).stem == "T_surf_NMC811" else 89
        expected = ["Time [s]"] + ([f"Temperature {i} [°C]" for i in range(1, surface_count + 1)] if surface else
                   ["Voltage [V]" if Path(path).stem.startswith("U") else "Temperature [°C]"])
        require(header == expected, f"Unknown CSV schema in {Path(path).name}: {header[:4]}")
        n = 0
        first = last = None
        monotonic = True
        previous = None
        nonfinite = 0
        for row in reader:
            require(len(row) == len(header), f"Ragged/blank row {n + 2} in {Path(path).name}")
            try:
                values = [float(value) for value in row]
            except ValueError as exc:
                raise DatasetError(f"Nonnumeric row {n + 2} in {Path(path).name}") from exc
            require(math.isfinite(values[0]), "Nonfinite clock is not a recognized schema")
            nonfinite += sum(not math.isfinite(v) for v in values[1:])
            if previous is not None:
                monotonic &= values[0] > previous
            previous = values[0]
            first = row[0] if first is None else first
            last = row[0]
            n += 1
    require(n > 0, "Empty measurement export")
    return {"data_rows": n, "columns": len(header), "measurement_channels": len(header) - 1,
            "header": header, "clock_start_string": first, "clock_end_string": last,
            "clock_strictly_increasing": monotonic, "nonfinite_measurement_values_preserved": nonfinite}


def split_exact_csv(source, output_dir, stem, max_bytes=20_000_000, preview_rows=200):
    """Split at physical data-row boundaries; headers and all row bytes unchanged."""
    require(max_bytes > 0 and preview_rows > 0, "Positive size/preview limits required")
    source, output_dir = Path(source), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parts, data_digest = [], hashlib.sha256()
    preview_path = output_dir.parent.parent / "previews_first_200_rows_NOT_ANALYSIS_INPUT" / (stem + "_first_200_rows.csv")
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    row_n = 0
    current = None
    try:
        with source.open("rb") as reader, preview_path.open("wb") as preview:
            header = reader.readline()
            require(header.endswith(b"\n") and b'"' not in header, "Unsupported multiline/quoted CSV header")
            require(len(header) < max_bytes, "Header exceeds part-size limit")
            preview.write(header)
            for line in reader:
                require(b'"' not in line and line.strip(), "Unsupported quoted/multiline/blank CSV data row")
                require(len(header) + len(line) <= max_bytes, "A single data row exceeds part-size limit")
                if current is None or current.tell() + len(line) > max_bytes:
                    if current:
                        current.close()
                        parts[-1]["row_end"] = row_n
                    part = output_dir / f"{stem}_part_{len(parts) + 1:03d}.csv"
                    current = part.open("wb")
                    current.write(header)
                    parts.append({"path": part, "row_start": row_n + 1})
                row_n += 1
                current.write(line)
                data_digest.update(line)
                if row_n <= preview_rows:
                    preview.write(line)
            require(row_n > 0, "No CSV data rows to copy")
            parts[-1]["row_end"] = row_n
    finally:
        if current:
            current.close()
    rebuilt, rebuilt_data = hashlib.sha256(), hashlib.sha256()
    rebuilt.update(header)
    for part in parts:
        path = part["path"]
        with path.open("rb") as stream:
            require(stream.readline() == header, "Split header changed")
            for line in stream:
                rebuilt.update(line)
                rebuilt_data.update(line)
        require(path.stat().st_size <= max_bytes, "Generated part exceeds byte cap")
        part["bytes"] = path.stat().st_size
        part["sha256"] = digest(path)
    require(rebuilt.hexdigest() == digest(source), "Byte-for-byte logical reconstruction differs from source")
    require(data_digest.hexdigest() == rebuilt_data.hexdigest(), "Data-row digest differs after splitting")
    return parts, {"source_reconstructed_sha256": rebuilt.hexdigest(), "data_rows_sha256": data_digest.hexdigest(),
                   "data_rows": row_n, "preview_path": preview_path, "preview_data_rows": min(preview_rows, row_n),
                   "headers_and_field_strings_unchanged": True, "all_source_rows_once_in_order": True}


def dataset_files(source):
    result = {}
    for chemistry, suffix in (("GraphiteLFP", "LFP"), ("GraphiteNMC-811", "NMC811")):
        expected_paths = set()
        for specification, name in EXPECTED.items():
            group, channel = specification.split("/")
            for extension in ("txt", "mat"):
                path = BASE / group / chemistry / f"{channel}_{suffix}.{extension}"
                require((source / path).is_file(), f"Required publisher measurement file missing: {path}")
                expected_paths.add(path)
                result[path] = {"chemistry": suffix, "measurement_kind": group, "channel": channel,
                                "name": f"{suffix.lower()}_{name}", "surface": channel == "T_surf"}
        actual = {p.relative_to(source) for p in (source / BASE).rglob("*") if p.is_file() and chemistry in p.parts
                  and not p.name.startswith("README")}
        require(actual == expected_paths, f"Unknown or unexpected measurement files for {chemistry}")
    return result


def prepare(source, output, license_record, max_bytes=20_000_000):
    source, output = Path(source).resolve(), Path(output).resolve()
    require(source.is_dir(), "Source directory does not exist")
    require(not output.exists(), "Output directory must be new")
    require(not output.is_relative_to(source), "Output must be outside original source directory")
    license_record = Path(license_record)
    evidence = json.loads(license_record.read_text(encoding="utf-8"))
    require(evidence.get("license_spdx") == "CC-BY-4.0" and evidence.get("evidence_basis"), "Unknown/unverified redistribution license; refusing data export")
    inventory = {r["path"]: r for r in json.loads((source / "inventory.json").read_text())}
    checksums = {}
    for line in (source / "checksums.sha512").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{128}) \*(.+)", line)
        require(match is not None, "Unknown publisher SHA-512 manifest syntax")
        checksums[match[2]] = match[1]
    files = dataset_files(source)
    records, nmc, source_inventory, columns, checks, preview_records = [], [], [], [], [], []
    # Validate all numeric exports before creating the output directory.
    schemas = {}
    for relative, specification in files.items():
        path = source / relative
        sha256 = digest(path)
        publisher_sha512 = digest(path, "sha512")
        require(relative.as_posix() in inventory and sha256 == inventory[relative.as_posix()]["sha256"], f"Local source SHA-256 mismatch: {relative}")
        require(publisher_sha512 == checksums.get(relative.as_posix()), f"Publisher SHA-512 mismatch: {relative}")
        row = {"source_path": relative.as_posix(), "chemistry": specification["chemistry"],
               "measurement_kind": specification["measurement_kind"], "channel_or_table": specification["channel"],
               "format": path.suffix[1:], "bytes": path.stat().st_size, "sha256": sha256,
               "publisher_sha512": publisher_sha512, "publisher_sha512_matches": True,
               "representation_note": "Publisher numeric CSV export with .txt suffix" if path.suffix == ".txt" else "MATLAB MCOS table container; inventoried, not decoded; no exact equivalence to TXT asserted"}
        if path.suffix == ".txt":
            schemas[relative] = inspect_csv(path, specification["surface"])
            row.update({k: v for k, v in schemas[relative].items() if k != "header"})
        source_inventory.append(row)
        if specification["chemistry"] == "NMC811":
            nmc.append(row)
    output.mkdir(parents=True)
    shutil.copyfile(license_record, output / "license_evidence.json")
    for relative, specification in files.items():
        if specification["chemistry"] != "LFP" or relative.suffix != ".txt":
            continue
        source_path = source / relative
        schema = schemas[relative]
        dest = output / "lfp" / specification["measurement_kind"].replace(" ", "_")
        parts, verification = split_exact_csv(source_path, dest, specification["name"], max_bytes)
        # A one-part file is an exact copy with a descriptive name, no part label.
        if len(parts) == 1:
            original_name = parts[0]["path"]
            renamed = dest / (specification["name"] + ".csv")
            original_name.rename(renamed)
            parts[0]["path"] = renamed
            require(digest(renamed) == digest(source_path), "Single-part copy is not byte-identical")
        for part in parts:
            records.append({"output_path": part["path"].relative_to(output).as_posix(), "source_path": relative.as_posix(),
                            "chemistry": "LFP", "measurement_kind": specification["measurement_kind"], "source_data_rows": schema["data_rows"],
                            "source_columns": schema["columns"], "source_measurement_channels": schema["measurement_channels"],
                            "source_clock_start_string": schema["clock_start_string"], "source_clock_end_string": schema["clock_end_string"],
                            "row_start": part["row_start"], "row_end": part["row_end"], "part_data_rows": part["row_end"] - part["row_start"] + 1,
                            "bytes": part["bytes"], "sha256": part["sha256"], "source_sha256": digest(source_path),
                            "logical_reconstruction_sha256": verification["source_reconstructed_sha256"], "data_rows_sha256": verification["data_rows_sha256"],
                            "transformation": "Byte-exact CSV copy with descriptive .csv name" if len(parts) == 1 else "Split only at data-row boundaries; exact source header repeated in each part"})
        for index, header in enumerate(schema["header"]):
            columns.append({"source_path": relative.as_posix(), "column_index_1_based": index + 1, "original_header": header,
                            "unit": "s" if index == 0 else ("V" if specification["measurement_kind"] == "cell voltages" else "degree_Celsius"),
                            "role": "original publisher sensor clock; no inferred event reference" if index == 0 else "publisher measurement channel",
                            "clock_offset_applied_s": 0, "resampling_applied": False})
        preview_records.append({"source_path": relative.as_posix(), "preview_path": verification["preview_path"].relative_to(output).as_posix(),
                                "data_rows": verification["preview_data_rows"], "purpose": "VIEWING PREVIEW ONLY; NOT AN ANALYSIS INPUT"})
        checks.append({"source_path": relative.as_posix(), **{k: v for k, v in verification.items() if k != "preview_path"},
                       "parts": len(parts), "source_sha256_unchanged": digest(source_path) == verification["source_reconstructed_sha256"]})
    for relative, specification in files.items():
        require(digest(source / relative) == inventory[relative.as_posix()]["sha256"], f"Original source changed during preparation: {relative}")
    csv_write(output / "csv_manifest.csv", records)
    csv_write(output / "column_dictionary.csv", columns)
    json_write(output / "source_measurement_inventory.json", source_inventory)
    json_write(output / "nmc_inventory_ONLY.json", nmc)
    json_write(output / "previews_manifest.json", preview_records)
    json_write(output / "transformation_log.json", checks)
    total_rows = sum(c["data_rows"] for c in checks)
    result = {"completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "passed": True,
              "dataset_doi": "10.14459/2023mp1717758", "lfp_source_measurement_tables": len(checks),
              "lfp_source_numeric_rows": total_rows, "lfp_measurement_channels_across_tables": sum(schemas[r]["measurement_channels"] for r in schemas if "GraphiteLFP" in r.parts),
              "output_csv_parts": len(records), "output_data_bytes": sum(r["bytes"] for r in records),
              "max_csv_bytes": max_bytes, "all_raw_row_bytes_and_clock_strings_preserved": True,
              "all_source_rows_once_in_order": True, "all_source_and_publisher_hashes_verified": True,
              "nmc_source_files_inventoried": len(nmc), "mat_source_files_inventoried_not_converted": 34,
              "preview_files": len(preview_records), "ai_assistance": "Preparation code and packaging metadata generated with AI assistance; original experimental values are publisher data.",
              "no_resampling_synchronization_onset_inference_or_model_fitting": True,
              "license_basis": evidence["evidence_basis"], "license_spdx": evidence["license_spdx"],
              "prepare_code_sha256": digest(Path(__file__)),
              "source_manifest_sha256": digest(source / "inventory.json"), "publisher_checksum_manifest_sha256": digest(source / "checksums.sha512")}
    json_write(output / "integrity.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--license-record", default=Path(__file__).with_name("license_evidence.json"), type=Path)
    parser.add_argument("--max-bytes", type=int, default=20_000_000)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.source, args.output, args.license_record, args.max_bytes), indent=2))
    except (DatasetError, OSError, ValueError, KeyError) as exc:
        print(f"PREPARATION FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
