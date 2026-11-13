"""AI-assisted ideal live-sensor simulator, not recovered HAULSIM telemetry."""
from pathlib import Path
import importlib.util
import math
import numpy as np

HERE=Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result
stable=module("live_stable_inputs",HERE.parent/"A_causal/inputs.py")
original=module("live_original_forecast",HERE.parent/"A/train.py")
A,B=stable.A,stable.B
HORIZONS=(60,120,300,600,1800)
METHODS=("persistence","linear_trend","physics_hold","hist_gradient_boosting")

def reserve_cutoff(events,capacity):
    stable.validate_events(events)
    if not events or not math.isfinite(capacity) or capacity<=0:raise ValueError("Invalid ledger or capacity")
    used=0.;budget=.6*capacity
    for e in events:
        energy=e["energy_kwh"]
        if energy>0 and used+energy>=budget:
            return e["start_s"]+(budget-used)/energy*(e["end_s"]-e["start_s"])
        used+=energy
    return events[-1]["end_s"]

def generate(events,capacity,cutoff_s,a=A,b=B):
    """Fixed offline scenario sampled at 1 Hz; no event aggregates reach predictors.
    Columns: time_s, pack_power_kw, equivalent_current_a, reference_cell_C, air_C.
    Temperature is continuous; current is right-continuous at event boundaries.
    """
    stable.validate_events(events)
    if (not events or not all(math.isfinite(x) for x in (capacity,cutoff_s,a,b))
        or capacity<=0 or cutoff_s<0 or cutoff_s>events[-1]["end_s"] or min(a,b)<0):
        raise ValueError("Invalid simulator parameters")
    rows=[];k=0;state=25.;start=events[0]["start_s"]
    for t in range(math.floor(cutoff_s)+1):
        while k<len(events)-1 and t>=events[k]["end_s"]:
            e=events[k];power=e["energy_kwh"]*3600/(e["end_s"]-e["start_s"])
            state=stable.advance(state,2.5*power/capacity,e["end_s"]-start,25.,a,b)
            k+=1;start=events[k]["start_s"]
        e=events[k];power=e["energy_kwh"]*3600/(e["end_s"]-e["start_s"])
        current=2.5*power/capacity
        temp=stable.advance(state,current,t-start,25.,a,b)
        rows.append((t,power,current,temp,25.))
    return np.asarray(rows,float)

def history_features(prefix,capacity,rr):
    s=np.asarray(prefix,float)
    if s.ndim!=2 or s.shape[1]!=5 or len(s)<61:raise ValueError("Need 61 sensor rows")
    h=s[-61:]
    if not np.isfinite(h).all() or np.any(np.diff(h[:,0])!=1):raise ValueError("Invalid sensor clock or reading")
    return stable.stable_features(h[:,[3,2,4]],capacity,rr)

def build_examples(stream,capacity,rr,horizon):
    s=np.asarray(stream,float)
    if (s.ndim!=2 or s.shape[1]!=5 or not len(s) or s[0,0]!=0
        or not np.isfinite(s).all() or np.any(np.diff(s[:,0])!=1)
        or not isinstance(horizon,int) or horizon<=0):raise ValueError("Invalid stream or horizon")
    origins=np.arange(60,len(s)-horizon,10,dtype=int)
    if not len(origins):raise ValueError("No eligible forecasts for horizon")
    x=np.stack([history_features(s[t-60:t+1],capacity,rr) for t in origins])
    target=s[origins+horizon,3]
    return dict(origin_s=origins,x=x,target_c=target,origin_temperature_c=x[:,0],delta_c=target-x[:,0])

def predict_history(prefix,capacity,rr,models):
    """Only a past/current sensor window and fitted estimators enter this function."""
    x=history_features(prefix,capacity,rr);now=x[0];result={}
    for horizon,model in models.items():
        result[horizon]={"persistence":float(now),"linear_trend":float(now+x[4]*horizon),
            "physics_hold":float(original.physics_forecast(now,x[6],x[12],horizon))}
        if model is not None:result[horizon]["hist_gradient_boosting"]=float(now+model.predict(x.reshape(1,-1))[0])
    return result

