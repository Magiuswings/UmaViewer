"""Read-only original UMA motion catalog; outputs only V8 MotionSources."""
import json,sys,re
from pathlib import Path
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/RawAssets')
from sqlite_mc import Database
REPO=Path('E:/UmaViewer-Workspace/UmaViewer-source');RAW=Path('E:/UmaViewer-Workspace/UmaRaw-CLI');ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/MotionSources');ROOT.mkdir(parents=True,exist_ok=True);inventory=json.loads((RAW/'archive-inventory.json').read_text());prefix=inventory['prefix'];meta=RAW/'raw-cache'/prefix/'meta';rows=[]
with Database(meta,REPO,'auto')as db:
    query="SELECT n,h,m,d FROM a WHERE n >= '3d/motion/' AND n < '3d/motioo/' AND (lower(n) LIKE '%idle%' OR lower(n) LIKE '%wait%' OR lower(n) LIKE '%stand%' OR lower(n) LIKE '%home%') ORDER BY n"
    for r in db.rows(query):
        rel='dat/'+r['h'][:2]+'/'+r['h'];member=prefix+'/'+rel;local=RAW/'raw-cache'/prefix/rel;rows.append({'name':r['n'],'hash':r['h'],'type':r['m'],'dependencies':(r['d']or'').split(';'),'present_in_source_archive':member in inventory['items'],'local_raw_cached':local.is_file(),'raw_cached_path':str(local),'archive_member':member,'archive_bytes':inventory['items'].get(member,{}).get('size')})
(ROOT/'standing-idle-candidates.json').write_text(json.dumps({'metadata_source':str(meta),'original_archive':inventory['archive'],'candidates':rows,'raw_sources_changed':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
preferred=[r for r in rows if re.search(r'(?i)(chr1001|crd1001|common|cmn|base|idle|stand)',r['name'])]
print('CANDIDATE_COUNT',len(rows),'PREFERRED',len(preferred));print('\n'.join(r['name']+' [present='+str(r['present_in_source_archive'])+']'for r in preferred[:170]))
