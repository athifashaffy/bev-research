"""Fit a reduced surface-temperature model, freeze, and evaluate separate records."""
from pathlib import Path
import sys,json,hashlib,csv
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent/'tools'))
sys.path.insert(0,str(ROOT/'research/coupled_thermal_2026_10_16/tools'))
import numpy as np
from scipy.io import loadmat
from scipy.optimize import least_squares
OUT=Path(__file__).resolve().parents[1] if Path(__file__).parent.name=='code' else ROOT/'APCOM_Coupled_Thermal_2026-10-16'
DATA=OUT/'sources'

def read_record(name):
    d=loadmat(DATA/name,simplify_cells=True)['Data']
    t=np.asarray(d['time'],float);t-=t[0]
    temp=d.get('SurfaceTemperature',d.get('Ts1',d.get('Ts')))
    air=d.get('AirTemperature',d.get('Tf'))
    arrays=[t,np.asarray(d['current'],float),np.asarray(temp,float),np.asarray(air,float)]
    assert all(x.shape==t.shape and np.isfinite(x).all() for x in arrays)
    assert np.all(np.diff(t)>0)
    return arrays

def predict(t,current,air,initial,a,b):
    dt=np.diff(t); decay=np.exp(-b*dt)
    eq=air[:-1]+a/b*current[:-1]**2
    pred=np.empty(len(t));pred[0]=initial
    for k in range(len(dt)):pred[k+1]=decay[k]*pred[k]+(1-decay[k])*eq[k]
    return pred

def metric(t,p,y):
    err=p-y;dt=np.diff(t)
    return {'RMSE_C':float(np.sqrt(np.average(err[1:]**2,weights=dt))),
        'MAE_C':float(np.average(abs(err[1:]),weights=dt)),
        'bias_C':float(np.average(err[1:],weights=dt)),
        'max_absolute_error_C':float(max(abs(err))),
        'measured_temperature_rise_range_C':float(np.ptp(y))}

if __name__=='__main__':
    (OUT/'results').mkdir(exist_ok=True)
    names=['A002_PeriodicPulseData.mat','A002_UDDS_P25.mat','A002_UDDS_P35.mat']
    t,i,y,air=read_record(names[0])
    weights=np.sqrt(np.r_[np.diff(t)[0],np.diff(t)]/np.mean(np.diff(t)))
    def residual(logp):
        a,b=np.exp(logp)
        return (predict(t,i,air,y[0],a,b)-y)*weights
    fit=least_squares(residual,np.log([1e-4,1e-3]),bounds=(np.log([1e-8,1e-6]),np.log([.1,1.])),xtol=1e-11,ftol=1e-11,gtol=1e-11)
    assert fit.success
    a,b=np.exp(fit.x)
    model={'equation':'dTs/dt = a*I_cell^2 - b*(Ts-Tair)',
       'a_K_per_A2_s':float(a),'b_per_s':float(b),'time_constant_s':float(1/b),
       'identifiability':'Only R_eff/C_eff and UA_eff/C_eff are fitted. No independently identified R, C or UA.',
       'fit_record':names[0],'test_records':names[1:],
       'fit_rule':'Full pulse record, time-weighted least squares, positive parameters; no test-record tuning.',
       'prediction_rule':'Measured initial surface temperature only. Left-held current and measured air input at original timestamps; no surface-temperature feedback.',
       'fit_success':bool(fit.success),'fit_nfev':int(fit.nfev),
       'dataset_doi':'10.17632/p8kf893yv3.1','nominal_cell_capacity_Ah':2.5,
       'domain':'A123 26650 m1b laboratory cell surface; not Z50 pack/core temperature'}
    # Freeze coefficients before consulting evaluation-record outcomes.
    (OUT/'results/frozen_cell_model.json').write_text(json.dumps(model,indent=2))
    metrics=[];audit=[]
    manifest=json.loads((DATA/'download_manifest.json').read_text())
    hashes={r['file']:r['sha256'] for r in manifest['files']}
    for index,name in enumerate(names):
        assert hashlib.sha256((DATA/name).read_bytes()).hexdigest()==hashes[name]
        t,i,y,air=read_record(name);p=predict(t,i,air,y[0],a,b)
        m=metric(t,p,y)
        # Comparator includes the measured initial offset and tracks chamber air only.
        baseline=air+(y[0]-air[0]);base=metric(t,baseline,y)
        active=(np.abs(i)>0.1)
        m.update(file=name,role='FIT' if index==0 else 'HELD_OUT_RECORD',
            air_following_baseline_RMSE_C=base['RMSE_C'],
            active_sample_RMSE_C=float(np.sqrt(np.mean((p[active]-y[active])**2))),
            mean_measured_air_C=float(np.mean(air)))
        metrics.append(m)
        audit.append({'file':name,'samples':len(t),'duration_s':float(t[-1]),
            'dt_min_median_max_s':[float(x) for x in [np.min(np.diff(t)),np.median(np.diff(t)),np.max(np.diff(t))]],
            'current_range_A':[float(min(i)),float(max(i))],
            'surface_range_C':[float(min(y)),float(max(y))],
            'air_range_C':[float(min(air)),float(max(air))],
            'missing_values':0,'strictly_increasing_times':True,'sha256':hashes[name]})
        with (OUT/'results'/name.replace('.mat','_prediction.csv')).open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['time_s','current_A','air_C','measured_surface_C','predicted_surface_C','air_baseline_C'])
            w.writerows(zip(t,i,air,y,p,baseline))
    (OUT/'results/record_metrics.json').write_text(json.dumps(metrics,indent=2))
    (OUT/'results/dataset_audit.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps({'model':model,'metrics':metrics},indent=2))
