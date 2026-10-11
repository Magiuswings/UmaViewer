import os
import json,sys,numpy as np
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));sys.path[:0]=[str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'),str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/NativeBody')];from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());rows=[]
for family in reg['families']:
 p=next(iter(family['parts'].values()));sk=pd.read_meshfile(p['base_mesh']).find('object')[0].find('skeleton');world=np.linalg.inv(inverse_bind(sk));points=json.loads(Path(family['source_points']).read_text());errors=[np.linalg.norm(world[x['index'],:3,3]-x['fitted_source_point_cm'])for x in points['points']];emapped=[err for err,x in zip(errors,points['points'])if x['core_mapping']];eapp=[err for err,x in zip(errors,points['points'])if not x['core_mapping']];rows.append((family['family'],max(errors),max(eapp)if eapp else 0,len([e for e in errors if e>.01])))
print('POINT_AUDIT_TOP',sorted(rows,key=lambda x:-x[1])[:15]);a=json.loads((R/'ClothingSources/parsed/bdy0001_00_01/bdy0001_00_01_1_0_2.json').read_text());b=json.loads((R/'ClothingSources/parsed/bdy0001_00_01/bdy0001_00_01_1_1_0.json').read_text());u=np.array([[v[k]for k in 'xy']for v in a['meshes'][0]['uvs'][0]['values']]);v=np.array([[v[k]for k in 'xy']for v in b['meshes'][0]['uvs'][0]['values']]);print('RACE_UV_PROFILES',u.shape,v.shape,'equal',np.array_equal(u,v))
