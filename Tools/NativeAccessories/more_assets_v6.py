import json,os,re,sys,tempfile
from pathlib import Path
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"))
sys.path.insert(0,str(REPO/'Tools/RawAssets'))
from uma_raw import Catalog,decode_selected
from raw_source import RawSource
scratch=ROOT/'.temp';tempfile.tempdir=str(scratch)
for n in ['TEMP','TMP','TMPDIR']:os.environ[n]=str(scratch)
raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'));cat=Catalog(raw,REPO,'auto')
bodies=[e for e in cat.select(prefixes=['3d/chara/body/bdy1001_'])if re.fullmatch(r'3d/chara/body/bdy1001_\d\d/pfb_bdy1001_\d\d',e.name)and raw.has('dat/'+e.file_hash[:2]+'/'+e.file_hash)]
print('ACTUAL_BODY_PREFABS',[e.name for e in bodies],flush=True);assert bodies
bodies.sort(key=lambda e:('_00'not in e.name,'_01'not in e.name,e.name));body=bodies[0]
ears=[e for e in cat.select(prefixes=['3d/motion/'],contains='_ear')if e.name.endswith('_ear')and e.size and e.size>9000 and raw.has('dat/'+e.file_hash[:2]+'/'+e.file_hash)]
ears.sort(key=lambda e:('1001'not in e.name,'home'not in e.name,-e.size));ears=ears[:14]
roots=[body,*cat.select(prefixes=[body.name.rsplit('/',1)[0]+'/textures/']),*ears]
selection=json.loads((ROOT/'resource-selection.json').read_text());selection['clothing']=body.name;selection['ear_candidates']=[e.name for e in ears];(ROOT/'resource-selection.json').write_text(json.dumps(selection,indent=2),encoding='utf8')
decode_selected(cat,roots,ROOT/'more-native',dependencies=True,validate=True,allow_missing=False);cat.db.close();print('ADDITIONAL_SOURCE_ASSETS',body.name,[(e.name,e.size)for e in ears],flush=True)
