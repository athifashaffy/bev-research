"""Prespecified nine-case A123-equivalent surface-temperature surrogate study.

Read-only native event inputs, frozen laboratory-cell parameters, exact exponential
integration. This does not identify Z50 cell current sharing, core temperature,
pack hotspots, cooling, reaction heat, or field warning performance.
"""
import argparse
import bisect
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import sqlite3
import sys

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent


def equivalent_current(power_kw, capacity_kwh):
    """Equal-P/E current in amperes: (kW/kWh) * 2.5 Ah."""
    if capacity_kwh <= 0:
        raise ValueError("Capacity must be positive")
    return 2.5 * power_kw / capacity_kwh


def exact_step(temperature_c, air_c, current_a, duration_s, a, b, g=1.):
    """Constant-input exponential solution; g multiplies mean-square heat."""
    if duration_s < 0 or a < 0 or b < 0 or g < 0:
        raise ValueError("Nonnegative duration and coefficients required")
    heat = a * g * current_a**2
    if b == 0:
        return temperature_c + heat * duration_s
    return temperature_c + (air_c - temperature_c + heat/b) * (-math.expm1(-b*duration_s))


def prepare_events(rows):
    """Normalize native minutes and kWh once, retaining every operating state."""
    events = []
    previous_end = 0.
    for row in rows:
        start = float(row["SimulationTime"]) * 60.
        duration = float(row["ElapsedTime"]) * 60.
        energy = float(row["ElectricityFromBatteryConsumed"])
        if not all(math.isfinite(v) for v in (start, duration, energy)) or duration <= 0 or energy < -1e-8:
            raise ValueError("Nonfinite/negative event input")
        if abs(start-previous_end) > 1e-6:
            raise ValueError("Truck events must be contiguous and nonoverlapping")
        energy = max(0., energy)
        events.append(dict(start_s=previous_end, end_s=start+duration,
                           duration_s=duration, energy_kwh=energy,
                           power_kw=energy*3600./duration, state=row["State"]))
        previous_end = start+duration
    if not events:
        raise ValueError("No truck events")
    return events


def reserve_cutoff(events, capacity_kwh):
    """Exact event-average integration of the external 80 to 20% window."""
    budget = .6*capacity_kwh
    remaining = budget
    for event in events:
        energy = event["energy_kwh"]
        if energy >= remaining and energy > 0:
            return event["start_s"] + event["duration_s"] * remaining/energy
        remaining -= energy
    return events[-1]["end_s"]


def sample_trace(events, capacity_kwh, stop_s, grid_s, a, b, g, air_c, extra_times=()):
    """Sample exact piecewise solution on grid plus event/reserve boundaries.

    Extra event boundaries guarantee all continuous-solution temperature extrema
    are retained: each constant-input segment is monotone. Warning rules remain
    sampled rules; finer output is evaluated separately.
    """
    if grid_s <= 0 or stop_s < 0 or stop_s > events[-1]["end_s"]+1e-7:
        raise ValueError("Invalid output interval")
    times = set(i*grid_s for i in range(int(stop_s/grid_s)+1))
    times.update((0., stop_s))
    times.update(e["end_s"] for e in events if 0 < e["end_s"] < stop_s)
    times.update(float(t) for t in extra_times if 0 < t < stop_s)
    time_s = sorted(times)
    boundaries = [air_c]
    for event in events:
        boundaries.append(exact_step(boundaries[-1], air_c,
                          equivalent_current(event["power_kw"], capacity_kwh),
                          event["duration_s"], a, b, g))
    starts = [e["start_s"] for e in events]
    temperature = []
    current = []
    power = []
    state = []
    instantaneous = []
    for t in time_s:
        index = min(bisect.bisect_right(starts, t)-1, len(events)-1)
        event = events[index]
        amps = equivalent_current(event["power_kw"], capacity_kwh)
        temp = exact_step(boundaries[index], air_c, amps, t-event["start_s"], a, b, g)
        temperature.append(temp)
        current.append(amps)
        power.append(event["power_kw"])
        state.append(event["state"])
        instantaneous.append(a*g*amps**2-b*(temp-air_c))
    return dict(time_s=time_s, temperature_c=temperature,
                equivalent_current_a=current, event_mean_power_kw=power,
                state=state, instantaneous_rate_c_s=instantaneous)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path, rows):
    if not rows:
        raise ValueError("No output rows")
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def trace_metrics(trace, warnings, air_c, common_s):
    t = trace["time_s"]
    y = trace["temperature_c"]
    rate = warnings["rate_c_s"]
    end = bisect.bisect_right(t, common_s)
    if abs(t[end-1]-common_s) > 1e-7:
        raise ValueError("Common window endpoint absent from sampled trace")
    finite_rate = [x for x in rate if x is not None and math.isfinite(x)]
    common_rate = [x for x in rate[:end] if x is not None and math.isfinite(x)]
    peak = max(y)
    return dict(peak_temperature_c=peak, peak_rise_c=peak-air_c,
                peak_time_s=t[y.index(peak)], end_temperature_c=y[-1],
                max_causal_rate_c_s=max(finite_rate) if finite_rate else None,
                max_instantaneous_rate_c_s=max(trace["instantaneous_rate_c_s"]),
                max_output_dt_s=max(b-a for a,b in zip(t,t[1:])),
                fixed_alarm_s=warnings["fixed_alarm_s"],
                candidate_alarm_s=warnings["candidate_alarm_s"],
                common_peak_temperature_c=max(y[:end]),
                common_peak_rise_c=max(y[:end])-air_c,
                common_end_temperature_c=y[end-1],
                common_max_causal_rate_c_s=max(common_rate) if common_rate else None,
                common_fixed_alarm_s=(warnings["fixed_alarm_s"] if warnings["fixed_alarm_s"] is not None and warnings["fixed_alarm_s"]<=common_s else None),
                common_candidate_alarm_s=(warnings["candidate_alarm_s"] if warnings["candidate_alarm_s"] is not None and warnings["candidate_alarm_s"]<=common_s else None))


