"""AI-assisted fixed-scenario live telemetry benchmark; original experiments untouched."""
from pathlib import Path
import os
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[key]="1"
import argparse,csv,datetime,hashlib,json,platform,re,sqlite3,sys,time
import joblib,numpy as np,scipy,sklearn
from threadpoolctl import threadpool_limits,threadpool_info
from telemetry import A,B,HORIZONS,METHODS,original,stable,generate,reserve_cutoff,build_examples,predict_history
HERE=Path(__file__).resolve().parent
REPRO=HERE.parents[1]
ROOT=REPRO.parent
write_json=original.write_json
sha=original.sha

def validate_output(path):
    path=Path(path).resolve()
    if path.exists() or any(path.is_relative_to(p) for p in (REPRO/"data",ROOT/"data")):
        raise ValueError("Use a new output directory outside input data")
    return path

def verify_proof(folder):
    folder=Path(folder)
    proof=json.loads((folder/"PROOF.json").read_text())
    if json.loads((folder/"status.json").read_text())["state"]!="COMPLETE":raise ValueError("Run incomplete")
    for path,digest in proof["inputs_and_scripts_sha256"].items():
        if sha(path)!=digest:raise ValueError("Changed source: "+path)
    for name,digest in proof["outputs_sha256"].items():
        if sha(folder/name)!=digest:raise ValueError("Changed output: "+name)
    return proof

def load_scenarios():
    base=REPRO/"data/workspace"
    native=base/"New_Afton_Experiments_2026-10-20"
    manifest=native/"run_manifest.json"
    frozen=base/"APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json"
    model=json.loads(frozen.read_text())
    if (model["a_K_per_A2_s"],model["b_per_s"])!=(A,B):raise ValueError("Coefficient mismatch")
    paths=[manifest,frozen,HERE/"telemetry.py",Path(__file__),HERE/"replay.py",
           HERE.parent/"A/train.py",HERE.parent/"A_causal/inputs.py"]
    cases={};streams={}
    for item in json.loads(manifest.read_text())["cases"]:
        if not re.fullmatch(r"C(?:080|100|120)_RR0[234]",item["id"]):continue
        if item["status"]!="EXECUTED_NATIVE_ARCHIVED":raise ValueError("Unexecuted case")
        p=native/item["result"].replace("\\","/")
        if sha(p)!=item["result_sha256"]:raise ValueError("Native ledger hash mismatch")
        with sqlite3.connect(p.as_uri()+"?mode=ro",uri=True) as db:
            rows=db.execute("SELECT SimulationTime, ElapsedTime, ElectricityFromBatteryConsumed FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime,Id").fetchall()
        events=[dict(start_s=float(s)*60,end_s=float(s+d)*60,energy_kwh=float(e)) for s,d,e in rows]
        cap=float(item["capacity_kwh"]);cut=reserve_cutoff(events,cap)
        name=item["id"]
        cases[name]={"capacity_kwh":cap,"rr_pct":float(item["rolling_resistance_percent"]),
                     "reserve_cutoff_s":cut,"events":len(events),"native_source":str(p)}
        streams[name]=generate(events,cap,cut)
        paths.append(p)
    if len(cases)!=9:raise ValueError("Expected nine scenarios")
    return cases,streams,{str(p):sha(p) for p in paths}

