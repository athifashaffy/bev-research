"""Run supporting audit tools without changing their archived inputs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ("hashes", "physics", "ml", "plots", "all")
TOOL_FILES = {
    "physics": "audit_physics.py",
    "ml": "audit_ml.py",
    "plots": "plot_saved_results.py",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="bev-reproduce",
        description=("Audit archived sources and saved simulation/forecast outputs. "
                     "These commands do not provide measured pack validation."),
    )
    result.add_argument("command", choices=COMMANDS)
    result.add_argument(
        "--data-root", type=Path, default=PROJECT_ROOT / "data" / "workspace",
        help="Archived source root (default: this project's data/workspace)",
    )
    result.add_argument(
        "--output", type=Path,
        help="New output directory (default: a new timestamped folder under results/)",
    )
    return result


def _relative(value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("Manifest paths must be strings")
    text = value.replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or ":" in text:
        raise ValueError(f"Unsafe manifest path: {value!r}")
    return Path(*path.parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_output(output: Path, data_directory: Path) -> None:
    if output.exists():
        raise ValueError(f"Output already exists; choose a new path: {output}")
    if output == data_directory or output.is_relative_to(data_directory):
        raise ValueError("Output cannot be inside the input data directory tree")


def _hashes(data_root: Path, output: Path) -> None:
    data_directory = data_root.parent
    manifest = data_directory / "SOURCE_MANIFEST.json"
    content = json.loads(manifest.read_text(encoding="utf-8-sig"))
    records = content.get("files") if isinstance(content, dict) else content
    if not isinstance(records, list) or not records:
        raise ValueError("SOURCE_MANIFEST.json must contain a nonempty files array")
    results, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each source manifest record must be an object")
        relative = _relative(record.get("path"))
        label = relative.as_posix()
        expected_hash, expected_bytes = record.get("sha256"), record.get("bytes")
        if label in seen:
            raise ValueError(f"Duplicate manifest path: {label}")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
            raise ValueError(f"Invalid SHA-256 for {label}")
        if type(expected_bytes) is not int or expected_bytes < 0:
            raise ValueError(f"Invalid byte count for {label}")
        seen.add(label)
        source = (data_directory / relative).resolve()
        if not source.is_relative_to(data_directory):
            raise ValueError(f"Manifest path escapes the input directory: {label}")
        actual_bytes = source.stat().st_size if source.is_file() else None
        actual_hash = _sha256(source) if source.is_file() else None
        results.append({
            "path": label, "expected_bytes": expected_bytes,
            "actual_bytes": actual_bytes, "expected_sha256": expected_hash.lower(),
            "actual_sha256": actual_hash,
            "passed": actual_bytes == expected_bytes and actual_hash == expected_hash.lower(),
        })
    passed = all(record["passed"] for record in results)
    output.mkdir(parents=True, exist_ok=False)
    report = output / "hash_verification.json"
    report.write_text(json.dumps({
        "all_passed": passed, "files_checked": len(results), "files": results,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Hash verification: {sum(r['passed'] for r in results)}/{len(results)} files passed", flush=True)
    if not passed:
        raise ValueError(f"Source verification failed; see {report}")


def _tool(command: str, data_root: Path, output: Path) -> None:
    tool = PROJECT_ROOT / "tools" / TOOL_FILES[command]
    if not tool.is_file():
        raise FileNotFoundError(f"Required audit tool is missing: {tool}")
    arguments = [sys.executable, "-B", str(tool)]
    if command == "ml":
        arguments += [
            "--input", str(data_root / "APCOM_Draft_Experiments_2026-10-27" / "experiment_a"),
            "--source-root", str(data_root), "--output", str(output),
        ]
    else:
        arguments += ["--root", str(data_root), "--output", str(output)]
    print(f"Running {command} audit; output: {output}", flush=True)
    completed = subprocess.run(arguments, cwd=PROJECT_ROOT, shell=False, check=False)
    if completed.returncode:
        raise RuntimeError(f"{command} tool failed with exit status {completed.returncode}")


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    data_root = arguments.data_root.expanduser().resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = (arguments.output or PROJECT_ROOT / "results" / f"run-{stamp}").expanduser().resolve()
    try:
        if not data_root.is_dir():
            raise FileNotFoundError(f"Input root is not a directory: {data_root}")
        _new_output(output, data_root.parent)
        if arguments.command == "hashes":
            _hashes(data_root, output)
        elif arguments.command == "all":
            output.mkdir(parents=True, exist_ok=False)
            _hashes(data_root, output / "hashes")
            for command in ("physics", "ml", "plots"):
                _tool(command, data_root, output / command)
        else:
            _tool(arguments.command, data_root, output)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"bev-reproduce: {error}", file=sys.stderr)
        return 1
    print(f"Output written to {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
