"""
Independent verification of the headline numbers.

Run:
    python code/verify.py

Recomputes, from the derived tables in ../data/derived, the quantities that the
paper depends on, and asserts each against the stored result. Exits non-zero on
any mismatch so it can be used as a check in CI or before a submission.

Checks performed
  1. Worked thermal example (case C100_RR03, native event Id 44) reproduces the
     saved trace to better than 1e-9 degrees C.
  2. The closed-form solution agrees with a fine-step numerical integration of
     the same ODE, confirming the algebra rather than just the arithmetic.
  3. Per-case energy, mean power and reserve windows are internally consistent.
  4. Temperature rises and forecast errors are compared with the measured-cell
     residual band, which is the limit of what the model can resolve.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DERIVED = os.path.join(ROOT, "data", "derived")

A_COEF = 4.344635339312832e-05   # K/(A^2 s), identified as R_eff / C_eff
B_COEF = 0.002655462788692412    # 1/s,       identified as K_eff / C_eff
T_AIR = 25.0
RESID_LO, RESID_HI = 0.109, 0.117

EVENT = dict(
    case="C100_RR03",
    start_s=701.852626103349,
    end_s=1380.826476833902,
    energy_kwh=58.927842765108,
    capacity_kwh=354.0,
    t_start_c=25.000772630233,
    saved_end_c=25.066656834106034,
)

_failures = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("   " + detail) if detail else ""))
    if not ok:
        _failures.append(name)


def closed_form(t_s, i_a, t_start_c, t_air_c=T_AIR):
    """Exact solution of dT/dt = a I^2 - b (T - T_air) for constant I and air."""
    decay = np.exp(-B_COEF * t_s)
    steady = A_COEF * i_a ** 2 / B_COEF
    return t_air_c + (t_start_c - t_air_c) * decay + steady * (1.0 - decay)


def integrate(t_s, i_a, t_start_c, t_air_c=T_AIR, steps=2_000_000):
    """Forward integration of the same ODE, as an independent algebra check."""
    dt = t_s / steps
    temp = t_start_c
    heat = A_COEF * i_a ** 2
    for _ in range(steps):
        temp += (heat - B_COEF * (temp - t_air_c)) * dt
    return temp


def check_worked_example():
    print("\n1. Worked thermal example, case %s" % EVENT["case"])
    dur_s = EVENT["end_s"] - EVENT["start_s"]
    power_kw = EVENT["energy_kwh"] / (dur_s / 3600.0)
    i_eq = 2.5 * power_kw / EVENT["capacity_kwh"]

    print("     duration            %.9f s" % dur_s)
    print("     event-average power %.9f kW" % power_kw)
    print("     equivalent current  %.9f A   (ASSUMED, not measured)" % i_eq)
    print("     time constant 1/b   %.4f s" % (1.0 / B_COEF))

    predicted = closed_form(dur_s, i_eq, EVENT["t_start_c"])
    delta = abs(predicted - EVENT["saved_end_c"])
    check("closed form reproduces saved trace",
          delta < 1e-9, "delta = %.3e C" % delta)

    # Forward Euler is first order, so its own truncation error sets the floor
    # here: it scales as O(b * dt * rise). The tolerance below is that expected
    # error with a decade of headroom, not an arbitrary loosening.
    steps = 200_000
    dt = dur_s / steps
    euler_tol = 10.0 * B_COEF * dt * (A_COEF * i_eq ** 2 / B_COEF)
    numeric = integrate(dur_s, i_eq, EVENT["t_start_c"], steps=steps)
    delta_n = abs(numeric - predicted)
    check("closed form agrees with numerical integration",
          delta_n < euler_tol,
          "delta = %.3e C, Euler tolerance = %.3e C" % (delta_n, euler_tol))

    steady_rise = A_COEF * i_eq ** 2 / B_COEF
    check("event ends below its own equilibrium",
          predicted - T_AIR < steady_rise,
          "rise %.6f C vs equilibrium %.6f C" % (predicted - T_AIR, steady_rise))


def check_case_table():
    print("\n2. Nine-case operating table")
    df = pd.read_csv(os.path.join(DERIVED, "table2_nominal_reserve.csv"))
    check("nine configurations present", len(df) == 9, "n = %d" % len(df))

    # energy over the window must equal 60% of nominal capacity, the reserve rule
    budget = 0.60 * df["capacity_kwh"]
    check("window energy equals the 60% reserve budget",
          bool(np.allclose(df["window_energy_kwh"], budget, atol=1e-6)),
          "max deviation %.2e kWh" % float((df["window_energy_kwh"] - budget).abs().max()))

    # mean power must equal window energy divided by window hours
    implied = df["window_energy_kwh"] / (df["window_end_s"] / 3600.0)
    check("mean power equals energy over elapsed hours",
          bool(np.allclose(implied, df["mean_power_kw"], rtol=1e-9)),
          "max relative error %.2e"
          % float(((implied - df["mean_power_kw"]).abs() / df["mean_power_kw"]).max()))

    check("air held at 25 C in every case",
          bool((df["air_c"] == 25.0).all()))

    rise_lo, rise_hi = df["peak_rise_c"].min(), df["peak_rise_c"].max()
    print("     peak rise range     %.6f to %.6f C" % (rise_lo, rise_hi))
    check("every modelled rise is below the measured-cell residual band",
          rise_hi < RESID_LO,
          "max rise %.6f C vs residual floor %.3f C" % (rise_hi, RESID_LO))

    margin = df["margin_to_60c_study_screen_c"]
    print("     margin to 60 C      %.3f to %.3f C  (spread %.3f C)"
          % (margin.min(), margin.max(), margin.max() - margin.min()))
    check("margin spread across all nine cases is under 0.1 C",
          float(margin.max() - margin.min()) < 0.1)


def check_forecasting():
    print("\n3. Forecasting benchmark")
    df = pd.read_csv(os.path.join(DERIVED, "table4_pooled_metrics.csv"))
    check("four horizons by five methods",
          len(df) == 20, "n = %d" % len(df))

    worst = df["rmse_c"].max()
    print("     largest pooled RMSE %.6f C" % worst)
    check("entire benchmark lies below the measured-cell residual band",
          worst < RESID_LO,
          "worst %.6f C vs residual floor %.3f C" % (worst, RESID_LO))

    # the claim the paper makes: boosting leads on BOTH measures at 2, 5, 10 min
    for horizon in (120, 300, 600):
        sub = df[df["horizon_s"] == horizon].set_index("method")
        wins_both = (
            sub.loc["hist_gradient_boosting", "rmse_c"] == sub["rmse_c"].min()
            and sub.loc["hist_gradient_boosting", "mae_c"] == sub["mae_c"].min()
        )
        check("boosting leads on RMSE and MAE at %d s" % horizon, bool(wins_both))

    # and the exception the paper is careful to state
    sub = df[df["horizon_s"] == 60].set_index("method")
    check("at 60 s boosting does NOT lead on MAE, as the paper states",
          sub.loc["hist_gradient_boosting", "mae_c"] > sub["mae_c"].min(),
          "boosting %.3e vs best %.3e"
          % (sub.loc["hist_gradient_boosting", "mae_c"], sub["mae_c"].min()))

    # interpretable baseline failures at the long horizon
    sub = df[df["horizon_s"] == 600].set_index("method")
    check("at 600 s the trend baseline is worse than persistence",
          sub.loc["linear_trend", "rmse_c"] > sub.loc["persistence", "rmse_c"])
    check("at 600 s the held-input physics baseline is worse than persistence",
          sub.loc["physics_hold", "rmse_c"] > sub.loc["persistence", "rmse_c"])


def check_warning_rules():
    print("\n4. Frozen warning rules")
    quiet = pd.read_csv(os.path.join(DERIVED, "frozen_rule_summary.csv"))
    check("no rule fires on any modelled normal trajectory",
          int(quiet["trajectories_with_debounced_alarm"].sum()) == 0,
          "alarms = %d" % int(quiet["trajectories_with_debounced_alarm"].sum()))

    lab = pd.read_csv(os.path.join(DERIVED, "table5_rule_response.csv"),
                      encoding="utf-8-sig")
    for col in ("lead_time_s", "misses", "field_false_alarm_rate"):
        all_unavailable = bool((lab[col].astype(str) == "UNAVAILABLE").all())
        check("%s is reported as UNAVAILABLE throughout" % col, all_unavailable)

    check("no verified independent reference event is claimed",
          int(lab["verified_independent_reference_events"].sum()) == 0)


def main():
    print("=" * 72)
    print("Verification of headline numbers")
    print("Temperatures are A123-equivalent cell surface values from a fitted")
    print("model. They are not measured or validated Z50 pack temperatures.")
    print("=" * 72)

    check_worked_example()
    check_case_table()
    check_forecasting()
    check_warning_rules()

    print("\n" + "=" * 72)
    if _failures:
        print("FAILED (%d):" % len(_failures))
        for name in _failures:
            print("   - " + name)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
