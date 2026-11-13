"""The 20 forecast inputs, computed from the last 61 one-second sensor samples.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

This is a dependency-free copy of ``stable_features`` in
reproducibility/experiments/A_causal/inputs.py, which built the inputs of the
paper's Table 2 run. The arithmetic is kept step for step (12-decimal rounding,
centred ``math.fsum`` slope) so that both give bit-identical values; the tests
replay the saved run to prove it.
"""
import math

HISTORY = 61          # samples: t-60 ... t
DECIMALS = 12
SLOPE_DENOMINATOR = 18910.   # sum of (i - 30)^2 for i = 0..60

SIGNALS = ("temperature_c", "equivalent_current_a", "air_c")
STATS = ("last", "mean", "minimum", "maximum", "slope_per_s", "last_difference")
FEATURE_NAMES = [f"{s}_{k}" for s in SIGNALS for k in STATS] + ["capacity_kwh", "rolling_resistance_pct"]

# Positions used by the baselines.
TEMPERATURE_LAST, TEMPERATURE_SLOPE, CURRENT_LAST, AIR_LAST = 0, 4, 6, 12


def history_features(history, capacity_kwh, rr_pct):
    """history: 61 rows of (temperature_c, equivalent_current_a, air_c), oldest first."""
    rows = [tuple(float(v) for v in r) for r in history]
    if len(rows) != HISTORY or any(len(r) != 3 for r in rows):
        raise ValueError("Expected 61 three-channel history samples")
    if not all(math.isfinite(v) for r in rows for v in r):
        raise ValueError("History contains a non-finite reading")
    if not math.isfinite(capacity_kwh) or capacity_kwh <= 0 or not math.isfinite(rr_pct):
        raise ValueError("Invalid configuration")
    row = []
    for j in range(3):
        col = [round(r[j], DECIMALS) for r in rows]
        # Subtracting the last value makes a constant channel exactly zero before summation.
        slope = math.fsum((i - 30) * (v - col[-1]) for i, v in enumerate(col)) / SLOPE_DENOMINATOR
        row.extend([col[-1], math.fsum(col) / HISTORY, min(col), max(col), slope, col[-1] - col[-2]])
    row.extend([float(capacity_kwh), float(rr_pct)])
    return [round(float(v), DECIMALS) + 0. for v in row]
