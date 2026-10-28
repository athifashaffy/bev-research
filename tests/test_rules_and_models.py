"""Tests for the frozen warning rules, the baselines and the learned models."""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from bev_research import baselines, features, metrics, models, rules  # noqa: E402
from bev_research.config import RESIDUAL_LO_C  # noqa: E402


# ----------------------------------------------------------------- rules
def test_seven_frozen_rules():
    found = rules.frozen_rules()
    assert len(found) == 7
    assert sum(r.kind == "fixed" for r in found) == 4
    assert sum(r.kind == "rate" for r in found) == 3


def test_flat_record_never_fires():
    time_s = np.arange(0, 600, 1.0)
    flat = np.full_like(time_s, 25.0)
    assert not any(r["responded"] for r in rules.screen(time_s, flat))


def test_ramp_fires_fixed_rules_in_threshold_order():
    """Hotter thresholds must fire later. Catches an inverted comparison."""
    time_s = np.arange(0, 2000, 1.0)
    temps = 25.0 + time_s * 0.02          # reaches 65 C
    results = {r["rule"]: r for r in rules.screen(time_s, temps)}
    firing = [results["fixed_%gC" % t]["first_response_s"]
              for t in (45, 50, 55, 60)]
    assert all(v is not None for v in firing)
    assert firing == sorted(firing)


def test_debounce_blocks_an_immediate_response():
    """A record that starts already hot must still wait out the debounce."""
    time_s = np.arange(0, 60, 1.0)
    hot = np.full_like(time_s, 99.0)
    result = rules.evaluate(rules.frozen_rules()[0], time_s, hot)
    assert result["responded"]
    assert result["first_response_s"] >= rules.frozen_rules()[0].debounce_s


def test_causal_slope_has_no_lookahead():
    """A step must not raise the slope before it happens."""
    time_s = np.arange(0, 400, 1.0)
    temps = np.where(time_s < 200, 25.0, 60.0)
    slope = rules.causal_slope(time_s, temps)
    assert np.nanmax(slope[time_s < 200]) == pytest.approx(0.0, abs=1e-12)
    assert np.nanmax(slope[time_s >= 200]) > 1.0


def test_slope_window_start_is_not_eligible():
    """Samples without a full 60 s window are NaN, not silently zero."""
    time_s = np.arange(0, 120, 1.0)
    slope = rules.causal_slope(time_s, 25.0 + time_s * 0.01)
    assert np.isnan(slope[:60]).all()
    assert np.isfinite(slope[61:]).all()


def test_known_slope_recovered_in_c_per_min():
    time_s = np.arange(0, 300, 1.0)
    slope = rules.causal_slope(time_s, 25.0 + time_s * (3.0 / 60.0))
    assert np.nanmedian(slope) == pytest.approx(3.0, abs=1e-9)


def test_unavailable_is_a_literal_not_a_number():
    assert rules.UNAVAILABLE == "UNAVAILABLE"
    assert "sensor-clock" in rules.UNAVAILABLE_REASON


# ------------------------------------------------------------- baselines
def test_persistence_predicts_no_change():
    assert np.all(baselines.persistence(10) == 0.0)


def test_trend_extrapolates_linearly():
    out = baselines.linear_trend(np.array([0.001]), 600)
    assert out[0] == pytest.approx(0.6)


def test_physics_hold_relaxes_toward_its_asymptote():
    """Starting above the asymptote, the prediction must be a decrease."""
    out = baselines.physics_hold(np.array([40.0]), np.array([0.0]),
                                 np.array([25.0]), 600)
    assert out[0] < 0


# ---------------------------------------------------------------- models
def _linear_problem(n=400, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    y = 2.0 * x[:, 0] - 1.5 * x[:, 1] + 0.3
    return x, y


def test_ridge_recovers_a_linear_signal():
    x, y = _linear_problem()
    predicted = models.ridge_predict(models.ridge_fit(x, y, 1e-6), x)
    assert metrics.rmse(predicted, y) < 1e-6


def test_ridge_penalty_shrinks_predictions():
    x, y = _linear_problem()
    weak = models.ridge_predict(models.ridge_fit(x, y, 1e-6), x)
    strong = models.ridge_predict(models.ridge_fit(x, y, 1e6), x)
    assert np.std(strong) < np.std(weak)


def test_ridge_intercept_is_unpenalised():
    """Heavy penalty must still centre on the mean, not collapse toward zero."""
    x, y = _linear_problem()
    y = y + 100.0
    strong = models.ridge_predict(models.ridge_fit(x, y, 1e9), x)
    assert np.mean(strong) == pytest.approx(np.mean(y), abs=1e-6)


def test_gbt_beats_the_mean_on_a_nonlinear_signal():
    rng = np.random.default_rng(1)
    x = rng.uniform(-2, 2, size=(600, 2))
    y = np.sin(x[:, 0] * 2.0) + x[:, 1] ** 2
    model = models.gbt_fit(x, y, rounds=60, learning_rate=0.1)
    predicted = models.gbt_predict(model, x)
    assert metrics.rmse(predicted, y) < metrics.rmse(np.full_like(y, y.mean()), y) / 2


def test_lambda_selection_prefers_the_better_penalty():
    x, y = _linear_problem()
    chosen = models.select_lambda(x[:300], y[:300], x[300:], y[300:])
    assert chosen in models.RIDGE_LAMBDAS
    assert chosen <= 1.0           # a clean linear signal needs little penalty


# --------------------------------------------------------------- metrics
def test_rmse_and_mae_are_zero_on_perfect_predictions():
    y = np.array([1.0, 2.0, 3.0])
    assert metrics.rmse(y, y) == 0.0
    assert metrics.mae(y, y) == 0.0


def test_rmse_penalises_outliers_more_than_mae():
    actual = np.zeros(100)
    predicted = np.zeros(100)
    predicted[0] = 10.0
    assert metrics.rmse(predicted, actual) > metrics.mae(predicted, actual)


def test_resolution_floor_matches_the_residual_band():
    assert not metrics.is_resolvable(0.05)
    assert metrics.is_resolvable(RESIDUAL_LO_C)
    assert "below" in metrics.resolution_note(0.005)


# -------------------------------------------------------------- features
def test_design_matrix_is_causal_and_well_formed():
    n = 500
    time_grid = np.arange(n, dtype=float)
    temps = 25.0 + time_grid * 1e-4
    built = features.build_design(temps, np.ones(n), np.full(n, 25.0),
                                  horizon_s=60, capacity_kwh=354.0,
                                  rr_percent=3, history_s=60)
    design, target, names, origins = built
    assert design.shape[0] == target.shape[0] == len(origins)
    assert design.shape[1] == len(names) == 20
    assert origins.min() >= 60                 # never starts before a full window
    assert origins.max() + 60 < n              # never indexes past the end
    assert np.isfinite(design).all()


def test_design_returns_none_when_the_record_is_too_short():
    short = np.full(50, 25.0)
    assert features.build_design(short, np.ones(50), np.full(50, 25.0),
                                 horizon_s=600, capacity_kwh=354.0,
                                 rr_percent=3) is None


def test_target_is_change_not_absolute_temperature():
    n = 400
    temps = np.linspace(25.0, 26.0, n)
    _, target, _, _ = features.build_design(
        temps, np.ones(n), np.full(n, 25.0), 60, 354.0, 3)
    assert target.mean() < 1.0                 # a change, not a 25 C level
    assert target.mean() > 0.0
