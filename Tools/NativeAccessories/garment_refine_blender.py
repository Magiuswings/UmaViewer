import os
import sys,json
from pathlib import Path
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001")) / 'clothing-parts';REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')];import build_ck3_mod as b
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pdx=b.parser_only(Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh")));a=dict(np.load(R/'garment-prepared.npz'));rep=json.loads((R/'garment-preparation.json').read_text());stock=pdx.read_meshfile(rep['stock_body']);sk=stock.find('object')[0].find('skeleton');sn=stock.find('object')[0].find('mesh');bind=inverse_bind(sk);bp=np.array(sn.attrib['p']).reshape(-1,3)*.01;bt=np.array(sn.attrib['tri']).reshape(-1,3);bix=np.array(sn.find('skin').attrib['ix']).reshape(-1,4);bw=np.array(sn.find('skin').attrib['w']).reshape(-1,4)
p=a['p'][:,[0,2,1]].copy();original=p.copy();ct=a['faces'];ix=a['ix'];w=a['w'];folder=Path(os.environ.get("UMA_V6_GAME", "D:/steam/steamapps/common/Crusader Kings III/game")) / 'gfx/models/portraits/female_body';cases=[]
def skin(v,ix,w,m):
 h=np.column_stack([v,np.ones(len(v))]);res=np.zeros_like(v)
 for j in range(4):res+=np.einsum('nij,nj->ni',m[np.maximum(ix[:,j],0)],h)[:,:3]*w[:,j,None]
 return res
for clip in [None,'female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim']:
 if clip:
  z=pdx.read_meshfile(str(folder/clip));f=z.find('info').attrib['sa'][0]//2;m=globals_for(z.find('info'),z.find('samples'),f,sk)@bind;m[:,:3,3]*=.01
 else:m=np.repeat(np.eye(4)[None],len(sk),axis=0)
 body=skin(bp,bix,bw,m);bvh=BVHTree.FromPolygons([Vector(x)for x in body],bt.tolist(),all_triangles=True);linear=sum(m[np.maximum(ix[:,j],0),:3,:3]*w[:,j,None,None]for j in range(4));cases.append((clip,m,bvh,np.linalg.pinv(linear)))
counts=[]
for iteration in range(20):
 updates=0
 for clip,m,bvh,inv in cases:
  posed=skin(p,ix,w,m);correction=np.zeros_like(p);num=np.zeros(len(p))
  for i,v in enumerate(posed):
   hit,n,fi,dist=bvh.find_nearest(Vector(v));signed=(Vector(v)-hit).dot(n)
   if signed<.004 and dist<.07 and p[i,1]<.9:
    delta=np.array(n)*min(.02,.004-signed);correction[i]+=inv[i]@delta;num[i]+=1;updates+=1
  # Centroid checks catch triangle interiors that cross a convex knee despite safe corner positions.
  for t in ct:
   v=posed[t].mean(0);hit,n,fi,dist=bvh.find_nearest(Vector(v));signed=(Vector(v)-hit).dot(n)
   if signed<.003 and dist<.035 and p[t,1].mean()<.9:
    delta=np.array(n)*min(.01,.003-signed)
    for i in t:correction[i]+=inv[i]@delta;num[i]+=1
  valid=num>0;p[valid]+=.6*correction[valid]/num[valid,None]
 counts.append(updates);print('GARMENT_CLEARANCE_ITER',iteration,updates,flush=True)
# Preserve exact duplicate source geometry through common correction so seam islands don't split.
q=np.round(original,5);unique,ids=np.unique(q,axis=0,return_inverse=True);delta=p-original;total=np.zeros((len(unique),3));np.add.at(total,ids,delta);total/=np.bincount(ids)[:,None];p=original+total[ids]
a['p']=p[:,[0,2,1]];delta=a['p']-original[:,[0,2,1]]
for key in ['b0','b1','b3','b4','s1','s2']:a[key]+=delta
np.savez_compressed(R/'garment-prepared.npz',**a);out=dict(iterations=20,source_pose_samples=[x[0]for x in cases],vertex_projection_counts=counts,rest_correction_max_m=float(np.linalg.norm(delta,axis=1).max()),rest_correction_p99_m=float(np.quantile(np.linalg.norm(delta,axis=1),.99)),method='Fixed rest geometry adapted across neutral, installed idle middle and throne middle LBS, including triangle-centroid clearance; no runtime cloth simulation')
(R/'garment-clearance-fit.json').write_text(json.dumps(out,indent=2));print(out,flush=True)