def run(output):
    output=validate_output(output)
    if (np.__version__,scipy.__version__,sklearn.__version__)!=("2.3.5","1.16.3","1.7.2"):
        raise RuntimeError("Use experiments/A/requirements.txt")
    cases,streams,source_hashes=load_scenarios()
    protocol={"name":"ideal-live-simulated-telemetry-v1","frozen_before_fit":True,
      "scenario":"Archived complete activity energy/duration defines a constant-power offline scenario; not recovered instantaneous HAULSIM output.",
      "observation":"Noiseless, zero-latency sensor samples at integer seconds; only time <= origin is exposed to predictors.",
      "temperature_domain":"Generated A123-equivalent reference-cell surface, not measured truck pack.",
      "integration":"Exact heat equation across fractional event boundaries; current right-continuous.",
      "current_mapping":"2.5 Ah * activity_power_kW / capacity_kWh",
      "initial_temperature_c":25,"air_temperature_c":25,"a":A,"b":B,
      "reserve_rule":"80% initial SOC to 20% reserve, all activity energy included",
      "history_s":60,"origin_spacing_s":10,"horizons_s":HORIZONS,"methods":METHODS,
      "feature_names":original.FEATURE_NAMES,"numerics":"Centered math.fsum; 12 decimal histories/features",
      "model_grid":original.GRIDS["hist_gradient_boosting"],"seed":original.SEED,
      "evaluation":"Original nested whole-configuration splits; future generated temperatures only used as labels.",
      "success_rule":"Strictly beat each of three baselines on both pooled RMSE and MAE.",
      "limitations":["Same route and synthetic generator across configurations.","Within-activity variations, noise and reporting delay not represented.","30-minute forecasts depend on future workload; no future activity schedule is an input.","No pack or fault-detection validation."]}
    output.mkdir(parents=True);(output/"models").mkdir()
    write_json(output/"status.json",{"state":"RUNNING"})
    write_json(output/"protocol.json",protocol);write_json(output/"cases.json",cases)
    plan=original.nested_group_plan(cases);write_json(output/"fold_assignments.json",plan)
    sensor_rows=[]
    for name,s in streams.items():
        sensor_rows.extend(dict(case=name,time_s=int(r[0]),pack_power_kw=float(r[1]),
            equivalent_current_a=float(r[2]),reference_cell_temperature_c=float(r[3]),air_c=float(r[4])) for r in s)
    original.write_csv(output/"telemetry.csv.gz",sensor_rows)
    predictions=[];features=[];per_case=[];selections=[];replay_checks=[]
    start=time.perf_counter()
    with threadpool_limits(limits=1):
      pools=threadpool_info()
      for h in HORIZONS:
        examples={n:build_examples(s,cases[n]["capacity_kwh"],cases[n]["rr_pct"],h) for n,s in streams.items()}
        x=np.vstack([e["x"] for e in examples.values()])
        delta=np.concatenate([e["delta_c"] for e in examples.values()])
        groups=np.concatenate([np.repeat(n,len(e["origin_s"])) for n,e in examples.items()])
        for name,e in examples.items():
            features.extend({"case":name,"horizon_s":h,"origin_s":int(t),"max_input_time_s":int(t),
                **dict(zip(original.FEATURE_NAMES,map(float,e["x"][i])))} for i,t in enumerate(e["origin_s"]))
        for fold in plan:
            name=fold["outer_test"];e=examples[name];now=e["x"][:,0]
            model,selection=original.fit_selected("hist_gradient_boosting",x,delta,groups,fold)
            selections.append({"horizon_s":h,**selection})
            path=output/"models"/f"{name}_h{h}.joblib";joblib.dump(model,path)
            restored=joblib.load(path)
            pred={"persistence":now,"linear_trend":now+e["x"][:,4]*h,
                  "physics_hold":original.physics_forecast(now,e["x"][:,6],e["x"][:,12],h),
                  "hist_gradient_boosting":now+model.predict(e["x"])}
            readback=now+restored.predict(e["x"])
            if not np.array_equal(readback,pred["hist_gradient_boosting"]):raise AssertionError("Model readback mismatch")
            # At separated origins, execute the streaming-prefix prediction path.
            for idx in sorted({0,len(now)//2,len(now)-1}):
                t=int(e["origin_s"][idx]);c=cases[name]
                replay=predict_history(streams[name][t-60:t+1],c["capacity_kwh"],c["rr_pct"],{h:restored})[h]
                if any(replay[m]!=float(pred[m][idx]) for m in METHODS):raise AssertionError("Prefix replay mismatch")
                replay_checks.append(dict(case=name,horizon_s=h,origin_s=t,matched=True))
            for method in METHODS:
                per_case.append({"case":name,"horizon_s":h,"method":method,**original.error_metrics(e["target_c"],pred[method])})
                predictions.extend(dict(case=name,horizon_s=h,method=method,origin_s=int(t),target_s=int(t+h),
                    origin_temperature_c=float(now[i]),target_temperature_c=float(e["target_c"][i]),
                    predicted_temperature_c=float(pred[method][i])) for i,t in enumerate(e["origin_s"]))
        print(json.dumps({"horizon_s":h,"finished":True}),flush=True)
    pooled=[];decisions=[]
    for h in HORIZONS:
        for method in METHODS:
            rr=[r for r in predictions if r["horizon_s"]==h and r["method"]==method]
            pooled.append({"horizon_s":h,"method":method,**original.error_metrics([r["target_temperature_c"] for r in rr],[r["predicted_temperature_c"] for r in rr])})
        own=next(r for r in pooled if r["horizon_s"]==h and r["method"]=="hist_gradient_boosting")
        baselines=[r for r in pooled if r["horizon_s"]==h and r["method"]!="hist_gradient_boosting"]
        decisions.append({"horizon_s":h,"boosting_beats_all_on_both":all(own["rmse_c"]<r["rmse_c"] and own["mae_c"]<r["mae_c"] for r in baselines)})
    fits=sum(s["fit_count"] for s in selections)
    if fits!=405:raise AssertionError("Unexpected fit count")
    for file,rows in [("features.csv.gz",features),("predictions.csv.gz",predictions),
                      ("pooled_metrics.csv",pooled),("per_case_metrics.csv",per_case)]:
        original.write_csv(output/file,rows)
    write_json(output/"model_selection.json",selections);write_json(output/"replay_checks.json",replay_checks)
    versions={"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__,"sklearn":sklearn.__version__,"joblib":joblib.__version__,"platform":platform.platform()}
    write_json(output/"summary.json",{"mode":"ideal_simulated_live_sensors","versions":versions,"threadpools":pools,
        "model_fit_count":fits,"elapsed_s":time.perf_counter()-start,"decisions":decisions,
        "sensor_rows":len(sensor_rows),"forecast_origins":len(features),"metrics":pooled})
    for p,digest in source_hashes.items():
        if sha(p)!=digest:raise AssertionError("Source changed during run")
    write_json(output/"status.json",{"state":"COMPLETE","input_hashes_unchanged":True})
    write_json(output/"PROOF.json",{"recorded_by":"AI-assisted A_live/train.py","utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command":[sys.executable,*sys.argv],"versions":versions,"inputs_and_scripts_sha256":source_hashes,
        "outputs_sha256":{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="PROOF.json"}})
    verify_proof(output)
    print(json.dumps({"complete":True,"decisions":decisions}),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",required=True,type=Path)
    run(parser.parse_args().output)

