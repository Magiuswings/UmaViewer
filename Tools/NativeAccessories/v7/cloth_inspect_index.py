import os
import sys,json,os,tempfile,re
from pathlib import Path
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'));ROOT.mkdir(parents=True,exist_ok=True);scratch=ROOT/'.temp';scratch.mkdir(exist_ok=True);tempfile.tempdir=str(scratch)
for k in ['TEMP','TMP','TMPDIR']:os.environ[k]=str(scratch)
REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path.insert(0,str(REPO/'Tools/RawAssets'))
from raw_source import RawSource
from sqlite_mc import Database
from uma_raw import Catalog
raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'));cat=Catalog(raw,REPO,'auto')
with Database(raw.master,REPO,'auto')as db:
 for table in ['chara_data','dress_data']:
  cols=[r['name']for r in db.rows('PRAGMA table_info('+table+')')];print('COLS',table,cols)
 actors=[r for r in db.rows('SELECT id,height,shape,bust,skin,socks,sex FROM chara_data WHERE id IN (1001,1002)')];print('ACTORS',actors)
 dresses=list(db.rows('SELECT id,chara_id,body_type,body_type_sub,body_setting FROM dress_data WHERE chara_id IN (0,1001,1002)'));print('DRESS_RELATIONS',dresses)
 entries=cat.select(prefixes=['3d/chara/body/bdy1001_','3d/chara/body/bdy1002_','3d/chara/body/bdy00']);prefabs=[e.name for e in entries if re.fullmatch(r'3d/chara/body/bdy(?:100[12]|00\d\d)_\d\d/pfb_bdy[^/]+',e.name)];print('PREFAB_COUNT',len(prefabs));print('PREFAB_SAMPLE',prefabs[:20]);print('GENERIC_FAMILIES',sorted(set(e.name.split('/')[3]for e in entries if '/pfb_'in e.name and'/clothes/'not in e.name)))
cat.db.close()

