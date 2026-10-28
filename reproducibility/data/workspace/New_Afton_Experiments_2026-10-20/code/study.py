"""Native case authoring and auditable external energy/temperature arithmetic."""
import argparse
import hashlib
import json
import math
import shutil
import sqlite3
from pathlib import Path
from lxml import etree as ET

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent
SOURCE = ROOT/"HAULSIM_Road_Surface_2026-10-15/models/RR03/New_Afton_A_RR03.hsmdb"
RESULT_TABLES = ["HS_EquipmentState", "HS_MaterialMovement", "HS_ExperimentResult",
                "HS_LocationEvent", "HS_SimulationRunDump", "HS_ElectricityUsage",
                "TCO_HaulRouteAnalysisResult", "TCO_HaulRouteSegmentResult"]

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def pack(s):
    return dict(capacity_kwh=354*s, tare_kg=48148+8255*(s-1),
                pack_kg=8255*s, battery_kw=480*s,
                wheel_kw=min(391,.85*(480*s-20)))

def advance(T, boundary, current, seconds, a, b):
    if b == 0:
        return T+a*current**2*seconds
    return T+(boundary-T+a*current**2/b)*(-math.expm1(-b*seconds))

def score(events, capacity, horizon=120):
    """Partial final event is prorated assuming constant event-average power.

    Native rows are retained. A completed unloading is credited only at its
    end, including at the exact cutoff. No interpolation of delivery tonnage.
    """
    budget=.6*capacity
    used=0.; cutoff=horizon; loads=0
    for r in events:
        start=r["SimulationTime"]; duration=r["ElapsedTime"]
        if start >= cutoff-1e-10:
            break
        assert duration>0 and r["ElectricityFromBatteryConsumed"]>=-1e-8
        fraction=min(1., (cutoff-start)/duration)
        energy=max(0.,r["ElectricityFromBatteryConsumed"])
        if energy*fraction>budget-used:
            fraction=max(0.,(budget-used)/energy)
            cutoff=start+fraction*duration
        used+=energy*fraction
        if r["State"]=="Unloading" and r.get("DeliveryComplete",True) and fraction>=1-1e-10:
            loads+=1
    return dict(cutoff_min=cutoff, energy_kwh=used, end_soc_pct=80-100*used/capacity,
                completed_loads=loads, completed_tonnes=45*loads,
                reserve_reached=used>=budget-1e-7)

def put(root,path,value):
    n=root.find(path)
    if n is None: raise ValueError(path)
    n.attrib.pop("{http://www.w3.org/2001/XMLSchema-instance}nil",None)
    n.text=str(value)

