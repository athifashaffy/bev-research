"""Run every test suite and integrity check in this repository with one command.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

    python scripts/check_all.py            # all suites
    python scripts/check_all.py --list     # show the suites without running them

Each suite runs in its own process with the working directory its README uses.
Nothing here writes inside the repository: outputs go to a temporary folder that
is deleted afterwards. Exit status is non-zero if any suite fails.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPRO = ROOT / "reproducibility"


def suites(tmp):
    py = [sys.executable, "-B"]
    unit = py + ["-m", "unittest", "discover"]
    return [
        # (name, working directory, command, extra environment)
        ("reproducibility package", REPRO, unit + ["-s", "tests"], {"PYTHONPATH": "src"}),
        ("reproducibility tools", REPRO, unit + ["-s", "tools", "-p", "test_*.py"], {}),
        ("TUM CSV preparation", REPRO, unit + ["-s", "data/tum", "-p", "test_prepare_tum_csv.py"], {}),
        ("TUM CSV hashes", REPRO, py + ["data/tum/verify_tum_csv.py", "--dataset", "data/tum/dataset"], {}),
        ("bev-reproduce all", REPRO, py + ["-m", "bev_research.cli", "all", "--output", str(tmp / "reproduce")],
         {"PYTHONPATH": "src"}),
        ("Experiment A", REPRO, unit + ["-s", "experiments/A/tests"], {}),
        ("Experiment A_causal", REPRO, unit + ["-s", "experiments/A_causal/tests"], {}),
        ("Experiment A_live (paper)", REPRO, unit + ["-s", "experiments/A_live/tests"], {}),
        ("Experiment A_lab", REPRO, unit + ["-s", "experiments/A_lab/tests"], {}),
        ("Experiment A_models", REPRO, unit + ["-s", "experiments/A_models/tests"], {}),
        ("Experiment B rules", REPRO / "experiments/B", unit + ["-s", "code", "-p", "test_rules.py"], {}),
        ("NumPy reconstruction", ROOT / "reconstruction", py + ["-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], {}),
        ("Edge forecaster", ROOT / "edge", unit + ["-s", "tests"], {"PYTHONPATH": "src"}),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list the suites and exit")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="bev-checks-") as t:
        plan = suites(Path(t))
        if args.list:
            for name, cwd, cmd, env in plan:
                print(f"{name:28} (in {cwd.relative_to(ROOT)}) {' '.join(cmd[1:])}")
            return 0
        results = []
        for name, cwd, cmd, env in plan:
            start = time.perf_counter()
            proc = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True)
            seconds = time.perf_counter() - start
            results.append((name, proc.returncode == 0, seconds))
            print(f"{'PASS' if proc.returncode == 0 else 'FAIL'}  {name:28} {seconds:6.1f} s", flush=True)
            if proc.returncode:
                print("      " + (proc.stdout + proc.stderr).strip().replace("\n", "\n      ")[-4000:])
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} suites passed"
          + (f"; failed: {', '.join(failed)}" if failed else "."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
