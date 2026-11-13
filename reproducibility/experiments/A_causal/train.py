"""AI-assisted corrected simulation benchmark; original experiment is preserved.

Run from any directory with the original pinned Experiment A dependencies.
Outputs are newly fitted results, not historical estimators or field validation.
"""
from pathlib import Path
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
import argparse
import csv
import datetime
import hashlib
import importlib.util
import json
import platform
import sqlite3
import sys
import time
import numpy as np
import scipy
import sklearn
from threadpoolctl import threadpool_limits, threadpool_info
from inputs import A, B, DECIMALS, history_as_of, stable_features, validate_events

HERE=Path(__file__).resolve().parent
REPRO=HERE.parents[1]
SOURCE=REPRO/'data/workspace'
spec=importlib.util.spec_from_file_location('original_experiment_a',HERE.parent/'A/train.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
MODES=('completed_events','retrospective_control')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def make_examples(name, case, events, horizon_s, mode):
    if mode not in MODES:
        raise ValueError('Unknown input protocol')
    grid,values=case['grid_s'],case['grid_values']
    if grid[0]!=0 or np.any(np.diff(grid)!=1):
        raise ValueError('Expected zero-based, contiguous target grid')
    records={k:[] for k in ('origin_s','x','target_c','origin_temperature_c','delta_c','current_a','air_c','source_end_s')}
    for origin in range(60,int(grid[-1])-horizon_s+1,10):
        # Retrospective target availability is not a predictor.
        if not np.isfinite(values[origin-60:origin+horizon_s+1]).all():
            continue
        if mode=='completed_events':
            history,meta=history_as_of(events,origin,case['capacity_kwh'])
            source_end=meta['latest_available_event_end_s']
            assert source_end<=origin
        else:
            history=values[origin-60:origin+1]
            source_end=next(e['end_s'] for e in events if e['start_s']<=origin<e['end_s'])
        x=stable_features(history,case['capacity_kwh'],case['rr_pct'])
        target=float(values[origin+horizon_s,0])
        for key,value in dict(origin_s=origin,x=x,target_c=target,origin_temperature_c=x[0],
                              delta_c=target-x[0],current_a=x[6],air_c=x[12],source_end_s=source_end).items():
            records[key].append(value)
    return {'case':name,**{k:np.asarray(v) for k,v in records.items()}}


def make_protocol(mode):
    if mode not in MODES:
        raise ValueError('Unknown input protocol')
    protocol={'name':'event-availability-comparison-v1','mode':mode,'frozen_before_fitting':True,
        'event_available_at':'Recorded end, zero additional reporting latency assumed',
        'temperature_input':'Completed-event reconstructed temperature, then last-known-current extrapolation to origin',
        'cold_start':{'temperature_C':25.,'air_C':25.,'current_A':0.},
        'target':'Unchanged archived event-average synthetic temperature at target time; never an input in completed_events mode',
        'numerics':{'canonical_decimal_places':DECIMALS,'slope':'Centered scalar math.fsum; constant-channel slope exactly zero'},
        'history_s':60,'spacing_s':10,'horizons_s':original.HORIZONS,'feature_names':original.FEATURE_NAMES,
        'model_grids':original.GRIDS,'seed':original.SEED,'groups':'Original nested whole-configuration folds',
        'success_rule':'Strictly beat all three baselines on pooled RMSE and MAE separately at each horizon',
        'limitations':['Simulation benchmark with delayed input reports, not measured truck temperatures.',
                       'No telemetry exists to recover actual within-event current.',
                       'No prediction is credited with real-time knowledge of an unfinished event.',
                       'Cross-platform exact estimator identity is unverified.']}
    control=mode=='retrospective_control'
    protocol['allows_unfinished_event_inputs']=control
    protocol['temperature_input_kind']='retrospective_target_history' if control else 'estimated_from_completed_events'
    if control:
        protocol['event_available_at']='Not constrained in this retrospective control; complete event averages are used from event start'
        protocol['temperature_input']='Archived retrospective temperature/current history through the forecast origin'
        protocol['cold_start']=None
        protocol['limitations']=[
            'Retrospective simulation control with unfinished-event information; not an online forecasting protocol.',
            'Shared synthetic targets, not measured truck temperatures.',
            'Cross-platform exact estimator identity is unverified.']
    return protocol


def run(output,mode):
    output=Path(output).resolve()
    if mode not in MODES or output.exists() or output.is_relative_to(REPRO/'data'):
        raise ValueError('Choose a valid protocol and a new output folder outside input data')
    versions={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
              'sklearn':sklearn.__version__,'platform':platform.platform()}
    if (np.__version__,scipy.__version__,sklearn.__version__)!=('2.3.5','1.16.3','1.7.2'):
        raise RuntimeError('Install experiments/A/requirements.txt pinned dependencies')
    source=SOURCE/'APCOM_Study_2026-10-22/results/thermal_nominal_traces.csv'
    native=SOURCE/'New_Afton_Experiments_2026-10-20'
    manifest_path=native/'run_manifest.json'
    frozen_path=SOURCE/'APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json'
    archive=HERE.parent/'A/archived_reference/table_4_pooled_metrics.csv'
    paths=[source,manifest_path,frozen_path,archive,Path(__file__),HERE/'inputs.py',HERE.parent/'A/train.py']
    cases=original.load_cases(source)
    frozen=json.loads(frozen_path.read_text())
    assert (frozen['a_K_per_A2_s'],frozen['b_per_s'])==(A,B)
    events={}
    for meta in json.loads(manifest_path.read_text())['cases']:
        if meta['id'] not in cases or meta['status']!='EXECUTED_NATIVE_ARCHIVED':
            continue
        path=native/meta['result'].replace('\\','/')
        if digest(path)!=meta['result_sha256']:
            raise ValueError('Native input hash mismatch')
        paths.append(path)
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            rows=db.execute("SELECT SimulationTime, ElapsedTime, ElectricityFromBatteryConsumed FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime,Id").fetchall()
        events[meta['id']]=[{'start_s':s*60,'end_s':(s+d)*60,'energy_kwh':e} for s,d,e in rows]
        validate_events(events[meta['id']])
    assert set(events)==set(cases)
    hashes={str(p):digest(p) for p in paths}
    output.mkdir(parents=True)
    protocol=make_protocol(mode)
    save_json(output/'protocol.json',protocol)
    save_json(output/'status.json',{'state':'RUNNING'})
    started=time.perf_counter()
    plan=original.nested_group_plan(cases)
    save_json(output/'fold_assignments.json',plan)
    examples={h:{n:make_examples(n,c,events[n],h,mode) for n,c in cases.items()} for h in original.HORIZONS}
    features=[]
    for h,bycase in examples.items():
        for name,e in bycase.items():
            for i,t in enumerate(e['origin_s']):
                features.append({'case':name,'horizon_s':h,'origin_s':int(t),'target_s':int(t+h),
                    'latest_report_end_s':float(e['source_end_s'][i]),
                    **dict(zip(original.FEATURE_NAMES,map(float,e['x'][i])))})
    original.write_csv(output/'features.csv.gz',features)
    availability={'mode':mode,'origins':len(features),
                  'origins_using_unfinished_event':sum(r['latest_report_end_s']>r['origin_s'] for r in features)}
    if mode=='completed_events':assert availability['origins_using_unfinished_event']==0
    save_json(output/'availability.json',availability)
    predictions=[];per_case=[];selections=[]
    with threadpool_limits(limits=1):
        pools=threadpool_info()
        for h,bycase in examples.items():
            x=np.vstack([e['x'] for e in bycase.values()]);delta=np.concatenate([e['delta_c'] for e in bycase.values()])
            groups=np.concatenate([np.repeat(n,len(e['origin_s'])) for n,e in bycase.items()])
            for fold in plan:
                name=fold['outer_test'];e=bycase[name];now=e['origin_temperature_c']
                pred={'persistence':now,'linear_trend':now+e['x'][:,4]*h,
                      'physics_hold':original.physics_forecast(now,e['current_a'],e['air_c'],h)}
                for method in original.METHODS[3:]:
                    model,selection=original.fit_selected(method,x,delta,groups,fold)
                    pred[method]=now+model.predict(e['x']);selections.append({'horizon_s':h,**selection})
                for method in original.METHODS:
                    per_case.append({'case':name,'horizon_s':h,'method':method,**original.error_metrics(e['target_c'],pred[method])})
                    for i,t in enumerate(e['origin_s']):
                        predictions.append({'case':name,'horizon_s':h,'method':method,'origin_s':int(t),'target_s':int(t+h),
                            'estimated_origin_temperature_c':float(now[i]),'true_temperature_c':float(e['target_c'][i]),
                            'predicted_temperature_c':float(pred[method][i]),'error_c':float(pred[method][i]-e['target_c'][i])})
            print(json.dumps({'horizon_s':h,'finished':True}),flush=True)
    pooled=[];decisions=[]
    for h in original.HORIZONS:
        for method in original.METHODS:
            rows=[r for r in predictions if r['horizon_s']==h and r['method']==method]
            pooled.append({'horizon_s':h,'method':method,**original.error_metrics([r['true_temperature_c'] for r in rows],[r['predicted_temperature_c'] for r in rows])})
        baselines=[r for r in pooled if r['horizon_s']==h and r['method'] in original.METHODS[:3]]
        for method in original.METHODS[3:]:
            own=next(r for r in pooled if r['horizon_s']==h and r['method']==method)
            decisions.append({'horizon_s':h,'method':method,
                'beats_all_baselines_on_both':all(own['rmse_c']<b['rmse_c'] and own['mae_c']<b['mae_c'] for b in baselines)})
    count=sum(s['fit_count'] for s in selections)
    assert count==792
    original.write_csv(output/'predictions.csv.gz',predictions)
    original.write_csv(output/'pooled_metrics.csv',pooled)
    original.write_csv(output/'per_case_metrics.csv',per_case)
    save_json(output/'model_selection.json',selections)
    save_json(output/'summary.json',{'mode':mode,'model_fit_count':count,'versions':versions,
        'threadpools':pools,'elapsed_s':time.perf_counter()-started,'decisions':decisions,'metrics':pooled,
        'scope':'NEW_REFIT_CORRECTED_PROTOCOL; NOT FIELD VALIDATION','protocol_sha256':digest(output/'protocol.json')})
    if not all(digest(Path(p))==sha for p,sha in hashes.items()):
        raise AssertionError('Input or implementation changed during run')
    save_json(output/'status.json',{'state':'COMPLETE','input_hashes_unchanged':True})
    save_json(output/'PROOF.json',{'recorded_by':'AI-assisted A_causal/train.py','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'command':[sys.executable,*sys.argv],'versions':versions,'inputs_and_scripts_sha256':hashes,
        'outputs_sha256':{p.name:digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name!='PROOF.json'}})
    print(json.dumps({'complete':True,'decisions':decisions}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=MODES,default='completed_events')
    args=parser.parse_args()
    run(args.output,args.mode)
