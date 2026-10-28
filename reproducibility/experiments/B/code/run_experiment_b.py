"""Execute Section 4.5 on archived measurements, with an explicit event gate.

Only experiment_b outputs are written. No raw data, historical results or models
are modified. Forecast responses reuse hash-verified saved origin predictions.
"""
from pathlib import Path
from collections import defaultdict
import csv
import datetime
import gzip
import hashlib
import json
import math
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
BEV=ROOT.parents[1]
SRC=BEV/'LFP_Data_Feasibility_2026-10-20'
TUM=SRC/'sources'/'tum'
MEAS=TUM/'thermal runaway propagation data set'/'measurement data'
OLD=BEV/'ML_Forecasting_2026-10-25'/'lfp'
RESULT=ROOT/'results'
FIG=ROOT/'figures'
sys.path.insert(0,str(BEV/'New_Afton_Experiments_2026-10-20'/'tools'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from rules import causal_grid,trailing_rate,alarm_response,voltage_condition

FIXED=(45,50,55,60)
RATES=(1,2,5)
RULE_IDS=[f'fixed_{x}C' for x in FIXED]+[f'rate_{x}C_min' for x in RATES]
SPLITS={'241029':'train','241030':'train','241126':'train','241127':'train','250129':'train',
        '250130':'development','250211':'test','250212':'test'}


def digest(path,algorithm='sha256'):
    return hashlib.new(algorithm,path.read_bytes()).hexdigest()


def finite(value):
    return value is not None and math.isfinite(value)


def cleaned(value):
    if isinstance(value,dict):return {k:cleaned(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [cleaned(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def write_json(path,value):
    path.write_text(json.dumps(cleaned(value),ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')


def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else '' if isinstance(v,float) and not finite(v) else v for k,v in row.items()})


def read_pair(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        rows=csv.reader(stream);next(rows)
        a=[[float(x) for x in row[:2]] for row in rows if row]
    return [r[0] for r in a],[r[1] for r in a]


def describe(path,t,y,kind,dataset,record):
    good=[v for v in y if finite(v)]
    return dict(dataset=dataset,record=record,kind=kind,path=str(path.relative_to(BEV)),
                sha256=digest(path),n_samples=len(t),n_finite_values=len(good),
                start_s=t[0],end_s=t[-1],first_finite_s=next(ti for ti,yi in zip(t,y) if finite(yi)),
                last_finite_s=next(ti for ti,yi in zip(t[::-1],y[::-1]) if finite(yi)),
                finite_time=all(finite(ti) for ti in t),strictly_increasing=all(b>a for a,b in zip(t,t[1:])),
                median_dt_s=statistics.median(b-a for a,b in zip(t,t[1:])),max_dt_s=max(b-a for a,b in zip(t,t[1:])),
                min_value=min(good),max_value=max(good))


def source_integrity():
    paths=list(sorted((SRC/'sources'/'sheffield').glob('*.csv')))
    for category in ('cell temperatures','cell voltages','venting temperatures'):
        paths.extend(sorted((MEAS/category/'GraphiteLFP').glob('*LFP.txt')))
    inventory={r['path']:r for r in json.loads((TUM/'inventory.json').read_text(encoding='utf-8'))}
    checks=dict(line.split(' *',1)[::-1] for line in (TUM/'checksums.sha512').read_text().splitlines())
    result=[]
    for p in paths:
        if p.suffix=='.csv':
            expected=json.loads(p.with_suffix('.csv.provenance.json').read_text(encoding='utf-8'))['sha256']
            expected512=None
        else:
            key=p.relative_to(TUM).as_posix()
            expected=inventory[key]['sha256'];expected512=checks[key]
        actual=digest(p)
        assert actual==expected,f'Archived SHA256 mismatch: {p}'
        if expected512:assert digest(p,'sha512')==expected512,f'Publisher SHA512 mismatch: {p}'
        result.append(dict(path=str(p.relative_to(BEV)),sha256=actual,archived_sha256_matches=True,
                           publisher_sha512_matches=True if expected512 else None,bytes=p.stat().st_size))
    assert len(result)==43,len(result)
    return result


def load_temperatures():
    previous={r['record']:r for r in json.loads((BEV/'APCOM_Study_2026-10-22'/'results'/'lfp_sheffield_records.json').read_text(encoding='utf-8'))}
    result=[];inventory=[]
    for path in sorted((SRC/'sources'/'sheffield').glob('*.csv')):
        with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        t=[float(r['Time (s)']) for r in rows];y=[float(r['Cell Temperature (degC)']) for r in rows]
        heater=next((float(r['Time (s)']) for r in rows if finite(float(r['Heater Power (W)'])) and float(r['Heater Power (W)'])>1),None)
        record=path.stem
        item=dict(dataset='Sheffield',record=record,split=SPLITS[record[:6]],group=record[:6],t=t,y=y,
                  heater_start_s=heater,quality_flags=previous[record]['quality_flags'])
        result.append(item);inventory.append(describe(path,t,y,'cell_temperature','Sheffield',record))
    for i in range(1,7):
        path=MEAS/'cell temperatures'/'GraphiteLFP'/f'T{i}_LFP.txt'
        t,y=read_pair(path);record=f'T{i}'
        flags=['One dependent five-cell module; no independent test per TC']
        flags.append('Damaged heater/cell1-associated TC ends near185.9s; not extrapolated' if i==1 else 'Exact TC filename to cell-interface mapping remains unverified')
        result.append(dict(dataset='TUM',record=record,split='transfer',group='TUM_LFP_MODULE_1',t=t,y=y,
                           heater_start_s=0.,quality_flags=flags))
        inventory.append(describe(path,t,y,'cell_temperature','TUM',record))
    return result,inventory


def screen(trajectories):
    responses=[];coverage=[];features=[];grids={}
    for item in trajectories:
        g=causal_grid(item['t'],item['y'],gap_limit=1.01 if item['dataset']=='Sheffield' else 2.)
        rates=trailing_rate(g['values'],g['segment'])
        key=(item['dataset'],item['record']);grids[key]=(g,rates)
        common=dict(dataset=item['dataset'],record=item['record'],split=item['split'],independence_group=item['group'])
        coverage.append(dict(**common,n_grid_points=len(g['time_s']),n_valid_temperature=sum(finite(v) for v in g['values']),
             n_valid_60s_rate=sum(finite(v) for v in rates),first_grid_s=g['time_s'][0],last_grid_s=g['time_s'][-1],
             first_valid_rate_s=next((t for t,v in zip(g['time_s'],rates) if finite(v)),None),
             max_measurement_age_s=max(g['measurement_age_s']),raw_heater_start_s=item['heater_start_s'],quality_flags=item['quality_flags']))
        for family,thresholds,values,unit in [('fixed',FIXED,g['values'],'C'),('rate',RATES,rates,'C/min')]:
            for threshold in thresholds:
                r=alarm_response(g['time_s'],values,g['segment'],threshold,rate=family=='rate')
                responses.append(dict(**common,rule=f'fixed_{threshold}C' if family=='fixed' else f'rate_{threshold}C_min',
                    family=family,threshold=threshold,threshold_units=unit,comparison='strict >',**r,
                    independent_reference_s=None,lead_time_s='UNAVAILABLE',miss_status='UNAVAILABLE: no independent physical reference',
                    interpretation='Descriptive threshold response only; not TR warning lead time or a confirmed miss'))
        features.extend(dict(**common,time_s=t,temperature_c=y,rate60_c_min=r,measurement_time_s=mt,
            measurement_age_s=age,segment=seg) for t,y,r,mt,age,seg in zip(g['time_s'],g['values'],rates,g['measurement_time_s'],g['measurement_age_s'],g['segment']))
    write_csv(RESULT/'rule_responses.csv',responses);write_csv(RESULT/'coverage.csv',coverage)
    with gzip.open(RESULT/'causal_features.csv.gz','wt',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(features[0]));w.writeheader()
        for row in features:w.writerow({k:'' if isinstance(v,float) and not finite(v) else v for k,v in row.items()})
    return responses,coverage,grids


def event_audit(inventory,trajectories,responses):
    events=[];voltage=[];voltage_traces={};vent_traces={};common_clock=[]
    for item in trajectories:
        events.append(dict(dataset=item['dataset'],record=item['record'],independence_group=item['group'],
            candidate_event='Independent physical TR/vent reference',reference_time_s=None,reference_lower_s=None,reference_upper_s=None,
            verified_independent_physical_event=False,clock_uncertainty_bound_s=None,
            status='UNAVAILABLE',reason='No independent temperature-free physical reference with verified sensor-clock uncertainty; temperature slope/heater startup are excluded as onset labels'))
    tc={r['record']:r for r in trajectories if r['dataset']=='TUM'}
    for i in range(1,6):
        path=MEAS/'cell voltages'/'GraphiteLFP'/f'U{i}_LFP.txt';t,u=read_pair(path)
        row=describe(path,t,u,'cell_voltage','TUM',f'U{i}')
        condition=voltage_condition(t,u)
        voltage.append(dict(**row,**condition,reference_type='Study-defined electrical condition, not physical TR onset',
            absolute_clock_uncertainty_bound_s=None,physical_origin_unverified=True,
            fault_exclusion='A sustained measured collapse is visible; sense-wire/contact failure cannot independently be excluded from the archive'))
        inventory.append(row);voltage_traces[f'U{i}']=(t,u)
        bracket=condition['bracket_s']
        events.append(dict(dataset='TUM',record=f'U{i}',independence_group='TUM_LFP_MODULE_1',
            candidate_event='Native U<=0.1 V sustained for5s with normal preheater context',reference_time_s=condition['condition_start_s'],
            reference_lower_s=bracket[0] if bracket else None,reference_upper_s=bracket[1] if bracket else None,
            verified_independent_physical_event=False,clock_uncertainty_bound_s=None,status='DESCRIPTIVE_ELECTRICAL_CONDITION',
            reason='Independent measured voltage channel, but no audited clock-offset bound or independent sense-wire-fault exclusion; not TR or vent onset'))
        for name,item in tc.items():
            common_clock.append(dict(voltage=f'U{i}',temperature=name,native_first_timestamp_difference_s=t[0]-item['t'][0],
                common_numeric_clock_overlap_start_s=max(t[0],item['t'][0]),common_numeric_clock_overlap_end_s=min(t[-1],item['t'][-1]),
                documented_logger='Paper Section2.3 describes both signals on the same CAN logger',
                observed_phase_is_absolute_offset_bound=False,absolute_clock_offset_uncertainty_bound_s=None,
                mapping='Module-level comparison only; no unverified TC-to-cell pairing'))
        path=MEAS/'venting temperatures'/'GraphiteLFP'/f'T{i}vent_LFP.txt';tv,v=read_pair(path)
        inventory.append(describe(path,tv,v,'vent_temperature','TUM',f'T{i}vent'));vent_traces[f'T{i}vent']=(tv,v)
        events.append(dict(dataset='TUM',record=f'T{i}vent',independence_group='TUM_LFP_MODULE_1',candidate_event='Independent vent opening',
            reference_time_s=None,reference_lower_s=None,reference_upper_s=None,verified_independent_physical_event=False,
            clock_uncertainty_bound_s=None,status='UNAVAILABLE',reason='Vent thermocouple is a temperature signal, not a vent-opening switch or independently synchronized visual event'))
    first=min((r for r in voltage if r['condition_start_s'] is not None),key=lambda r:r['condition_start_s'],default=None)
    relative=[]
    for rule in RULE_IDS:
        times=[r['alarm_s'] for r in responses if r['dataset']=='TUM' and r['rule']==rule and r['alarm_s'] is not None]
        alarm=min(times) if times else None;bracket=first['bracket_s'] if first else None
        relative.append(dict(independence_group='TUM_LFP_MODULE_1',rule=rule,module_first_any_tc_alarm_s=alarm,
            first_qualified_voltage_channel=first['record'] if first else None,
            electrical_condition_start_s=first['condition_start_s'] if first else None,
            electrical_condition_confirmed_s=first['confirmed_s'] if first else None,
            conditional_condition_minus_alarm_lower_s=bracket[0]-alarm if bracket and alarm is not None else None,
            conditional_condition_minus_alarm_upper_s=bracket[1]-alarm if bracket and alarm is not None else None,
            interval_covers_sampling_only=True,unknown_clock_offset_not_bounded=True,
            physical_tr_lead_time_s='UNAVAILABLE',interpretation='Arithmetic alarm-to-electrical-condition interval conditional on the shared numeric clock; external heater can cause early alarms; not prediction validation'))
    write_csv(RESULT/'event_register.csv',events);write_json(RESULT/'event_register.json',events)
    write_csv(RESULT/'voltage_condition_audit.csv',voltage);write_json(RESULT/'voltage_condition_audit.json',voltage)
    write_csv(RESULT/'clock_alignment_audit.csv',common_clock)
    write_csv(RESULT/'module_alarm_to_voltage_condition.csv',relative)
    video=SRC/'video_audit'/'event_annotations.json'
    write_json(RESULT/'event_admissibility.json',dict(verified_independent_physical_reference_events=0,
        main_table5_lead_time='UNAVAILABLE',main_table5_misses='UNAVAILABLE',main_table5_field_false_alarms='UNAVAILABLE',
        temperature_derived_onset_used=False,heater_start_is_reference_event=False,
        voltage_definition='Prespecified <=0.1 V sustained5elapsedseconds with normal preheater baseline; electrical observable only',
        voltage_clock='Same CAN logger reported; source sensor timestamps retained; no independently audited absolute clock-offset uncertainty bound',
        voltage_fault_exclusion='Sense-wire/contact loss cannot be excluded independently; physical voltage-collapse interpretation unverified',
        vent_channel='Thermocouple temperature at a vent is not independent vent-opening evidence',
        videos='Edited playback, no verified sensor-clock synchronization; prior visible-plume observations retained only on video clock',
        prior_video_audit_path=str(video.relative_to(BEV)),prior_video_audit_sha256=digest(video),
        paper_doi='10.1016/j.etran.2023.100305',paper_section='2.3 common CAN logging; 3.1.2 temperature-and-voltage propagation criterion not reproduced here',
        paper_author_fulltext='https://www.researchgate.net/publication/376591319_Thermal_runaway_propagation_in_automotive_lithium-ion_batteries_with_NMC-811_and_LFP_cathodes_Safety_requirements_and_impact_on_system_integration'))
    return voltage,relative,voltage_traces,vent_traces


def table5(responses):
    rows=[]
    groups=[('Sheffield_all','Sheffield',None),('Sheffield_train','Sheffield','train'),('Sheffield_development','Sheffield','development'),('Sheffield_test','Sheffield','test'),('TUM_channels','TUM',None)]
    for title,dataset,split in groups:
        for rule in RULE_IDS:
            data=[r for r in responses if r['dataset']==dataset and (split is None or r['split']==split) and r['rule']==rule]
            times=[r['alarm_s'] for r in data if r['alarm_s'] is not None]
            rows.append(dict(record_set=title,rule=rule,records_or_channels=len(data),
                date_groups=len({r['independence_group'] for r in data}) if dataset=='Sheffield' else None,
                independent_module_experiments=1 if dataset=='TUM' else None,
                responses=len(times),first_crossing_records=sum(r['first_crossing_s'] is not None for r in data),
                total_eligible_samples=sum(r['eligible_samples'] for r in data),
                first_alarm_min_s=min(times) if times else None,first_alarm_median_s=statistics.median(times) if times else None,
                first_alarm_max_s=max(times) if times else None,verified_independent_reference_events=0,
                lead_time_s='UNAVAILABLE',misses='UNAVAILABLE',field_false_alarm_rate='UNAVAILABLE',
                interpretation='Descriptive record/channel responses; Sheffield outcomes not independently confirmed; TUM channels belong to one module'))
    write_csv(RESULT/'table5.csv',rows);write_json(RESULT/'table5.json',rows)
    return rows


def forecast_screen():
    manifest=json.loads((OLD/'results'/'final_artifact_manifest.json').read_text(encoding='utf-8'))['files']
    lookup={Path(x['path']).as_posix():x for x in manifest}
    names=['results/downstream_origin_predictions.csv.gz','results/selected_family_by_horizon.csv',
           'models/boosting_10s.joblib','models/boosting_30s.joblib','models/boosting_60s.joblib']
    verified=[]
    for name in names:
        expected=next(x['sha256'] for key,x in lookup.items() if key.replace('\\','/')==name)
        path=OLD/name;actual=digest(path);assert expected==actual,name
        verified.append(dict(path=str(path.relative_to(BEV)),sha256=actual,archived_manifest_matches=True))
    grouped=defaultdict(list)
    with gzip.open(OLD/'results'/'downstream_origin_predictions.csv.gz','rt',newline='') as stream:
        for row in csv.DictReader(stream):
            if row['dataset'] not in ('Sheffield_test','TUM_transfer'):continue
            grouped[(row['dataset'],row['record'],int(row['horizon_s']))].append(row)
    rows=[]
    for (dataset,record,horizon),data in sorted(grouped.items()):
        t=[float(r['origin_s']) for r in data]
        current=[float(r['current_temperature_c']) if r['current_temperature_c'] else math.nan for r in data]
        forecast=[float(r['forecast_temperature_c']) if r['forecast_temperature_c'] else math.nan for r in data]
        segments=[0]*len(t)
        for threshold in FIXED:
            raw=alarm_response(t,current,segments,threshold);pred=alarm_response(t,forecast,segments,threshold)
            delta=raw['alarm_s']-pred['alarm_s'] if raw['alarm_s'] is not None and pred['alarm_s'] is not None else None
            rows.append(dict(dataset=dataset,record=record,horizon_s=horizon,model='Frozen Oct25 development-selected boosting',threshold_c=threshold,
                n_origins=len(t),available_origins=sum(finite(v) for v in forecast),
                forecast_first_point_origin_s=pred['first_crossing_s'],forecast_5s_response_origin_s=pred['alarm_s'],
                matched_current_first_point_origin_s=raw['first_crossing_s'],matched_current_5s_response_origin_s=raw['alarm_s'],
                matched_current_minus_forecast_response_origin_s=delta,lead_time_s='UNAVAILABLE',
                interpretation='Forecast-origin threshold response only; repeated5s forecasts do not prove future physical temperature persistence; no fitting or threshold tuning'))
    summaries=[]
    for dataset in ('Sheffield_test','TUM_transfer'):
        for horizon in (10,30,60):
            for threshold in FIXED:
                group=[r for r in rows if r['dataset']==dataset and r['horizon_s']==horizon and r['threshold_c']==threshold]
                diffs=[r['matched_current_minus_forecast_response_origin_s'] for r in group if r['matched_current_minus_forecast_response_origin_s'] is not None]
                summaries.append(dict(dataset=dataset,horizon_s=horizon,threshold_c=threshold,records_or_channels=len(group),
                    independent_module_experiments=1 if dataset=='TUM_transfer' else None,test_dates=2 if dataset=='Sheffield_test' else None,
                    forecast_responses=sum(r['forecast_5s_response_origin_s'] is not None for r in group),
                    matched_current_responses=sum(r['matched_current_5s_response_origin_s'] is not None for r in group),
                    earlier_forecast_response_count=sum(v>0 for v in diffs),tied_forecast_response_count=sum(v==0 for v in diffs),
                    later_forecast_response_count=sum(v<0 for v in diffs),median_current_minus_forecast_origin_s=statistics.median(diffs) if diffs else None,
                    physical_event_lead_time_s='UNAVAILABLE'))
    write_csv(RESULT/'forecast_threshold_responses.csv',rows);write_csv(RESULT/'forecast_threshold_summary.csv',summaries)
    write_json(RESULT/'forecast_reuse_integrity.json',dict(fitting_performed=False,model_selection_changed=False,thresholds_optimized=False,
        matched_origin_comparison=True,original_history_s=30,original_horizons_s=[10,30,60],verified_files=verified,
        caveat='Seven held-out Sheffield records share two test dates; TUM is one dependent module. No simulated ExperimentA model is applied to laboratory signals.'))
    return summaries


def save_figure(fig,name):
    for ext in ('png','svg','pdf'):fig.savefig(FIG/f'{name}.{ext}',dpi=240)
    plt.close(fig)


def figures(responses,voltage,voltage_traces,vent_traces):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.5,'axes.titlesize':10.5,'axes.labelsize':9.5,
                         'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,axs=plt.subplots(2,1,figsize=(6.6,9.5),gridspec_kw={'height_ratios':[27,6]})
    fig.subplots_adjust(left=.18,right=.855,top=.94,bottom=.085,hspace=.37)
    labels=['T >45°C','T >50°C','T >55°C','T >60°C','Rate >1\n°C/min','Rate >2\n°C/min','Rate >5\n°C/min']
    for ax,dataset in zip(axs,['Sheffield','TUM']):
        records=sorted({r['record'] for r in responses if r['dataset']==dataset})
        values=np.full((len(records),len(RULE_IDS)),np.nan)
        for i,record in enumerate(records):
            for j,rule in enumerate(RULE_IDS):
                row=next(r for r in responses if r['dataset']==dataset and r['record']==record and r['rule']==rule)
                if row['alarm_s'] is not None:values[i,j]=row['alarm_s']
        im=ax.imshow(np.ma.masked_invalid(values),aspect='auto',cmap='viridis',norm=LogNorm(vmin=8,vmax=2400))
        for i in range(len(records)):
            for j in range(len(RULE_IDS)):
                v=values[i,j]
                ax.text(j,i,'—' if math.isnan(v) else f'{v:.0f}',ha='center',va='center',fontsize=9.3,
                        color='#3b3b3b' if math.isnan(v) or v>500 else 'white')
        ax.set(yticks=range(len(records)),yticklabels=records,xticks=range(len(RULE_IDS)),xticklabels=labels)
        ax.set_title('Sheffield: 27 screening records\nNo independent physical onset' if dataset=='Sheffield' else 'TUM: six channels in one five-cell module',pad=9)
        if dataset=='Sheffield':
            for boundary in (14.5,19.5):ax.axhline(boundary,color='white',lw=2)
    cax=fig.add_axes([.88,.19,.025,.58]);fig.colorbar(im,cax=cax,label='First 5 s persistent response (s; log colour)')
    save_figure(fig,'warning_grid_responses')
    fig,axs=plt.subplots(2,1,figsize=(6.6,5.7),sharex=True)
    for row in voltage:
        t,u=voltage_traces[row['record']];axs[0].plot(t,u,label=row['record'],lw=1)
        if row['condition_start_s'] is not None:axs[0].scatter(row['condition_start_s'],.1,s=25,color='black',marker='x',zorder=4)
    axs[0].axhline(.1,color='black',ls='--',lw=.8)
    axs[0].set(ylim=(-.1,4.05),ylabel='Native voltage (V)',title='Study-defined voltage condition\nPhysical origin and clock uncertainty unverified')
    axs[0].legend(ncol=5,loc='upper right',frameon=True,facecolor='white',edgecolor='white',framealpha=.96)
    for name,(t,y) in vent_traces.items():axs[1].plot(t,y,label=name,lw=1)
    axs[1].set(xlim=(0,3000),ylim=(0,470),xlabel='Recorded sensor time (s)',ylabel='Vent temperature (°C)',title='Vent thermocouples do not independently\ntimestamp vent opening')
    axs[1].legend(ncol=5,loc='upper right',frameon=True,facecolor='white',edgecolor='white',framealpha=.96)
    for ax in axs:ax.grid(alpha=.18)
    fig.tight_layout();save_figure(fig,'electrical_and_vent_audit')


def main():
    protocol=ROOT/'01_experiment_b_protocol.json'
    assert json.loads(protocol.read_text(encoding='utf-8'))['fixed_thresholds_c']==list(FIXED)
    protocol_hash=digest(protocol)
    integrity=source_integrity()
    write_json(RESULT/'source_hashes.json',integrity)
    trajectories,inventory=load_temperatures()
    split_counts={split:sum(r['dataset']=='Sheffield' and r['split']==split for r in trajectories) for split in ('train','development','test')}
    assert split_counts=={'train':15,'development':5,'test':7},split_counts
    assert len({r['group'] for r in trajectories if r['split']=='test'})==2
    responses,coverage,grids=screen(trajectories)
    voltage,relative,vt,vent=event_audit(inventory,trajectories,responses)
    write_csv(RESULT/'native_channel_audit.csv',inventory)
    table=table5(responses);forecast=forecast_screen()
    figures(responses,voltage,vt,vent)
    summary=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=protocol_hash,
        draft_sha256=digest(ROOT.parent/'source_draft.txt'),rules_sha256=digest(Path(__file__).with_name('rules.py')),
        measurement_files_verified=len(integrity),source_checksum_mismatches=0,sheffield_records=27,
        sheffield_split_records=split_counts,sheffield_test_dates=['250211','250212'],
        tum_temperature_channels=6,tum_voltage_channels=5,tum_vent_temperature_channels=5,tum_independent_module_experiments=1,
        temperature_trajectories_screened=len(trajectories),rule_sensitivity_choices=len(RULE_IDS),record_rule_responses=len(responses),
        confirmed_tr_event_count=None,independently_verified_physical_reference_events=0,physical_event_lead_time='UNAVAILABLE',
        voltage_conditions_observed=sum(r['condition_start_s'] is not None for r in voltage),voltage_condition_is_TR_onset=False,
        voltage_condition_module_timing=relative,table5=table,forecast_threshold_summary=forecast,
        limits=['No temperature-derived landmark is used as independent event truth.',
                'Sheffield has 27 externally heated source records, not 35 ARC/oven records; low-temperature and censored records remain in the inventory.',
                'Heater startup is descriptive context; mass-channel corruption precludes a reliable vent label.',
                'Voltage-condition brackets bound sampling only; absolute sensor-clock offset and sense-wire/contact integrity are not independently bounded.',
                'TUM alarms are summarized at module level for electrical-condition comparisons; no unverified TC-to-cell pairings are invented.',
                'A heater-driven alarm occurring before a later voltage condition is not validated failure prediction.',
                'Forecast responses reuse saved development-selected laboratory temperature models; no training, threshold tuning, or ExperimentA-to-lab model transfer.',
                'No TR sensitivity, confirmed misses, field false-alarm rate or verified evacuation lead time is reported.'])
    write_json(RESULT/'summary.json',summary)
    write_json(RESULT/'protocol_hash.json',dict(protocol_sha256=protocol_hash,protocol_path=str(protocol.relative_to(BEV)),rules_sha256=summary['rules_sha256']))
    lines=['EXPERIMENT B: DESCRIPTIVE WARNING GRID','',
       'All 43 archived measurement files passed SHA256 checks; the 16 TUM text files also passed publisher SHA512 checks.',
       'Four strict fixed thresholds: 45, 50, 55 and 60 C; three strict past-60-second OLS thresholds: 1, 2 and 5 C/min. Each uses 5 elapsed seconds of debounce.',
       'Grid: latest available native value on integer seconds, no future interpolation, no repeated stale sample, no missing/gap bridging. A rate needs 61 valid points spanning 60 seconds.',
       'Sheffield: 27 screening records; 15 train / 5 development / 7 test records, with 2 held-out test dates. TUM: 6 thermocouples in one five-cell module.',
       'MAIN TABLE 5 PHYSICAL-REFERENCE LEAD TIME: UNAVAILABLE. No independently verified physical event with bounded clock alignment uncertainty.',
       'The supplementary <=0.1 V / 5 s condition was frozen before scoring. It is an electrical observable, not TR onset. Temperature alarms preceding it may be heater driven.',
       'Sampling brackets and arithmetic module-alarm-to-voltage-condition intervals are conditional on the shared numeric clock; unknown clock offset and sense-wire fault are not included.','']
    for row in table:
        if row['record_set'] in ('Sheffield_all','Sheffield_test','TUM_channels'):
            lines.append(f"{row['record_set']}, {row['rule']}: {row['responses']}/{row['records_or_channels']} responses; median first alarm {row['first_alarm_median_s']}s; physical lead time UNAVAILABLE.")
    lines+=['','The Sheffield rate responses all occur at 65 s because the first complete history becomes available at 60 s and already exceeds all three candidate rates; another 5 s satisfies debounce. This is a data-availability constraint, not verified physical event timing.',
            'Compatible forecast screen: saved Oct25 boosting forecasts only; 30 s history warm-up; strict fixed thresholds rescreened at identical available current/forecast origins; no fitting or tuning.',
            'For all four thresholds and all three horizons, the seven Sheffield test records have matched-current and forecast responses tied at 35 s. This does not establish TR warning ability. TUM response differences are reported descriptively for one dependent module.']
    (ROOT/'02_Results_and_Limitations.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert protocol_hash==digest(protocol),'Protocol changed during scoring'
    print('\n'.join(lines))


if __name__=='__main__':main()
