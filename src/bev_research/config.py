"""Frozen constants and repository paths.

Every number in this module is fixed by a prior fitting or specification step
and must not be re-tuned by downstream code. Changing any of them invalidates
the archived results, so they live in one place and are imported, never
redefined locally.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------- paths
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(PKG_DIR)
ROOT = os.path.dirname(SRC_DIR)

DATA = os.path.join(ROOT, "data")
DERIVED = os.path.join(DATA, "derived")
MANIFEST = os.path.join(DATA, "manifest")
RAW = os.path.join(DATA, "raw")
FIGURES = os.path.join(ROOT, "figures")

THERMAL_DIR = os.path.join(DERIVED, "thermal")
EXP_A_DIR = os.path.join(DERIVED, "experiment_a")
EXP_B_DIR = os.path.join(DERIVED, "experiment_b")

# ------------------------------------------------------- frozen thermal model
# Lumped single-state surface model fitted to A123 ANR26650M1-B cell records:
#
#     dT/dt = a * I**2 - b * (T - T_air)
#
# Only the two RATIOS are identifiable from this fit. a = R_eff / C_eff and
# b = K_eff / C_eff. Multiplying R, C and K by a common factor leaves the model
# unchanged, so individual physical parameters are NOT recovered by it.
A_COEF = 4.344635339312832e-05   # K / (A**2 * s)
B_COEF = 0.002655462788692412    # 1 / s
TAU_S = 1.0 / B_COEF             # 376.58 s

# Held-out residual error of the measured-cell fit. This is the resolution
# limit of the model: differences smaller than this are not physical findings.
RESIDUAL_LO_C = 0.109
RESIDUAL_HI_C = 0.117

# ------------------------------------------------------------- equivalent cell
# The equivalent-current relation is an ASSUMPTION, not a pack measurement.
# Pack voltage and series/parallel topology are not identified, so I = P / V is
# not claimed. Power per unit of configured energy is matched onto one cell:
#
#     I_equiv = CELL_CAPACITY_AH * P_kW / capacity_kWh
#
# Units work because kW/kWh = 1/h and Ah * 1/h = A.
CELL_CAPACITY_AH = 2.5

# --------------------------------------------------------------- vehicle spec
# Sandvik Z50 battery electric haul truck.
Z50 = {
    "empty_mass_kg": 48_148,
    "loaded_mass_kg": 98_192,
    "payload_t": 45,
    "continuous_power_kw": 480,
    "max_speed_kmh": 14,
    "pack_skid_kg": 8_255,
    "chemistry": "LiFePO4",
}

# ------------------------------------------------------------- operating rule
# External analysis stops at this fraction of nominal capacity, representing an
# 80 % to 20 % state-of-charge excursion. The raw simulation may run past it.
RESERVE_FRACTION = 0.60

# --------------------------------------------------------- temperature screens
# 60 C is a DECLARED STUDY SCREEN, not a Z50 pack or BMS limit. The matching
# A123 ANR26650M1-B datasheet gives -30..+55 C operating and -40..+60 C storage,
# so 55 C is reported alongside it.
STUDY_SCREEN_C = 60.0
DATASHEET_OPERATING_C = 55.0

# ------------------------------------------------------------- experiment grid
CAPACITIES_KWH = (283.2, 354.0, 424.8)
ROLLING_RESISTANCES_PCT = (2, 3, 4)
HORIZONS_S = (60, 120, 300, 600)
HISTORY_S = 60              # causal window length for features
RANDOM_SEED = 20261027      # matches the archived experiment_a protocol

# ------------------------------------------------------------- warning rules
# Seven rules, fixed before any laboratory record was screened. Each needs
# DEBOUNCE_S of elapsed record before it may fire.
FIXED_THRESHOLDS_C = (45.0, 50.0, 55.0, 60.0)
RATE_THRESHOLDS_C_PER_MIN = (1.0, 2.0, 5.0)
RATE_WINDOW_S = 60          # causal backward-looking slope window
DEBOUNCE_S = 5

NOT_MEASURED = (
    "A123-equivalent cell surface from a fitted model. Not a measured or "
    "validated Sandvik Z50 pack, core or hotspot temperature."
)


def thermal_note() -> str:
    """The sentence that has to travel with every temperature this code emits."""
    return NOT_MEASURED
