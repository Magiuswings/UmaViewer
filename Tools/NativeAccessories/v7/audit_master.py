import os
import json,os,sys
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));R.mkdir(parents=True,exist_ok=True);(R/'Reports').mkdir(exist_ok=True)
sys.path[:0]=[str(REPO/'Tools/RawAssets'),str(REPO/'Tools/PDXExporter')]
from raw_source import RawSource
from sqlite_mc import Database
raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'))
with Database(raw.master,REPO,'auto')as db:
    tables=list(db.rows("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"));selected=[t['name']for t in tables if any(k in t['name'].lower()for k in ['chara','dress','color','skin','hair','eye'])]
    schemas={t:list(db.rows('PRAGMA table_info('+t+')'))for t in selected}
    roles=list(db.rows('SELECT * FROM chara_data ORDER BY id'))
    namecols={t:[x['name']for x in cols if any(k in x['name'].lower()for k in ['name','color','skin','hair','eye'])]for t,cols in schemas.items()}
    info={'tables':[t['name']for t in tables],'schemas':schemas,'name_color_columns':namecols,'roles':roles}
    (R/'Reports/master-audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    print('ROLE_COUNT',len(roles));print('ROLE_COLUMNS',list(roles[0]));print('RELATED_TABLES',selected);print('COLUMNS',namecols);print('FIRST_ROLES',json.dumps(roles[:2],ensure_ascii=False))
    samples={}
    for t in selected:
        if any(k in t.lower()for k in ['skin','color','hair','eye','chara_name']):samples[t]=list(db.rows('SELECT * FROM '+t+' LIMIT 4'))
    (R/'Reports/color-table-samples.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf8');print('COLOR_SAMPLES',json.dumps(samples,ensure_ascii=False)[:10000])
