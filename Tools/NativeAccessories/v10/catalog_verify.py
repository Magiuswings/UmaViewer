import csv,json,hashlib,sys,collections
from pathlib import Path
OUT=Path(r'E:\UmaViewer-Exports\2026-10-13-UMA-V10\AnimationCatalog')
report=json.loads((OUT/'coverage_report.json').read_text(encoding='utf8'))
def csv_names(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return [r['logical_name'] for r in csv.DictReader(f)]
allnames=csv_names(OUT/'animation_catalog_all.csv');main=csv_names(OUT/'motion_index_only.csv');extra=csv_names(OUT/'supplementary_candidates_only.csv')
names=[];module_counts={}
for p in (OUT/'Modules').glob('*.csv'):
    current=csv_names(p);module_counts[p.stem]=len(current);names.extend(current)
assert len(allnames)==110084 and len(set(allnames))==len(allnames)
assert len(main)==95910 and len(extra)==14174
assert collections.Counter(names)==collections.Counter(allnames)
assert set(main).isdisjoint(extra) and set(main)|set(extra)==set(allnames)
sys.path.insert(0,r'E:\UmaViewer-Workspace\UmaViewer-source\Tools\RawAssets')
from sqlite_mc import Database
with Database(Path(report['meta']['path']),Path(r'E:\UmaViewer-Workspace\UmaViewer-source')) as db:
    expected=[r['n'] for r in db.rows(report['query'])]
assert expected==allnames
errors=[]
manifest=json.loads((OUT/'file_manifest.json').read_text(encoding='utf8'))
for item in manifest:
    p=OUT/item['path'];h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    if p.stat().st_size!=item['bytes'] or h.hexdigest()!=item['sha256']:errors.append(item['path'])
txt=list(OUT.rglob('*.txt'));bom=all(p.open('rb').read(3)==b'\xef\xbb\xbf' for p in txt)
assert not errors and bom
result=dict(passed=True,csv_rows=len(allnames),source_query_exact_ordered_match=True,unique=True,main_rows=len(main),supplementary_rows=len(extra),module_partition_exact=True,module_counts=module_counts,files_hashed=len(manifest),hash_errors=errors,txt_files=len(txt),all_txt_utf8_bom=bom,total_bytes=sum(x['bytes'] for x in manifest),actual_clip_decode_in_this_catalog=0)
(OUT/'independent_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
