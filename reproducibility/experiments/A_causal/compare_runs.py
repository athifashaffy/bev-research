"""Verify fresh-run provenance and compare corrected, control and archive results."""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def content(path):return gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes()

def compare(first,second,control,output):
    if output.exists():raise ValueError('Choose a fresh comparison output directory')
    for folder in (first,second,control):
        proof=load(folder/'PROOF.json')
        assert load(folder/'status.json')['state']=='COMPLETE'
        for p,digest in proof['inputs_and_scripts_sha256'].items():
            assert sha(Path(p))==digest, f'Changed source: {p}'
        for name,digest in proof['outputs_sha256'].items():
            assert sha(folder/name)==digest, f'Changed output: {folder/name}'
    one,two,ctrl=map(lambda p:load(p/'summary.json'),(first,second,control))
    assert one['mode']==two['mode']=='completed_events'
    assert ctrl['mode']=='retrospective_control'
    assert load(first/'protocol.json')==load(second/'protocol.json')
    repeat={name:content(first/name)==content(second/name) for name in
            ['features.csv.gz','predictions.csv.gz','pooled_metrics.csv','per_case_metrics.csv','fold_assignments.json']}
    selection=lambda p:[{k:v for k,v in r.items() if k!='elapsed_s'} for r in load(p/'model_selection.json')]
    repeat['model_selection_without_timing']=selection(first)==selection(second)
    assert all(repeat.values()),'Independent runs differ; repeatability failed'
    output.mkdir(parents=True)
    result={'repeatability':repeat,'scope':'Same environment, independent processes; cross-platform identity unverified',
            'source_hashes_verified':True,'availability':load(first/'availability.json'),
            'corrected_decisions':one['decisions'],'stable_control_decisions':ctrl['decisions']}
    (output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    archive=HERE.parent/'A/archived_reference/table_4_pooled_metrics.csv'
    with archive.open() as stream:old=list(csv.DictReader(stream))
    rows=[];claims=[]
    for mode,metrics,source in [('archived',old,archive),('stable_control',ctrl['metrics'],control/'summary.json'),('completed_events',one['metrics'],first/'summary.json')]:
        for r in metrics:
            row={'mode':mode,'horizon_s':int(r['horizon_s']),'method':r['method'],
                 'n_origins':int(r['n_origins']),'rmse_c':float(r['rmse_c']),'mae_c':float(r['mae_c'])}
            rows.append(row)
            claims.append({'status':'MATCHED','source':str(source),'source_sha256':sha(source),'values':row})
    with (output/'comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (output/'claims.json').write_text(json.dumps(claims,indent=2)+'\n')
    lines=['Corrected forecasting experiment: local analysis, AI-assisted.',
           'Source inputs, original implementations and manuscript were preserved. These are newly fitted models.',
           '', 'What changed:',
           'At a forecast origin, only reports from completed activities are used. During an unfinished activity, temperature is estimated using the last completed current.',
           'The initial temperature and ambient are assumed 25 C; initial current is assumed zero before any report. Event reports are assumed available exactly at event end.',
           'Targets remain the original retrospective synthetic temperatures. Thus this is a delayed-report simulation benchmark, not measured truck validation.',
           'Stable slopes use centered scalar math.fsum and 12-decimal feature canonicalization.',
           '', 'Corrected pooled results: RMSE / MAE in millidegrees C.']
    for horizon in (60,120,300,600):
        lines.append(f'Horizon {horizon//60} minutes:')
        for r in one['metrics']:
            if r['horizon_s']==horizon:
                lines.append(f"  {r['method']}: {1000*r['rmse_c']:.3f} / {1000*r['mae_c']:.3f}")
    lines+=['','Conclusions:',
            'The following pass/fail decisions apply the original rule: strictly beat every baseline on both pooled RMSE and MAE.']
    for label,summary in [('Corrected',one),('Stable retrospective control',ctrl)]:
        for method in ('ridge','hist_gradient_boosting'):
            wins=[str(r['horizon_s']//60) for r in summary['decisions'] if r['method']==method and r['beats_all_baselines_on_both']]
            lines.append(f"{label}, {method}: passes at {', '.join(wins)} minutes.")
    lines+=['The original two-minute boosting superiority is not retained in the stabilized retrospective control.',
            'The corrected protocol has weaker, estimated current-state information for every method; better relative performance does not imply better absolute or physical accuracy.',
            'It is inappropriate to claim that the original detailed conclusions were reproduced unchanged.',
            '', 'Verification:',
            'Two independent corrected runs match exactly for decompressed features/predictions, metric tables, folds and model-selection records excluding timings.',
            f"Origins using unfinished-event reports: {result['availability']['origins_using_unfinished_event']} of {result['availability']['origins']} horizon-origin rows.",
            'All final input, script and output hashes verified. This is same-environment repeatability; cross-platform estimator identity remains untested.',
            'All cases share a route and a synthetic thermal generator. Real pack temperatures and event-reporting latency remain unvalidated.',
            'The new event-availability assumption changes the scientific protocol. The author should review it and independently execute the reproduction commands before submission.']
    (output/'report.txt').write_text('\n'.join(lines)+'\n')
    proof={'script':str(Path(__file__)),'script_sha256':sha(Path(__file__)),
           'run_proof_sha256':{str(p/'PROOF.json'):sha(p/'PROOF.json') for p in (first,second,control)},
           'outputs_sha256':{p.name:sha(p) for p in sorted(output.iterdir())}}
    (output/'PROOF.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('first','second','control','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    compare(args.first.resolve(),args.second.resolve(),args.control.resolve(),args.output.resolve())
