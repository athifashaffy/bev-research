from pathlib import Path
import contextlib, hashlib, importlib.util, io, json, os, re, shutil, tempfile
from urllib.parse import urlsplit, unquote

DEST=Path(__file__).resolve().parent
REPO=DEST.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((DEST/'release_copy_manifest.json').read_text())
assert all(sha(DEST/x['file'])==x['release_sha256'] for x in manifest['records'])
links=[]
for p in DEST.rglob('*.html'):
    for raw in re.findall(r'(?:href|src)=["\']([^"\']+)',p.read_text(encoding='utf-8')):
        u=urlsplit(raw)
        if u.scheme or not u.path: continue
        q=(p.parent/unquote(u.path)).resolve()
        links.append({'page':p.relative_to(DEST).as_posix(),'link':raw,'exists':q.exists()})
assert all(x['exists'] for x in links),[x for x in links if not x['exists']]
for name in ['sources.json','sources_video.json']:
    m=json.loads((DEST/'charts'/name).read_text(encoding='utf-8'))
    for v in m['sources'].values(): assert sha(REPO/v['path'])==v['sha256']
    for c in m['charts']:
        assert sha(DEST/'charts'/c['file'])==c['png_sha256']
        assert sha(DEST/'charts'/c['data_copy'])==c['csv_sha256']

with tempfile.TemporaryDirectory(prefix='bev-walkthrough-public-check-') as tmp:
    stage=Path(tmp)
    os.environ['MPLCONFIGDIR']=str(stage/'mplconfig')
    spec=importlib.util.spec_from_file_location('walkthrough_test_charts',DEST/'charts/build_charts.py')
    chart=importlib.util.module_from_spec(spec); spec.loader.exec_module(chart)
    chart.HERE=stage
    with contextlib.redirect_stdout(io.StringIO()): chart.main()
    regenerated=json.loads((stage/'sources.json').read_text(encoding='utf-8'))
    csvs=sorted(p.name for p in stage.glob('*.csv'))
    comparisons={name:sha(stage/name)==sha(DEST/'charts'/name) for name in csvs}
    assert all(comparisons.values()),comparisons
    spec2=importlib.util.spec_from_file_location('walkthrough_test_video_charts',DEST/'charts/build_video_charts.py')
    video=importlib.util.module_from_spec(spec2); spec2.loader.exec_module(video)
    video.OUTPUT=stage
    with contextlib.redirect_stdout(io.StringIO()): video.main()
    video_meta=json.loads((stage/'sources_video.json').read_text(encoding='utf-8'))
    assert video_meta['validation']['source_hashes_unchanged_after_render']
    assert all(sha(REPO/x['path'])==x['sha256'] for x in json.loads((DEST/'charts/sources.json').read_text())['sources'].values())

assert all(sha(DEST/x['file'])==x['release_sha256'] for x in manifest['records'])
report={'status':'PASS','scope':'Public-copy integrity, portable links, chart regeneration against committed archived outputs',
        'archived_chart_source_hashes_verified':7,
        'copied_release_files_match_manifest':len(manifest['records']),
        'local_html_links_checked':len(links),'missing_local_links':0,
        'plot_data_regenerated_byte_identically':comparisons,
        'chart_recomputation':regenerated['validation'],
        'video_chart_variant_checks':video_meta['validation'],
        'not_tested':['No HAULSIM simulation rerun','No forecasting model refit','No new physical validation','No full scientific peer review'],
        'excluded_raw_capture_present':(DEST/'native_haulsim/road_properties_recording/raw_screen_recording.mp4').exists()}
assert not report['excluded_raw_capture_present']
# Report to stdout without overwriting the archived release check.
print(json.dumps(report,indent=2))
print(json.dumps({'status':'PASS','archived_chart_source_hashes_verified':7,
                  'html_links_checked':len(links),'plot_data_comparisons':comparisons,
                  'regenerated_forecast_points':regenerated['validation']['forecast_target_count']},indent=2))
