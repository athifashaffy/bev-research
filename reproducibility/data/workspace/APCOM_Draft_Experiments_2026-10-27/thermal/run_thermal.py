"""Independent regeneration retaining the archived A123-equivalent generator.

No native runs, source rewrites, or model refits are performed. Only the two
thermal ratios are identified; optional pulse-voltage anchors remain conditional.
"""
import csv
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sqlite3
import statistics
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PRIOR=ROOT/'APCOM_Study_2026-10-22'


def energy_between(events,start_s,end_s):
    """All-state energy from normalized constant-power events, clipping both ends."""
    if end_s<start_s:
        raise ValueError('End precedes start')
    return math.fsum(e['energy_kwh']*max(0.,min(e['end_s'],end_s)-max(e['start_s'],start_s)) /
                     (e['end_s']-e['start_s']) for e in events)


def recurring_cycles(rows,until_s):
    """Complete one-minute unload end to unload end, excluding initialization."""
    ends=[60.*(r['SimulationTime']+r['ElapsedTime']) for r in rows
          if r['State']=='Unloading' and r['ElapsedTime']>=1.-1e-8
          and 60.*(r['SimulationTime']+r['ElapsedTime'])<=until_s+1e-8]
    events=[dict(start_s=60.*r['SimulationTime'],end_s=60.*(r['SimulationTime']+r['ElapsedTime']),
                 energy_kwh=r['ElectricityFromBatteryConsumed']) for r in rows]
    return [dict(start_s=a,end_s=b,duration_s=b-a,energy_kwh=energy_between(events,a,b))
            for a,b in zip(ends,ends[1:])]


