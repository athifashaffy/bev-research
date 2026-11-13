"""The seven frozen warning rules.

Four fixed-temperature rules and three rate-of-rise rules, specified before any
laboratory record was screened and never re-tuned afterwards. Freezing them is
what makes the laboratory screen meaningful: the rules could not have been
fitted to the records they are tested on.

Important framing, enforced in the vocabulary of this module. A rule firing on
a laboratory record is a RESPONSE to recorded heating. It is not a verified
thermal-runaway detection, and the time it fires is not a lead time. Neither
archive contains an independent, temperature-free onset reference with bounded
sensor-clock uncertainty, so no lead time can be computed at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np

from .config import (DEBOUNCE_S, FIXED_THRESHOLDS_C, RATE_THRESHOLDS_C_PER_MIN,
                     RATE_WINDOW_S)


@dataclass(frozen=True)
class Rule:
    """One frozen warning rule."""
    name: str
    kind: str           # "fixed" or "rate"
    threshold: float    # degrees C, or degrees C per minute
    debounce_s: float = DEBOUNCE_S

    def __str__(self) -> str:
        unit = "C" if self.kind == "fixed" else "C/min"
        return "%s (> %g %s)" % (self.name, self.threshold, unit)


def frozen_rules() -> list[Rule]:
    """The seven rules, in their fixed order."""
    rules = [Rule("fixed_%gC" % t, "fixed", t) for t in FIXED_THRESHOLDS_C]
    rules += [Rule("rate_%gC_min" % r, "rate", r)
              for r in RATE_THRESHOLDS_C_PER_MIN]
    return rules


def causal_slope(time_s: np.ndarray, temperature_c: np.ndarray,
                 window_s: float = RATE_WINDOW_S) -> np.ndarray:
    """Backward-looking slope in degrees C per minute.

    Strictly causal: each sample uses only the ``window_s`` of record that
    precedes it. Samples without a full window are returned as NaN and are
    excluded from screening, which is why eligible-sample counts are lower for
    the rate rules than for the fixed rules.
    """
    time_s = np.asarray(time_s, dtype=float)
    temperature_c = np.asarray(temperature_c, dtype=float)
    out = np.full(time_s.shape, np.nan)
    start_idx = np.searchsorted(time_s, time_s - window_s, side="left")
    for i in range(len(time_s)):
        j = start_idx[i]
        if j >= i:
            continue
        span = time_s[i] - time_s[j]
        if span < window_s * 0.999:     # incomplete window, not eligible
            continue
        out[i] = (temperature_c[i] - temperature_c[j]) / span * 60.0
    return out


def evaluate(rule: Rule, time_s: np.ndarray, temperature_c: np.ndarray,
             slope_c_per_min: np.ndarray | None = None) -> dict:
    """Apply one rule to one record.

    Returns the first sample where the rule's condition holds AND the record
    has run for at least ``rule.debounce_s``. Keys:

        eligible_samples   samples the rule could legally act on
        exceedances        samples where the condition held
        responded          whether a debounced response occurred
        first_response_s   time of that response, or None
    """
    time_s = np.asarray(time_s, dtype=float)
    if rule.kind == "fixed":
        value = np.asarray(temperature_c, dtype=float)
    elif rule.kind == "rate":
        if slope_c_per_min is None:
            slope_c_per_min = causal_slope(time_s, temperature_c)
        value = np.asarray(slope_c_per_min, dtype=float)
    else:
        raise ValueError("unknown rule kind %r" % rule.kind)

    eligible = np.isfinite(value)
    exceeds = eligible & (value > rule.threshold)
    debounced = exceeds & (time_s >= time_s[0] + rule.debounce_s)
    hits = np.flatnonzero(debounced)

    return {
        "rule": rule.name,
        "eligible_samples": int(eligible.sum()),
        "exceedances": int(exceeds.sum()),
        "responded": bool(hits.size),
        "first_response_s": float(time_s[hits[0]]) if hits.size else None,
    }


def screen(time_s: np.ndarray, temperature_c: np.ndarray,
           rules: list[Rule] | None = None) -> Iterator[dict]:
    """Apply every frozen rule to one record, reusing the slope computation."""
    rules = frozen_rules() if rules is None else rules
    slope = causal_slope(time_s, temperature_c)
    for rule in rules:
        yield evaluate(rule, time_s, temperature_c, slope)


# Reporting vocabulary. These three quantities cannot be computed from either
# laboratory archive and are reported as this literal rather than estimated.
UNAVAILABLE = "UNAVAILABLE"
UNAVAILABLE_REASON = (
    "No independent, temperature-free physical reference with verified "
    "sensor-clock uncertainty. Temperature slope and heater start-up are "
    "excluded as onset labels, so lead time, missed detections and field "
    "false-alarm rate are not computable from these records."
)
