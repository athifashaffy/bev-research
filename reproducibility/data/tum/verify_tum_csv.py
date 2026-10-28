"""Verify split CSV artifacts without the original large source file. Stdlib only."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys


def verify(dataset):
    dataset = Path(dataset).resolve()
    integrity = json.loads((dataset / "integrity.json").read_text(encoding="utf-8"))
    with (dataset / "csv_manifest.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    groups = defaultdict(list)
    for row in rows:
        path = (dataset / row["output_path"]).resolve()
        if not path.is_relative_to(dataset):
            raise ValueError("Manifest path escapes dataset directory")
        if path.stat().st_size != int(row["bytes"]) or path.stat().st_size > integrity["max_csv_bytes"]:
            raise ValueError("Part size mismatch or cap exceeded")
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Part SHA-256 mismatch")
        groups[row["source_path"]].append(row)
    previews = {r["source_path"]: r for r in json.loads((dataset / "previews_manifest.json").read_text())}
    total_rows, max_part = 0, 0
    for source, parts in groups.items():
        parts.sort(key=lambda r: int(r["row_start"]))
        logical, data = hashlib.sha256(), hashlib.sha256()
        next_row, original_header, preview_bytes = 1, None, bytearray()
        for part in parts:
            if int(part["row_start"]) != next_row:
                raise ValueError("Gap/overlap in source data-row ranges")
            path = dataset / part["output_path"]
            max_part = max(max_part, path.stat().st_size)
            with path.open("rb") as stream:
                header = stream.readline()
                if original_header is None:
                    original_header = header
                    logical.update(header)
                    preview_bytes.extend(header)
                elif header != original_header:
                    raise ValueError("Part header differs from first part")
                count = 0
                for line in stream:
                    logical.update(line)
                    data.update(line)
                    count += 1
                    if next_row + count - 1 <= 200:
                        preview_bytes.extend(line)
            if count != int(part["part_data_rows"]) or count != int(part["row_end"]) - int(part["row_start"]) + 1:
                raise ValueError("Part row count mismatch")
            next_row += count
        if next_row - 1 != int(parts[0]["source_data_rows"]):
            raise ValueError("Logical source row count mismatch")
        if logical.hexdigest() != parts[0]["source_sha256"] or logical.hexdigest() != parts[0]["logical_reconstruction_sha256"]:
            raise ValueError("Logical source reconstruction SHA-256 mismatch")
        if data.hexdigest() != parts[0]["data_rows_sha256"]:
            raise ValueError("Data rows SHA-256 mismatch")
        preview_path = (dataset / previews[source]["preview_path"]).resolve()
        if not preview_path.is_relative_to(dataset) or preview_path.read_bytes() != bytes(preview_bytes):
            raise ValueError("Preview differs from first 200 source rows")
        total_rows += next_row - 1
    if len(groups) != 17 or len(rows) != integrity["output_csv_parts"] or total_rows != integrity["lfp_source_numeric_rows"]:
        raise ValueError("Dataset-level file/count mismatch")
    return {"passed": True, "source_measurement_tables": len(groups), "csv_parts": len(rows),
            "data_rows_preserved": total_rows, "max_individual_csv_bytes": max_part,
            "all_logical_source_sha256_match": True, "all_preview_first_200_rows_match": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.dataset), indent=2))
    except (OSError, ValueError, KeyError) as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
