"""Reference predictors the learned models must beat to be worth anything.

All three predict the CHANGE in temperature over the horizon, matching the
target built in :mod:`bev_research.features`.

These are not strawmen. On the measured A123 cell, persistence beats both
learned models from 2 to 10 minutes. The learned models win only on the
synthetic traces, where the target is the deterministic output of a known
equation and there is an equation to rediscover.
"""
from __future__ import annotations

import numpy as np

from .config import A_COEF, B_COEF


def persistence(n_origins: int) -> np.ndarray:
    """Predict no change. The honest floor for any forecasting claim."""
    return np.zeros(n_origins, dtype=float)


def linear_trend(temperature_slope_c_per_s: np.ndarray,
                 horizon_s: float) -> np.ndarray:
    """Extrapolate the causal 60 s slope forward.

    Degrades badly at long horizons on a saturating response: a straight line
    keeps climbing while the true curve flattens toward equilibrium. At the
    10 minute horizon this baseline is worse than persistence.
    """
    return np.asarray(temperature_slope_c_per_s, dtype=float) * horizon_s


def physics_hold(temperature_now_c: np.ndarray, current_now_a: np.ndarray,
                 air_now_c: np.ndarray, horizon_s: float) -> np.ndarray:
    """Run the frozen thermal model forward with the inputs frozen at the origin.

    This is the strongest baseline at short horizons because the model is
    correct. It degrades at long horizons for a different reason than the trend
    baseline: the equation is right, but holding the current fixed is wrong
    once the duty cycle moves to another event.
    """
    temperature_now_c = np.asarray(temperature_now_c, dtype=float)
    steady = A_COEF * np.asarray(current_now_a, dtype=float) ** 2 / B_COEF
    asymptote = np.asarray(air_now_c, dtype=float) + steady
    decayed = asymptote + (temperature_now_c - asymptote) * np.exp(
        -B_COEF * horizon_s)
    return decayed - temperature_now_c


def all_baselines(design: np.ndarray, names: list[str], horizon_s: float
                  ) -> dict[str, np.ndarray]:
    """Compute all three baselines from a design matrix built by `features`."""
    col = {name: design[:, i] for i, name in enumerate(names)}
    return {
        "persistence": persistence(design.shape[0]),
        "linear_trend": linear_trend(col["T_slope"], horizon_s),
        "physics_hold": physics_hold(col["T_last"], col["I_last"],
                                     col["A_last"], horizon_s),
    }
