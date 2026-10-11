import os
"""Restricted real-pose garment clearance repair: body unchanged, all source points/UV/tri/weights retained."""
import json,sys,copy
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));sys.path[:0]=[str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'),str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/NativeBody')];from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());bodydir=next(Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'v5')).rglob('uma_0001_body_base.mesh')).parent;bn=pd.read_meshfile(str(bodydir/'uma_0001_body_base.mesh')).find('object')[0].find('mesh');bp=np.array(bn.attrib['p']).reshape(-1,3);bt=np.array(bn.attrib['tri']).reshape(-1,3);bi=np.array(bn.find('skin').attrib['ix']).reshape(-1,4);bw=np.array(bn.find('skin').attrib['w']).reshape(-1,4);bb0=np.array(pd.read_meshfile(str(bodydir/'uma_0001_body_b0.mesh')).find('object')[0].find('mesh').attrib['p']).reshape(-1,3);bs1=np.array(pd.read_meshfile(str(bodydir/'uma_0001_body_s1.mesh')).find('object')[0].find('mesh').attrib['p']).reshape(-1,3);folder=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body'))
def posed(p,ix,w,mat):
 out=np.zeros_like(p);h=np.column_stack([p,np.ones(len(p))])
 for j in range(4):out+=np.einsum('nij,nj->ni',mat[np.maximum(ix[:,j],0)],h)[:,:3]*w[:,j,None]
 return out
reports=[]
for familyname,actor in [('bdy1001_00',1001),('bdy1002_00',1002),('bdy0020_00_00',1001)]:
 family=next(f for f in reg['families']if f['family']==familyname);body=bp if actor==1001 else bp+(bb0-bp)+(bs1-bp);sk=pd.read_meshfile(next(iter(family['parts'].values()))['base_mesh']).find('object')[0].find('skeleton');bind=inverse_bind(sk);cases=[]
 for clip in [None,'female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim']:
  if clip:
   a=pd.read_meshfile(str(folder/clip));f=a.find('info').attrib['sa'][0]//2;mat=globals_for(a.find('info'),a.find('samples'),f,sk)@bind
  else:mat=np.repeat(np.eye(4)[None],len(sk),axis=0)
  b=posed(body,bi,bw,mat);bvh=BVHTree.FromPolygons([Vector(p)for p in b],bt.tolist(),all_triangles=True);cases.append((clip,mat,bvh))
 partrows=[]
 for category,part in family['parts'].items():
  if category=='headwear':continue
  trees={'base':pd.read_meshfile(part['base_mesh'])};trees.update({key:pd.read_meshfile(path)for key,path in part['shape_targets'].items()});nodereports=[]
  for oi,obj in enumerate(trees['base'].find('object')):
   for mi,node in enumerate(obj.findall('mesh')):
    base=np.array(node.attrib['p']).reshape(-1,3);current=base.copy();ix=np.array(node.find('skin').attrib['ix']).reshape(-1,4);w=np.array(node.find('skin').attrib['w']).reshape(-1,4);tri=np.array(node.attrib['tri']).reshape(-1,3);shape_delta=np.zeros_like(base)
    if actor==1002:
     for key in ['bs_body_breast_shape_1','bs_body_gaunt_1']:shape_delta+=np.array(trees[key].find('object')[oi].findall('mesh')[mi].attrib['p']).reshape(-1,3)-base
    inverses=[]
    for clip,mat,bvh in cases:inverses.append(np.linalg.pinv(sum(mat[np.maximum(ix[:,j],0),:3,:3]*w[:,j,None,None]for j in range(4))))
    counts=[]
    for iteration in range(16):
     updated=0
     for ci,(clip,mat,bvh)in enumerate(cases):
      p=posed(current+shape_delta,ix,w,mat);correction=np.zeros_like(p);amount=np.zeros(len(p))
      for i,v in enumerate(p):
       hit,n,fi,dist=bvh.find_nearest(Vector(v));signed=(Vector(v)-hit).dot(n)
       if signed<.25 and dist<5:
        corr=np.array(n)*min(.8,.25-signed);correction[i]+=inverses[ci][i]@corr;amount[i]+=1;updated+=1
      for t in tri:
       center=p[t].mean(0);hit,n,fi,dist=bvh.find_nearest(Vector(center));signed=(Vector(center)-hit).dot(n)
       if signed<.20 and dist<2.5:
        corr=np.array(n)*min(.5,.20-signed)
        for i in t:correction[i]+=inverses[ci][i]@corr;amount[i]+=1
      valid=amount>0;current[valid]+=.55*correction[valid]/amount[valid,None];delta=current-base;length=np.linalg.norm(delta,axis=1);over=length>2.5;delta[over]*=2.5/length[over,None];current=base+delta
     counts.append(updated)
    # Equal base coordinates receive one common delta to avoid opening UV seams.
    _,ids=np.unique(np.round(base,4),axis=0,return_inverse=True);delta=current-base;total=np.zeros((ids.max()+1,3));np.add.at(total,ids,delta);total/=np.bincount(ids)[:,None];delta=total[ids]
    for tag,tree in trees.items():
     target=tree.find('object')[oi].findall('mesh')[mi];p=np.array(target.attrib['p']).reshape(-1,3)+delta;target.attrib['p']=p.ravel().tolist();n=np.zeros_like(p);cross=np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]])
     for j in range(3):np.add.at(n,tri[:,j],cross)
     n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12);target.attrib['n']=n.ravel().tolist();target.find('aabb').attrib.update(min=p.min(0).tolist(),max=p.max(0).tolist());c=(p.min(0)+p.max(0))/2;target.attrib['boundingsphere']=c.tolist()+[float(np.linalg.norm(p-c,axis=1).max())]
    nodereports.append(dict(object=obj.tag,mesh=mi,max_correction_cm=float(np.linalg.norm(delta,axis=1).max()),p99_correction_cm=float(np.quantile(np.linalg.norm(delta,axis=1),.99)),vertex_projection_counts=counts))
  for tag,tree in trees.items():path=part['base_mesh']if tag=='base'else part['shape_targets'][tag];pd.write_meshfile(path,tree);pd.read_meshfile(path)
  partrows.append(dict(part=category,nodes=nodereports))
 reports.append(dict(family=familyname,actor=actor,body_unchanged=True,body_clothed=False,method='16 restricted clearance cycles over neutral/actual stock idle+throne, current actor body+s1/b0; whole common correction applied to sixBS; source points/weights/UV/tri untouched; maximum 2.5cm garment delta',parts=partrows));print('REAL_POSE_REFINED',familyname,flush=True)
(R/'Reports/clothing-representative-refinement.json').write_text(json.dumps(reports,indent=2),encoding='utf8')

