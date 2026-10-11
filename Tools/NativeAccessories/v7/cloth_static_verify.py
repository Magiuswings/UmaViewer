import os
"""Read all emitted apparel PDX, exact source points/core bind/morph topology + real stock LBS motion statistics."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());core=pd.read_meshfile(str(R/'Rigs/body.mesh')).find('object')[0].find('skeleton');bind=inverse_bind(core);folder=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body'));clips=[]
for name in ['female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim']:
 a=pd.read_meshfile(str(folder/name));count=a.find('info').attrib['sa'][0];clips.append((name,a,count))
rows=[];failures=[];matcache={}
for fi,family in enumerate(reg['families']):
 points=json.loads(Path(family['source_points']).read_text());familyrows=[]
 for category,part in family['parts'].items():
  trees=[('base',pd.read_meshfile(part['base_mesh']))]+[(key,pd.read_meshfile(file))for key,file in part['shape_targets'].items()];bases=[o.findall('mesh')for o in trees[0][1].find('object')];point_errors=[];names=[]
  for tag,tree in trees:
   for oi,obj in enumerate(tree.find('object')):
    sk=obj.find('skeleton');assert list(sk)[:len(core)]and all(sk[i].tag==core[i].tag and sk[i].attrib==core[i].attrib for i in range(len(core)));assert len(sk)==family['bones'];world=np.linalg.inv(inverse_bind(sk));assert len(points['points'])==points['source_bones'];point_errors.extend(float(np.linalg.norm(world[x['index'],:3,3]-x['fitted_source_point_cm']))for x in points['points']);names=[n.tag for n in sk]
    for mi,node in enumerate(obj.findall('mesh')):
     base=bases[oi][mi];assert node.attrib['tri']==base.attrib['tri'];assert node.attrib['u0']==base.attrib['u0'];assert node.find('skin').attrib==base.find('skin').attrib;assert np.isfinite(np.array(node.attrib['p'])).all()
  maxpoint=max(point_errors);assert maxpoint<.0011
  # Direct unchanged stock t/q/s, including source helper bind-local defaults.
  stats=[]
  for clip,anim,count in clips:
   frame=count//2;sk=trees[0][1].find('object')[0].find('skeleton');signature=tuple(names);cachekey=(signature,clip,frame)
   if cachekey not in matcache:matcache[cachekey]=globals_for(anim.find('info'),anim.find('samples'),frame,sk)@inverse_bind(sk)
   matrices=matcache[cachekey];ratioall=[];finite=True
   for obj in trees[0][1].find('object'):
    for node in obj.findall('mesh'):
     p=np.array(node.attrib['p']).reshape(-1,3);ix=np.array(node.find('skin').attrib['ix']).reshape(-1,4);w=np.array(node.find('skin').attrib['w']).reshape(-1,4);hp=np.column_stack([p,np.ones(len(p))]);actual=np.zeros_like(p)
     for j in range(4):actual+=np.einsum('nij,nj->ni',matrices[np.maximum(ix[:,j],0)],hp)[:,:3]*w[:,j,None]
     assert np.isfinite(actual).all();tri=np.array(node.attrib['tri']).reshape(-1,3);edges=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]);before=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1);after=np.linalg.norm(actual[edges[:,0]]-actual[edges[:,1]],axis=1);valid=before>.1;ratioall.extend((after[valid]/before[valid]).tolist())
   stats.append(dict(animation=clip,frame=int(frame),finite=True,edge_length_threshold_cm=.1,edge_stretch_p99=float(np.quantile(ratioall,.99)),edge_stretch_max=float(max(ratioall))))
  familyrows.append(dict(part=category,base=part['base_mesh'],morph_targets=len(part['shape_targets']),morph_uv_tri_skin_exact=True,core146_exact=True,native_source_points=points['source_bones'],native_source_points_missing=0,source_point_max_error_cm=maxpoint,stock_animation_stats=stats))
 rows.append(dict(family=family['family'],parts=familyrows,bones=family['bones']))
 if(fi+1)%10==0:print('CLOTHING_STATIC_VERIFIED',fi+1,'/',len(reg['families']),flush=True)
report=dict(families=len(rows),parts=sum(len(r['parts'])for r in rows),pdx_files=sum(7*len(r['parts'])for r in rows),all_source_point_errors_below_cm=.0011,source_points_dropped=0,all_core146_exact=True,all_morph_uv_tri_skin_exact=True,all_stock_samples_finite=True,body_clothed_fixed=False,game_verified=False,collision_free_not_asserted=True,rows=rows);dest=R/'Reports/clothing-static-validation.json';dest.write_text(json.dumps(report,indent=2),encoding='utf8');print('CLOTHING_STATIC_AUDIT_COMPLETE',report['families'],report['parts'],report['pdx_files'],flush=True)
