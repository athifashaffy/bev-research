"""Step-by-step hand check of the paper's Equations (1)-(5) and Table 1.

AI-written (Claude, 12 November 2026) so the author can rerun every step.
It uses only the Python standard library and its own arithmetic: it does not
import the repository's haulage, thermal or forecasting code. It opens the
archived HAULSIM result files read-only, writes nothing, and prints its working.

Usage (from reproducibility/):
  python tools/walkthrough_equations.py                 # central case C100_RR03
  python tools/walkthrough_equations.py --case C080_RR04

The PAPER_TABLE1 values were typed from the Google Doc as read on 12 Nov 2026.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data/workspace"
NATIVE = ROOT / "New_Afton_Experiments_2026-10-20"
MODEL = ROOT / "APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json"
Q_REF_AH = 2.5          # reference-cell charge capacity
AIR_C = 25.0            # air and starting temperature in the standard run
LOAD_T = 45.0           # tonnes per completed delivery
START_SOC, RESERVE_SOC = 0.80, 0.20
# energy kWh, rolling %, mean power kW, cycle energy kWh, reserve min, payload t, peak rise C
PAPER_TABLE1 = {
    "C080_RR02": (283.2, 2, 133.26, 60.57, 72.37, 90, 0.07606), "C080_RR03": (283.2, 3, 141.73, 66.09, 70.06, 90, 0.08464),
    "C080_RR04": (283.2, 4, 149.84, 71.62, 68.04, 90, 0.09318), "C100_RR02": (354.0, 2, 149.44, 61.03, 88.34, 135, 0.06056),
    "C100_RR03": (354.0, 3, 159.39, 66.79, 85.60, 135, 0.06804), "C100_RR04": (354.0, 4, 168.80, 72.41, 71.88, 90, 0.07541),
    "C120_RR02": (424.8, 2, 150.80, 62.19, 108.09, 180, 0.04295), "C120_RR03": (424.8, 3, 160.73, 67.92, 93.35, 135, 0.04811),
    "C120_RR04": (424.8, 4, 170.26, 73.65, 90.63, 135, 0.05328)}


def load_events(case: str) -> list[dict]:
    """Truck activity rows exactly as stored: start and duration in minutes, energy in kWh."""
    path = (NATIVE / "results" / case / "native_run.hsmdb").resolve()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT SimulationTime, ElapsedTime, ElectricityFromBatteryConsumed, State "
                          "FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime, Id").fetchall()
    return [{"start": float(s), "dur": float(d), "end": float(s) + float(d), "energy": float(e), "state": st} for s, d, e, st in rows]


def capacities() -> dict:
    manifest = json.loads((NATIVE / "run_manifest.json").read_text(encoding="utf-8"))
    return {c["id"]: float(c["capacity_kwh"]) for c in manifest["cases"] if c["id"] in PAPER_TABLE1}


def power_kw(event: dict) -> float:
    """Equation (1): P = 60 E / dt, with E in kWh and dt in minutes."""
    return 60.0 * event["energy"] / event["dur"]


def reserve_cutoff_min(events: list[dict], capacity: float) -> float:
    """Minute at which cumulative energy reaches (0.80 - 0.20) x nominal energy."""
    budget, used = (START_SOC - RESERVE_SOC) * capacity, 0.0
    for e in events:
        if e["energy"] > 0 and used + e["energy"] >= budget:
            return e["start"] + (budget - used) / e["energy"] * e["dur"]   # constant power inside the activity
        used += e["energy"]
    return events[-1]["end"]


def energy_until(events: list[dict], minute: float) -> float:
    total = 0.0
    for e in events:
        if e["end"] <= minute:
            total += e["energy"]
        elif e["start"] < minute:
            total += e["energy"] * (minute - e["start"]) / e["dur"]
    return total


def cycle_energy(events: list[dict]) -> float:
    """Energy from the end of one completed unload to the end of the next (first full cycle)."""
    ends = [e["end"] for e in events if e["state"] == "Unloading"]
    return sum(e["energy"] for e in events if e["start"] >= ends[0] - 1e-9 and e["end"] <= ends[1] + 1e-9)


def step(rise: float, current: float, seconds: float, a: float, b: float, g: float = 1.0) -> float:
    """Equation (5) written for the rise above air: rise' = rise e^(-b dt) + (g a I^2 / b)(1 - e^(-b dt))."""
    decay = math.exp(-b * seconds)
    return rise * decay + g * a * current ** 2 / b * (1.0 - decay)


def rise_at(events: list[dict], capacity: float, second: float, a: float, b: float, g: float = 1.0) -> float:
    rise = 0.0
    for e in events:
        current = Q_REF_AH * power_kw(e) / capacity                      # Equation (2)
        start_s, end_s = e["start"] * 60.0, e["end"] * 60.0
        if second <= start_s:
            break
        rise = step(rise, current, min(second, end_s) - start_s, a, b, g)
    return rise


