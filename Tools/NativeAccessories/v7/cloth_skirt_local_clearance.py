import os
"""Bounded 1002 D skirt clearance against ONLY complete legs and stockings; no global body projection."""
import json,sys,copy
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));A=R/'ClothingParts/AB-bdy1002_00';sys.path[:0]=[str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'),str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind,globals_for
from cloth_fit_export import normals_tangents
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());fam=next(f for f in reg['families']if f['family']=='bdy1002_00');ab=json.loads((A/'ab-candidates.json').read_text());D=next(c for c in ab['candidates']if c['case']=='D');trees={tag:pd.read_meshfile(file)for tag,file in D['files'].items()};sk=trees['base'].find('object')[0].find('skeleton');bind=inverse_bind(sk);names=[b.tag for b in sk]
bodydir=next(Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'v5')).rglob('uma_0001_body_base.mesh')).parent
def loadpoints(file):
 tree=pd.read_meshfile(str(file));nodes=[n for o in tree.find('object')for n in o.findall('mesh')];return tree,nodes
_,[bn]=loadpoints(bodydir/'uma_0001_body_base.mesh');bp=np.array(bn.attrib['p']).reshape(-1,3);bt=np.array(bn.attrib['tri']).reshape(-1,3);bix=np.array(bn.find('skin').attrib['ix']).reshape(-1,4);bw=np.array(bn.find('skin').attrib['w']).reshape(-1,4)
for tag in ['b0','s1']:_,[n]=loadpoints(bodydir/('uma_0001_body_'+tag+'.mesh'));bp+=np.array(n.attrib['p']).reshape(-1,3)-np.array(bn.attrib['p']).reshape(-1,3)
legvertex=np.array([sum(w for bi,w in zip(ix,ws)if w>0 and any(s in names[bi]for s in ['_hip','_knee','_ankle','_toe']))>.45 for ix,ws in zip(bix,bw)]);bt=bt[np.all(legvertex[bt],axis=1)]
def deform(p,ix,w,mat):
 h=np.column_stack([p,np.ones(len(p))]);out=np.zeros_like(p)
 for j in range(4):out+=np.einsum('nij,nj->ni',mat[np.maximum(ix[:,j],0)],h)[:,:3]*w[:,j,None]
 return out
def actor_nodes(files):
 base=loadpoints(files['base'])[1];b0=loadpoints(files['b0'])[1];s1=loadpoints(files['s1'])[1];return [(np.array(n.attrib['p']).reshape(-1,3)+np.array(x.attrib['p']).reshape(-1,3)+np.array(y.attrib['p']).reshape(-1,3)-2*np.array(n.attrib['p']).reshape(-1,3),np.array(n.attrib['tri']).reshape(-1,3),np.array(n.find('skin').attrib['ix']).reshape(-1,4),np.array(n.find('skin').attrib['w']).reshape(-1,4))for n,x,y in zip(base,b0,s1)]
sock=fam['parts']['socks'];sockfiles={'base':sock['base_mesh'],'b0':sock['shape_targets']['bs_body_breast_shape_1'],'s1':sock['shape_targets']['bs_body_gaunt_1']};socks=actor_nodes(sockfiles);clothes=actor_nodes(D['files']);mats=[]
folder=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body'))
for label,clip in [('neutral',None),('idle','female_body_idle_1.anim'),('throne','female_body_throneRoom_ruler1_1.anim')]:
 if clip:a=pd.read_meshfile(str(folder/clip));frames=[a.find('info').attrib['sa'][0]//2]
 else:frames=[0]
 for frame in frames:
  mat=globals_for(a.find('info'),a.find('samples'),frame,sk)@bind if clip else np.repeat(np.eye(4)[None],len(sk),axis=0);p=deform(bp,bix,bw,mat);surfaces=[p[bt]]
  for sp,st,six,sw in socks:surfaces.append(deform(sp,six,sw,mat)[st])
  triangles=np.concatenate(surfaces);normal=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-10);mats.append((label,mat,triangles,normal,cKDTree(triangles.mean(1))))
