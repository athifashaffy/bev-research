"""Replay simulated readings and compute forecasts from a rolling past-only window.
AI-assisted. Model files must be from your own verified A_live run; not untrusted files.
"""
import os
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[key]="1"
import argparse,csv,gzip,json,time
from collections import deque
from pathlib import Path
import joblib
from threadpoolctl import threadpool_limits
from telemetry import HORIZONS,predict_history
from train import verify_proof

def replay(folder,case,start_s=60,end_s=120,speed=0):
    folder=Path(folder);verify_proof(folder)
    c=json.loads((folder/"cases.json").read_text())[case]
    models={h:joblib.load(folder/"models"/f"{case}_h{h}.joblib") for h in HORIZONS}
    history=deque(maxlen=61)
    with threadpool_limits(limits=1),gzip.open(folder/"telemetry.csv.gz","rt") as f:
      for r in csv.DictReader(f):
        if r["case"]!=case:continue
        t=int(r["time_s"])
        if t>end_s:break
        history.append([t,float(r["pack_power_kw"]),float(r["equivalent_current_a"]),float(r["reference_cell_temperature_c"]),float(r["air_c"])])
        if t<start_s:continue
        item={"simulation_time_s":t,"sensor":{k:float(r[k]) for k in ("pack_power_kw","equivalent_current_a","reference_cell_temperature_c","air_c")},"domain":"SIMULATED reference cell"}
        if len(history)==61 and t%10==0:
            item["forecasts"]=predict_history(list(history),c["capacity_kwh"],c["rr_pct"],models)
        print(json.dumps(item),flush=True)
        if speed>0:time.sleep(1/speed)
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--run",type=Path,required=True)
    p.add_argument("--case",default="C100_RR03");p.add_argument("--from-s",type=int,default=1200)
    p.add_argument("--to-s",type=int,default=1210);p.add_argument("--speed",type=float,default=0,help="0 accelerated, 1 one sample per real second")
    a=p.parse_args()
    if a.from_s<0 or a.to_s<a.from_s or a.speed<0:p.error("Invalid time range or speed")
    replay(a.run,a.case,a.from_s,a.to_s,a.speed)

