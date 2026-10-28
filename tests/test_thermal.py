"""Tests for the frozen thermal model.

These check physical and mathematical properties, not just that numbers come
out. A model that passes these cannot be silently wrong in the ways that would
matter: wrong equilibrium, wrong time constant, non-causal behaviour, or an
equivalent-current relation that quietly stops being the documented assumption.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from bev_research import thermal  # noqa: E402
from bev_research.config import A_COEF, B_COEF, CELL_CAPACITY_AH, TAU_S  # noqa: E402

# The archived worked example: native event Id 44, case C100_RR03.
EVENT = dict(duration_s=678.973850730553, energy_kwh=58.927842765108,
             capacity_kwh=354.0, t_start_c=25.000772630233, air_c=25.0,
             saved_end_c=25.066656834106034)


def test_worked_example_reproduces_saved_trace():
    power = EVENT["energy_kwh"] / (EVENT["duration_s"] / 3600.0)
    current = thermal.equivalent_current(power, EVENT["capacity_kwh"])
    end = thermal.step(EVENT["t_start_c"], current, EVENT["duration_s"],
                       EVENT["air_c"])
    assert abs(end - EVENT["saved_end_c"]) < 1e-9


def test_closed_form_matches_numerical_integration():
    power = EVENT["energy_kwh"] / (EVENT["duration_s"] / 3600.0)
    current = thermal.equivalent_current(power, EVENT["capacity_kwh"])
    steps = 50_000
    exact = thermal.step(EVENT["t_start_c"], current, EVENT["duration_s"],
                         EVENT["air_c"])
    approx = thermal.integrate(EVENT["t_start_c"], current,
                               EVENT["duration_s"], EVENT["air_c"], steps)
    tol = thermal.euler_tolerance(current, EVENT["duration_s"], steps)
    assert abs(approx - exact) < tol


def test_zero_duration_is_identity():
    assert thermal.step(30.0, 5.0, 0.0, 25.0) == pytest.approx(30.0)


def test_negative_duration_rejected():
    with pytest.raises(ValueError):
        thermal.step(30.0, 5.0, -1.0, 25.0)


def test_zero_current_decays_to_air():
    """With no heating the surface must relax to air temperature, not past it."""
    end = thermal.step(40.0, 0.0, 10 * TAU_S, 25.0)
    assert 25.0 < end < 25.01


def test_long_hold_reaches_equilibrium():
    current = 2.0
    expected = 25.0 + thermal.equilibrium_rise(current)
    end = thermal.step(25.0, current, 50 * TAU_S, 25.0)
    assert end == pytest.approx(expected, abs=1e-9)


def test_never_overshoots_equilibrium():
    """A first-order lag cannot overshoot. Catches a sign or algebra error."""
    current = 3.0
    ceiling = 25.0 + thermal.equilibrium_rise(current)
    for duration in (1, 10, 100, 1_000, 10_000):
        assert thermal.step(25.0, current, duration, 25.0) <= ceiling + 1e-12


def test_time_constant_covers_63_percent():
    """After one tau the gap to equilibrium must close by 1 - 1/e."""
    current = 2.0
    rise = thermal.step(25.0, current, TAU_S, 25.0) - 25.0
    assert rise / thermal.equilibrium_rise(current) == pytest.approx(
        1 - np.exp(-1), abs=1e-9)


def test_equilibrium_rise_matches_coefficients():
    current = 1.7
    assert thermal.equilibrium_rise(current) == pytest.approx(
        A_COEF * current ** 2 / B_COEF)


def test_equivalent_current_is_the_documented_assumption():
    """Guards the relation itself: I = 2.5 Ah * P / capacity, never P / V."""
    assert thermal.equivalent_current(312.442421348234, 354.0) == pytest.approx(
        CELL_CAPACITY_AH * 312.442421348234 / 354.0)


def test_equivalent_current_scales_inversely_with_capacity():
    assert thermal.equivalent_current(100.0, 300.0) == pytest.approx(
        2 * thermal.equivalent_current(100.0, 600.0))


def test_zero_capacity_rejected():
    with pytest.raises(ValueError):
        thermal.equivalent_current(100.0, 0.0)


def test_replay_carries_temperature_between_events():
    """Events must not reset to air. Catches the most damaging replay bug."""
    events = [thermal.Event(0, 600, 40.0), thermal.Event(600, 1200, 40.0)]
    out = thermal.replay(events, 354.0, air_c=25.0)
    assert out[1] > out[0] > 25.0


def test_replay_single_event_matches_step():
    event = thermal.Event(0.0, EVENT["duration_s"], EVENT["energy_kwh"])
    out = thermal.replay([event], EVENT["capacity_kwh"], air_c=25.0,
                         initial_c=EVENT["t_start_c"])
    assert out[0] == pytest.approx(EVENT["saved_end_c"], abs=1e-9)


def test_resample_holds_current_piecewise_constant():
    """Current is an event average; interpolating it would invent values."""
    time_s = np.array([0.0, 10.0, 20.0])
    grid, temp, cur, air = thermal.resample_to_grid(
        time_s, np.array([25.0, 26.0, 27.0]), np.array([1.0, 5.0, 9.0]),
        np.full(3, 25.0), dt_s=1.0)
    assert set(np.unique(cur)).issubset({1.0, 5.0, 9.0})
    assert cur[5] == 1.0 and cur[15] == 5.0
    assert temp[5] == pytest.approx(25.5)   # temperature IS interpolated
