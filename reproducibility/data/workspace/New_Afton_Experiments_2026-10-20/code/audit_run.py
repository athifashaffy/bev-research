"""Read-only native output audit; never writes simulated values into a model."""
import json
import sqlite3
import sys
from pathlib import Path
from study import OUT, ROOT, sha

def read(path):
    c=sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True)
    c.row_factory=sqlite3.Row
    events=[dict(r) for r in c.execute("SELECT * FROM HS_EquipmentState WHERE EquipmentClass='Truck' ORDER BY SimulationTime,Id")]
    moves=[dict(r) for r in c.execute("SELECT * FROM HS_MaterialMovement")]
    c.close()
    # These cases configure a deterministic one-minute unloading service.
    # Native Quantity is populated even when that service is cut off at 120 min.
    for r in events:
        r["DeliveryComplete"] = r["State"]=="Unloading" and r["ElapsedTime"]>=1-1e-8
    assert sum(r["DeliveryComplete"] for r in events)==len(moves), "Unloading completion disagrees with material movements"
    return events,moves

def audit(case):
    archived=OUT/"results"/case/"native_run.hsmdb"
    p=archived if archived.exists() else OUT/"models"/case/(case+".hsmdb")
    events,moves=read(p)
    assert events, "No new native results"
    end=events[-1]["SimulationTime"]+events[-1]["ElapsedTime"]
    assert abs(end-120)<1e-6
    assert abs(sum(r["ElapsedTime"] for r in events)-120)<1e-6
    assert all(abs(a["SimulationTime"]+a["ElapsedTime"]-b["SimulationTime"])<1e-6 for a,b in zip(events,events[1:]))
    tonnes=sum(r["Quantity"] for r in moves)
    total=sum(r["ElectricityFromBatteryConsumed"] for r in events)
    wheel=sum(r["EnergyToWheels"] for r in events)
    stationary=sum(r["ElectricityFromBatteryConsumed"] for r in events if abs(r["DistanceTravelled"])<1e-9)
    errors=[r["ElectricityFromBatteryConsumed"]-(r["EnergyToWheels"]/.85+20*r["ElapsedTime"]/60) for r in events]
    manifest=json.loads((OUT/"run_manifest.json").read_text())
    info=next(r for r in manifest["cases"] if r["id"]==case)
    cap=info["capacity_kwh"]
    a=dict(case=case,truck_events=len(events),end_min=end,completed_tonnes=tonnes,
           audit_source=str(p.relative_to(OUT)),audit_source_sha256=sha(p),
           material_movements=len(moves),native_energy_kwh=total,wheel_traction_kwh=wheel,
           expected_all_state_energy_kwh=wheel/.85+40,
           stationary_energy_kwh=stationary,native_final_soc_pct=events[-1]["EnergyLevel"],
           native_soc_debit_kwh=cap*(80-events[-1]["EnergyLevel"])/100,
           corrected_final_soc_pct=80-total/cap*100,
           max_event_energy_reconstruction_error_kwh=max(map(abs,errors)),
           total_reconstruction_error_pct=100*(total-(wheel/.85+40))/(wheel/.85+40),
           deliveries_min=[r["SimulationTime"]+r["ElapsedTime"] for r in events if r["DeliveryComplete"]])
    a["native_soc_missing_kwh"]=total-a["native_soc_debit_kwh"]
    a["missing_minus_stationary_kwh"]=a["native_soc_missing_kwh"]-stationary
    if case=="BASELINE_ENERGY_OFF":
        for key in ["native_energy_kwh","stationary_energy_kwh","native_final_soc_pct",
                    "native_soc_debit_kwh","corrected_final_soc_pct",
                    "max_event_energy_reconstruction_error_kwh","total_reconstruction_error_pct",
                    "native_soc_missing_kwh","missing_minus_stationary_kwh"]:
            a[key]=None
        a["battery_audit_status"]="NOT_APPLICABLE_ENERGY_DISABLED"
        old,_=read(ROOT/"HAULSIM_Road_Surface_2026-10-15/results/RR03/New_Afton_A_RR03.hsmdb")
        keys=["SimulationTime","ElapsedTime","DistanceTravelled","EnergyToWheels","EnergyFromWheels","Quantity"]
        a["baseline_same_row_count"]=len(events)==len(old)
        a["baseline_max_numeric_difference"]=max(abs(x[k]-y[k])for x,y in zip(events,old)for k in keys)
        a["baseline_state_sequence_equal"]=[r["State"]for r in events]==[r["State"]for r in old]
    path=OUT/"results"/case/"audit.json";path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(a,indent=2))
    print(json.dumps(a,indent=2))

if __name__=="__main__": audit(sys.argv[1])