def make(case_id, s=1, rr=3, energy=True):
    dest=OUT/"models"/case_id/(case_id+".hsmdb")
    if dest.exists(): raise FileExistsError(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SOURCE,dest); shutil.copy2(SOURCE.with_suffix(".hsm"),dest.with_suffix(".hsm"))
    c=sqlite3.connect(dest); c.row_factory=sqlite3.Row
    existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    cleared={}
    for t in RESULT_TABLES:
        if t in existing:
            c.execute(f'DELETE FROM "{t}"'); cleared[t]=c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    p=pack(s)
    if energy:
        row=c.execute("SELECT * FROM TruckType").fetchone()
        tx=ET.fromstring(row["XmlContent"].encode()); truck=tx.find(".//truck")
        cfg=ET.fromstring(row["ConfigurationXml"].encode())
        for path,val in {
            "model":case_id+" New Afton scenario",
            "desc":"Hypothetical battery family; all-state energy reconciled externally",
            "specs":"Assumed 20 kW auxiliaries; eta 0.85; fixed 440 kW retarder; no regen or charging",
            "engines/engine/name":f"Assumed {p['wheel_kw']} kW wheel power",
            "engines/engine/gross_power":p["wheel_kw"],
            "engines/engine/net_power":p["wheel_kw"],
        }.items(): put(truck,path,val)
        for axle in truck.findall("axles/axle"):
            put(axle,"empty_weight",p["tare_kg"]/2)
            put(axle,"full_weight",(p["tare_kg"]+45000)/2)
        curve=",".join(f"{i/10:.1f} {min(300000,p['wheel_kw']*1000/max(i/36,1e-9))/9.80665:.8f}" for i in range(141))
        put(truck,"rimpulls/graph/linestring",curve)
        # Retarder curve is deliberately untouched: it stays at 440 kW.
        put(truck,"fuels/graph[@type='elec']/linestring",f"-100 0 20,0 0 20,100 0 {p['wheel_kw']/.85+20:.12f}")
        e=cfg.find("EquipmentEnergyProperty")
        for k,v in dict(EnergyCapacity=p["capacity_kwh"],InitialEnergyMinLevel=80,
                        InitialEnergyMaxLevel=80,EnableElectricEnergy="true",
                        EnableRegenerativeBraking="false",MaximumRegenerativeCharging=0,
                        RegenerativeEfficiencyFactor=0,IsRechargingOrRefuellingEnabled="false",
                        MinimumEnergyThreshold=0,UseVariableEnergyRange="false",RefuellingRate=0).items():
            put(e,k,v)
        c.execute("UPDATE TruckType SET Description=?,XmlContent=?,ConfigurationXml=?",
                  (case_id+" New Afton-informed scenario",ET.tostring(tx,encoding="unicode"),ET.tostring(cfg,encoding="unicode")))
        c.execute("UPDATE HS_TruckType SET MotorPower=?,EmptyTruckWeight=?,FullTruckWeight=?,TyreLoadEmpty=?,TyreLoadFull=?",
                  (p["wheel_kw"],p["tare_kg"]/1000,(p["tare_kg"]+45000)/1000,p["tare_kg"]/2000,(p["tare_kg"]+45000)/2000))
        c.execute("UPDATE HS_Truck SET Name=?",("Truck "+case_id,))
    c.execute("UPDATE NetworkArc SET RollingResistance=?",(rr,))
    c.execute("UPDATE HS_ExperimentDetail SET RunTime=120,Replications=1,Description=?",(case_id,))
    c.execute("UPDATE HS_ExperimentScenario SET Haulers=1,Description=?",(case_id,))
    c.commit()
    assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    assert c.execute("SELECT COUNT(*) FROM HS_EquipmentState").fetchone()[0]==0
    geometry=dict(c.execute("SELECT SUM(Length) length_m,MIN(RollingResistance) rr_min,MAX(RollingResistance) rr_max FROM NetworkArc").fetchone())
    assert abs(geometry["length_m"]-1500)<1e-6
    c.close()
    return dict(id=case_id,scale=s,rolling_resistance_percent=rr,**p,
                native_energy_enabled=energy,status="PREPARED_NOT_RUN",
                model=str(dest.relative_to(OUT)),pre_run_sha256=sha(dest),
                pre_run_result_counts=cleared,geometry=geometry)

def build():
    manifest_path=OUT/"run_manifest.json"
    if manifest_path.exists():raise FileExistsError(manifest_path)
    cases=[make("BASELINE_ENERGY_OFF",energy=False)]
    for s in (.8,1.,1.2):
        for rr in (2,3,4):
            cases.append(make(f"C{int(s*100):03d}_RR{rr:02d}",s,rr))
    cases.append(make("C100_RR03_REPEAT"))
    m=dict(source_model=str(SOURCE.relative_to(ROOT)),source_sha256=sha(SOURCE),
           core_cases=9,total_native_runs_planned=11,cases=cases)
    manifest_path.write_text(json.dumps(m,indent=2))
    print(json.dumps(dict(prepared=len(cases),source_sha256=m["source_sha256"],all_empty=True)))

def archive(case_id):
    mp=OUT/"run_manifest.json";m=json.loads(mp.read_text())
    case=next(x for x in m["cases"] if x["id"]==case_id)
    src=OUT/case["model"];dest=OUT/"results"/case_id/"native_run.hsmdb"
    if dest.exists():raise FileExistsError(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    # SQLite backup gives a transactionally consistent snapshot of a live DB.
    with sqlite3.connect(src.as_uri()+"?mode=ro",uri=True) as c:
        n=c.execute("SELECT COUNT(*) FROM HS_EquipmentState WHERE EquipmentClass='Truck'").fetchone()[0]
        assert n>0, "No new native result rows"
        end=c.execute("SELECT MAX(SimulationTime+ElapsedTime) FROM HS_EquipmentState WHERE EquipmentClass='Truck'").fetchone()[0]
        assert abs(end-120)<1e-6,(case_id,end)
        with sqlite3.connect(dest) as d:c.backup(d)
    case.update(status="EXECUTED_NATIVE_ARCHIVED",result=str(dest.relative_to(OUT)),result_sha256=sha(dest),truck_rows=n,horizon_min=end)
    mp.write_text(json.dumps(m,indent=2))
    print(json.dumps({k:case[k] for k in ["id","status","truck_rows","horizon_min","result_sha256"]}))

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("action",choices=["build","archive"]);ap.add_argument("case",nargs="?")
    args=ap.parse_args()
    build() if args.action=="build" else archive(args.case)
