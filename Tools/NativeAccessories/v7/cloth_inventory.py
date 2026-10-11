import os
import sys,json,re,os,tempfile,hashlib
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'));ROOT.mkdir(parents=True,exist_ok=True);SCRATCH=ROOT/'.temp';SCRATCH.mkdir(exist_ok=True);tempfile.tempdir=str(SCRATCH)
for k in ['TEMP','TMP','TMPDIR']:os.environ[k]=str(SCRATCH)
REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/RawAssets'),str(REPO/'Tools/HeadlessExporter')]
from raw_source import RawSource,raw_relative
from sqlite_mc import Database
from uma_raw import Catalog
from body_profiles import body_profile
raw=RawSource(Path('E:/uma'),ROOT/'raw-workspace');cat=Catalog(raw,REPO,'auto')
with Database(raw.master,REPO,'auto')as db:
 actors=list(db.rows('SELECT id,height,shape,bust,skin,socks,sex FROM chara_data WHERE id IN (1001,1002)'))
 cols=['id','chara_id','general_purpose','body_type','body_type_sub','body_setting','use_gender','body_shape','costume_type','head_sub_id','use_season','use_race','use_live','use_home','use_dress_change']
 dresses=list(db.rows('SELECT '+','.join(cols)+' FROM dress_data WHERE chara_id IN (0,1001,1002)'));names={r['index']:r['text']for r in db.rows('SELECT "index",text FROM text_data WHERE id=14')}
 for d in dresses:d['display_name']=names.get(d['id'],'')
entries=cat.select(prefixes=['3d/chara/body/bdy1001_','3d/chara/body/bdy1002_','3d/chara/body/bdy00']);groups=defaultdict(list);excluded=[]
for e in entries:
 if '/clothes/'in e.name or re.search(r'_cloth\d*$|_bust\d*_cloth\d*$',e.name):
  if '/pfb_'in e.name:excluded.append(dict(prefab=e.name,reason='Physics-only clothes prefab loaded by LoadPhysics, not a renderable body selection'))
  continue
 profile=body_profile(e.name)
 if profile:
  groups['bdy'+profile['costume_id']+'_'+profile['body_type_sub']+'_'+profile['body_setting']].append((e,profile))
 elif re.fullmatch(r'3d/chara/body/bdy100[12]_\d\d/pfb_bdy100[12]_\d\d',e.name):groups[e.name.rsplit('/',1)[-1].removeprefix('pfb_')].append((e,None))
