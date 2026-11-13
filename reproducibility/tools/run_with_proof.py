"""Run a command and save a proof record of exactly what produced its outputs.

AI-assisted tool (Claude, 9 November 2026). It records provenance; it does not
check that a figure is scientifically correct.

Record:
  python tools/run_with_proof.py --output results/my-plots \
      --script tools/plot_saved_results.py \
      --input data/workspace/APCOM_Study_2026-10-22/results/operations_comparison.csv \
      -- python tools/plot_saved_results.py --root data/workspace --output results/my-plots

Verify later (re-hashes every recorded file and reports any difference):
  python tools/run_with_proof.py --verify results/my-plots/PROOF.json

The record is written to <output>/PROOF.json and <output>/PROOF.md. The output
folder must be new, so a record never mixes old and new files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

PACKAGES = ("numpy", "scipy", "matplotlib", "scikit-learn", "pandas")
PROOF_NAMES = {"PROOF.json", "PROOF.md"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def describe(path: Path, base: Path) -> dict:
    try:
        shown = path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        shown = str(path.resolve())
    return {"path": shown, "bytes": path.stat().st_size, "sha256": sha256(path)}


def versions() -> dict:
    found = {"python": platform.python_version(), "platform": platform.platform()}
    for name in PACKAGES:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = None
    return found


def git_state(base: Path) -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=base, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    status = run("status", "--porcelain")
    return {"commit": run("rev-parse", "HEAD"),
            "uncommitted_changes": None if status is None else bool(status)}


def output_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.name not in PROOF_NAMES)


def write_markdown(record: dict, path: Path) -> None:
    lines = ["# Proof record", "",
             f"- **Run (UTC):** {record['started_utc']} to {record['finished_utc']}",
             f"- **Command:** `{' '.join(record['command'])}`",
             f"- **Exit code:** {record['exit_code']}",
             f"- **Working folder:** `{record['working_directory']}`",
             f"- **Git commit:** `{record['git']['commit']}` (uncommitted changes: {record['git']['uncommitted_changes']})",
             f"- **Recorded by:** {record['recorded_by']}", ""]
    for title, key in (("Scripts", "scripts"), ("Inputs", "inputs"), ("Outputs", "outputs")):
        lines += [f"## {title}", "", "| File | Bytes | SHA-256 |", "| --- | --- | --- |"]
        lines += [f"| `{f['path']}` | {f['bytes']} | `{f['sha256']}` |" for f in record[key]] or ["| (none) | | |"]
        lines.append("")
    lines += ["## Software", "", "| Package | Version |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in record["versions"].items()]
    lines += ["", "Check it: `python tools/run_with_proof.py --verify PROOF.json`", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def record_run(command: list[str], output: Path, scripts: list[Path], inputs: list[Path]) -> int:
    base = Path.cwd()
    if output.exists():
        raise SystemExit(f"Output folder already exists: {output}. Use a new folder so the proof covers only this run.")
    for path in scripts + inputs:
        if not path.is_file():
            raise SystemExit(f"Not a file: {path}")
    before = {str(p): sha256(p) for p in scripts + inputs}
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    exit_code = subprocess.run(command, cwd=base).returncode
    finished = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    changed = [p for p, h in before.items() if sha256(Path(p)) != h]
    if changed:
        raise SystemExit(f"Inputs or scripts changed during the run, no proof written: {changed}")
    if not output.is_dir():
        raise SystemExit(f"The command did not create the output folder {output}; no proof written.")
    record = {"schema": "bev-proof/1", "recorded_by": "tools/run_with_proof.py (AI-assisted tool)",
              "started_utc": started, "finished_utc": finished, "command": command, "exit_code": exit_code,
              "working_directory": str(base), "git": git_state(base), "versions": versions(),
              "scripts": [describe(p, base) for p in scripts],
              "inputs": [describe(p, base) for p in inputs],
              "outputs": [describe(p, base) for p in output_files(output)]}
    (output / "PROOF.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    write_markdown(record, output / "PROOF.md")
    print(f"Proof written: {output / 'PROOF.json'} ({len(record['outputs'])} outputs, exit code {exit_code})")
    return exit_code


def verify(proof_path: Path) -> int:
    record = json.loads(proof_path.read_text(encoding="utf-8"))
    base = Path(record["working_directory"])
    if not base.is_dir():
        base = Path.cwd()
    problems = 0
    for group in ("scripts", "inputs", "outputs"):
        for item in record[group]:
            path = Path(item["path"])
            path = path if path.is_absolute() else base / path
            if not path.is_file():
                status, problems = "MISSING", problems + 1
            elif sha256(path) != item["sha256"]:
                status, problems = "CHANGED", problems + 1
            else:
                status = "ok"
            print(f"{status:8} {group[:-1]:6} {item['path']}")
    recorded = {Path(i["path"]).name for i in record["outputs"]}
    folder = proof_path.parent
    extra = [p.name for p in output_files(folder) if p.name not in recorded]
    for name in extra:
        print(f"{'EXTRA':8} output {name}")
    problems += len(extra)
    print("All files match the proof record." if problems == 0 else f"{problems} difference(s) found.")
    return 0 if problems == 0 else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verify", type=Path, help="Check an existing PROOF.json instead of running")
    parser.add_argument("--output", type=Path, help="New folder the command writes its outputs to")
    parser.add_argument("--script", type=Path, action="append", default=[], help="Script file to fingerprint (repeatable)")
    parser.add_argument("--input", type=Path, action="append", default=[], help="Input data file to fingerprint (repeatable)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run, after --")
    args = parser.parse_args(argv)
    if args.verify:
        return verify(args.verify)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not args.output or not command:
        parser.error("--output and a command after -- are required (or use --verify)")
    return record_run(command, args.output, args.script, args.input)


if __name__ == "__main__":
    sys.exit(main())