def pulse_edges(time_s,current_a,voltage_v):
    """Sampled apparent delta-V/delta-I at >=5 A edges; not ohmic identification.

    Require stable three-sample plateaus on both sides (range <=0.1 A), each
    spanning <=5 s, with adjacent edge interval <=2 s. Store adjacent and
    median-three quotients to expose finite-window polarization sensitivity.
    Positive recorded current corresponds to charging in this file; retain the
    signed quotient rather than using abs() to hide inconsistent voltage steps.
    """
    if len(time_s)!=len(current_a) or len(time_s)!=len(voltage_v):
        raise ValueError('Mismatched electrical arrays')
    if any(not math.isfinite(float(x)) for seq in (time_s,current_a,voltage_v) for x in seq):
        raise ValueError('Nonfinite electrical arrays')
    if any(b<=a for a,b in zip(time_s,time_s[1:])):
        raise ValueError('Time must increase')
    out=[]
    for k in range(3,len(time_s)-2):
        di=float(current_a[k]-current_a[k-1])
        if abs(di)<5. or time_s[k]-time_s[k-1]>2.:
            continue
        pre_i=list(map(float,current_a[k-3:k]))
        post_i=list(map(float,current_a[k:k+3]))
        if max(pre_i)-min(pre_i)>.1 or max(post_i)-min(post_i)>.1:
            continue
        if time_s[k-1]-time_s[k-3]>5. or time_s[k+2]-time_s[k]>5.:
            continue
        dv=float(voltage_v[k]-voltage_v[k-1])
        median_di=statistics.median(post_i)-statistics.median(pre_i)
        median_dv=statistics.median(map(float,voltage_v[k:k+3]))-statistics.median(map(float,voltage_v[k-3:k]))
        out.append(dict(index=k,time_s=float(time_s[k]),edge_interval_s=float(time_s[k]-time_s[k-1]),
            previous_current_a=float(current_a[k-1]),current_a=float(current_a[k]),delta_current_a=di,delta_voltage_v=dv,
            adjacent_apparent_r_ohm=dv/di,median3_apparent_r_ohm=median_dv/median_di))
    return out


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_csv(name,rows):
    with (HERE/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_json(name,value):
    (HERE/name).write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')


def archived_generator():
    path=PRIOR/'code/thermal_analysis.py'
    spec=importlib.util.spec_from_file_location('frozen_archived_thermal_generator',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def distribution(x):
    import numpy as np
    return dict(n=len(x),min=float(min(x)),q25=float(np.quantile(x,.25)),median=float(np.median(x)),
                q75=float(np.quantile(x,.75)),max=float(max(x)))


def temperature_channels(data):
    surface=next((data[k] for k in ('SurfaceTemperature','Ts1','Ts') if k in data),None)
    air=next((data[k] for k in ('AirTemperature','Tf') if k in data),None)
    if surface is None or air is None:
        raise ValueError('Missing measured temperature channels')
    return surface,air


def electrical_and_residual_audit(model,generator):
    """Recompute frozen residuals and diagnose a conditional electrical anchor."""
    sys.path.insert(0,str(ROOT/'research/coupled_thermal_2026_10_16/tools'))
    import numpy as np
    from scipy.io import loadmat
    source=ROOT/'APCOM_Coupled_Thermal_2026-10-16/sources'
    manifest=json.loads((source/'download_manifest.json').read_text())
    expected={r['file']:r['sha256'] for r in manifest['files']}
    prior_metrics=json.loads((source.parent/'results/record_metrics.json').read_text())
    metrics=[]
    all_prediction_rows=[]
    electrical=None
    a,b=model['a_K_per_A2_s'],model['b_per_s']
    for name in [model['fit_record']]+model['test_records']:
        path=source/name
        digest=sha(path)
        assert digest==expected[name], 'Laboratory source hash mismatch'
        data=loadmat(path,simplify_cells=True)['Data']
        t=np.array(data['time'],dtype=float);t-=t[0]
        current=np.asarray(data['current'],float)
        raw_surface,raw_air=temperature_channels(data)
        surface=np.asarray(raw_surface,float)
        air=np.asarray(raw_air,float)
        voltage=np.asarray(data['voltage'],float)
        assert all(np.isfinite(x).all() for x in (t,current,surface,air,voltage))
        dt=np.diff(t)
        assert np.all(dt>0)
        pred=np.empty(len(t));pred[0]=surface[0]
        for k,duration in enumerate(dt):
            pred[k+1]=generator.exact_step(pred[k],air[k],current[k],duration,a,b)
        err=pred-surface
        metric=dict(file=name,role='FIT' if name==model['fit_record'] else 'HELD_OUT_RECORD',
            samples=len(t),duration_s=float(t[-1]),timestamp_dt_s=distribution(dt),
            rmse_c=float(np.sqrt(np.average(err[1:]**2,weights=dt))),
            mae_c=float(np.average(abs(err[1:]),weights=dt)),
            bias_c=float(np.average(err[1:],weights=dt)),max_absolute_error_c=float(np.max(np.abs(err))),
            source_sha256=digest)
        reference=next(r for r in prior_metrics if r['file']==name)
        assert abs(metric['rmse_c']-reference['RMSE_C'])<1e-10
        metric['difference_from_archived_rmse_c']=metric['rmse_c']-reference['RMSE_C']
        metrics.append(metric)
        for row in zip(t,current,voltage,air,surface,pred,err):
            all_prediction_rows.append(dict(record=name,**{key:float(value) for key,value in zip(
                ('time_s','current_a','voltage_v','air_c','measured_surface_c','predicted_surface_c','residual_c'),row)}))
        if name==model['fit_record']:
            edges=pulse_edges(t.tolist(),current.tolist(),voltage.tolist())
            assert edges
            save_csv('pulse_edges.csv',edges)
            positive=[e for e in edges if e['adjacent_apparent_r_ohm']>0 and e['median3_apparent_r_ohm']>0]
            adjacent=distribution([e['adjacent_apparent_r_ohm'] for e in positive])
            median3=distribution([e['median3_apparent_r_ohm'] for e in positive])
            conditional=[]
            for method,dist in [('adjacent_sample',adjacent),('three_sample_median',median3)]:
                resistance=dist['median']
                capacity=resistance/a
                conditional.append(dict(method=method,assumed_effective_heat_resistance_ohm=resistance,
                    conditional_C_J_per_K=capacity,conditional_K_W_per_K=b*capacity,
                    used_to_generate_temperature=False))
            electrical=dict(record=name,current_convention='Positive recorded current raises terminal voltage; charging-positive convention',
                edge_rule='abs(delta I)>=5 A; previous/current samples no more than 2 s apart; stable 3-sample plateaus each side current range<=0.1 A, each spanning<=5 s',
                edges_accepted=len(edges),edges_positive=len(positive),edge_interval_s=distribution([e['edge_interval_s'] for e in edges]),
                all_signed_adjacent_apparent_resistance_ohm=distribution([e['adjacent_apparent_r_ohm'] for e in edges]),
                all_signed_median3_apparent_resistance_ohm=distribution([e['median3_apparent_r_ohm'] for e in edges]),
                nonpositive_paired_edges=[e for e in edges if e not in positive],
                conditional_anchor_selection='540 edges with both quotients positive; all 541 signed edges retained above and in pulse_edges.csv; no absolute-value transform. A near-simultaneous current-to-rest transition has zero adjacent voltage jump.',
                adjacent_apparent_resistance_ohm=adjacent,median3_apparent_resistance_ohm=median3,
                conditional_anchors=conditional,source_sha256=digest,
                interpretation='Sampled apparent deltaV/deltaI, not a unique ohmic or heat-generation resistance. Distribution quantiles describe observed edges, not confidence bounds.',
                limitations=['Approximately 1 s voltage/current samples do not resolve the instantaneous ohmic voltage jump.',
                    'OCV/SOC drift, hysteresis, preexisting and evolving polarization, finite switching phase, contacts and instrument synchronization enter deltaV/deltaI.',
                    'Three-sample medians include additional polarization and differ from adjacent-sample quotients; neither isolates irreversible heat-generation R.',
                    'Pulse edges within one cell and one repeating record are correlated, not independent cell tests.',
                    'C=R/a and K=b*R/a are conditional on treating a sampled apparent electrical R as the effective thermal heat-generation R; these are not uniquely measured C,K.',
                    'No cell-to-pack C or K scaling is established; baseline generator remains exactly the archived ratio model.'])
    save_csv('cell_frozen_residuals.csv',all_prediction_rows)
    save_json('cell_residual_metrics.json',dict(model=model,records=metrics,
        fit_loss='Previously fitted time-weighted least squares over full pulse record, positive log(a),log(b); no test-record tuning.',
        original_parameter_bounds=dict(a_K_per_A2_s=[1e-8,.1],b_per_s=[1e-6,1.]),
        initial_conditions='Measured initial cell surface temperature for each record; left-held measured current and measured air thereafter; no temperature feedback.',
        identifiability='Only a=R_eff/C_eff and b=K_eff/C_eff; scaling R,C,K by any common positive factor produces the identical thermal trajectory.',
        status='Frozen coefficients retained; residuals independently recomputed, not a new independent-cell validation or refit.'))
    save_json('pulse_edge_audit.json',electrical)
    return metrics,electrical


def plot(cases,envelopes,variants,common_s):
    sys.path.insert(0,str(ROOT/'New_Afton_Experiments_2026-10-20/tools'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FormatStrFormatter
    plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'legend.fontsize':8,'pdf.fonttype':42,'svg.fonttype':'none'})
    colors={2:'#0072B2',3:'#D55E00',4:'#009E73'}
    styles={283.2:':',354.:'-',424.8:'--'}
    fig,ax=plt.subplots(figsize=(6.3,3.8),layout='constrained')
    for meta,trace in cases:
        ax.plot(np.array(trace['time_s'])/60.,np.array(trace['temperature_c'])-25.,
                color=colors[meta['rr_percent']],linestyle=styles[meta['capacity_kwh']],linewidth=1.2,
                label=f"{meta['capacity_kwh']:g} kWh / RR{meta['rr_percent']}%")
    ax.axvline(common_s/60,color='0.3',linestyle='-.',linewidth=.8)
    ax.set(title='Archived A123-equivalent generator: nine normal-operation cases',xlabel='Elapsed native operating time (min)',
           ylabel='Cell-equivalent surface temperature rise (°C)')
    ax.grid(alpha=.2)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.22),ncol=3,frameon=False)
    for ext in ('png','pdf','svg'):
        fig.savefig(HERE/f'thermal_nominal_rise.{ext}',dpi=220)
    plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(6.3,3.65),layout='constrained')
    for ax,air in zip(axes,(25.,35.,40.)):
        maxrise=0.
        for env in envelopes:
            if env['air_c']!=air:
                continue
            t=np.array(env['time_s'])/60.
            maxrise=max(maxrise,max(env['max_temperature_c'])-air)
            ax.fill_between(t,env['min_temperature_c'],env['max_temperature_c'],color=colors[env['rr_percent']],alpha=.05,linewidth=0)
            ax.plot(t,env['max_temperature_c'],color=colors[env['rr_percent']],linestyle=styles[env['capacity_kwh']],linewidth=.85)
        ax.set(title=f'Air / initial {air:g} °C',xlabel='Elapsed time (min)',xlim=(0,110),ylim=(air-.04*maxrise,air+1.07*maxrise))
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        ax.grid(alpha=.2)
    axes[0].set_ylabel('A123-equivalent cell surface (°C)')
    fig.suptitle('Assumed sensitivity envelopes: 27 a/b/g variants per case and air',fontsize=10)
    handles=[Line2D([0],[0],color=colors[r],label=f'RR{r}%') for r in (2,3,4)]
    handles += [Line2D([0],[0],color='0.3',linestyle=styles[c],label=f'{c:g} kWh') for c in styles]
    fig.legend(handles=handles,loc='outside lower center',ncol=3,frameon=False)
    for ext in ('png','pdf','svg'):
        fig.savefig(HERE/f'thermal_sensitivity_envelopes.{ext}',dpi=220)
    plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(6.3,3.),sharey=True,layout='constrained')
    capcolors={283.2:'#0072B2',354.:'#D55E00',424.8:'#009E73'}
    for ax,rr in zip(axes,(2,3,4)):
        for cap in styles:
            points=sorted([r for r in variants if r['rr_percent']==rr and r['capacity_kwh']==cap
                           and r['a_multiplier']==1 and r['g']==1 and r['air_c']==25],key=lambda r:r['b_multiplier'])
            ax.plot([r['b_multiplier'] for r in points],[r['common_peak_rise_c'] for r in points],marker='o',markersize=3,
                    color=capcolors[cap],label=f'{cap:g} kWh')
        ax.set(title=f'RR {rr}%',xlabel='b multiplier',xticks=[.5,1,2])
        ax.grid(alpha=.2)
    axes[0].set_ylabel('Common-window peak surface rise (°C)')
    axes[1].legend(loc='upper center',bbox_to_anchor=(.5,-.25),ncol=3,frameon=False)
    fig.suptitle('Cooling-ratio sensitivity: nominal a and g; air 25 °C',fontsize=10)
    for ext in ('png','pdf','svg'):
        fig.savefig(HERE/f'thermal_cooling_ratio_sensitivity.{ext}',dpi=220)
    plt.close(fig)


