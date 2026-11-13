"""Equation (2) and the thermal baseline (Equation (5) with current held).

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

Dependency-free copies of the formulas in reproducibility/experiments/A_live/
telemetry.py (Eq. 2) and reproducibility/experiments/A/train.py
(``physics_forecast``). ``current * current`` matches NumPy's square used there.
"""
import math

REFERENCE_CELL_AH = 2.5


def equivalent_current(pack_power_kw, capacity_kwh):
    """Equation (2): current of a 2.5 Ah reference cell at the pack's C-rate.

    An assumed mapping (nominal voltage, equal current sharing), not a measured
    cell current.
    """
    if not capacity_kwh > 0:
        raise ValueError("capacity_kwh must be positive")
    return REFERENCE_CELL_AH * pack_power_kw / capacity_kwh


def thermal_hold(temperature_c, current_a, air_c, horizon_s, a, b):
    """Equation (5) run for the whole horizon with today's current and air held."""
    if b == 0:
        return temperature_c + a * (current_a * current_a) * horizon_s
    return temperature_c + (air_c - temperature_c + a * (current_a * current_a) / b) * (-math.expm1(-b * horizon_s))
