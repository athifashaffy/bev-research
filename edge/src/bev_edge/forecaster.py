"""Rolling one-second sensor buffer and the four forecasts made from it.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

Readings must arrive once per second with whole-second timestamps. A gap, a
repeated or backwards timestamp, or a non-finite reading empties the buffer:
nothing is filled in, interpolated or resampled, so the next forecast waits
until 61 consecutive good samples exist again.
"""
import math
from collections import deque

from .features import AIR_LAST, CURRENT_LAST, HISTORY, TEMPERATURE_LAST, TEMPERATURE_SLOPE, history_features
from .thermal import thermal_hold

METHODS = ("persistence", "linear_trend", "physics_hold", "hist_gradient_boosting")


class SensorBuffer:
    def __init__(self):
        self.rows = deque(maxlen=HISTORY)   # (time_s, temperature_c, current_a, air_c)
        self.resets = 0

    def push(self, time_s, current_a, temperature_c, air_c):
        """Add one reading. Returns False if it started a new buffer."""
        if float(time_s) != int(time_s):
            raise ValueError(f"Timestamps must be whole seconds, got {time_s!r}")
        t = int(time_s)
        values = (float(temperature_c), float(current_a), float(air_c))
        if not all(math.isfinite(v) for v in values):
            self.clear()
            return False
        continuous = not self.rows or t == self.rows[-1][0] + 1
        if not continuous:
            self.clear()
        self.rows.append((t, *values))
        return continuous

    def clear(self):
        if self.rows:
            self.resets += 1
        self.rows.clear()

    @property
    def ready(self):
        return len(self.rows) == HISTORY

    @property
    def time_s(self):
        return self.rows[-1][0] if self.rows else None

    def history(self):
        return [r[1:] for r in self.rows]


class Forecaster:
    """Feed readings with ``push``; it returns a forecast every ``every_s`` seconds once ready."""

    def __init__(self, bundle, capacity_kwh, rr_pct, every_s=10):
        if not capacity_kwh > 0 or every_s < 1:
            raise ValueError("capacity_kwh must be positive and every_s at least 1")
        self.bundle, self.capacity_kwh, self.rr_pct, self.every_s = bundle, float(capacity_kwh), float(rr_pct), int(every_s)
        self.buffer = SensorBuffer()

    def push(self, time_s, current_a, temperature_c, air_c):
        self.buffer.push(time_s, current_a, temperature_c, air_c)
        if self.buffer.ready and self.buffer.time_s % self.every_s == 0:
            return self.forecast()
        return None

    def forecast(self):
        if not self.buffer.ready:
            raise RuntimeError("Need 61 consecutive one-second readings first")
        x = history_features(self.buffer.history(), self.capacity_kwh, self.rr_pct)
        now, t = x[TEMPERATURE_LAST], self.buffer.time_s
        horizons = []
        for h in self.bundle.horizons:
            horizons.append({
                "horizon_s": h, "target_time_s": t + h,
                "persistence": now,
                "linear_trend": now + x[TEMPERATURE_SLOPE] * h,
                "physics_hold": thermal_hold(now, x[CURRENT_LAST], x[AIR_LAST], h, self.bundle.a, self.bundle.b),
                "hist_gradient_boosting": now + self.bundle.models[h].predict(x),
            })
        return {"time_s": t, "temperature_c": now, "bundle": self.bundle.name, "forecasts": horizons}