def nearest(q,t,n,tree):
 _,ids=tree.query(q,k=min(40,len(t)));a=t[ids,0];b=t[ids,1];c=t[ids,2];nn=n[ids];v=q[:,None,:];distance=np.sum((v-a)*nn,axis=2);proj=v-distance[:,:,None]*nn;ab=b-a;ac=c-a;aq=proj-a;d00=np.sum(ab*ab,2);d01=np.sum(ab*ac,2);d11=np.sum(ac*ac,2);d20=np.sum(aq*ab,2);d21=np.sum(aq*ac,2);den=np.maximum(d00*d11-d01*d01,1e-20);u=(d11*d20-d01*d21)/den;w=(d00*d21-d01*d20)/den;inside=(u>=0)&(w>=0)&(u+w<=1);best=np.where(inside[:,:,None],proj,a);bestdist=np.where(inside,np.sum((v-proj)**2,2),np.inf)
 for start,end in [(a,b),(b,c),(c,a)]:
  edge=end-start;f=np.clip(np.sum((v-start)*edge,2)/np.maximum(np.sum(edge*edge,2),1e-20),0,1);hit=start+f[:,:,None]*edge;dd=np.sum((v-hit)**2,2);sel=dd<bestdist;best[sel]=hit[sel];bestdist[sel]=dd[sel]
 choice=np.argmin(bestdist,1);row=np.arange(len(q));hit=best[row,choice];norm=nn[row,choice];dist=np.sqrt(bestdist[row,choice]);return hit,norm,dist,np.sum((q-hit)*norm,1)
