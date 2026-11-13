"""Error measures, and the resolution limit they have to be read against.

Both RMSE and MAE are reported throughout. They disagree at the one-minute
horizon, where gradient boosting leads on RMSE but the held-input physics
baseline leads on MAE, and reporting only one would have produced a cleaner but
wrong claim.
"""
from __future__ import annotations

import numpy as np

from .config import RESIDUAL_HI_C, RESIDUAL_LO_C


def rmse(predicted: np.ndarray, actual: np.ndarray) -> float:
    predicted, actual = np.asarray(predicted), np.asarray(actual)
    return float(np.sqrt(np.mean((predicted - actual) ** 2)))


def mae(predicted: np.ndarray, actual: np.ndarray) -> float:
    predicted, actual = np.asarray(predicted), np.asarray(actual)
    return float(np.mean(np.abs(predicted - actual)))


def max_abs_error(predicted: np.ndarray, actual: np.ndarray) -> float:
    predicted, actual = np.asarray(predicted), np.asarray(actual)
    return float(np.max(np.abs(predicted - actual)))


def score(predicted: np.ndarray, actual: np.ndarray) -> dict:
    return {
        "rmse_c": rmse(predicted, actual),
        "mae_c": mae(predicted, actual),
        "max_absolute_error_c": max_abs_error(predicted, actual),
        "n": int(len(actual)),
    }


def is_resolvable(error_c: float) -> bool:
    """Is a reported error large enough to be a physical finding?

    The measured-cell fit's own held-out residual is 0.109 to 0.117 degrees C.
    An error below that floor describes how closely a method reproduces the
    study's synthetic generator, not how well it predicts a real temperature.
    """
    return float(error_c) >= RESIDUAL_LO_C


def resolution_note(error_c: float) -> str:
    if is_resolvable(error_c):
        return "at or above the %.3f-%.3f C measured-cell residual band" % (
            RESIDUAL_LO_C, RESIDUAL_HI_C)
    return ("below the %.3f-%.3f C measured-cell residual band; reproduces the "
            "synthetic generator rather than resolving a physical difference"
            % (RESIDUAL_LO_C, RESIDUAL_HI_C))


def pool_by(frame, group_cols, value_cols):
    """Equal-weight mean across held-out units, with the spread retained.

    Reporting the range alongside the mean matters here: a mean that hides a
    threefold spread across configurations would overstate how settled the
    ranking is.
    """
    aggregated = frame.groupby(list(group_cols))[list(value_cols)].agg(
        ["mean", "min", "max", "count"])
    aggregated.columns = ["_".join(c) for c in aggregated.columns]
    return aggregated.reset_index()
