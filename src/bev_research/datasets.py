"""Loaders for the committed derived data.

Everything here reads from ``data/derived``, which contains outputs computed by
this study. No loader in this module touches licence-restricted third-party
records: those live under ``data/raw``, which is not committed. See
``data/README.md`` for the DOIs and the checksum manifest.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .config import EXP_A_DIR, EXP_B_DIR, MANIFEST, THERMAL_DIR


def _read(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            "%s not found. Run from the repository root, or see data/README.md"
            % path)
    return pd.read_csv(path, encoding="utf-8-sig")


# ------------------------------------------------------------------ thermal
def nominal_traces(case: str | None = None) -> pd.DataFrame:
    """Full generated traces, 45,094 samples across nine configurations.

    Adds an ``air_c`` column, since the stored file carries temperature and
    rise but not air directly.
    """
    frame = _read(os.path.join(THERMAL_DIR, "nominal_traces_all_cases.csv"))
    frame["air_c"] = frame["temperature_c"] - frame["rise_c"]
    if case is not None:
        frame = frame[frame["case"] == case].copy()
        if frame.empty:
            raise KeyError("no case named %r" % case)
    return frame.sort_values("time_s").reset_index(drop=True)


def reserve_summary() -> pd.DataFrame:
    """Nine configurations, each run to its own 60 % reserve endpoint."""
    return _read(os.path.join(THERMAL_DIR, "table2_nominal_reserve.csv"))


def common_window() -> pd.DataFrame:
    """The same nine on one shared 68.0389726 minute window."""
    return _read(os.path.join(THERMAL_DIR, "table2_common_window.csv"))


def operations_comparison() -> pd.DataFrame:
    return _read(os.path.join(THERMAL_DIR, "operations_comparison.csv"))


def sensitivity_envelopes() -> pd.DataFrame:
    """729 assumed variants: 81 per configuration across a, b and heating."""
    return _read(os.path.join(THERMAL_DIR, "sensitivity_envelopes.csv"))


def frozen_rule_summary() -> pd.DataFrame:
    """Rule screening over the modelled normal trajectories."""
    return _read(os.path.join(THERMAL_DIR, "frozen_rule_summary.csv"))


# ------------------------------------------------------------- experiment A
def pooled_metrics() -> pd.DataFrame:
    """Table 4: pooled RMSE and MAE, five methods by four horizons."""
    return _read(os.path.join(EXP_A_DIR, "table4_pooled_metrics.csv"))


def per_case_metrics() -> pd.DataFrame:
    """180 fold-level rows behind Table 4."""
    return _read(os.path.join(EXP_A_DIR, "per_case_metrics.csv"))


def predictions() -> pd.DataFrame:
    """83,980 stored predictions, gzip compressed."""
    path = os.path.join(EXP_A_DIR, "predictions.csv.gz")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return pd.read_csv(path, compression="gzip")


# ------------------------------------------------------------- experiment B
def rule_response_table() -> pd.DataFrame:
    """Table 5. Lead time, misses and false-alarm rate read UNAVAILABLE."""
    return _read(os.path.join(EXP_B_DIR, "table5_rule_response.csv"))


def rule_responses() -> pd.DataFrame:
    """Per-record, per-rule responses behind Table 5."""
    return _read(os.path.join(EXP_B_DIR, "rule_responses.csv"))


# --------------------------------------------------------------- provenance
def source_checksums() -> pd.DataFrame:
    """SHA-256 for all 43 third-party source files, for verifying your copy."""
    import json
    with open(os.path.join(MANIFEST, "source_checksums.json"),
              encoding="utf-8") as handle:
        return pd.DataFrame(json.load(handle))


def tum_channel_index() -> pd.DataFrame:
    """Metadata for the six TUM channels. One module, dependent channels."""
    return _read(os.path.join(MANIFEST, "tum_channel_index.csv"))


def event_register() -> pd.DataFrame:
    """Why no verified onset time exists for any record."""
    return _read(os.path.join(MANIFEST, "event_register.csv"))


def case_grid() -> list[tuple[str, float, float]]:
    """(case, capacity_kwh, rr_percent) for the nine configurations."""
    frame = reserve_summary()
    return [(r["case"], float(r["capacity_kwh"]), float(r["rr_percent"]))
            for _, r in frame.iterrows()]