actor_by_id={a['id']:a for a in actors};records=[];not_selected=[]
def present(e):return raw.has(raw_relative(e.file_hash))
for family,options in sorted(groups.items()):
 generic=options[0][1]is not None
 if generic:
  f=options[0][1];related=[d for d in dresses if d['chara_id']==0 and d['body_type']==int(f['costume_id'])and d['body_type_sub']==int(f['body_type_sub'])]
  look={(int(p['height']),int(p['shape']),int(p['bust'])):(e,p)for e,p in options};resolved=[]
  for actor in actors:
   key=(actor['height'],actor['shape'],actor['bust']);pair=look.get(key);resolved.append(dict(character_id=actor['id'],actual_profile=dict(height=key[0],shape=key[1],bust=key[2]),actual_prefab=pair[0].name if pair else None,cached=bool(pair and present(pair[0]))))
  # Only model-selectable common families for these two actual actors are in scope.
  if not related or not any(r['cached']for r in resolved):
   not_selected.append(dict(family=family,reason='No type/subtype dress relationship or neither actor actual-profile cached render prefab',dress_ids=[d['id']for d in related],actor_resolution=resolved));continue
  wanted={(1,0,1),(1,0,2)}|{(a['height'],a['shape'],a['bust'])for a in actors};selected=[(e,p)for key,(e,p)in sorted(look.items())if key in wanted and present(e)]
  recipients=[1001,1002];identity='0001';unique_key='shared_'+family;basis=next(((e,p)for e,p in selected if (int(p['height']),int(p['shape']),int(p['bust']))==(1,0,2)),selected[0]);sourceprefix=basis[0].name.rsplit('/',1)[0]+'/';profile=dict(costume_id=f['costume_id'],body_type_sub=f['body_type_sub'],body_setting=f['body_setting']);relationships=related
 else:
  e,_=options[0];a=int(family[3:7]);variant=int(family.rsplit('_',1)[-1]);selected=options if present(e)else[]
  if not selected:not_selected.append(dict(family=family,reason='Character prefab is not locally cached'));continue
  recipients=[a];identity=str(a);unique_key='character_'+family;basis=selected[0];sourceprefix=e.name.rsplit('/',1)[0]+'/';profile=None;relationships=[d for d in dresses if d['chara_id']==a and d['body_type_sub']==variant];resolved=[dict(character_id=a,actual_profile=None,actual_prefab=e.name,cached=True)]
 # Texture roots match native selection at only the chosen bust/skin/socks, preserving color/area variants.
 candidate_textures=[e for e in entries if e.name.startswith(sourceprefix+'textures/')and present(e)]
 busts={str(p['bust'])for _,p in selected if p}|{str(actor_by_id[i]['bust'])for i in recipients};skin={'0','1'};textures=[]
 for e in candidate_textures:
  stem=e.name.rsplit('/',1)[-1]
  if not generic:textures.append(e);continue
  # Strictly exclude texture bust profiles unused by selected sources, keep shared area/color/code masks.
  fields=stem.split('_');ending='_'.join(fields[-2:])if fields[-2:] == ['shad','c']else fields[-1]
  suffix=stem[len('tex_'+family):]if stem.startswith('tex_'+family)else ''
  is_map=stem.endswith(('_diff','_shad_c','_base','_ctrl'))
  selected_bust=any(re.search(r'_[01]_'+re.escape(b)+r'(?:_\d+)?_(?:diff|shad_c|base|ctrl)$',stem)for b in busts)
  special=any(k in stem for k in ['_area','_waku','_zekken','_num'])
  if selected_bust or special:textures.append(e)
 prefabs=[dict(prefab=e.name,profile=p,bytes=e.size)for e,p in selected];roots=[e for e,p in selected]+textures;closure,missing,cycles=cat.closure(roots);uncached=[e.name for e in closure if not present(e)]
 records.append(dict(key=unique_key,family=family,generic=generic,GenericBodyFamily=profile,output_character_directory=identity,shared_asset_once=generic,characters=recipients,dress_data=relationships,actor_resolution=resolved,basis_prefab=basis[0].name,selected_prefabs=prefabs,texture_roots=[e.name for e in textures],root_names=[e.name for e in roots],decoded_path=str(ROOT/'named'/family),parsed_directory=str(ROOT/'parsed'/family),dependency_count=len(closure),estimated_decoded_bytes=sum(e.size or 0 for e in closure),missing_indexed_dependencies=[x['name']for x in missing],uncached_dependencies=uncached,status='index_ready'if not missing and not uncached else 'incomplete_dependencies'))
index=dict(version=1,characters=actors,source_master=str(raw.master),source_meta=str(raw.meta),private_keys_serialized=False,source_selection_logic=dict(character='UmaViewerUI.ListCostumes + Builder.LoadNormalUma: character_id/body_type_sub -> bdy{character}_{sub}',generic='ListCostumes dedup bdy{type}_{sub}_{model_setting}; dress lookup matches type/sub only. Master body_setting is an enum controlling variants/colors and MUST NOT equal prefab model_setting. LoadNormalUma uses actual actor height/shape/bust; selected h1_s0_b1/b2 are shared fit references',physics='LoadPhysics /clothes/ prefabs excluded from drawable source selection'),dress_relationships=dresses,records=records,excluded_physics_prefabs=excluded,out_of_scope_families=not_selected,counts=dict(unique_families=len(records),shared_families=sum(r['generic']for r in records),character_families=sum(not r['generic']for r in records),selected_drawable_prefabs=sum(len(r['selected_prefabs'])for r in records),character_dress_rows=sum(d['chara_id']in(1001,1002)for d in dresses),complete_dependency_families=sum(r['status']=='index_ready'for r in records)))
(ROOT/'cloth-source-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf8');cat.db.close();print('CLOTH_SOURCE_INDEX',json.dumps(index['counts']),flush=True);print('INDEX_PATH',str(ROOT/'cloth-source-index.json'),flush=True);print('FAMILY_BYTES_MB',round(sum(r['estimated_decoded_bytes']for r in records)/1024**2,1),flush=True)

