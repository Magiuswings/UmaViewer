import sys,json
from pathlib import Path
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/RawAssets')
from sqlite_mc import Database
repo=Path('E:/UmaViewer-Workspace/UmaViewer-source');d=Database(Path('E:/UmaViewer-Workspace/UmaRaw-CLI/raw-cache/Persistent/meta'),repo,'auto');base='3d/motion/event/body/chara/chr1001_00/anm_eve_chr1001_00_idle01_loop';names=[base,base.replace('/body','/facial')+'_face',base.replace('/body','/facial')+'_ear'];query='SELECT n,h,m,d FROM a WHERE n IN ('+','.join("'"+n+"'"for n in names)+')';print(json.dumps(list(d.rows(query)),indent=2),flush=True);d.close()
