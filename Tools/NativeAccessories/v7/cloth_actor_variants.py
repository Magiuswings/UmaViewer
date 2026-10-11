import os
"""Native racer socks 3/6 textures as material-only actor variants; common base UV stays exact."""
import json,copy,gc
from pathlib import Path
import numpy as np
from PIL import Image
import UnityPy
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'ClothingSources';OUT=ROOT/'ClothingParts'
regfile=OUT/'clothing-registration.json';reg=json.loads(regfile.read_text());index=json.loads((SRC/'cloth-source-index.json').read_text(encoding='utf8'));summary=[]
for family in reg['families']:
 if not family['family'].startswith('bdy0001_00_'):continue
 src=next(r for r in index['records']if r['family']==family['family']);base=next(s for s in src['selected_prefabs']if s['prefab']==src['basis_prefab']);bust=base['profile']['bust'];native_name=f'tex_bdy0001_00_00_1_{bust}_06_diff';native_file=next(Path(src['decoded_path']).rglob(native_name));assert native_file.exists();env=UnityPy.Environment();env.load_file(native_file.read_bytes(),name=native_name);obj=next(o for o in env.objects if o.type.name=='Texture2D');tex=obj.parse_as_object();image=tex.image.convert('RGBA');path=Path(family['directory'])/f'uma_0001_clothing_{family["family"][3:]}_m01_socks06_diffuse.dds';image.save(path,pixel_format='DXT5');source_png=Path(src['parsed_directory'])/'resources/textures'/(native_name+'.png');image.save(source_png)
 for partkey,part in family['parts'].items():
  settings=copy.deepcopy(part['meshsettings']);changed=False
  for setting in settings:
   if setting['source_material']==1:setting['diffuse']=str(path);changed=True
  if not changed:continue
  variant=dict(characters=[1002],mesh_name=part['mesh_name'].removesuffix('_mesh')+'_socks06_mesh',entity=part['entity'].removesuffix('_entity')+'_socks06_entity',meshsettings=settings,base_mesh=part['base_mesh'],shape_targets=part['shape_targets'],source_native_texture=str(native_file),native_texture_selector=f'UmaContainerCharacter.LoadBody case0001 material-slot1: skin1,basis bust{bust},socks06',actor_actual_profile='h1_s1_b0',basis_texture_profile=f'h1_s0_b{bust}',uv_policy='Source actual1002 b0 model has5407 vertices vs sharedb2 5401/UV differs; use native same-basis atlas with actual socks06 to preserve common UV; no duplicate mesh geometry')
  part['actor_variants']=[v for v in part.get('actor_variants',[])if v.get('characters')!=[1002]]+[variant]
 summary.append(dict(family=family['family'],socks03_for_character=1001,socks06_for_character=1002,variant_diffuse=str(path),mesh_geometry_duplicated=False));del env;gc.collect();print('RACER_SOCK_VARIANT',family['family'],'parts',list(family['parts']),flush=True)
reg['native_actor_material_variants']=summary;tmp=regfile.with_suffix('.tmp');tmp.write_text(json.dumps(reg,indent=2),encoding='utf8');tmp.replace(regfile);(OUT/'native-actor-material-variants.json').write_text(json.dumps(summary,indent=2),encoding='utf8')