dest=A/'Dlocal';dest.mkdir(exist_ok=True);deltas=[];audit=[]
for ni,((p,t,ix,w),sm,classified)in enumerate(zip(clothes,fam['parts']['clothes']['source_maps'],D['classification'])):
 raw=json.loads(Path(fam['source_snapshot']).read_text())['meshes'][sm['mesh']];sourcep=np.array([[v[k]for k in 'xyz']for v in raw['vertices']]);sids=np.array(sm['source_vertex_ids']);front=set(classified['front_source_vertex_ids']);affected=set(classified['affected_source_vertex_ids']);# include side-front neighbours, exclude rear/native waist
 active=np.array([sid in affected and sourcep[sid,2]>-.06 and sourcep[sid,1]<.97 for sid in sids]);delta=np.zeros_like(p);base=np.array([n for o in trees['base'].find('object')for n in o.findall('mesh')][ni].attrib['p']).reshape(-1,3);neighbors=cKDTree(base).query(base,k=12)[1];inverses=[np.linalg.pinv(sum(mat[np.maximum(ix[:,j],0),:3,:3]*w[:,j,None,None]for j in range(4)))for label,mat,triangles,norm,tr in mats];initial=[]
 for iteration in range(8):
  corr=np.zeros_like(p);amount=np.zeros(len(p));states=[]
  for ci,(label,mat,triangles,norm,tr)in enumerate(mats):
   posed=deform(p+delta,ix,w,mat);hit,normal,dist,signed=nearest(posed[active],triangles,norm,tr);ids=np.flatnonzero(active);valid=(dist<1.8)&(signed<.22);selected=ids[valid];inc=normal[valid]*np.clip(.22-signed[valid],0,.45)[:,None];corr[selected]+=np.einsum('nij,nj->ni',inverses[ci][selected],inc);amount[selected]+=1;window=dist<1.8;states.append(dict(pose=label,local_penetrating_skirt_vertices=int(sum((signed<0)&window)),local_clearance_under_2_2mm=int(sum((signed<.22)&window)),local_minimum_signed_cm=float(signed[window].min()),distant_signed_not_collision_min_cm=float(signed.min())))
   localtri=t[np.all(active[t],axis=1)];centers=posed[localtri].mean(1);ch,cn,cd,cs=nearest(centers,triangles,norm,tr);cvalid=(cd<1.8)&(cs<.18);ct=localtri[cvalid];cinc=cn[cvalid]*np.clip(.18-cs[cvalid],0,.35)[:,None]
   for k in range(3):
    vids=ct[:,k];np.add.at(corr,vids,.4*np.einsum('nij,nj->ni',inverses[ci][vids],cinc));np.add.at(amount,vids,.4)
   states[-1]['local_triangle_centers_inside']=int(sum((cd<1.8)&(cs<0)))
  if iteration==0:initial=states
  valid=amount>0;delta[valid]+=.45*corr[valid]/amount[valid,None];# local spatial smoothing keeps UV duplicates and source pleats intact
  dist=np.linalg.norm(base[neighbors]-base[:,None,:],axis=2);coef=np.exp(-(dist/.9)**2)*active[neighbors];smooth=np.sum(delta[neighbors]*coef[:,:,None],axis=1)/np.maximum(coef.sum(1)[:,None],1e-10);delta[active]=.7*delta[active]+.3*smooth[active];delta[~active]=0;length=np.linalg.norm(delta,axis=1);over=length>.8;delta[over]*=.8/length[over,None]
 # Original duplicate source points receive a common delta; all source six shape endpoints get identical offset.
 _,groups=np.unique(np.round(base,4),axis=0,return_inverse=True);tot=np.zeros((groups.max()+1,3));np.add.at(tot,groups,delta);tot/=np.bincount(groups)[:,None];delta=tot[groups];old=np.cross(base[t[:,1]]-base[t[:,0]],base[t[:,2]]-base[t[:,0]]);orientation=[]
 for tag,tree in trees.items():
  node=[n for o in tree.find('object')for n in o.findall('mesh')][ni];before=np.array(node.attrib['p']).reshape(-1,3);after=before+delta;normalbefore=np.cross(before[t[:,1]]-before[t[:,0]],before[t[:,2]]-before[t[:,0]]);normalafter=np.cross(after[t[:,1]]-after[t[:,0]],after[t[:,2]]-after[t[:,0]]);dot=np.sum(normalbefore*normalafter,1);assert np.all(dot[np.linalg.norm(normalbefore,axis=1)>1e-5]>0),'triangle orientation flipped';orientation.append(dict(tag=tag,flipped_triangles=0));node.attrib['p']=after.ravel().tolist();normal=np.zeros_like(after)
  for j in range(3):np.add.at(normal,t[:,j],normalafter)
  normal,tangent=normals_tangents(after,t,np.array(node.attrib['u0']).reshape(-1,2));node.attrib['n']=normal.ravel().tolist();node.attrib['ta']=tangent.ravel().tolist();node.find('aabb').attrib.update(min=after.min(0).tolist(),max=after.max(0).tolist());center=(after.min(0)+after.max(0))/2;node.attrib['boundingsphere']=center.tolist()+[float(np.linalg.norm(after-center,axis=1).max())]
 deltas.append(delta);audit.append(dict(mesh=ni,source_candidate_vertex_ids=sids[active].tolist(),changed_source_vertex_ids=sids[np.linalg.norm(delta,axis=1)>1e-5].tolist(),changed_vertices=int(sum(np.linalg.norm(delta,axis=1)>1e-5)),max_delta_cm=float(np.linalg.norm(delta,axis=1).max()),p99_delta_cm=float(np.quantile(np.linalg.norm(delta,axis=1),.99)),before=initial,last_iteration=states,orientation=orientation));print('LOCAL_SKIRT_CLEARANCE',ni,audit[-1]['changed_vertices'],audit[-1]['max_delta_cm'],states,flush=True)
files={}
for tag,tree in trees.items():
 file=dest/Path(D['files'][tag]).name;pd.write_meshfile(str(file),tree);pd.read_meshfile(str(file));files[tag]=str(file)
candidate=copy.deepcopy(D);candidate.update(case='Dlocal',files=files,geometry_unchanged=False,bounded_local_geometry_correction=True,correction_report=str(dest/'local-clearance.json'));ab['candidates']=[c for c in ab['candidates']if c['case']!='Dlocal']+[candidate];(A/'ab-candidates.json').write_text(json.dumps(ab,indent=2),encoding='utf8');np.savez_compressed(dest/'source-vertex-deltas.npz',**{f'm{i}_delta_cm':d for i,d in enumerate(deltas)});(dest/'local-clearance.json').write_text(json.dumps(dict(body_unchanged=True,weights='D identical for all seven endpoints',geometry_policy='Only native forward/side-forward skirt sourceIDs; targets solely legs and socks; source torso/hands excluded; 0.8cm maximum smooth rest compensation; same delta all seven endpoints; no triangle orientation flips',reference_leg_triangles=len(bt),reference_sock_triangles=sum(len(x[1])for x in socks),nodes=audit),indent=2),encoding='utf8')
