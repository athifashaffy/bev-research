"""Portable reconstruction audit of archived simulation and laboratory inputs.

AI-generated supporting code created for this evidence audit. This is a new audit,
not the original experiment, a new native simulation, a parameter fit, or field
validation. It reproduces source arithmetic without establishing pack physics.

Usage:
    python -B audit_physics_portable.py --root /path/to/inputs --output /new/output

Requires Python 3.10+, NumPy and SciPy. Preserve the workspace-relative directory
layout listed in the adjacent PORTABLE_INPUTS.json. No HAULSIM installation is
needed. Source scripts are hashed, never imported or executed. SQLite uses mode=ro.
The output must be a new directory outside the protected input directory trees.
All reported source paths are relative; inputs are pinned by size and SHA-256.
"""
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
import csv
import datetime
import hashlib
import json
import math
import sqlite3
import statistics
import argparse

ROOT = OUT = THERM = COUPLED = None
SOURCES = {}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def safe_relative(value):
    # Archived Windows manifests contain backslashes; normalize on every OS.
    value = str(value).replace('\\', '/')
    relative = PurePosixPath(value)
    check(not relative.is_absolute() and '..' not in relative.parts and ':' not in value,
          f'Input path must be relative and stay within the root: {value}')
    return Path(*relative.parts)


def configure():
    global ROOT, OUT, THERM, COUPLED
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, required=True, help='Input root with the archived relative directory layout')
    parser.add_argument('--output', type=Path, required=True, help='New directory for audit output; existing paths are rejected')
    args = parser.parse_args()
    ROOT, OUT = args.root.expanduser().resolve(), args.output.expanduser().resolve()
    check(ROOT.is_dir(), f'Input root is not a directory: {ROOT}')
    check(OUT != ROOT and not OUT.exists(), 'Output must be a new directory, distinct from the input root')
    specification = json.loads(Path(__file__).with_name('PORTABLE_INPUTS.json').read_text(encoding='utf-8'))
    protected = {ROOT / safe_relative(item['path']).parts[0] for item in specification['inputs']}
    check(not any(OUT == folder or OUT.is_relative_to(folder.resolve()) for folder in protected),
          'Output cannot be inside a protected input/source directory tree')
    for item in specification['inputs']:
        path = register(ROOT / safe_relative(item['path']))
        check(path.stat().st_size == item['size_bytes'], f'Input size differs: {item["path"]}')
        check(SOURCES[str(path)] == item['sha256'], f'Input SHA-256 differs: {item["path"]}')
    # Fail before creating output if the external data-reading dependency is absent.
    try:
        from scipy.io import loadmat  # noqa: F401
    except ImportError as error:
        raise RuntimeError('Install numpy and scipy before running this audit') from error
    THERM = ROOT / 'APCOM_Draft_Experiments_2026-10-27/thermal'
    COUPLED = ROOT / 'APCOM_Coupled_Thermal_2026-10-16'
    OUT.mkdir(parents=True, exist_ok=False)