def plot_results(nominals, envelopes, common_s, figures):
    # Existing local dependencies are reused without modifying raw archives.
    dependency_dir = ROOT/"New_Afton_Experiments_2026-10-20/tools"
    if dependency_dir.exists():
        sys.path.insert(0, str(dependency_dir))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.size":9, "axes.titlesize":10,
                         "axes.labelsize":9, "legend.fontsize":8,
                         "svg.fonttype":"none", "pdf.fonttype":42})
    colors={2:"#0072B2",3:"#D55E00",4:"#009E73"}
    styles={283.2:":",354.:"-",424.8:"--"}
    fig,ax=plt.subplots(figsize=(6.3,3.8),layout="constrained")
    for case in nominals:
        row,trace=case["summary"],case["trace"]
        ax.plot(np.array(trace["time_s"])/60., np.array(trace["temperature_c"])-25.,
                color=colors[row["rr_percent"]], linestyle=styles[row["capacity_kwh"]],
                linewidth=1.25,label=f'{row["capacity_kwh"]:g} kWh / RR {row["rr_percent"]}%')
    ax.axvline(common_s/60,color="0.35",linewidth=.9,linestyle="-.")
    ax.text(common_s/60+1.,ax.get_ylim()[1]*.88,"Common\nwindow",fontsize=8,color="0.3")
    ax.set(xlabel="Elapsed native operating time (min)",
           ylabel="A123-equivalent cell surface rise (°C)",
           title="Nine normal-operation surrogates: nominal 25 °C air")
    ax.grid(alpha=.2)
    ax.legend(ncol=3,loc="upper center",bbox_to_anchor=(.5,-.22),frameon=False)
    for suffix in ("png","svg","pdf"):
        fig.savefig(figures/f"thermal_nominal_rise.{suffix}",dpi=220)
    plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(6.3,3.7),sharey=False,layout="constrained")
    from matplotlib.ticker import FormatStrFormatter
    # Nine lines in each facet; shaded bounds across 27 a/b/g scenarios per line.
    for ax,air in zip(axes,(25.,35.,40.)):
        for group in envelopes:
            if group["air_c"]!=air:
                continue
            t=np.array(group["time_s"])/60.
            color=colors[group["rr_percent"]]
            style=styles[group["capacity_kwh"]]
            ax.fill_between(t,group["min_temperature_c"],group["max_temperature_c"],color=color,alpha=.05,linewidth=0)
            ax.plot(t,group["max_temperature_c"],color=color,linestyle=style,linewidth=.85)
        ax.set_title(f"Air / initial {air:g} °C")
        ax.set_xlabel("Elapsed time (min)")
        ax.set_xlim(0,110)
        # Each absolute-temperature facet has an identical rise range above air.
        # A common absolute y axis would hide the small surrogate rise entirely.
        largest_rise=max(max(gr["max_temperature_c"])-air for gr in envelopes if gr["air_c"]==air)
        ax.set_ylim(air-.04*largest_rise,air+1.07*largest_rise)
        ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
        ax.grid(alpha=.2)
    axes[0].set_ylabel("A123-equivalent cell surface (°C)")
    fig.suptitle("Assumed sensitivity scenarios: envelopes over 27 a/b/g variants",fontsize=10)
    # Color/style legends apply to both plots and preserve readable facet area.
    from matplotlib.lines import Line2D
    handles=[Line2D([0],[0],color=colors[rr],label=f"RR {rr}%") for rr in (2,3,4)]
    handles += [Line2D([0],[0],color="0.25",linestyle=styles[c],label=f"{c:g} kWh") for c in styles]
    fig.legend(handles=handles,ncol=3,loc="outside lower center",frameon=False)
    for suffix in ("png","svg","pdf"):
        fig.savefig(figures/f"thermal_sensitivity_envelopes.{suffix}",dpi=220)
    plt.close(fig)


