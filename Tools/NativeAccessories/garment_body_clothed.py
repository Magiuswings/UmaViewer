import os
import sys,json,copy
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001")) / 'clothing-parts';REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')];import build_ck3_mod as b
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pdx=b.parser_only(Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh")));rep=json.loads((R/'garment-preparation.json').read_text());original=pdx.read_meshfile(rep['stock_body']);o=original.find('object')[0];sk=o.find('skeleton');sn=o.find('mesh');names=[x.tag for x in sk];bind=inverse_bind(sk);p=np.array(sn.attrib['p']).reshape(-1,3)*.01;n=np.array(sn.attrib['n']).reshape(-1,3);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12);tri=np.array(sn.attrib['tri']).reshape(-1,3);ix=np.array(sn.find('skin').attrib['ix']).reshape(-1,4);w=np.array(sn.find('skin').attrib['w']).reshape(-1,4)
cnode=pdx.read_meshfile(str(R/'uma_1001_clothing_00.mesh')).find('object')[0].find('mesh');cp=np.array(cnode.attrib['p']).reshape(-1,3)*.01;ct=np.array(cnode.attrib['tri']).reshape(-1,3);ci=np.array(cnode.find('skin').attrib['ix']).reshape(-1,4);cw=np.array(cnode.find('skin').attrib['w']).reshape(-1,4);clothbvh=BVHTree.FromPolygons([Vector(x)for x in cp],ct.tolist(),all_triangles=True);native=np.load(R/'source-native-skin-reference.npz');skinp=native['p'][:,[0,2,1]];skinbvh=BVHTree.FromPolygons([Vector(x)for x in skinp],native['tri'].tolist(),all_triangles=True)
clothdistance=np.array([clothbvh.find_nearest(Vector(x))[3]for x in p]);nakeddistance=np.array([skinbvh.find_nearest(Vector(x))[3]for x in p]);handids=[i for i,s in enumerate(names)if '_fi_'in s or s.endswith('_wrist')or s.endswith('_prop')];handmass=sum(w[:,j]*np.isin(ix[:,j],handids)for j in range(4));protected=(p[:,1]>1.245)|(handmass>.6)|(nakeddistance<.025)
# Source exposed anatomy is immutable; only surface samples close to the actual garment are candidates.
coverage=np.clip((.065-clothdistance)/.03,0,1);coverage[protected]=0;coverage*=np.clip((nakeddistance-.025)/.02,0,1)
# Socks/shoes need explicit inner-body clearance despite their sparse sole topology.
coveredleg=(p[:,1]<.55)&~protected;coverage[coveredleg]=1
adj=[set()for _ in p]
for t in tri:
 for i in t:adj[i].update(t.tolist())
for it in range(3):
 q=coverage.copy()
 for i,row in enumerate(adj):
  if not protected[i]:q[i]=.5*coverage[i]+.5*np.mean(coverage[list(row)])
 coverage=q;coverage[protected]=0
# Welded UV duplicates receive one common delta, preserving seam continuity.
world=np.linalg.inv(bind);joints={name:world[i,:3,3]*.01 for i,name in enumerate(names)}
chains={'torso':['body_root','bn_sp_lumbar','bn_sp_thoracic','bn_sp_cervical']}
for side in ['l','r']:
 chains['leg_'+side]=['bn_'+side+'_hip','bn_'+side+'_knee','bn_'+side+'_ankle','bn_'+side+'_ftBall'];chains['arm_'+side]=['bn_'+side+'_clavicle','bn_'+side+'_shoulder','bn_'+side+'_elbow','bn_'+side+'_forearm','bn_'+side+'_wrist']
def nearest(point,chain):
 choices=[]
 for aa,bb in zip(chain,chain[1:]):
  a0=joints[aa];edge=joints[bb]-a0;t=np.clip(np.dot(point-a0,edge)/max(edge@edge,1e-12),0,1);q=a0+edge*t;choices.append((np.linalg.norm(point-q),q))
 return min(choices,key=lambda x:x[0])[1]
center=np.zeros_like(p)
for i,point in enumerate(p):
 mass={}
 for key,chain in chains.items():mass[key]=sum(w[i,j]for j in range(4)if ix[i,j]>=0 and names[ix[i,j]]in chain)
 key=max(mass,key=mass.get);center[i]=nearest(point,chains[key])
radial=p-center;factor=np.where(p[:,1]<.15,.30,np.where(p[:,1]<.62,.22,.18));delta=-radial*(factor*coverage)[:,None]
_,ids=np.unique(np.round(p,6),axis=0,return_inverse=True);groups=[np.flatnonzero(ids==j)for j in range(ids.max()+1)]
for group in groups:
 if protected[group].any():delta[group]=0;coverage[group]=0
 else:delta[group]=delta[group].mean(0)
shrunk=p+delta;tree=copy.deepcopy(original);node=tree.find('object')[0].find('mesh');node.attrib['p']=(shrunk*100).ravel().tolist();file=R/'uma_0001_body_clothed.mesh';pdx.write_meshfile(str(file),tree);read=pdx.read_meshfile(str(file));rn=read.find('object')[0].find('mesh');assert rn.attrib['tri']==sn.attrib['tri'];assert rn.attrib['u0']==sn.attrib['u0'];assert rn.find('skin').attrib==sn.find('skin').attrib;assert np.array_equal(inverse_bind(read.find('object')[0].find('skeleton')),bind)
mask=dict(body_file=str(file),key='bs_body_clothed',coverage=coverage.tolist(),protected=protected.tolist(),native_exposed_skin_distance_m=nakeddistance.tolist(),clothing_nearest_distance_m=clothdistance.tolist(),delta_cm=(delta*100).tolist(),vertices_moved=int(np.count_nonzero(np.linalg.norm(delta,axis=1)>1e-8)),protected_vertices=int(protected.sum()),protected_delta_max_cm=float(np.linalg.norm(delta[protected]*100,axis=1).max()),max_shrink_cm=float(np.linalg.norm(delta*100,axis=1).max()),coverage_method='Native1001 exposed-skin BVH distances protect naked arms/thighs; all fingers/wrist/prop and neck/head protected; garment-distance coverage with fixed skeleton-center radial shrink and shared UV seam displacement',topology_uv_weights_binds_exact=True,unchanged_source_body=rep['stock_body']);(R/'body-clothed-coverage-mask.json').write_text(json.dumps(mask,indent=2),encoding='utf8');np.savez_compressed(R/'body-clothed-coverage-mask.npz',p=p,clothed=shrunk,coverage=coverage,protected=protected,clothing_distance=clothdistance,naked_distance=nakeddistance);print('BODY_CLOTHED',mask['vertices_moved'],mask['protected_vertices'],mask['max_shrink_cm'],flush=True)
# Compare actual neutral/idle/sitting triangles before and after, same exported outfit.
def posed(points,ix,w,m):
 h=np.column_stack([points,np.ones(len(points))]);res=np.zeros_like(points)
 for j in range(4):res+=np.einsum('nij,nj->ni',m[np.maximum(ix[:,j],0)],h)[:,:3]*w[:,j,None]
 return res
folder=Path(os.environ.get("UMA_V6_GAME", "D:/steam/steamapps/common/Crusader Kings III/game")) / 'gfx/models/portraits/female_body';reports=[]
for clip in [None,'female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim']:
 if clip:
  a=pdx.read_meshfile(str(folder/clip));frames=sorted({0,a.find('info').attrib['sa'][0]//2,a.find('info').attrib['sa'][0]-1})
 else:frames=[0]
 for frame in frames:
  m=globals_for(a.find('info'),a.find('samples'),frame,sk)@bind if clip else np.repeat(np.eye(4)[None],len(sk),axis=0);m[:,:3,3]*=.01;cloth=posed(cp,ci,cw,m);cbvh=BVHTree.FromPolygons([Vector(x)for x in cloth],ct.tolist(),all_triangles=True);values={}
  for title,points in [('basis',p),('clothed',shrunk)]:
   body=posed(points,ix,w,m);bvh=BVHTree.FromPolygons([Vector(x)for x in body],tri.tolist(),all_triangles=True);pairs=bvh.overlap(cbvh);bad={q[1]for q in pairs};values[title]=dict(intersecting_triangle_pairs=len(pairs),clothing_triangles=len(bad),shoes_triangles=sum(cp[ct[i],1].mean()<.15 for i in bad),socks_triangles=sum(.15<=cp[ct[i],1].mean()<.62 for i in bad),skirt_waist_triangles=sum(.62<=cp[ct[i],1].mean()<.90 for i in bad),upper_triangles=sum(cp[ct[i],1].mean()>=.90 for i in bad),finite=bool(np.isfinite(body).all()))
  reports.append(dict(animation=clip,frame=int(frame),models=values))
(R/'body-clothed-animation-collision.json').write_text(json.dumps(reports,indent=2,default=lambda x:int(x)),encoding='utf8');print('BODY_CLOTHED_COLLISION',json.dumps(reports,default=lambda x:int(x)),flush=True)
