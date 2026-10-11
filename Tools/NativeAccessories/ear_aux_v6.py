import json,sys,os,tempfile
from pathlib import Path
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"))
sys.path[:0]=[str(REPO/'Tools/RawAssets'),str(REPO/'Tools/HeadlessExporter')]
from uma_raw import Catalog,decode_selected
from raw_source import RawSource
from export_assets import Package
tempfile.tempdir=str(ROOT/'.temp')
for n in ['TEMP','TMP','TMPDIR']:os.environ[n]=tempfile.tempdir
raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'));cat=Catalog(raw,REPO,'auto');decode_selected(cat,[cat.get('3d/animator/drivenkeylocator')],ROOT/'locator-native',dependencies=True,validate=True,allow_missing=False);cat.db.close()
package=Package(ROOT/'named-models');targets=[]
for o in package.objects:
    if o.type.name=='MonoBehaviour':
        t=o.read_typetree()
        if '_targetFaces'in t and'ear_target'in t.get('m_Name',''):targets.append(t)
assert len(targets)==1;(ROOT/'parsed/ear-driven-targets.json').write_text(json.dumps(targets,indent=2),encoding='utf8');print('RECOVERED_EAR_TARGET_TABLE',len(targets[0]['_targetFaces']),str(targets[0]['_targetFaces'][0])[:500])