def run():
    from warning_rules import analyse_warning, RULES
    results=OUT/"results"
    figures=OUT/"figures"
    results.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    source=ROOT/"New_Afton_Experiments_2026-10-20"
    manifest_path=source/"run_manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    model_path=ROOT/"APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json"
    model=json.loads(model_path.read_text(encoding="utf-8"))
    record_metrics_path=model_path.with_name("record_metrics.json")
    record_metrics=json.loads(record_metrics_path.read_text(encoding="utf-8"))
    a=model["a_K_per_A2_s"]
    b=model["b_per_s"]
    assert math.isclose(a,4.344635339312832e-05,rel_tol=1e-14)
    assert math.isclose(b,.002655462788692412,rel_tol=1e-14)
    cases=[]
    sources=[]
    for case in manifest["cases"]:
        if not (case["id"].startswith(("C080_","C100_","C120_")) and case["status"]=="EXECUTED_NATIVE_ARCHIVED"):
            continue
        path=source/case["result"]
        digest=sha256(path)
        if digest!=case["result_sha256"]:
            raise ValueError("Native archive SHA-256 mismatch: "+case["id"])
        with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(row) for row in db.execute("SELECT * FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime,Id")]
        events=prepare_events(rows)
        cutoff=reserve_cutoff(events,case["capacity_kwh"])
        cases.append(dict(meta=case,events=events,cutoff_s=cutoff))
        sources.append(dict(case=case["id"],path=str(path),expected_sha256=case["result_sha256"],actual_sha256=digest,
                            verified=True,event_count=len(events),cutoff_min=cutoff/60.))
    if len(cases)!=9:
        raise ValueError(f"Expected exactly nine archived core cases, got {len(cases)}")
    common_s=min(c["cutoff_s"] for c in cases)
    variant_rows=[]
    convergence_rows=[]
    nominal_rows=[]
    nominal_traces=[]
    nominals=[]
    envelopes=[]
    envelope_rows=[]
    for case in cases:
        meta=case["meta"]
        events=case["events"]
        cutoff=case["cutoff_s"]
        groups={}
        for am,bm,g,air in itertools.product((.5,1.,2.),(.5,1.,2.),(1.,2.,4.),(25.,35.,40.)):
            base=dict(case=meta["id"],capacity_kwh=meta["capacity_kwh"],rr_percent=meta["rolling_resistance_percent"],
                      a_multiplier=am,b_multiplier=bm,mean_square_heat_multiplier=g,air_c=air,
                      initial_temperature_c=air,cutoff_min=cutoff/60.,common_window_min=common_s/60.)
            trace=sample_trace(events,meta["capacity_kwh"],cutoff,1.,a*am,b*bm,g,air,(common_s,))
            warnings=analyse_warning(trace["time_s"],trace["temperature_c"])
            metrics=trace_metrics(trace,warnings,air,common_s)
            fine=sample_trace(events,meta["capacity_kwh"],cutoff,.5,a*am,b*bm,g,air,(common_s,))
            fine_warning=analyse_warning(fine["time_s"],fine["temperature_c"])
            fine_metrics=trace_metrics(fine,fine_warning,air,common_s)
            row={**base,**metrics}
            for key in ("peak_temperature_c","max_causal_rate_c_s","max_output_dt_s","fixed_alarm_s","candidate_alarm_s"):
                row["grid_0p5s_"+key]=fine_metrics[key]
            variant_rows.append(row)
            convergence_rows.append({**base,
                "peak_temperature_difference_c_1s_minus_0p5s":metrics["peak_temperature_c"]-fine_metrics["peak_temperature_c"],
                "max_causal_rate_difference_c_s_1s_minus_0p5s":metrics["max_causal_rate_c_s"]-fine_metrics["max_causal_rate_c_s"],
                "fixed_alarm_status_agrees":(metrics["fixed_alarm_s"] is None)==(fine_metrics["fixed_alarm_s"] is None),
                "candidate_alarm_status_agrees":(metrics["candidate_alarm_s"] is None)==(fine_metrics["candidate_alarm_s"] is None),
                "fixed_alarm_time_difference_s":(metrics["fixed_alarm_s"]-fine_metrics["fixed_alarm_s"] if metrics["fixed_alarm_s"] is not None and fine_metrics["fixed_alarm_s"] is not None else None),
                "candidate_alarm_time_difference_s":(metrics["candidate_alarm_s"]-fine_metrics["candidate_alarm_s"] if metrics["candidate_alarm_s"] is not None and fine_metrics["candidate_alarm_s"] is not None else None)})
            if air not in groups:
                groups[air]=dict(case=meta["id"],capacity_kwh=meta["capacity_kwh"],rr_percent=meta["rolling_resistance_percent"],
                                 air_c=air,time_s=trace["time_s"],
                                 min_temperature_c=list(trace["temperature_c"]),max_temperature_c=list(trace["temperature_c"]))
            else:
                group=groups[air]
                group["min_temperature_c"]=[min(x,y) for x,y in zip(group["min_temperature_c"],trace["temperature_c"])]
                group["max_temperature_c"]=[max(x,y) for x,y in zip(group["max_temperature_c"],trace["temperature_c"])]
            if (am,bm,g,air)==(1.,1.,1.,25.):
                nominal_rows.append(row)
                nominals.append(dict(summary=row,trace=trace))
                for i,t in enumerate(trace["time_s"]):
                    nominal_traces.append(dict(case=meta["id"],capacity_kwh=meta["capacity_kwh"],rr_percent=meta["rolling_resistance_percent"],
                        time_s=t,temperature_c=trace["temperature_c"][i],rise_c=trace["temperature_c"][i]-air,
                        equivalent_current_a=trace["equivalent_current_a"][i],event_mean_power_kw=trace["event_mean_power_kw"][i],
                        state=trace["state"][i],causal_ols_rate_c_s=warnings["rate_c_s"][i]))
        for air,group in groups.items():
            envelopes.append(group)
            for i,t in enumerate(group["time_s"]):
                envelope_rows.append(dict(case=meta["id"],capacity_kwh=meta["capacity_kwh"],rr_percent=meta["rolling_resistance_percent"],
                    air_c=air,time_s=t,min_temperature_c=group["min_temperature_c"][i],
                    max_temperature_c=group["max_temperature_c"][i],variants_in_envelope=27))
        print(json.dumps(dict(case=meta["id"],cutoff_min=cutoff/60.,completed_variants=len(variant_rows))),flush=True)
    assert len(variant_rows)==729
    assert len(nominal_rows)==9 and len(envelopes)==27
    write_csv(results/"thermal_variant_summary.csv",variant_rows)
    write_csv(results/"thermal_grid_convergence.csv",convergence_rows)
    write_csv(results/"thermal_nominal_summary.csv",nominal_rows)
    write_csv(results/"thermal_nominal_traces.csv",nominal_traces)
    write_csv(results/"thermal_sensitivity_envelopes.csv",envelope_rows)
    sensitivity=dict(variants=len(variant_rows),fixed_alarm_count=sum(r["fixed_alarm_s"] is not None for r in variant_rows),
                     candidate_alarm_count=sum(r["candidate_alarm_s"] is not None for r in variant_rows),
                     max_peak_temperature_c=max(r["peak_temperature_c"] for r in variant_rows),
                     max_peak_rise_c=max(r["peak_rise_c"] for r in variant_rows),
                     max_causal_rate_c_s=max(r["max_causal_rate_c_s"] for r in variant_rows),
                     max_instantaneous_rate_c_s=max(r["max_instantaneous_rate_c_s"] for r in variant_rows),
                     maximum_temperature_variant=max(variant_rows,key=lambda r:r["peak_temperature_c"]),
                     nominal_fixed_alarm_count=sum(r["fixed_alarm_s"] is not None for r in nominal_rows),
                     nominal_candidate_alarm_count=sum(r["candidate_alarm_s"] is not None for r in nominal_rows))
    convergence=dict(max_abs_peak_temperature_difference_c=max(abs(r["peak_temperature_difference_c_1s_minus_0p5s"]) for r in convergence_rows),
                     max_abs_causal_rate_difference_c_s=max(abs(r["max_causal_rate_difference_c_s_1s_minus_0p5s"]) for r in convergence_rows),
                     fixed_alarm_disagreements=sum(not r["fixed_alarm_status_agrees"] for r in convergence_rows),
                     candidate_alarm_disagreements=sum(not r["candidate_alarm_status_agrees"] for r in convergence_rows),
                     paired_finite_fixed_alarm_count=sum(r["fixed_alarm_time_difference_s"] is not None for r in convergence_rows),
                     paired_finite_candidate_alarm_count=sum(r["candidate_alarm_time_difference_s"] is not None for r in convergence_rows),
                     note="No finite alarms means status agreement only; alarm-timing convergence is not identified. Exact event boundaries are included in both grids, so the constant-input model's monotone-segment peaks are captured independently of grid spacing.")
    audited_paths=[manifest_path,model_path,record_metrics_path,OUT/"01_Analysis_Protocol.txt",Path(__file__),Path(__file__).with_name("test_thermal_analysis.py"),Path(__file__).with_name("warning_rules.py")]
    audit=dict(study_date="2026-10-22",model_domain="A123-equivalent laboratory-cell surface surrogate, not Z50 pack/core/hotspot temperature",
        input_units=dict(native_time="min",native_energy="kWh",internal_time="s",event_mean_power="kW",current="A",temperature="C"),
        equation="dTs/dt = (a * a_multiplier) * g * (2.5 Ah * P_kW / capacity_kWh)^2 - (b * b_multiplier) * (Ts - Tair)",
        integration="Exact exponential per constant event-average input; nominal 1 s grid plus every event, reserve, and common-window boundary; repeated at 0.5 s",
        reserve_rule="All-state event consumption to 0.60 * nominal capacity; stationary events included; no native energy-level feedback",
        common_window_s=common_s,common_window_min=common_s/60.,
        sensitivity_grid=dict(a_multipliers=[.5,1.,2.],b_multipliers=[.5,1.,2.],mean_square_heat_multipliers=[1.,2.,4.],air_c=[25.,35.,40.],initial_temperature="equal to air boundary",variants_per_case=81),
        warnings_rules=RULES,source_hashes=[dict(path=str(p),sha256=sha256(p)) for p in audited_paths],native_sources=sources,
        frozen_model={**model,"source_record_metrics":record_metrics,"validation_status":"Reported from the existing frozen model's prior held-out records, not a new laboratory validation; all records concern the same A123 cell."},
        nominal_cases=nominal_rows,sensitivity_summary=sensitivity,convergence=convergence,
        test_evidence=dict(red="Nine expected assertion failures before core implementation: missing exact_step, equivalent_current, prepare_events, reserve_cutoff, sample_trace behaviors",green="python -m unittest discover -s code -p test_thermal_analysis.py -v: 9 passed",scope="Analytic cooling/heating, SI units, zero cooling, stationary reserve, input step clipping, heat multiplier, overlap rejection; shared causal/persistence tests reside in test_warning_rules.py"),
        limitations=["Only a=R_eff/C_eff and b=UA_eff/C_eff are fitted ratios; physical R, C and UA are not independently identified.",
            "Stress multipliers are assumed scenarios, not statistical confidence or prediction intervals.",
            "Event-mean power loses within-event current variation. g scenarios bracket unresolved heating but are not measured RMS-current bounds.",
            "Z50 current-sharing topology and cooling are unknown; equal-P/E matching does not validate A123-to-Z50 temperature transfer.",
            "No reaction heat, internal short circuit, cell core, pack hotspot, thermal coupling, or failure progression is represented.",
            "Normal scenarios are not failure tests. Zero simulated alarms does not estimate mine false alarms per hour, safety, fire probability, or detection sensitivity.",
            "Configurations vary capacity, mass and power together; thermal differences cannot be attributed to capacity alone."],
        outputs=dict(nominal_trace_rows=len(nominal_traces),envelope_trace_rows=len(envelope_rows),envelope_count=len(envelopes),variant_summary_rows=len(variant_rows)),
        reproduction=["python -m unittest discover -s code -p test_thermal_analysis.py -v","python code/thermal_analysis.py"])
    (results/"thermal_audit.json").write_text(json.dumps(audit,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(dict(sensitivity_summary=sensitivity,convergence=convergence)),flush=True)
    plot_results(nominals,envelopes,common_s,figures)


if __name__=="__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