def table_row(case: str, events: list[dict], capacity: float, common_min: float, a: float, b: float) -> tuple:
    cutoff = reserve_cutoff_min(events, capacity)
    payload = LOAD_T * sum(1 for e in events if e["state"] == "Unloading" and e["end"] <= cutoff)
    mean_power = energy_until(events, common_min) / (common_min / 60.0)
    peak = max(rise_at(events, capacity, s, a, b) for s in range(int(math.floor(common_min * 60.0)) + 1))
    return mean_power, cycle_energy(events), cutoff, payload, peak


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", default="C100_RR03", choices=sorted(PAPER_TABLE1))
    args = parser.parse_args(argv)
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    a, b = model["a_K_per_A2_s"], model["b_per_s"]
    caps = capacities()
    all_events = {c: load_events(c) for c in PAPER_TABLE1}
    common = min(reserve_cutoff_min(all_events[c], caps[c]) for c in PAPER_TABLE1)
    case, events, cap = args.case, all_events[args.case], caps[args.case]

    print(f"=== {case}: nominal battery energy {cap} kWh, {len(events)} truck activities ===\n")
    print("EQUATION (1)  P = 60 E / dt        and        EQUATION (2)  I_eq = 2.5 Ah x P / E_nom")
    print(f"{'start min':>9} {'dur min':>8} {'state':<17} {'E kWh':>8} {'P kW':>8} {'I_eq A':>7} {'used kWh':>9}")
    used = 0.0
    for e in events:
        used += e["energy"]
        p = power_kw(e)
        print(f"{e['start']:9.3f} {e['dur']:8.3f} {e['state']:<17} {e['energy']:8.3f} {p:8.2f} {Q_REF_AH * p / cap:7.3f} {used:9.2f}")
    hardest = max((e for e in events if e["start"] < reserve_cutoff_min(events, cap)), key=power_kw)
    i_max = Q_REF_AH * power_kw(hardest) / cap
    print(f"\nHardest activity before the reserve: {hardest['state']}, P = 60 x {hardest['energy']:.3f} / {hardest['dur']:.3f} = {power_kw(hardest):.2f} kW")
    print(f"  I_eq = 2.5 x {power_kw(hardest):.2f} / {cap} = {i_max:.3f} A")

    budget = (START_SOC - RESERVE_SOC) * cap
    cutoff = reserve_cutoff_min(events, cap)
    print(f"\nENERGY RESERVE  budget = (0.80 - 0.20) x {cap} = {budget:.2f} kWh")
    print(f"  cumulative energy reaches the budget at minute {cutoff:.2f} (reserve time)")
    done = [e for e in events if e["state"] == "Unloading" and e["end"] <= cutoff]
    print(f"  unloads finished before that: {len(done)}  ->  payload = {len(done)} x 45 = {45 * len(done)} t")
    print(f"  earliest reserve time of all nine cases = {common:.2f} min (the common comparison period)")
    e_common = energy_until(events, common)
    print(f"  energy used in the common period = {e_common:.3f} kWh -> mean power = {e_common:.3f} / ({common:.3f}/60) = {e_common / (common / 60):.2f} kW")
    print(f"  energy of one full cycle (unload end to next unload end) = {cycle_energy(events):.2f} kWh")

    print(f"\nEQUATIONS (3)-(5)  a = {a:.9e} K/(A^2 s), b = {b:.12f} 1/s")
    print(f"  time constant 1/b = {1 / b:.1f} s = {1 / b / 60:.2f} min;  1 - e^-1 = {100 * (1 - math.exp(-1)):.1f} %")
    print(f"  steady rise at {i_max:.2f} A = a I^2 / b = {a:.4e} x {i_max ** 2:.3f} / {b:.6f} = {a * i_max ** 2 / b:.3f} C")
    # Equation (4) integrated in tiny steps against the closed form of Equation (5), first 30 minutes of this case.
    euler, t, dt, k = 0.0, 0.0, 0.01, 0
    while t < 1800.0 - 1e-9:
        while events[k]["end"] * 60.0 <= t + 1e-9:
            k += 1
        current = Q_REF_AH * power_kw(events[k]) / cap
        euler += dt * (a * current ** 2 - b * euler)
        t += dt
    exact = rise_at(events, cap, 1800.0, a, b)
    print(f"  check of the algebra: Equation (4) stepped every 0.01 s for 30 min gives {euler:.6f} C; Equation (5) gives {exact:.6f} C; difference {abs(euler - exact):.1e} C")
    sampled = max(rise_at(events, cap, s, a, b) for s in range(int(math.floor(common * 60)) + 1))
    exact_peak = max(rise_at(events, cap, min(e["end"], common) * 60.0, a, b) for e in events if e["start"] < common)
    print(f"  peak rise over the common period: {sampled:.5f} C at whole seconds; {exact_peak:.5f} C at the exact activity boundary")
    for g in (1.0, 2.0):
        peak = max(rise_at(events, cap, min(e["end"], cutoff) * 60.0, a, b, g) for e in events if e["start"] < cutoff)
        print(f"  peak rise over the run to the reserve with g = {g:g}: {peak:.3f} C")

    print("\nTABLE 1, all nine cases recomputed here (calc) beside the paper (doc)")
    print(f"{'case':<10} {'mean kW':>16} {'cycle kWh':>14} {'reserve min':>15} {'payload t':>11} {'peak rise C':>19}  verdict")
    worst = True
    for c in PAPER_TABLE1:
        calc = table_row(c, all_events[c], caps[c], common, a, b)
        doc = PAPER_TABLE1[c][2:]
        ok = all(abs(x - y) <= 0.5 * 10 ** -d * 1.0000001 for x, y, d in zip(calc, doc, (2, 2, 2, 0, 5)))
        worst &= ok
        print(f"{c:<10} {calc[0]:8.2f}/{doc[0]:<7.2f} {calc[1]:7.2f}/{doc[1]:<6.2f} {calc[2]:8.2f}/{doc[2]:<6.2f} {calc[3]:5.0f}/{doc[3]:<5.0f} {calc[4]:9.5f}/{doc[4]:<9.5f}  {'match' if ok else 'DIFFERS'}")
    print("\nAll Table 1 values match at the printed precision." if worst else "\nAt least one Table 1 value differs.")
    return 0 if worst else 1


if __name__ == "__main__":
    sys.exit(main())
