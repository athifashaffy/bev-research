"""Independent read-only analysis of nine archived HAULSIM configurations.

Reproduce from the BEV workspace using the command saved in operations_audit.json.
No HAULSIM process is launched and no database or historical manifest is changed.
Native time units are minutes; event battery consumption is kWh.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
import statistics
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parent
SOURCE = ROOT / "New_Afton_Experiments_2026-10-20"
TOL = 1e-8


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


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_native(path):
    """SQLite opens explicitly in read-only mode; no temporary copy is altered."""
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        events = [dict(row) for row in db.execute(
            "SELECT * FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime,Id")]
        moves = [dict(row) for row in db.execute("SELECT * FROM HS_MaterialMovement")]
        tx, cfg = db.execute("SELECT XmlContent,ConfigurationXml FROM TruckType").fetchone()
    validate_events(events)
    truck_xml, config_xml = ET.fromstring(tx), ET.fromstring(cfg)
    graph = truck_xml.find(".//fuels/graph[@type='elec']/linestring").text
    electrical_peak = max(float(point.split()[2]) for point in graph.split(","))
    config = {
        "capacity_kwh": float(config_xml.findtext(".//EnergyCapacity")),
        "initial_soc_min_pct": float(config_xml.findtext(".//InitialEnergyMinLevel")),
        "initial_soc_max_pct": float(config_xml.findtext(".//InitialEnergyMaxLevel")),
        "tare_kg": sum(float(x.text) for x in truck_xml.findall(".//axles/axle/empty_weight")),
        "wheel_cap_kw": float(truck_xml.findtext(".//engines/engine/net_power")),
        "electrical_curve_at_full_wheel_power_kw": electrical_peak,
        "native_regeneration_enabled": config_xml.findtext(".//EnableRegenerativeBraking"),
        "native_recharging_enabled": config_xml.findtext(".//IsRechargingOrRefuellingEnabled"),
        "native_energy_enabled": config_xml.findtext(".//EnableElectricEnergy"),
        "configured_dump_time_min": float(truck_xml.findtext(".//dump_time")),
        "native_energy_graph": graph,
    }
    return events, moves, config


def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze():
    manifest_path = SOURCE / "run_manifest.json"
    manifest_hash = sha256(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = [c for c in manifest["cases"] if c["id"].startswith("C") and not c["id"].endswith("REPEAT")]
    if len(cases) != 9:
        raise ValueError("Expected exactly nine core archived cases")
    source_model = ROOT / manifest["source_model"]
    if sha256(source_model) != manifest["source_sha256"]:
        raise ValueError("Original source-model hash does not match")
    records, summaries, details, event_rows = {}, [], [], []
    for case in cases:
        path = SOURCE / case["result"]
        digest = sha256(path)
        if case["status"] != "EXECUTED_NATIVE_ARCHIVED" or digest != case["result_sha256"]:
            raise ValueError(f"Unadmitted native source: {case['id']}")
        events, moves, config = read_native(path)
        records[case["id"]] = events
        cap = case["capacity_kwh"]
        for field, expected in (("capacity_kwh", cap), ("tare_kg", case["tare_kg"]),
                                ("electrical_curve_at_full_wheel_power_kw", case["wheel_kw"] / .85 + 20),
                                ("wheel_cap_kw", case["wheel_kw"]),
                                ("initial_soc_min_pct", 80), ("initial_soc_max_pct", 80),
                                ("configured_dump_time_min", 1)):
            if abs(config[field] - expected) > TOL:
                raise ValueError(f"Manifest/configuration mismatch: {case['id']} {field}")
        assert config["native_regeneration_enabled"] == "false"
        assert config["native_recharging_enabled"] == "false"
        assert config["native_energy_enabled"] == "true"
        assert abs(events[0]["SimulationTime"]) < TOL
        end = events[-1]["SimulationTime"] + events[-1]["ElapsedTime"]
        assert abs(end - 120) < TOL
        assert abs(sum(row["ElapsedTime"] for row in events) - 120) < TOL
        deliveries = completed_deliveries(events)
        raw_tonnes = sum(row["Quantity"] for row in moves)
        assert len(deliveries) == len(moves) == 4
        assert abs(sum(row["Quantity"] for row in deliveries) - raw_tonnes) < TOL
        assert raw_tonnes == 180
        assert all(abs(row["ElectricityGeneratedByRegenerativeBraking"]) < TOL for row in events)
        assert all(abs(row["ElectricityGeneratedByInfrastructure"]) < TOL for row in events)
        peak = max(row["ElectricityFromBatteryConsumed"] * 60 / row["ElapsedTime"] for row in events)
        assert peak <= case["battery_kw"] * 1.01
        reserve = reserve_score(events, cap)
        assert reserve["reserve_attained"] and abs(reserve["end_soc_pct"] - 20) < TOL
        ledger = energy_ledger(events, cap, events[-1]["EnergyLevel"])
        assert abs(ledger["missing_minus_stationary_kwh"]) < 1e-6
        assert abs(ledger["ledger_residual_pct"]) < 1
        feasible_cycles = complete_cycles(events, reserve["cutoff_min"])
        assert feasible_cycles
        all_cycles = complete_cycles(events)
        delivery_ends = [row["SimulationTime"] + row["ElapsedTime"] for row in deliveries]
        first_energy = integrate_energy(events, 0, delivery_ends[0])
        tail_energy = integrate_energy(events, delivery_ends[-1], 120)
        assert abs(first_energy + sum(c["energy_kwh"] for c in all_cycles) + tail_energy
                   - ledger["all_state_energy_kwh"]) < 1e-6
        row = {
            "case": case["id"], "configuration_scale": case["scale"], "capacity_kwh": cap,
            "rolling_resistance_pct": case["rolling_resistance_percent"],
            "pack_mass_kg": case["pack_kg"], "vehicle_tare_kg": case["tare_kg"],
            "battery_nominal_rating_kw": case["battery_kw"], "wheel_cap_kw": case["wheel_kw"],
            "native_electrical_curve_full_load_kw": config["electrical_curve_at_full_wheel_power_kw"],
            "common_window_min": None, "common_window_energy_kwh": None,
            "reserve_time_min": reserve["cutoff_min"], "reserve_energy_kwh": reserve["energy_kwh"],
            "reserve_completed_loads": reserve["completed_loads"], "reserve_completed_tonnes": reserve["completed_tonnes"],
            "complete_recurring_cycles_before_reserve": len(feasible_cycles),
            "recurring_cycle_energy_kwh": statistics.mean(c["energy_kwh"] for c in feasible_cycles),
            "recurring_cycle_time_min": statistics.mean(c["duration_min"] for c in feasible_cycles),
            "raw_120min_tonnes": raw_tonnes, "raw_120min_energy_kwh": ledger["all_state_energy_kwh"],
            "native_120min_final_soc_pct": ledger["native_final_soc_pct"],
            "corrected_120min_final_soc_pct": ledger["corrected_final_soc_pct"],
            "native_soc_omitted_stationary_kwh": ledger["stationary_energy_kwh"],
        }
        summaries.append(row)
        details.append({"case": case["id"], "archive": str(path.relative_to(ROOT)),
                        "sha256_expected": case["result_sha256"], "sha256_observed": digest,
                        "hash_match": True, "truck_event_count": len(events), "end_min": end,
                        "native_material_movements": len(moves), "native_completed_tonnes": raw_tonnes,
                        "config": config, "ledger": ledger, "reserve": reserve,
                        "delivery_completion_min": delivery_ends, "first_delivery_energy_kwh": first_energy,
                        "complete_recurring_cycles_raw": all_cycles,
                        "complete_recurring_cycles_before_reserve": feasible_cycles,
                        "incomplete_tail_after_last_delivery_energy_kwh": tail_energy,
                        "raw_window_energy_divided_by_four_kwh_NOT_recurring_cycle": ledger["all_state_energy_kwh"] / 4,
                        "peak_event_mean_battery_kw": peak})
        used = 0.0
        for index, ev in enumerate(events):
            used += ev["ElectricityFromBatteryConsumed"]
            event_rows.append({"case": case["id"], "event_index": index,
                               "state": ev["State"], "start_min": ev["SimulationTime"],
                               "end_min": ev["SimulationTime"] + ev["ElapsedTime"],
                               "duration_min": ev["ElapsedTime"], "battery_energy_kwh": ev["ElectricityFromBatteryConsumed"],
                               "mean_power_kw": ev["ElectricityFromBatteryConsumed"] * 60 / ev["ElapsedTime"],
                               "cumulative_all_state_energy_kwh": used,
                               "corrected_end_soc_pct": 80 - 100 * used / cap,
                               "native_end_soc_pct": ev["EnergyLevel"],
                               "completed_delivery": ev in deliveries})
    common = min(row["reserve_time_min"] for row in summaries)
    trace_rows = []
    for row in summaries:
        events = records[row["case"]]
        row["common_window_min"] = common
        row["common_window_energy_kwh"] = integrate_energy(events, 0, common)
        times = sorted({0.0, common, row["reserve_time_min"], 120.0} |
                       {e["SimulationTime"] + e["ElapsedTime"] for e in events})
        for time in times:
            trace_rows.append({"case": row["case"], "time_min": time,
                               "all_state_energy_kwh": integrate_energy(events, 0, time),
                               "corrected_soc_pct": 80 - 100 * integrate_energy(events, 0, time) / row["capacity_kwh"],
                               "within_external_reserve": time <= row["reserve_time_min"] + TOL})
    repeat = next(c for c in manifest["cases"] if c["id"] == "C100_RR03_REPEAT")
    baseline = sorted((row for row in summaries if row["capacity_kwh"] == 354),
                      key=lambda row: row["rolling_resistance_pct"])
    baseline_effects = {key + "_change_pct": 100 * (baseline[-1][key] / baseline[0][key] - 1)
                        for key in ("common_window_energy_kwh", "reserve_time_min",
                                    "recurring_cycle_energy_kwh", "recurring_cycle_time_min")}
    baseline_effects.update({"configuration": "354 kWh / 8,255 kg pack / 391 kW wheel cap",
                             "rolling_resistance_from_pct": 2, "rolling_resistance_to_pct": 4,
                             "reserve_completed_tonnes_from": baseline[0]["reserve_completed_tonnes"],
                             "reserve_completed_tonnes_to": baseline[-1]["reserve_completed_tonnes"]})
    audit = {
        "analysis_date": "2026-10-22", "analysis_kind": "fresh read-only nine-case operational scoring",
        "protocol": "APCOM_Study_2026-10-22/01_Analysis_Protocol.txt",
        "source_manifest": str(manifest_path.relative_to(ROOT)), "source_manifest_sha256": manifest_hash,
        "source_model_sha256_expected": manifest["source_sha256"],
        "source_model_sha256_observed": sha256(source_model),
        "source_manifest_unchanged_after_read": sha256(manifest_path) == manifest_hash,
        "core_archives_verified": len(details), "native_runs_executed_by_this_analysis": 0,
        "baseline_354_rr2_to_rr4_effects": baseline_effects,
        "central_repeat_status": repeat["status"], "central_repeat_result_available": "result" in repeat,
        "central_repeat_interpretation": "No executed central repeat is available; repeatability was not tested.",
        "common_feasible_time_min": common,
        "reserve_definition": "All-state native battery consumption integrated until 0.60*nominal capacity is spent; 80% initial to 20% external reserve.",
        "within_event_assumption": "Constant recorded mean battery power within each native event; cutoff is interpolated analytically.",
        "delivery_definition": "Unloading service of at least the configured 1 minute completes at or before the cutoff; native movement count and tonnes cross-checked.",
        "energy_ledger": "Native ElectricityFromBatteryConsumed includes all states. Native EnergyLevel omits stationary consumption in these files. Corrected state = 80 - 100*cumulative_kWh/capacity_kWh.",
        "ledger_reconstruction_note": "Wheel energy/0.85 + 20 kW auxiliaries is a cross-check, not a replacement for native event energy; small numerical/curve residuals are retained.",
        "cycle_definition": "Recurring unload-to-unload intervals ending before reserve; initialization-to-first delivery and incomplete tail are excluded.",
        "configuration_confound": "Nominal capacity, pack mass, vehicle tare and nominal battery rating change together. Wheel power is 309.4 kW at scale 0.8 and 391 kW at scales 1.0/1.2. Native full-wheel-load battery curve endpoints are 384, 480 and 480 kW, despite nominal battery ratings of 384, 480 and 576 kW. Effects are battery-configuration comparisons, not isolated capacity effects.",
        "raw_window_caveat": "All nine raw 120-minute files show 4 completed loads / 180 t; all extend past the external reserve. Negative native final SOC is retained as a diagnostic and is not feasible operation.",
        "no_charging_or_regeneration": True,
        "reproduction_command": "& 'C:/Users/athif/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'C:/Users/athif/Documents/ChatGPT/BEV/APCOM_Study_2026-10-22/code/operations.py'",
        "test_command": "& 'C:/Users/athif/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s APCOM_Study_2026-10-22/code -p test_operations.py -v",
        "test_first_evidence": "Eight hand-calculated tests were written first and executed with 8 expected failures because operations.py was absent, before implementation. A ninth regression test for the native electrical curve endpoint then failed before the ambiguous power labeling was corrected.",
        "cases": details, "comparison": summaries,
    }
    assert audit["source_manifest_unchanged_after_read"]
    for detail in details:
        assert sha256(ROOT / detail["archive"]) == detail["sha256_observed"]
    results = STUDY / "results"
    results.mkdir(exist_ok=True)
    write_csv(results / "operations_comparison.csv", summaries)
    table_keys = ("case", "capacity_kwh", "rolling_resistance_pct", "common_window_energy_kwh",
                  "reserve_time_min", "reserve_completed_loads", "reserve_completed_tonnes",
                  "recurring_cycle_energy_kwh", "recurring_cycle_time_min")
    table = [{key: round(row[key], 2) if isinstance(row[key], float) else row[key]
              for key in table_keys} for row in summaries]
    write_csv(results / "operations_table.csv", table)
    write_csv(results / "operations_event_ledger.csv", event_rows)
    write_csv(results / "operations_energy_traces.csv", trace_rows)
    (results / "operations_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return summaries, records, audit


def make_figures(summaries, records):
    """6.5-inch figures with vector PDF/SVG companions for publication layout."""
    try:
        import matplotlib
    except ImportError:
        sys.path.insert(0, str(SOURCE / "tools"))
        import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5,
                         "axes.labelsize": 9.5, "axes.titlesize": 10,
                         "legend.fontsize": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 300,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    colors = {283.2: "#1768AC", 354.0: "#CC5A24", 424.8: "#19806A"}
    markers = {283.2: "o", 354.0: "s", 424.8: "^"}
    def legend_handles():
        return [Line2D([], [], color=color, marker=markers[cap], label=f"{cap:g} kWh")
                for cap, color in colors.items()]
    figures = STUDY / "figures"
    figures.mkdir(exist_ok=True)

    def save(fig, name):
        for suffix in ("png", "svg", "pdf"):
            fig.savefig(figures / f"{name}.{suffix}", facecolor="white")
        plt.close(fig)

    def metric(ax, key, ylabel, letter, digits=1):
        for cap, color in colors.items():
            rows = sorted((r for r in summaries if r["capacity_kwh"] == cap),
                          key=lambda r: r["rolling_resistance_pct"])
            ax.plot([r["rolling_resistance_pct"] for r in rows], [r[key] for r in rows],
                    marker=markers[cap], color=color, lw=1.6, ms=5)
        ax.set(xticks=[2, 3, 4], xlim=(1.88, 4.12), ylabel=ylabel)
        ax.set_title(letter, loc="left", fontweight="bold", pad=6)
        ax.grid(axis="y", color="#dddddd", lw=.6)

    common = summaries[0]["common_window_min"]
    fig, axes = plt.subplots(1, 3, figsize=(6.5, 3.35))
    metric(axes[0], "common_window_energy_kwh", "Battery energy (kWh)", "(a) Equal-time energy")
    metric(axes[1], "reserve_time_min", "Time to reserve (min)", "(b) Reserve time")
    metric(axes[2], "reserve_completed_tonnes", "Completed tonnes (t)", "(c) Payload")
    axes[2].set(yticks=[90, 135, 180], ylim=(80, 190))
    for ax in axes:
        ax.set_xlabel("Resistance (%)")
    fig.legend(handles=legend_handles(), loc="upper center", bbox_to_anchor=(.5, .99), ncol=3, frameon=False)
    fig.text(.5, .025, f"Rolling resistance scenarios. Energy: first {common:.2f} min. Payload: completed unloads to reserve.",
             ha="center", va="bottom", fontsize=8.5)
    fig.subplots_adjust(left=.09, right=.985, bottom=.23, top=.78, wspace=.64)
    save(fig, "operations_comparison")

    fig, axes = plt.subplots(1, 3, figsize=(6.5, 3.3), sharey=True)
    for ax, rr in zip(axes, (2, 3, 4)):
        for row in summaries:
            if row["rolling_resistance_pct"] != rr:
                continue
            events, cutoff, cap = records[row["case"]], row["reserve_time_min"], row["capacity_kwh"]
            times = sorted({0.0, cutoff} | {e["SimulationTime"] + e["ElapsedTime"] for e in events
                                          if e["SimulationTime"] + e["ElapsedTime"] <= cutoff})
            soc = [80 - 100 * integrate_energy(events, 0, t) / cap for t in times]
            ax.plot(times, soc, color=colors[cap], lw=1.5)
            ax.scatter([cutoff], [20], color=colors[cap], marker=markers[cap], s=24, zorder=4)
        ax.axhline(20, color="#777777", ls="--", lw=.8)
        ax.axvline(common, color="#888888", ls=":", lw=.8)
        ax.set(title=f"{rr}% rolling resistance", xlabel="Elapsed time (min)",
               xlim=(0, 125), ylim=(15, 83), xticks=[0, 40, 80, 120], yticks=[20, 40, 60, 80])
        ax.grid(axis="y", color="#e0e0e0", lw=.6)
    axes[0].set_ylabel("Corrected nominal energy (%)")
    fig.legend(handles=legend_handles(), loc="upper center", bbox_to_anchor=(.5, .99), ncol=3, frameon=False)
    fig.text(.5, .018, "All-state consumption; markers end at 20% reserve. Dotted line: common feasible time.",
             ha="center", va="bottom", fontsize=8.5)
    fig.subplots_adjust(left=.09, right=.985, bottom=.22, top=.78, wspace=.17)
    save(fig, "operations_corrected_energy")

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.3))
    metric(axes[0], "recurring_cycle_energy_kwh", "Cycle energy (kWh)", "(a) Complete-cycle energy")
    metric(axes[1], "recurring_cycle_time_min", "Cycle time (min)", "(b) Complete-cycle time")
    for ax in axes:
        ax.set_xlabel("Rolling resistance (%)")
    fig.legend(handles=legend_handles(), loc="upper center", bbox_to_anchor=(.5, .99), ncol=3, frameon=False)
    fig.text(.5, .025, "Complete unload-to-unload means before reserve; initialization and final tail excluded.",
             ha="center", va="bottom", fontsize=8.5)
    fig.subplots_adjust(left=.09, right=.985, bottom=.22, top=.78, wspace=.33)
    save(fig, "operations_complete_cycles")


if __name__ == "__main__":
    rows, records, audit = analyze()
    make_figures(rows, records)
    print(json.dumps({"core_archives_verified": audit["core_archives_verified"],
                      "common_feasible_time_min": audit["common_feasible_time_min"],
                      "central_repeat_status": audit["central_repeat_status"],
                      "reserve_time_range_min": [min(r["reserve_time_min"] for r in rows),
                                                 max(r["reserve_time_min"] for r in rows)],
                      "outputs": ["operations_audit.json", "operations_comparison.csv",
                                  "operations_table.csv", "operations_event_ledger.csv",
                                  "operations_energy_traces.csv", "three figures in png/svg/pdf"]}, indent=2))
