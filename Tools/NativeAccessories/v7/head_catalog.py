import os
"""Full two-character source inventory. Read original archives; output only HeadSources."""
import sys,os,tempfile,json,re
from pathlib import Path
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'HeadSources'));ROOT.mkdir(parents=True,exist_ok=True);scratch=ROOT/'.temp';scratch.mkdir(exist_ok=True);tempfile.tempdir=str(scratch)
for key in ['TEMP','TMP','TMPDIR']:os.environ[key]=str(scratch)
REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path.insert(0,str(REPO/'Tools/RawAssets'))
from raw_source import RawSource,raw_relative
from uma_raw import Catalog,decode_selected
from sqlite_mc import Database
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'));existing=raw.root;existing_meta=raw.meta;existing_master=raw.master
raw.workspace=ROOT/'.raw-work';raw.workspace.mkdir(exist_ok=True);raw.root=raw.workspace/'raw-cache'/raw.prefix if raw.prefix else raw.workspace/'raw-cache'
oldfetch=raw.fetch
raw.path_for_hash=lambda h:(existing/raw_relative(h))if(existing/raw_relative(h)).is_file()else(raw.root/raw_relative(h))
raw.fetch=lambda rels:oldfetch([r for r in rels if not(existing/Path(r)).is_file()])
cat=Catalog(raw,REPO,'auto');actors=[]
with Database(existing_master,REPO,'auto')as db:
    for char in ['1001','1002']:
        rows=list(db.rows('SELECT * FROM chara_data WHERE id='+char));assert len(rows)==1;actors.append({k:rows[0][k]for k in ['id','name','height','shape','bust','skin','tail_model_id']if k in rows[0]})
heads=[];rejected=[];earclips=[];tailmodels=[]
for actor in actors:
    char=str(actor['id']);entries=cat.select(prefixes=['3d/chara/head/chr'+char+'_'])
    for entry in entries:
        if '/pfb_'not in entry.name:continue
        pub=cat.public(entry)
        if re.fullmatch(r'3d/chara/head/chr'+char+r'_\d{2}/pfb_chr'+char+r'_\d{2}',entry.name):heads.append({'character_id':char,'variant':entry.name.rsplit('_',1)[-1],**pub,'dependencies':entry.dependencies})
        else:rejected.append({'character_id':char,**pub,'reason':'not actual chrNNNN_VV model prefab (physics/driven/control/other resource excluded)'})
    clips=[e for e in cat.select(prefixes=['3d/motion/'],contains=char)if e.name.endswith('_ear')]
    earclips.extend({'character_id':char,'character_match':bool(re.search(r'(?:chr'+char+r'_|crd'+char+r'\d\d_|_'+char+r'_)',e.name)),**cat.public(e)}for e in clips)
    tail='tail'+str(actor['tail_model_id']).zfill(4)+'_00';prefix='3d/chara/tail/'+tail+'/';entry=cat.get(prefix+'pfb_'+tail)
    tailmodels.append({'character_id':char,'tail_model_id':actor['tail_model_id'],'prefab':cat.public(entry)if entry else None,'textures':[cat.public(e)for e in cat.select(prefixes=[prefix+'textures/'])if '_'+char+'_'in e.name or '_0000_'in e.name]})
inventory={'actors':actors,'head_prefabs':heads,'head_prefab_total':len(heads),'head_prefab_available':sum(h['present']for h in heads),'non_model_prefabs_excluded':rejected,'ear_clips':earclips,'tails':tailmodels,'source_archive_originals_unmodified':True,'output_cache_boundary':str(raw.workspace),'metadata_only':True}
dump(ROOT/'head-source-catalog.json',inventory)
print(json.dumps({'actors':actors,'heads':[(h['name'],h['present'],h['size_bytes'])for h in heads],'rejected_count':len(rejected),'tails':[(t['character_id'],t['tail_model_id'],t['prefab'],len(t['textures']))for t in tailmodels],'ear_clips_count':len(earclips)},ensure_ascii=False,indent=2),flush=True)
if '--decode' in sys.argv:
    for h in heads:
        if not h['present']:continue
        name=h['name'];folder=ROOT/'decoded'/('chr'+h['character_id']+'_'+h['variant']);roots=[cat.get(name)];prefix=name.rsplit('/',1)[0]+'/textures/';roots.extend(e for e in cat.select(prefixes=[prefix])if e.size)
        if folder.exists():continue
        print('DECODING_HEAD',name,flush=True);manifest=decode_selected(cat,roots,folder,dependencies=True,validate=True,allow_missing=True);h['decoded_path']=str(folder);h['closure_complete']=manifest['passed'];h['missing_resources']=manifest['missing_files'];dump(ROOT/'head-source-catalog.json',inventory)
    for t in tailmodels:
        if not t['prefab']or not t['prefab']['present']:continue
        folder=ROOT/'decoded'/('tail_'+t['character_id']);roots=[cat.get(t['prefab']['name']),*[cat.get(e['name'])for e in t['textures']if e['present']]]
        if folder.exists():continue
        print('DECODING_TAIL',t['character_id'],flush=True);manifest=decode_selected(cat,roots,folder,dependencies=True,validate=True,allow_missing=True);t['decoded_path']=str(folder);t['closure_complete']=manifest['passed'];t['missing_resources']=manifest['missing_files'];dump(ROOT/'head-source-catalog.json',inventory)
    # Runtime driver targets for each character reside on base head prefab;
    # generic drivenkeylocator only needs one shared copy.
    entry=cat.get('3d/animator/drivenkeylocator');folder=ROOT/'decoded/locator'
    if entry and cat.public(entry)['present']and not folder.exists():decode_selected(cat,[entry],folder,dependencies=True,validate=True,allow_missing=True)
if '--motions' in sys.argv:
    selected=[cat.get(e['name'])for e in earclips if e['character_id']=='1002'and e['character_match']and e['present']]
    folder=ROOT/'decoded/ear-motion-1002'
    if not folder.exists():decode_selected(cat,selected,folder,dependencies=True,validate=True,allow_missing=True)
cat.db.close()
