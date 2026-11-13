"""The frozen lumped-surface thermal model.

    dT/dt = a * I**2 - b * (T - T_air)

The first term is ohmic heating, the second is Newtonian cooling to the
surrounding air. For constant current and constant air temperature the equation
has a closed-form solution, which is what the study uses: each simulation event
has a single event-average current, so the trace is an exact piecewise
composition of closed-form segments rather than a numerical integration.

Everything in this module returns A123-equivalent CELL SURFACE temperatures.
They are not measured or validated pack temperatures.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from .config import A_COEF, B_COEF, CELL_CAPACITY_AH, TAU_S


def equivalent_current(power_kw: float | np.ndarray,
                       capacity_kwh: float) -> float | np.ndarray:
    """Assumed equivalent cell current for a given power and pack capacity.

    This matches power per unit of configured energy onto a single
    ``CELL_CAPACITY_AH`` cell. It is NOT ``P / V``: the pack voltage and
    series/parallel topology are not identified, so no pack current is claimed.

    Units: kW / kWh = 1/h, and Ah * 1/h = A.
    """
    if capacity_kwh <= 0:
        raise ValueError("capacity_kwh must be positive, got %r" % capacity_kwh)
    return CELL_CAPACITY_AH * power_kw / capacity_kwh


def equilibrium_rise(current_a: float | np.ndarray) -> float | np.ndarray:
    """Steady-state rise above air if the current were held indefinitely."""
    return A_COEF * np.asarray(current_a) ** 2 / B_COEF


def step(temperature_c: float | np.ndarray,
         current_a: float | np.ndarray,
         duration_s: float | np.ndarray,
         air_c: float | np.ndarray) -> float | np.ndarray:
    """Advance the surface temperature over one constant-current interval.

    Exact solution, not a discretisation:

        T(t) = T_air + (T0 - T_air) * exp(-b t) + (a I^2 / b) (1 - exp(-b t))
    """
    duration_s = np.asarray(duration_s, dtype=float)
    if np.any(duration_s < 0):
        raise ValueError("duration_s must be non-negative")
    decay = np.exp(-B_COEF * duration_s)
    steady = equilibrium_rise(current_a)
    return air_c + (temperature_c - air_c) * decay + steady * (1.0 - decay)


def integrate(temperature_c: float, current_a: float, duration_s: float,
              air_c: float, steps: int = 200_000) -> float:
    """Forward-Euler integration of the same ODE.

    Only used to cross-check the algebra of :func:`step`. First order, so its
    own truncation error is O(b * dt * rise); see :func:`euler_tolerance`.
    """
    dt = duration_s / steps
    heat = A_COEF * current_a ** 2
    temp = float(temperature_c)
    for _ in range(steps):
        temp += (heat - B_COEF * (temp - air_c)) * dt
    return temp


def euler_tolerance(current_a: float, duration_s: float, steps: int,
                    headroom: float = 10.0) -> float:
    """Expected truncation error of :func:`integrate`, with headroom."""
    dt = duration_s / steps
    return headroom * B_COEF * dt * float(equilibrium_rise(current_a))


@dataclass(frozen=True)
class Event:
    """One simulation event with a single event-average power."""
    start_s: float
    end_s: float
    energy_kwh: float
    state: str = ""

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def mean_power_kw(self) -> float:
        """Event-average power. Hides any shorter peaks inside the event."""
        hours = self.duration_s / 3600.0
        if hours <= 0:
            raise ValueError("event has non-positive duration")
        return self.energy_kwh / hours


def replay(events: Sequence[Event], capacity_kwh: float,
           air_c: float = 25.0, initial_c: float | None = None
           ) -> np.ndarray:
    """Run the frozen model across a sequence of events.

    Returns the surface temperature at the END of each event. Temperature is
    carried forward between events and is never reset: an event's starting
    temperature is the previous event's ending temperature.
    """
    temp = air_c if initial_c is None else float(initial_c)
    out = np.empty(len(events), dtype=float)
    for i, ev in enumerate(events):
        current = equivalent_current(ev.mean_power_kw, capacity_kwh)
        temp = float(step(temp, current, ev.duration_s, air_c))
        out[i] = temp
    return out


def resample_to_grid(time_s: np.ndarray, temperature_c: np.ndarray,
                     current_a: np.ndarray, air_c: np.ndarray,
                     dt_s: float = 1.0):
    """Put an event-sampled trace onto a uniform grid.

    Temperature and air are interpolated because they are continuous. Current
    is an event average and is therefore held piecewise-constant: interpolating
    it would invent current values that the simulation never produced.
    """
    time_s = np.asarray(time_s, dtype=float)
    grid = np.arange(0.0, np.floor(time_s[-1]) + dt_s, dt_s)
    temp = np.interp(grid, time_s, temperature_c)
    air = np.interp(grid, time_s, air_c)
    idx = np.clip(np.searchsorted(time_s, grid, side="right") - 1,
                  0, len(time_s) - 1)
    cur = np.asarray(current_a, dtype=float)[idx]
    return grid, temp, cur, air


def time_constant_s() -> float:
    """1 / b, the e-folding time of the cooling term."""
    return TAU_S
