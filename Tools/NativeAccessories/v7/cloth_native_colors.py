import os
"""Preserve native generic dress-color-set/area-map selectors without printing master rows."""
import json,sys,gc
from pathlib import Path
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/RawAssets')]
from raw_source import RawSource
from sqlite_mc import Database
import UnityPy
raw=RawSource(Path('E:/uma'),ROOT/'raw-workspace')
with Database(raw.master,REPO,'auto')as db:
 tables=[r['name']for r in db.rows("SELECT name FROM sqlite_master WHERE type='table' AND name='chara_dress_color_set'")];rows=list(db.rows('SELECT * FROM chara_dress_color_set'))if tables else []
 allowed={'id','dress_id','area_map_id','color_r1','color_r2','color_g1','color_g2','color_b1','color_b2','toon_color_r1','toon_color_r2','toon_color_g1','toon_color_g2','toon_color_b1','toon_color_b2'};colors=[{k:v for k,v in r.items()if k in allowed}for r in rows]
idx=json.loads((ROOT/'cloth-source-index.json').read_text(encoding='utf8'));contracts=[]
for record in idx['records']:
 if not record['generic']:continue
 area_files=[f for f in Path(record['decoded_path']).rglob('*')if f.is_file()and f.name.endswith('_area')]
 if not area_files:continue
 out=Path(record['parsed_directory']);area=[]
 for f in area_files:
  env=UnityPy.Environment();env.load_file(f.read_bytes(),name=f.name)
  for obj in env.objects:
   if obj.type.name=='Texture2D':
    t=obj.parse_as_object();path=out/'resources/textures'/(t.m_Name+'.png');path.parent.mkdir(parents=True,exist_ok=True);t.image.save(path);area.append(dict(name=t.m_Name,path='textures/'+path.name))
  del env;gc.collect()
 dress=record['dress_data'][0]if record['dress_data']else None;options=[r for r in colors if dress and r.get('dress_id')==dress['id']]if dress and dress.get('body_setting')==4 else colors;default=options[0]if options else None;chosen=next((a for a in area if default and a['name'].endswith(str(default.get('area_map_id',0)).zfill(2)+'_area')),area[0]if area else None)
 contract=dict(family=record['family'],body_setting_enum=dress.get('body_setting')if dress else None,native_default_color_set=default,color_set_variants=options,area_maps=area,default_area=chosen,selector='UmaContainerCharacter.ApplyDressColorAndArea: body_setting==4 -> first matching dress_id palette; otherwise first global palette; area_map_id D2 suffix',unity_properties={'color_r1':'_MaskColorR1','color_r2':'_MaskColorR2','color_g1':'_MaskColorG1','color_g2':'_MaskColorG2','color_b1':'_MaskColorB1','color_b2':'_MaskColorB2','toon_color_r1':'_MaskToonColorR1','toon_color_r2':'_MaskToonColorR2','toon_color_g1':'_MaskToonColorG1','toon_color_g2':'_MaskToonColorG2','toon_color_b1':'_MaskToonColorB1','toon_color_b2':'_MaskToonColorB2'})
 (out/'native-color-variants.json').write_text(json.dumps(contract,indent=2),encoding='utf8');contracts.append(dict(family=record['family'],contract=str(out/'native-color-variants.json'),areas=len(area),palettes=len(options)))
 for source in record['selected_prefabs']:
  file=Path(source['parsed_path']);d=json.loads(file.read_text(encoding='utf8'));d['native_color_contract']=str(out/'native-color-variants.json')
  for m in d['materials']:
   if chosen:
    prop=next((p for p in m['properties']if p['name']=='_MaskColorTex'),None)
    if prop:prop['texture']=chosen['path'];prop['native_binding_source']='ApplyDressColorAndArea selected area_map_id'
   m['native_default_mask_colors']=default;m['native_color_variants']=contract['color_set_variants']
  file.write_text(json.dumps(d,indent=2),encoding='utf8')
 print('NATIVE_COLOR_VARIANTS',record['family'],'areas',len(area),'palettes',len(options),flush=True)
(ROOT/'cloth-native-color-index.json').write_text(json.dumps(contracts,indent=2),encoding='utf8');print('NATIVE_COLOR_STAGE_COMPLETE',len(contracts),flush=True)