def main():
    generator=archived_generator()
    model_path=ROOT/'APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json'
    model=json.loads(model_path.read_text())
    a,b=model['a_K_per_A2_s'],model['b_per_s']
    assert a==4.344635339312832e-05 and b==.002655462788692412
    protocol=dict(date='2026-10-27',generator='Unchanged archived thermal_analysis.py exact exponential with Ieq=2.5*P_kW/capacity_kWh',
        a_K_per_A2_s=a,b_per_s=b,nominal_air_c=25.,nominal_initial_temperature_c=25.,reserve='External all-state 0.60*nominal kWh window (80% to 20%); includes stationary energy',
        table2='Primary common feasible time, start 0; all-state energy/time mean power; complete recurring unload-end to unload-end cycles only; cycle count reported',
        output_grid='1 s plus exact event/reserve/common endpoints, identical to archived baseline',
        sensitivity=dict(a_multipliers=[.5,1.,2.],b_multipliers=[.5,1.,2.],g_mean_square_heat=[1.,2.,4.],air_initial_c=[25.,35.,40.]),
        interpretation='A123-equivalent cell surface scenario; not a validated Z50 pack temperature. Multipliers are assumed stress scenarios, not statistical or measured RMS bounds.',
        pulse_anchor='Conditional sampled electrical deltaV/deltaI only; never substitutes a new generator or uniquely identifies R,C,K.',
        screens='60 °C retained as declared study screen; 55 °C supplemental historical matching-capacity M1-B operating screen; neither is a Z50 limit.')
    save_json('protocol.json',protocol)
    manifest_path=ROOT/'New_Afton_Experiments_2026-10-20/run_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    cases=[]
    sources=[]
    for meta in manifest['cases']:
        if not (meta['id'].startswith(('C080_','C100_','C120_')) and meta['status']=='EXECUTED_NATIVE_ARCHIVED'):
            continue
        path=manifest_path.parent/meta['result']
        digest=sha(path)
        assert digest==meta['result_sha256']
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute("SELECT * FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime,Id")]
        events=generator.prepare_events(rows)
        cutoff=generator.reserve_cutoff(events,meta['capacity_kwh'])
        cases.append(dict(meta=meta,raw=rows,events=events,cutoff_s=cutoff))
        sources.append(dict(case=meta['id'],path=str(path),sha256=digest,manifest_hash_match=True,events=len(rows),cutoff_min=cutoff/60.))
    assert len(cases)==9
    common_s=min(c['cutoff_s'] for c in cases)
    assert abs(common_s/60.-68.03897261395167)<1e-10
    archived_nominal=list(csv.DictReader((PRIOR/'results/thermal_nominal_traces.csv').open()))
    expected_traces={meta['id']:[] for meta in (c['meta'] for c in cases)}
    for row in archived_nominal:
        expected_traces[row['case']].append(row)
    table=[]
    reserve_summary=[]
    all_traces=[]
    all_cycles=[]
    variants=[]
    envelopes=[]
    envelope_rows=[]
    plotting=[]
    prior_variants=list(csv.DictReader((PRIOR/'results/thermal_variant_summary.csv').open()))
    prior_lookup={(r['case'],float(r['a_multiplier']),float(r['b_multiplier']),float(r['mean_square_heat_multiplier']),float(r['air_c'])):r for r in prior_variants}
    maximum_trace_difference=0.
    maximum_sensitivity_difference=0.
    for case in cases:
        meta,events,cutoff=case['meta'],case['events'],case['cutoff_s']
        base=dict(case=meta['id'],capacity_kwh=meta['capacity_kwh'],rr_percent=meta['rolling_resistance_percent'])
        nominal=generator.sample_trace(events,meta['capacity_kwh'],cutoff,1.,a,b,1.,25.,(common_s,))
        previous=expected_traces[meta['id']]
        assert len(previous)==len(nominal['time_s'])
        for k,t in enumerate(nominal['time_s']):
            assert t==float(previous[k]['time_s'])
            delta=abs(nominal['temperature_c'][k]-float(previous[k]['temperature_c']))
            maximum_trace_difference=max(maximum_trace_difference,delta)
            assert delta<1e-12
            all_traces.append({**base,'time_s':t,'temperature_c':nominal['temperature_c'][k],
                'equivalent_current_a':nominal['equivalent_current_a'][k],'current_eq_a':nominal['equivalent_current_a'][k],
                'air_c':25.,'event_mean_power_kw':nominal['event_mean_power_kw'][k],'power_kw':nominal['event_mean_power_kw'][k],
                'state':nominal['state'][k],'within_common_window':t<=common_s+1e-8,'own_reserve_endpoint_s':cutoff})
        plotting.append((base,nominal))
        for window,end,collection in [('common',common_s,table),('own_reserve',cutoff,reserve_summary)]:
            temps=[v for t,v in zip(nominal['time_s'],nominal['temperature_c']) if t<=end+1e-8]
            assert abs(nominal['time_s'][len(temps)-1]-end)<1e-8
            energy=energy_between(events,0.,end)
            cycles=recurring_cycles(case['raw'],end)
            assert cycles
            for cycle in cycles:
                all_cycles.append({**base,'window':window,**cycle})
            collection.append({**base,'window':window,'window_start_s':0.,'window_end_s':end,'window_end_min':end/60.,
                'air_c':25.,'initial_temperature_c':25.,'window_energy_kwh':energy,'mean_power_kw':energy*3600./end,
                'complete_recurring_cycles':len(cycles),'energy_per_complete_cycle_kwh':statistics.mean(c['energy_kwh'] for c in cycles),
                'cycle_energy_min_kwh':min(c['energy_kwh'] for c in cycles),'cycle_energy_max_kwh':max(c['energy_kwh'] for c in cycles),
                'cycle_time_mean_min':statistics.mean(c['duration_s'] for c in cycles)/60.,
                'peak_surface_c':max(temps),'peak_rise_c':max(temps)-25.,'end_surface_c':temps[-1],'end_rise_c':temps[-1]-25.,
                'margin_to_60c_study_screen_c':60.-max(temps),'margin_to_55c_historical_operating_screen_c':55.-max(temps),
                'temperature_domain':'A123-equivalent cell surface; not validated Z50 pack'})
        groups={}
        for am,bm,g,air in itertools.product((.5,1.,2.),(.5,1.,2.),(1.,2.,4.),(25.,35.,40.)):
            tr=generator.sample_trace(events,meta['capacity_kwh'],cutoff,1.,a*am,b*bm,g,air,(common_s,))
            common_temp=[v for t,v in zip(tr['time_s'],tr['temperature_c']) if t<=common_s+1e-8]
            peak=max(tr['temperature_c'])
            row={**base,'a_multiplier':am,'b_multiplier':bm,'g':g,'air_c':air,'initial_temperature_c':air,
                'reserve_endpoint_s':cutoff,'common_endpoint_s':common_s,'peak_surface_c':peak,'peak_rise_c':peak-air,
                'end_surface_c':tr['temperature_c'][-1],'end_rise_c':tr['temperature_c'][-1]-air,
                'common_peak_surface_c':max(common_temp),'common_peak_rise_c':max(common_temp)-air,
                'common_end_surface_c':common_temp[-1],'common_end_rise_c':common_temp[-1]-air,
                'margin_to_60c_study_screen_c':60.-peak,'margin_to_55c_historical_operating_screen_c':55.-peak}
            ref=prior_lookup[(meta['id'],am,bm,g,air)]
            difference=max(abs(peak-float(ref['peak_temperature_c'])),abs(tr['temperature_c'][-1]-float(ref['end_temperature_c'])))
            maximum_sensitivity_difference=max(maximum_sensitivity_difference,difference)
            assert difference<1e-12
            variants.append(row)
            if air not in groups:
                groups[air]={**base,'air_c':air,'time_s':tr['time_s'],
                             'min_temperature_c':list(tr['temperature_c']),'max_temperature_c':list(tr['temperature_c'])}
            else:
                env=groups[air]
                env['min_temperature_c']=[min(x,y) for x,y in zip(env['min_temperature_c'],tr['temperature_c'])]
                env['max_temperature_c']=[max(x,y) for x,y in zip(env['max_temperature_c'],tr['temperature_c'])]
        for env in groups.values():
            envelopes.append(env)
            for t,lo,hi in zip(env['time_s'],env['min_temperature_c'],env['max_temperature_c']):
                envelope_rows.append({**base,'air_c':env['air_c'],'time_s':t,'min_surface_c':lo,'max_surface_c':hi,'variants_in_envelope':27})
        print(json.dumps(dict(case=meta['id'],nominal_peak_c=max(nominal['temperature_c']),sensitivity_variants=81)),flush=True)
    assert len(variants)==729 and len(envelopes)==27 and len(all_traces)==45094
    save_csv('table2_common_window.csv',table)
    save_csv('nominal_reserve_summary.csv',reserve_summary)
    save_csv('nominal_traces.csv',all_traces)
    save_csv('complete_recurring_cycles.csv',all_cycles)
    save_csv('sensitivity_summary.csv',variants)
    save_csv('sensitivity_envelopes.csv',envelope_rows)
    metrics,electrical=electrical_and_residual_audit(model,generator)
    datasheet=dict(dataset=dict(url='https://data.mendeley.com/datasets/p8kf893yv3/1',publication_date='2021-08-17',cell='A123 26650 m1b 2.5 Ah',sampling='No blanket 1 s claim; see raw timestamp distributions.'),
        historical_matching_capacity=dict(url='https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/ANR-A123-26650.pdf',
            author='A123 Systems',document='ANR26650M1-B',copyright='2012',document_id='MD100113-02',nominal_capacity_ah=2.5,minimum_capacity_ah=2.4,operating_temperature_c=[-30.,55.],storage_temperature_c=[-40.,60.],
            applicability='Matches model/capacity label; exact serial-unit vintage is not established.'),
        later_revision=dict(url='https://lithiumwerks.com/wp-content/uploads/2022/08/26650-Power-Cell-080322.pdf',author='LithiumWerks',document_id='SF00008rev2',date='2022-08',
            typical_capacity_ah=2.6,minimum_capacity_ah=2.5,discharge_temperature_c=[-30.,60.],charge_temperature_c=[0.,60.]),
        screen_interpretation='60 °C is retained only as the declared study screen. Historical matching-capacity M1-B specifies 55 °C upper operating temperature and 60 °C storage temperature. Later M1B revision differs. Draft M1A reference must be corrected; no Z50 BMS operating limit is established.')
    save_json('datasheet_audit.json',datasheet)
    hashed=[Path(__file__),HERE/'test_thermal.py',PRIOR/'code/thermal_analysis.py',PRIOR/'results/thermal_nominal_traces.csv',PRIOR/'results/thermal_variant_summary.csv',PRIOR/'results/operations_comparison.csv',model_path,manifest_path,HERE.parent/'source_draft.txt']
    audit=dict(protocol=protocol,common_window_s=common_s,common_window_min=common_s/60.,source_hashes=[dict(path=str(p),sha256=sha(p)) for p in hashed],native_sources=sources,
        table2=table,nominal_reserve=reserve_summary,
        regeneration_checks=dict(nominal_trace_rows=len(all_traces),case_air_envelopes=len(envelopes),envelope_rows=len(envelope_rows),sensitivity_variants=len(variants),
            max_abs_difference_from_archived_nominal_temperature_c=maximum_trace_difference,max_abs_difference_from_archived_sensitivity_peak_end_c=maximum_sensitivity_difference),
        sensitivity=dict(max_surface_c=max(r['peak_surface_c'] for r in variants),max_rise_c=max(r['peak_rise_c'] for r in variants),
            max_common_surface_c=max(r['common_peak_surface_c'] for r in variants),max_common_rise_c=max(r['common_peak_rise_c'] for r in variants),
            max_temperature_case=max(variants,key=lambda r:r['peak_surface_c'])),
        cell_residual_metrics=metrics,pulse_anchor=electrical,datasheet=datasheet,
        tests=dict(red='5 expected missing-behavior assertion failures before implementing new functions, plus one alias-normalization regression failure before fixing the record-schema mismatch',green='6 tests passed; archived core tests retained and rerun separately'),
        limitations=['EqualP/E matching is a cell-equivalent scenario; topology, per-cell current, pack cooling and cell-to-pack thermal scaling are unknown.',
            'Only a=R_eff/C_eff and b=K_eff/C_eff are thermal-fit parameters; any electrical anchoring is conditional and does not establish unique C,K or pack parameters.',
            'No ventilation velocity-to-K relation is measured or simulated; air boundaries and ratio multipliers are declared assumptions, not literature-derived field validation.',
            'Event-average power omits within-event current variance; g=1/2/4 values are assumed heating scenarios, not defensible measured RMS bounds.',
            'Nominal modeled rises are smaller than the prior same-cell held-out RMSE and cannot establish validated thermal ranking across Z50 configurations.',
            'Complete recurring cycle estimates are based on one common-window cycle per configuration; simulation repeats are not independent experimental replications.',
            '60 °C is a declared screen, not a verified exact-cell or Z50 operational limit; 55 °C historical-cell margins are supplemental.',
            'No reaction heat, core temperatures, pack hotspots, failures, mine false-alarm rates or safe operating decisions are established.'],
        reproduction=['python -m unittest discover -s APCOM_Draft_Experiments_2026-10-27/thermal -p test_thermal.py -v','python APCOM_Draft_Experiments_2026-10-27/thermal/run_thermal.py'])
    save_json('thermal_audit.json',audit)
    plot(plotting,envelopes,variants,common_s)
    print(json.dumps(dict(common_window_min=common_s/60.,rows=len(all_traces),variants=len(variants),
                         conditional_anchors=electrical['conditional_anchors'],max_sensitivity_c=audit['sensitivity']['max_surface_c'])),flush=True)


if __name__=='__main__':
    main()