def register(path):
    path = path.resolve()
    check(path.is_relative_to(ROOT), 'Input escapes the selected root')
    check(path.is_file(), f'Required input is missing: {path.relative_to(ROOT).as_posix()}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    previous = SOURCES.setdefault(str(path), digest)
    check(previous == digest, f'Input changed during audit: {path.relative_to(ROOT).as_posix()}')
    return path


def read_json(path):
    return json.loads(register(path).read_text(encoding='utf-8-sig'))


def read_csv(path):
    with register(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def save_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def save_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def integrate(events, start_min, end_min):
    return math.fsum(e['ElectricityFromBatteryConsumed'] *
        max(0., min(end_min, e['SimulationTime'] + e['ElapsedTime']) - max(start_min, e['SimulationTime'])) /
        e['ElapsedTime'] for e in events)


def cutoff(events, capacity):
    remaining = .6 * capacity
    for e in events:
        spent = e['ElectricityFromBatteryConsumed']
        if spent >= remaining:
            return e['SimulationTime'] + e['ElapsedTime'] * remaining / spent
        remaining -= spent
    raise AssertionError('Reserve not reached')


def theta_at(case, t_s, a, b, g=1.):
    """Independent excess-temperature recurrence, using exp rather than expm1.

    It propagates only event segments up to requested time. Each segment is
    monotonic, so end points determine exact piecewise continuous extrema.
    """
    theta, peak = 0., 0.
    for e in case['events']:
        duration = min(t_s, 60. * (e['SimulationTime'] + e['ElapsedTime'])) - 60. * e['SimulationTime']
        if duration <= 0:
            break
        power = 60. * e['ElectricityFromBatteryConsumed'] / e['ElapsedTime']
        current = 2.5 * power / case['capacity_kwh']
        decay = math.exp(-b * duration)
        theta = theta * decay + g * a * current * current / b * (1. - decay)
        peak = max(peak, theta)
        if 60. * (e['SimulationTime'] + e['ElapsedTime']) >= t_s:
            break
    return theta, peak


def main():
    configure()
    manifest_path = ROOT / 'New_Afton_Experiments_2026-10-20/run_manifest.json'
    manifest = read_json(manifest_path)
    frozen = read_json(COUPLED / 'results/frozen_cell_model.json')
    a, b = frozen['a_K_per_A2_s'], frozen['b_per_s']
    old_ops = {r['case']: r for r in read_csv(ROOT / 'APCOM_Study_2026-10-22/results/operations_comparison.csv')}
    old_thermal = {r['case']: r for r in read_csv(THERM / 'table2_common_window.csv')}
    traces = read_csv(THERM / 'nominal_traces.csv')
    variants = read_csv(THERM / 'sensitivity_summary.csv')
    cases = {}
    for meta in manifest['cases']:
        if meta['id'] not in old_ops:
            continue
        path = register(manifest_path.parent / safe_relative(meta['result']))
        check(SOURCES[str(path)] == meta['result_sha256'], "Audit check failed: SOURCES[str(path)] == meta['result_sha256']")
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            events = [dict(r) for r in db.execute("SELECT * FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime,Id")]
            tx, cfg = db.execute('SELECT XmlContent,ConfigurationXml FROM TruckType').fetchone()
            experiment = dict(db.execute('SELECT * FROM HS_ExperimentDetail').fetchone())
            moves = [dict(r) for r in db.execute('SELECT * FROM HS_MaterialMovement')]
            arcs = [dict(r) for r in db.execute('SELECT * FROM NetworkArc')]
            zmin, zmax = db.execute('SELECT MIN(Z),MAX(Z) FROM NetworkNode').fetchone()
        truck, config = ET.fromstring(tx), ET.fromstring(cfg)
        cap = float(config.findtext('.//EnergyCapacity'))
        check(cap == meta['capacity_kwh'], "Audit check failed: cap == meta['capacity_kwh']")
        check(all(e['ElapsedTime'] > 0 and e['ElectricityFromBatteryConsumed'] >= 0 for e in events), "Audit check failed: all(e['ElapsedTime'] > 0 and e['ElectricityFromBatteryConsumed'] >= 0 for e in events)")
        check(all(abs(x['SimulationTime'] + x['ElapsedTime'] - y['SimulationTime']) < 1e-8 for x, y in zip(events, events[1:])), "Audit check failed: all(abs(x['SimulationTime'] + x['ElapsedTime'] - y['SimulationTime']) < 1e-8 for x, y in zip(events, events[1:]))")
        check(abs(sum(e['ElapsedTime'] for e in events) - 120) < 1e-8, "Audit check failed: abs(sum(e['ElapsedTime'] for e in events) - 120) < 1e-8")
        unloads = [e for e in events if e['State'] == 'Unloading' and e['ElapsedTime'] >= 1 - 1e-8]
        ends = [e['SimulationTime'] + e['ElapsedTime'] for e in unloads]
        reserve = cutoff(events, cap)
        cycles = [(x, y, integrate(events, x, y)) for x, y in zip(ends, ends[1:]) if y <= reserve + 1e-8]
        stationary = math.fsum(e['ElectricityFromBatteryConsumed'] for e in events if abs(e['DistanceTravelled']) < 1e-9)
        total = integrate(events, 0., 120.)
        missing = total - cap * (.8 - events[-1]['EnergyLevel'] / 100.)
        expected = sum(e['EnergyToWheels'] for e in events) / .85 + 40.
        row = dict(case=meta['id'], capacity_kwh=cap, rr_percent=meta['rolling_resistance_percent'],
            archive_sha256=SOURCES[str(path)], event_count=len(events), experiment_replications=experiment['Replications'],
            reserve_time_min=reserve, reserve_energy_kwh=.6 * cap,
            reserve_deliveries=sum(t <= reserve + 1e-8 for t in ends),
            reserve_tonnes=sum(e['Quantity'] for e in unloads if e['SimulationTime'] + e['ElapsedTime'] <= reserve + 1e-8),
            recurring_cycles_before_reserve=len(cycles), recurring_cycle_energy_kwh=statistics.mean(e for _, _, e in cycles),
            recurring_cycle_time_min=statistics.mean(y - x for x, y, _ in cycles),
            raw_total_energy_kwh=total, raw_completed_deliveries=len(moves), raw_completed_tonnes=sum(e['Quantity'] for e in moves),
            raw_native_final_energy_pct=events[-1]['EnergyLevel'], stationary_energy_kwh=stationary,
            native_missing_minus_stationary_kwh=missing - stationary,
            wheel_efficiency_auxiliary_formula_residual_pct=100. * (total / expected - 1.),
            pack_mass_kg_manifest=meta['pack_kg'], tare_kg=sum(float(x.text) for x in truck.findall('.//axles/axle/empty_weight')),
            wheel_cap_kw=float(truck.findtext('.//engines/engine/net_power')),
            electrical_curve_cap_kw=max(float(p.split()[2]) for p in truck.findtext(".//fuels/graph[@type='elec']/linestring").split(',')),
            nominal_rating_kw_manifest=meta['battery_kw'], route_arc_length_m=sum(e['Length'] for e in arcs),
            route_node_rise_m=zmax-zmin, route_max_grade=max(e['Grade'] for e in arcs),
            route_min_grade=min(e['Grade'] for e in arcs), events=events)
        for key in ('reserve_time_min', 'recurring_cycle_energy_kwh', 'recurring_cycle_time_min'):
            check(abs(row[key] - float(old_ops[meta['id']][key])) < 1e-9, "Audit check failed: abs(row[key] - float(old_ops[meta['id']][key])) < 1e-9")
        check(abs(missing - stationary) < 1e-9, 'Audit check failed: abs(missing - stationary) < 1e-9')
        cases[meta['id']] = row
    check(len(cases) == 9, 'Audit check failed: len(cases) == 9')
    common_min = min(c['reserve_time_min'] for c in cases.values())
    common_s = common_min * 60.
    for case_id, row in cases.items():
        energy = integrate(row['events'], 0., common_min)
        endpoint, peak = theta_at(row, common_s, a, b)
        currents = [2.5 * 60. * e['ElectricityFromBatteryConsumed'] / e['ElapsedTime'] / row['capacity_kwh'] for e in row['events'] if e['SimulationTime'] <= row['reserve_time_min']]
        row.update(common_window_min=common_min, common_energy_kwh=energy, common_mean_power_kw=energy * 60. / common_min,
            nominal_common_peak_rise_c=peak, nominal_common_end_rise_c=endpoint,
            nominal_current_min_a=min(currents), nominal_current_max_a=max(currents))
        for own, old in [('common_mean_power_kw','mean_power_kw'),('nominal_common_peak_rise_c','peak_rise_c'),('nominal_common_end_rise_c','end_rise_c')]:
            check(abs(row[own] - float(old_thermal[case_id][old])) < 2e-12, 'Audit check failed: abs(row[own] - float(old_thermal[case_id][old])) < 2e-12')
    trace_error = 0.
    current_error = 0.
    for tr in traces:
        row = cases[tr['case']]
        theta, _ = theta_at(row, float(tr['time_s']), a, b)
        trace_error = max(trace_error, abs(25. + theta - float(tr['temperature_c'])))
        current_error = max(current_error, abs(2.5 * float(tr['event_mean_power_kw']) / row['capacity_kwh'] - float(tr['equivalent_current_a'])))
    check(trace_error < 2e-12 and current_error < 1e-12, 'Audit check failed: trace_error < 2e-12 and current_error < 1e-12')
    sensitivity_error = 0.
    for tr in variants:
        row = cases[tr['case']]
        aa, bb, g, air = a * float(tr['a_multiplier']), b * float(tr['b_multiplier']), float(tr['g']), float(tr['air_c'])
        endpoint, peak = theta_at(row, row['reserve_time_min'] * 60., aa, bb, g)
        ce, cp = theta_at(row, common_s, aa, bb, g)
        for own, old in [(air+endpoint,'end_surface_c'),(air+peak,'peak_surface_c'),(air+ce,'common_end_surface_c'),(air+cp,'common_peak_surface_c')]:
            sensitivity_error = max(sensitivity_error, abs(own - float(tr[old])))
    check(sensitivity_error < 2e-12, 'Audit check failed: sensitivity_error < 2e-12')
    unique_inputs = {(r['case'],float(r['a_multiplier'])*float(r['g']),float(r['b_multiplier']),float(r['air_c'])) for r in variants}
    duplicate_max_difference = 0.
    grouped = {}
    for r in variants:
        key=(r['case'],float(r['a_multiplier'])*float(r['g']),float(r['b_multiplier']),float(r['air_c']))
        values = [float(r[k]) for k in ('peak_surface_c','end_surface_c','common_peak_surface_c','common_end_surface_c')]
        if key in grouped:
            duplicate_max_difference=max(duplicate_max_difference,max(abs(x-y) for x,y in zip(values,grouped[key])))
        grouped[key]=values
    from scipy.io import loadmat
    residuals = []
    download = read_json(COUPLED / 'sources/download_manifest.json')
    expected_hashes = {r['file']:r['sha256'] for r in download['files']}
    for name in ('A002_PeriodicPulseData.mat','A002_UDDS_P25.mat','A002_UDDS_P35.mat'):
        path = register(COUPLED / 'sources' / name)
        check(SOURCES[str(path)] == expected_hashes[name], 'Audit check failed: SOURCES[str(path)] == expected_hashes[name]')
        data = loadmat(path, simplify_cells=True)['Data']
        t = [float(x)-float(data['time'][0]) for x in data['time']]
        current = data['current']
        surface = data.get('SurfaceTemperature',data.get('Ts1',data.get('Ts')))
        air = data.get('AirTemperature',data.get('Tf'))
        temp = float(surface[0])
        weighted_error, weighted_abs, duration, peak_error = [], [], [], 0.
        for k in range(len(t)-1):
            h = t[k+1]-t[k]
            decay=math.exp(-b*h)
            eq=float(air[k])+a/b*float(current[k])**2
            temp=decay*temp+(1.-decay)*eq
            err=temp-float(surface[k+1])
            weighted_error.append(h*err**2);weighted_abs.append(h*abs(err));duration.append(h)
            peak_error=max(peak_error,abs(err))
        residuals.append(dict(file=name,role='FIT' if 'Periodic' in name else 'SAME_CELL_OTHER_RECORD',
            samples=len(t), duration_s=t[-1],time_weighted_rmse_c=math.sqrt(math.fsum(weighted_error)/math.fsum(duration)),
            time_weighted_mae_c=math.fsum(weighted_abs)/math.fsum(duration),max_absolute_error_c=peak_error,
            timestamp_dt_min_s=min(duration),timestamp_dt_max_s=max(duration),source_sha256=SOURCES[str(path)]))
    current_max = max(r['nominal_current_max_a'] for r in cases.values())
    central_low, central_high = cases['C100_RR02'], cases['C100_RR04']
    central = cases['C100_RR03']
    derived = dict(a_over_b_K_per_A2=a/b,time_constant_s=1/b,time_constant_min=1/b/60,
        event_equivalent_current_range_a=[min(r['nominal_current_min_a'] for r in cases.values()),current_max],
        maximum_constant_current_equilibrium_rise_c=a/b*current_max**2,
        common_window_mean_power_range_kw=[min(r['common_mean_power_kw'] for r in cases.values()),max(r['common_mean_power_kw'] for r in cases.values())],
        nominal_common_peak_rise_range_c=[min(r['nominal_common_peak_rise_c'] for r in cases.values()),max(r['nominal_common_peak_rise_c'] for r in cases.values())],
        central_rr2_to4_cycle_energy_change_pct=100*(central_high['recurring_cycle_energy_kwh']/central_low['recurring_cycle_energy_kwh']-1),
        central_rr2_to4_cycle_time_change_pct=100*(central_high['recurring_cycle_time_min']/central_low['recurring_cycle_time_min']-1),
        central_rr2_to4_reserve_time_change_pct=100*(central_high['reserve_time_min']/central_low['reserve_time_min']-1),
        central_cycle_pct_of_354_nominal=100*central['recurring_cycle_energy_kwh']/354,
        central_whole_run_energy_divided_by_deliveries_kwh=central['raw_total_energy_kwh']/central['raw_completed_deliveries'],
        operator_19pct_of_354_nominal_kwh=.19*354,operator_19pct_of_300_usable_kwh=.19*300,
        central_above_57kwh_pct=100*(central['recurring_cycle_energy_kwh']/57.-1),
        sensitivity_assignments=len(variants),effective_input_combinations=len(unique_inputs),
        maximum_sensitivity_surface_c=max(float(r['peak_surface_c']) for r in variants),
        maximum_sensitivity_rise_c=max(float(r['peak_rise_c']) for r in variants))
    save_csv('independent_case_checks.csv', [{k:v for k,v in r.items() if k!='events'} for r in cases.values()])
    save_json('independent_recomputation.json',dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        disclosure='AI-generated supporting code for a new evidence audit. No original source edited, original experiment re-executed, new native simulation run, parameter fit or field validation.',
        verification_scope='Source-level reproduction and internal arithmetic only; this does not validate truck physics.',
        nominal_trace_rows_checked=len(traces),maximum_nominal_temperature_difference_c=trace_error,
        maximum_equivalent_current_difference_a=current_error,maximum_sensitivity_summary_difference_c=sensitivity_error,
        maximum_duplicate_heating_product_summary_difference_c=duplicate_max_difference,
        derived=derived,laboratory_residuals=residuals))
    for name in ('APCOM_Study_2026-10-22/code/thermal_analysis.py','APCOM_Study_2026-10-22/code/operations.py',
                 'APCOM_Draft_Experiments_2026-10-27/thermal/run_thermal.py','APCOM_Coupled_Thermal_2026-10-16/code/fit_model.py',
                 'APCOM_Draft_Experiments_2026-10-27/thermal/protocol.json'):
        register(ROOT/name)
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in SOURCES.items())
    check(unchanged, 'Audit check failed: unchanged')
    save_json('input_hash_manifest.json', dict(all_read_inputs_unchanged=unchanged,required_input_count=len(SOURCES), inputs=[dict(path=Path(p).relative_to(ROOT).as_posix(),size_bytes=Path(p).stat().st_size,sha256=h) for p,h in SOURCES.items()]))
    print(json.dumps(dict(cases=len(cases),traces=len(traces),trace_max_abs_difference_c=trace_error,
        sensitivity_max_abs_difference_c=sensitivity_error,all_read_inputs_unchanged=unchanged,derived=derived,laboratory_residuals=residuals),indent=2))


if __name__ == '__main__':
    main()
