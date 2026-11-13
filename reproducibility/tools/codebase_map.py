"""Map the repository's Python files and locate every formula in the code.

AI-written (Claude, 13 November 2026). Read-only: it parses source files and
writes a JSON map to a new folder. Line numbers and code excerpts are read from
the files themselves, so the study page never relies on typed line numbers.

Usage (from reproducibility/):
  python tools/codebase_map.py --output results/codebase-map-001

Outputs:
  files.json     every Python file: layer, lines, first docstring line,
                 authorship statement found in its header (or "not stated"),
                 top-level functions with line numbers
  formulas.json  each registered formula: file, function, line, exact code line
The script stops if a registered formula can no longer be found.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # bev-research/
WS = "reproducibility/data/workspace"

LAYERS = [
    ("1 Original study code (15–27 Oct 2026)", [f"{WS}/**/*.py"]),
    ("2 Reproduction package", ["reproducibility/src/**/*.py", "reproducibility/experiments/A/*.py",
                                "reproducibility/experiments/B/code/*.py", "reproducibility/tools/audit_*.py",
                                "reproducibility/tools/plot_saved_results.py", "reproducibility/tests/*.py",
                                "reproducibility/tools/test_audit_ml.py", "reproducibility/data/tum/*.py"]),
    ("3 Root NumPy reconstruction (28 Oct 2026)", ["src/**/*.py", "experiments/*.py", "code/*.py", "tests/*.py"]),
    ("4 New checks and experiments (9–13 Nov 2026)", ["reproducibility/tools/run_with_proof.py", "reproducibility/tools/check_claims.py",
                                                     "reproducibility/tools/forecast_r2.py", "reproducibility/tools/codebase_map.py",
                                                     "reproducibility/tools/walkthrough_equations.py", "reproducibility/tools/refit_cell_model_check.py",
                                                     "reproducibility/tools/test_check_claims.py", "reproducibility/tools/test_run_with_proof.py",
                                                     "reproducibility/experiments/A_lab/**/*.py"]),
]

# (group, label, file, function, text that must appear on the line)
FORMULAS = [
    ("Haulage set-up", "Battery size, mass and power scale together", f"{WS}/New_Afton_Experiments_2026-10-20/code/study.py", "pack", "capacity_kwh=354*s"),
    ("Haulage set-up", "Wheel power cap = 0.85 × (battery power − 20 kW), max 391 kW", f"{WS}/New_Afton_Experiments_2026-10-20/code/study.py", "pack", "wheel_kw=min(391"),
    ("Haulage set-up", "Pulling force curve: min(300 kN, power ÷ speed)", f"{WS}/New_Afton_Experiments_2026-10-20/code/study.py", "make", "curve="),
    ("Haulage set-up", "Rolling resistance written into every road arc", f"{WS}/New_Afton_Experiments_2026-10-20/code/study.py", "make", "RollingResistance"),
    ("Reserve accounting", "Reserve budget = (80% − 20%) × capacity", "reproducibility/src/bev_research/haulage.py", "reserve_score", "budget ="),
    ("Reserve accounting", "Cut-off inside the last event, in proportion", "reproducibility/src/bev_research/haulage.py", "reserve_score", "cutoff = row"),
    ("Reserve accounting", "A delivery counts only if a full unload finishes before the cut-off", "reproducibility/src/bev_research/haulage.py", "completed_deliveries", "ElapsedTime\"] >= 1.0"),
    ("Reserve accounting", "Cycle energy between two completed unloads", "reproducibility/src/bev_research/haulage.py", "complete_cycles", "integrate_energy(events, a, b)"),
    ("Equation 1", "Power = energy ÷ time (original)", f"{WS}/APCOM_Study_2026-10-22/code/thermal_analysis.py", "prepare_events", "power_kw="),
    ("Equation 1", "Power = energy ÷ time (root version)", "src/bev_research/thermal.py", "mean_power_kw", "return"),
    ("Equation 2", "Equivalent current I = 2.5 × P ÷ E (original)", f"{WS}/APCOM_Study_2026-10-22/code/thermal_analysis.py", "equivalent_current", "return"),
    ("Equation 2", "Equivalent current (reproduction package)", "reproducibility/src/bev_research/thermal_model.py", "equivalent_current", "return"),
    ("Equation 2", "Equivalent current (root version)", "src/bev_research/thermal.py", "equivalent_current", "return"),
    ("Equation 3", "Heat balance used to fit a and b", f"{WS}/APCOM_Coupled_Thermal_2026-10-16/code/fit_model.py", "predict", "eq=air"),
    ("Equation 3", "Fit: a and b kept positive by fitting their logarithms", f"{WS}/APCOM_Coupled_Thermal_2026-10-16/code/fit_model.py", None, "a,b=np.exp(fit.x)"),
    ("Equation 4", "Exact step solution (original)", f"{WS}/APCOM_Study_2026-10-22/code/thermal_analysis.py", "exact_step", "expm1"),
    ("Equation 4", "Exact step solution (reproduction package)", "reproducibility/src/bev_research/thermal_model.py", "step", "return"),
    ("Equation 4", "Exact step solution (root version)", "src/bev_research/thermal.py", "step", "return"),
    ("Equation 5", "Ceiling ΔT∞ = a·I²/b (reproduction package)", "reproducibility/src/bev_research/thermal_model.py", "equilibrium_rise_c", "return"),
    ("Equation 5", "Ceiling ΔT∞ (root version)", "src/bev_research/thermal.py", "equilibrium_rise", "return"),
    ("Equation 5", "Time constant τ = 1/b", "reproducibility/src/bev_research/thermal_model.py", "time_constant_s", "1./self.b"),
    ("Forecasting (Experiment A)", "20 clues: last, mean, min, max, slope, last change", "reproducibility/experiments/A/train.py", "features_at", "row.extend((col[-1]"),
    ("Forecasting (Experiment A)", "60-second slope by least squares", "reproducibility/experiments/A/train.py", "features_at", "slopes ="),
    ("Forecasting (Experiment A)", "Target = temperature change over the horizon", "reproducibility/experiments/A/train.py", "build_examples", "delta.append(target - temp)"),
    ("Forecasting (Experiment A)", "Physics-hold forecast (Equation 4 with current held)", "reproducibility/experiments/A/train.py", "physics_forecast", "expm1"),
    ("Forecasting (Experiment A)", "Ridge: standardize, then penalized linear fit", "reproducibility/experiments/A/train.py", "estimator", "Ridge(alpha"),
    ("Forecasting (Experiment A)", "Gradient boosting settings", "reproducibility/experiments/A/train.py", "estimator", "HistGradientBoostingRegressor("),
    ("Forecasting (Experiment A)", "Hide one configuration; 4 inner folds of 2", "reproducibility/experiments/A/train.py", "nested_group_plan", "validation = train[i::4]"),
    ("Forecasting (Experiment A)", "RMSE and MAE", "reproducibility/experiments/A/train.py", "error_metrics", "rmse_c"),
    ("Forecasting (Experiment A)", "R² = 1 − SSE / SST (new, 13 Nov)", "reproducibility/tools/forecast_r2.py", "stats", "1 - sse / sst"),
    ("Forecasting (root version)", "Ridge solved in closed form", "src/bev_research/models.py", "ridge_fit", "np.linalg.solve"),
    ("Forecasting (root version)", "Hand-written boosting: add 0.08 × each new tree", "src/bev_research/models.py", "gbt_fit", "learning_rate * _apply"),
    ("Warning rules (Experiment B)", "60-second slope in °C per minute", "reproducibility/experiments/B/code/rules.py", "trailing_rate", "18910"),
    ("Warning rules (Experiment B)", "Alarm only after 5 s above the threshold", "reproducibility/experiments/B/code/rules.py", "alarm_response", "t-start>=5."),
]


def header_info(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    head = "\n".join(text.splitlines()[:20])
    first = ""
    try:
        doc = ast.get_docstring(ast.parse(text))
        first = (doc or "").strip().splitlines()[0] if doc else ""
    except SyntaxError:
        doc = None
    found = re.search(r"([^\n]*\b(?:AI-written|AI-assisted|AI-generated|AI adapted|Claude|Codex)\b[^\n]*)", head)
    authorship = found.group(1).strip(" #\"") if found else "not stated in header"
    funcs = []
    try:
        for node in ast.parse(text).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                funcs.append({"name": node.name, "line": node.lineno})
    except SyntaxError:
        pass
    return {"lines": len(text.splitlines()), "summary": first, "authorship": authorship, "definitions": funcs}


def locate(path: Path, func: str | None, needle: str):
    lines = path.read_text(encoding="utf-8").splitlines()
    if func is None:
        hits = [i for i, line in enumerate(lines, 1) if needle in line]
        if not hits:
            raise SystemExit(f"Formula text {needle!r} not found in {path}")
        return None, hits[0], lines[hits[0] - 1].strip()
    for node in ast.walk(ast.parse("\n".join(lines))):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            for i in range(node.lineno, node.end_lineno + 1):
                if needle in lines[i - 1]:
                    return node.lineno, i, lines[i - 1].strip()
            raise SystemExit(f"{needle!r} not found inside {func}() in {path}")
    raise SystemExit(f"Function {func}() not found in {path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output folder already exists: {args.output}")
    files, seen = [], set()
    for layer, patterns in LAYERS:
        for pattern in patterns:
            for path in sorted(ROOT.glob(pattern)):
                rel = path.relative_to(ROOT).as_posix()
                if rel in seen or "__pycache__" in rel:
                    continue
                seen.add(rel)
                files.append({"layer": layer, "path": rel, **header_info(path)})
    formulas = []
    for group, label, rel, func, needle in FORMULAS:
        start, line, code = locate(ROOT / rel, func, needle)
        formulas.append({"group": group, "label": label, "file": rel, "function": func,
                         "function_line": start, "line": line, "code": code})
    args.output.mkdir(parents=True)
    (args.output / "files.json").write_text(json.dumps(files, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.output / "formulas.json").write_text(json.dumps(formulas, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(files)} files, {len(formulas)} formulas located -> {args.output}")


if __name__ == "__main__":
    main()
