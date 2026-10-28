"""All-state energy, recurring cycles and external reserve scoring.

Functions copied unchanged from the archived operational analysis. Native time
is minutes and battery-state energy is kWh. Source identity is recorded below.
"""
import math
TOL=1e-8

def validate_events(events):
    """Reject unsupported gaps, overlap, non-finite data or net charging."""
    if not events:
        raise ValueError("No truck event ledger")
    last_end = None
    for row in events:
        start, duration, energy = (float(row[k]) for k in
            ("SimulationTime", "ElapsedTime", "ElectricityFromBatteryConsumed"))
        if not all(math.isfinite(v) for v in (start, duration, energy)):
            raise ValueError("Non-finite event ledger")
        if duration <= 0 or energy < 0:
            raise ValueError("Expected positive duration and nonnegative battery consumption")
        if last_end is not None and abs(start - last_end) > TOL:
            raise ValueError("Event ledger has a gap or overlap")
        last_end = start + duration

def integrate_energy(events, start=0.0, end=None):
    """Integrate each event at its recorded average power, clipping either end."""
    if end is None:
        end = events[-1]["SimulationTime"] + events[-1]["ElapsedTime"]
    if end < start:
        raise ValueError("Integration window ends before it starts")
    total = 0.0
    for row in events:
        a, duration = row["SimulationTime"], row["ElapsedTime"]
        overlap = max(0.0, min(a + duration, end) - max(a, start))
        total += row["ElectricityFromBatteryConsumed"] * overlap / duration
    return total

def completed_deliveries(events, until=math.inf):
    """A configured one-minute unload must finish before the external cutoff.

    Native Quantity may be populated on a truncated unload, so Quantity alone
    is not a completion flag. The main audit cross-checks the resulting count
    and tonnes against the native material-movement table.
    """
    return [row for row in events if row["State"] == "Unloading"
            and row["ElapsedTime"] >= 1.0 - TOL
            and row["SimulationTime"] + row["ElapsedTime"] <= until + TOL]

def reserve_score(events, capacity_kwh, initial_soc_pct=80.0, reserve_soc_pct=20.0):
    """Spend (80%-20%)*capacity with exact interpolation inside the final event."""
    validate_events(events)
    if not capacity_kwh > 0 or not 0 <= reserve_soc_pct <= initial_soc_pct <= 100:
        raise ValueError("Invalid capacity or energy-state bounds")
    budget = (initial_soc_pct - reserve_soc_pct) * capacity_kwh / 100
    used = 0.0
    cutoff = events[-1]["SimulationTime"] + events[-1]["ElapsedTime"]
    attained = False
    for row in events:
        energy = row["ElectricityFromBatteryConsumed"]
        if used + energy >= budget - TOL:
            fraction = (budget - used) / energy if energy else 0.0
            cutoff = row["SimulationTime"] + row["ElapsedTime"] * max(0.0, min(1.0, fraction))
            used = budget
            attained = True
            break
        used += energy
    completed = completed_deliveries(events, cutoff)
    return {"cutoff_min": cutoff, "energy_kwh": used,
            "reserve_attained": attained,
            "end_soc_pct": initial_soc_pct - 100 * used / capacity_kwh,
            "completed_loads": len(completed),
            "completed_tonnes": sum(row["Quantity"] for row in completed)}

def complete_cycles(events, until=math.inf):
    """Return only completed recurring unload-to-unload intervals.

    The initialization-to-first-unload interval and the incomplete final trip
    are excluded. No whole-window energy / delivered-load quotient is used.
    """
    ends = [row["SimulationTime"] + row["ElapsedTime"]
            for row in completed_deliveries(events, until)]
    return [{"start_min": a, "end_min": b, "duration_min": b - a,
             "energy_kwh": integrate_energy(events, a, b)}
            for a, b in zip(ends, ends[1:])]

def energy_ledger(events, capacity_kwh, native_final_soc_pct):
    total = integrate_energy(events)
    stationary = sum(row["ElectricityFromBatteryConsumed"] for row in events
                     if abs(row["DistanceTravelled"]) < 1e-9)
    native_debit = capacity_kwh * (80 - native_final_soc_pct) / 100
    wheel = sum(row["EnergyToWheels"] for row in events)
    expected = wheel / .85 + 20 * sum(row["ElapsedTime"] for row in events) / 60
    residuals = [row["ElectricityFromBatteryConsumed"] -
                 (row["EnergyToWheels"] / .85 + 20 * row["ElapsedTime"] / 60)
                 for row in events]
    return {"all_state_energy_kwh": total, "wheel_energy_kwh": wheel,
            "stationary_energy_kwh": stationary,
            "native_final_soc_pct": native_final_soc_pct,
            "native_soc_debit_kwh": native_debit,
            "native_soc_missing_kwh": total - native_debit,
            "missing_minus_stationary_kwh": total - native_debit - stationary,
            "corrected_final_soc_pct": 80 - 100 * total / capacity_kwh,
            "ledger_expected_kwh": expected, "ledger_residual_kwh": total - expected,
            "ledger_residual_pct": 100 * (total - expected) / expected,
            "max_event_ledger_residual_kwh": max(map(abs, residuals))}
