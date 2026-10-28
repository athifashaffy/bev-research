"""Causal feature construction for the forecasting experiments.

Every feature is computed from a backward-looking window only. No feature may
use a sample at or after the forecast origin, because a warning system running
on a truck cannot see the future. This is enforced structurally here rather
than checked afterwards.
"""
from __future__ import annotations

import numpy as np

from .config import HISTORY_S

SUMMARY_NAMES = ("last", "mean", "min", "max", "slope", "fd")


def window_summaries(windows: np.ndarray, prefix: str
                     ) -> list[tuple[str, np.ndarray]]:
    """Six summaries of a stack of equal-length causal windows.

    ``windows`` has shape (n_origins, window_length). The slope is a
    least-squares fit over the window in units per sample, which equals units
    per second on a 1 Hz grid.
    """
    windows = np.asarray(windows, dtype=float)
    n = windows.shape[1]
    centred = np.arange(n, dtype=float)
    centred -= centred.mean()
    denom = (centred ** 2).sum()
    slope = ((windows - windows.mean(axis=1, keepdims=True)) * centred
             ).sum(axis=1) / denom
    return [
        ("%s_last" % prefix, windows[:, -1]),
        ("%s_mean" % prefix, windows.mean(axis=1)),
        ("%s_min" % prefix, windows.min(axis=1)),
        ("%s_max" % prefix, windows.max(axis=1)),
        ("%s_slope" % prefix, slope),
        ("%s_fd" % prefix, windows[:, -1] - windows[:, 0]),
    ]


def build_design(temperature_c: np.ndarray, current_a: np.ndarray,
                 air_c: np.ndarray, horizon_s: int,
                 capacity_kwh: float, rr_percent: float,
                 history_s: int = HISTORY_S):
    """Design matrix and target for one configuration at one horizon.

    The target is the CHANGE in temperature over the horizon, not the absolute
    temperature. Predicting the change keeps every method on the same footing:
    a model that learns nothing still predicts zero, which is exactly the
    persistence baseline.

    Returns ``(X, y, names, origins)`` where ``origins`` indexes the "now"
    sample of each row on the input grid.
    """
    temperature_c = np.asarray(temperature_c, dtype=float)
    n = len(temperature_c)
    origins = np.arange(history_s, n - horizon_s)
    if origins.size == 0:
        return None

    idx = origins[:, None] + np.arange(-history_s, 1)[None, :]
    feats = (window_summaries(temperature_c[idx], "T")
             + window_summaries(np.asarray(current_a, dtype=float)[idx], "I")
             + window_summaries(np.asarray(air_c, dtype=float)[idx], "A"))

    names = [k for k, _ in feats] + ["capacity_kwh", "rr_percent"]
    cols = [v for _, v in feats] + [
        np.full(origins.size, float(capacity_kwh)),
        np.full(origins.size, float(rr_percent)),
    ]
    design = np.column_stack(cols)
    target = temperature_c[origins + horizon_s] - temperature_c[origins]
    return design, target, names, origins
