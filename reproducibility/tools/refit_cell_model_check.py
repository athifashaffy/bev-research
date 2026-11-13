"""Refit the two heat-equation coefficients from the lab pulse record and compare with the frozen values.

AI-written (Claude, 12 November 2026). Read-only check: it loads the three
archived A123 .mat records, repeats the documented fit rule (full pulse record,
time-weighted least squares, positive parameters) in its own code, and prints
the result. It writes no files and does not run the archived fit script, which
would write into the data folder. Needs NumPy and SciPy.

Usage (from reproducibility/):
  python tools/refit_cell_model_check.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.optimize import least_squares

BASE = Path(__file__).resolve().parents[1] / "data/workspace/APCOM_Coupled_Thermal_2026-10-16"
RECORDS = ["A002_PeriodicPulseData.mat", "A002_UDDS_P25.mat", "A002_UDDS_P35.mat"]


def read(name):
    d = loadmat(BASE / "sources" / name, simplify_cells=True)["Data"]
    t = np.asarray(d["time"], float)
    temp = d.get("SurfaceTemperature", d.get("Ts1", d.get("Ts")))
    air = d.get("AirTemperature", d.get("Tf"))
    return t - t[0], np.asarray(d["current"], float), np.asarray(temp, float), np.asarray(air, float)


def simulate(t, current, air, start, a, b):
    """Equation (5) between consecutive readings, holding each reading's current and air until the next."""
    out = np.empty(len(t))
    out[0] = start
    decay = np.exp(-b * np.diff(t))
    settle = air[:-1] + a / b * current[:-1] ** 2
    for k in range(len(decay)):
        out[k + 1] = decay[k] * out[k] + (1 - decay[k]) * settle[k]
    return out


def main():
    frozen = json.loads((BASE / "results/frozen_cell_model.json").read_text(encoding="utf-8"))
    t, i, y, air = read(RECORDS[0])
    w = np.sqrt(np.r_[np.diff(t)[0], np.diff(t)] / np.mean(np.diff(t)))
    fit = least_squares(lambda p: (simulate(t, i, air, y[0], *np.exp(p)) - y) * w, np.log([1e-4, 1e-3]),
                        bounds=(np.log([1e-8, 1e-6]), np.log([0.1, 1.0])), xtol=1e-11, ftol=1e-11, gtol=1e-11)
    a, b = np.exp(fit.x)
    print(f"refit   a = {a:.12e} K/(A^2 s)   b = {b:.12e} 1/s   time constant = {1 / b:.2f} s")
    print(f"frozen  a = {frozen['a_K_per_A2_s']:.12e} K/(A^2 s)   b = {frozen['b_per_s']:.12e} 1/s")
    rel = max(abs(a / frozen["a_K_per_A2_s"] - 1), abs(b / frozen["b_per_s"] - 1))
    print(f"largest relative difference = {rel:.1e}")
    print("\nHow well the frozen formula follows each measured record (time-weighted):")
    for name in RECORDS:
        t, i, y, air = read(name)
        err = (simulate(t, i, air, y[0], frozen["a_K_per_A2_s"], frozen["b_per_s"]) - y)[1:]
        rmse = float(np.sqrt(np.average(err ** 2, weights=np.diff(t))))
        print(f"  {name:<28} RMSE = {rmse:.3f} C   measured temperature swing = {np.ptp(y):.2f} C")
    return 0 if rel < 1e-6 else 1


if __name__ == "__main__":
    sys.exit(main())
