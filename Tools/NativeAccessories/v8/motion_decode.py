import json,sys,os,tempfile
from pathlib import Path
ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/MotionSources');ROOT.mkdir(parents=True,exist_ok=True);scratch=ROOT/'.temp';scratch.mkdir(exist_ok=True);tempfile.tempdir=str(scratch)
for key in ['TEMP','TMP','TMPDIR']:os.environ[key]=str(scratch)
REPO=Path('E:/UmaViewer-Workspace/UmaViewer-source');sys.path.insert(0,str(REPO/'Tools/RawAssets'))
from raw_source import RawSource,raw_relative
from uma_raw import Catalog,decode_selected
raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'));existing=raw.root;raw.workspace=ROOT/'.raw-work';raw.workspace.mkdir(exist_ok=True);raw.root=raw.workspace/'raw-cache'/raw.prefix;oldfetch=raw.fetch;raw.path_for_hash=lambda h:(existing/raw_relative(h))if(existing/raw_relative(h)).is_file()else(raw.root/raw_relative(h));raw.fetch=lambda rels:oldfetch([r for r in rels if not(existing/Path(r)).is_file()]);cat=Catalog(raw,REPO,'auto');base='3d/motion/event/body/chara/chr1001_00/anm_eve_chr1001_00_idle01_loop';body=cat.get(base);assert body
faces=[]
for prefix in ['3d/motion/event/facial/chara/chr1001_00/','3d/motion/event/facial/chara/chr0000_00/','3d/motion/event/facial/common/']:
    query="SELECT n,h,m,d,e FROM a WHERE n >= '"+prefix+"' AND n < '"+prefix+"~' ORDER BY n"
    for r in cat.db.rows(query):
        e=cat._entry(r);cat.cache[e.name]=e
        if 'idle'in e.name.lower()and e.name.endswith('_face'):faces.append(e)
if '--head-home'in sys.argv:
    names=['3d/motion/home/facial/type01/anm_hom_type01_000_001_loop_face','3d/motion/home/facial/type01/anm_hom_type01_000_001_loop_face_driven','3d/motion/home/body/type01/anm_hom_type01_000_001_loop'];faces=[cat.get(n)for n in names];assert all(faces)
if '--head-dynamic'in sys.argv:
    names=['3d/motion/home/facial/type01/anm_hom_type01_000_001_act01_face','3d/motion/home/facial/type01/anm_hom_type01_000_001_act02_face','3d/motion/mini/mode/facial/type00/anm_min_mde_type00_06_03_1001_face'];faces=[cat.get(n)for n in names];assert all(faces)
print('FACE_IDLE_CANDIDATES',[cat.public(e)for e in faces],flush=True);roots=[body]+faces[:12];report={'candidates':[cat.public(e)for e in roots],'selected_body':base,'selected_head_pending_clip_inspection':True,'source_archives_modified':False};(ROOT/'selected-native-candidates.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
for entry in roots:
    if not cat.public(entry)['present']:continue
    folder=ROOT/'bundles'/entry.name.rsplit('/',1)[-1]
    if folder.exists():continue
    manifest=decode_selected(cat,[entry],folder,dependencies=True,validate=True,allow_missing=True);(ROOT/(entry.name.rsplit('/',1)[-1]+'-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8');print('DECODED_NATIVE',entry.name,manifest['passed'],flush=True)
cat.db.close()
