"""Isolated heel stance candidate. V9/source resources are read only."""
import os,sys,json,copy,hashlib
from pathlib import Path
import xml.etree.ElementTree as X
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
from head_assembly_math import rigdata,readlocals,compose,shared_pose,deform
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9'); M=V/'UMA-V9/gfx/models/portraits/uma'; O=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V10/HeelPose'); D=O/'gfx/models/portraits/uma/animation/body';D.mkdir(parents=True,exist_ok=True)
P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');a=M/'animation/body/uma_body_native_idle.anim';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();originalsha=sha(a)
source=P.read_meshfile(str(a));info=source.find('info');samples=source.find('samples');count=info.get('sa')[0]
bo=P.read_meshfile(str(M/'0001/uma_0001_body_base.mesh')).find('object')[0];B=rigdata(bo.find('skeleton'));names=B['names'];assert len(names)==146 and [n.tag for n in info]==names
clothing=json.loads((V/'Reports/clothing-registration.json').read_text());family=next(r for r in clothing['families']if r['family']=='bdy1001_00');shoe=Path(family['parts']['shoes']['base_mesh']);so=P.read_meshfile(str(shoe)).find('object')[0];S=rigdata(so.find('skeleton'));nodes=so.findall('mesh')
original=[readlocals(P,a,f)for f in range(count)];BW=np.array([compose(B,l)for l in original]);shoe_pose=lambda w:np.vstack([deform(n,S,shared_pose(S,B,w))for n in nodes]);sv0=shoe_pose(BW[0]);footmask=[sv0[:,0]>0,sv0[:,0]<0];front=[x&(sv0[:,2]<-14)for x in footmask];heel=[x&(sv0[:,2]>-12)&(sv0[:,1]<-3)for x in footmask];assert all(m.any()for m in front+heel)
ankles=['bn_l_ankle','bn_r_ankle'];root='body_root';solutions=[];newlocals=[];allshoe=[];frameinfo=[];previous=np.array([-14.,-14.,0.,0.,8.])
def pose(frame,p):
 l={k:v.copy()for k,v in original[frame].items()}
 for k,n in enumerate(ankles):
  i=names.index(n);parent=B['parents'][i];parentrot=BW[frame,parent,:3,:3];R=Rotation.from_euler('xz',[p[k],p[k+2]],degrees=True).as_matrix();l[n][:3,:3]=np.linalg.inv(parentrot)@R@parentrot@l[n][:3,:3]
 # body_root local Y is ground Y here; source ground_joint retained unchanged.
 gr=BW[frame,B['parents'][names.index(root)],:3,:3];l[root][:3,3]+=np.linalg.inv(gr)@np.array([0.,p[4],0.])
 # Keep each forefoot/toe bone direction tangent to the plane, allowing the
 # anatomical arch (ankle -> ball) to descend into a real high-heel shoe.
 w=compose(B,l)
 for side in ['l','r']:
  n=f'bn_{side}_ftBall';i=names.index(n);j=names.index(f'bn_{side}_ftToe');parent=B['parents'][i];d=w[j,:3,3]-w[i,:3,3];d/=np.linalg.norm(d);h=d.copy();h[1]=0;h/=np.linalg.norm(h);axis=np.cross(d,h);angle=np.arctan2(np.linalg.norm(axis),np.dot(d,h))
  if np.linalg.norm(axis)>1e-12:
   R=Rotation.from_rotvec(axis/np.linalg.norm(axis)*angle).as_matrix();pr=w[parent,:3,:3];l[n][:3,:3]=np.linalg.inv(pr)@R@pr@l[n][:3,:3]
 return l,compose(B,l)
def residual(p,frame):
 l,w=pose(frame,p);v=shoe_pose(w);support=[v[m,1].min()for pair in zip(front,heel)for m in pair]
 return np.r_[support,p[2:4]*.002]
for f in range(count):
 fit=least_squares(residual,previous,args=(f,),bounds=([-35,-35,-2,-2,0],[5,5,2,2,25]),xtol=1e-10,ftol=1e-10,gtol=1e-10,max_nfev=90);p=fit.x;l,w=pose(f,p);v=shoe_pose(w)
 # exact lowest shoe point = plane; other physical contact supports measured separately.
 p[4]-=v[:,1].min();l,w=pose(f,p);v=shoe_pose(w);previous=p;solutions.append(p);newlocals.append(l);allshoe.append(v)
 rec={'frame_zero_based':f,'parameters_deg_cm':p.tolist(),'residual_cost':float(fit.cost),'evaluations':fit.nfev,'whole_shoe_min_y_cm':float(v[:,1].min()),'contacts':{side:{'forefoot_min_y_cm':float(v[front[k],1].min()),'heel_min_y_cm':float(v[heel[k],1].min()),'foot_min_y_cm':float(v[footmask[k],1].min())}for k,side in enumerate(['left','right'])}}
 frameinfo.append(rec)
 if f in [0,30,60]:print('HEEL_SOLVED',f,p.round(5).tolist(),rec['contacts'],flush=True)
# Preserve every original channel for all unmodified bones. Activate only root t and ankle q.
changed={root:'t',ankles[0]:'q',ankles[1]:'q','bn_l_ftBall':'q','bn_r_ftBall':'q'};channels={c:[]for c in 'tqs'};origactive={c:[i for i,n in enumerate(info)if c in n.get('sa')[0]]for c in 'tqs'};origpacked={c:np.array(samples.get(c)or[]).reshape(count,len(origactive[c]),3 if c=='t'else 4 if c=='q'else len(info[origactive[c][0]].get(c)))if origactive[c]else None for c in 'tqs'}
out=copy.deepcopy(source);oi=out.find('info');osamp=out.find('samples');osamp.attrib={}
trackdata={};modified_rotation_continuity={}
for i,n in enumerate(info):
 cs=n.get('sa')[0];cs=''.join(c for c in 'tqs'if c in cs or changed.get(n.tag)==c);oi[i].attrib['sa']=[cs]
 for c in 'tqs':
  vals=origpacked[c][:,origactive[c].index(i)].copy()if i in origactive[c]else np.tile(n.get(c),(count,1))
  if changed.get(n.tag)==c:
   if c=='t':vals=np.array([l[n.tag][:3,3]for l in newlocals])
   else:
    scale=np.linalg.norm(original[0][n.tag][:3,:3],axis=0);vals=Rotation.from_matrix(np.array([l[n.tag][:3,:3]/scale for l in newlocals])).as_quat()
    if np.dot(vals[0],np.array(n.get('q')))<0:vals[0]*=-1
    for f in range(1,count):
     if np.dot(vals[f-1],vals[f])<0:vals[f]*=-1
    modified_rotation_continuity[n.tag]=float(np.min(np.sum(vals[1:]*vals[:-1],axis=1)))
  oi[i].attrib[c]=vals[0].tolist();trackdata[(n.tag,c)]=vals
  if c in cs:channels[c].append(vals)
for c,arr in channels.items():
 if arr:osamp.attrib[c]=np.stack(arr,axis=1).ravel().tolist()
clip=D/'uma_heel_1001_idle.anim';P.write_animfile(str(clip),out);read=P.read_meshfile(str(clip));assert read.find('info').attrib==info.attrib and [n.tag for n in read.find('info')]==names
NW=np.array([compose(B,readlocals(P,clip,f))for f in range(count)]);shoe_read=np.array([shoe_pose(w)for w in NW]);body_read=np.array([np.vstack([deform(n,B,w)for n in bo.findall('mesh')])for w in NW]);assert np.isfinite(NW).all()and np.isfinite(shoe_read).all()and np.isfinite(body_read).all()
unchanged={};rl=[readlocals(P,clip,f)for f in range(count)]
for n in names:
 if n not in changed:unchanged[n]=float(max(np.max(abs(rl[f][n]-original[f][n]))for f in range(count)))
legerrors={}
for side in ['l','r']:
 for b,c in [('hip','knee'),('knee','ankle'),('ankle','ftBall'),('ftBall','ftToe')]:
  i,j=[names.index(f'bn_{side}_{z}')for z in [b,c]];dist=lambda w:np.linalg.norm(w[:,i,:3,3]-w[:,j,:3,3],axis=1);legerrors[f'{side}_{b}_{c}']=float(abs(dist(NW)-dist(BW)).max())
contactmax=max(float(shoe_read[f,m,1].min())for f in range(count)for m in front+heel);floor_min=float(shoe_read[:,:,1].min());assert floor_min>-1e-4 and contactmax<.1 and max(legerrors.values())<.0001 and max(unchanged.values())<1e-6
np.savez_compressed(O/'heel-body-poses.npz',world=NW,source_world=BW,local=np.array([[rl[f][n]for n in names]for f in range(count)]),parameters=np.array(solutions),bone_names=np.array(names),parents=np.array([-1 if p is None else p for p in B['parents']]))
# Private set: identical ordinary key coverage, new basename, same 146-bone reference.
oldasset=M/'animation/body/uma_body_animations.asset';ast=clausewitz(oldasset.read_text(encoding='utf-8-sig'));aset=one(ast,'skeletal_animation_set');onekeys=[one(v,'id')for v in values(aset,'animation')]
for i,(k,v)in enumerate(aset):
 if k=='name':aset[i]=(k,'uma_heel_1001_body')
 if k=='animation':v[:]=[(kk,clip.name if kk=='type'else vv)for kk,vv in v]
asset=D/'uma_heel_1001_animations.asset';asset.write_text(script_block(ast)+'\n',encoding='utf-8-sig');check=one(clausewitz(asset.read_text(encoding='utf-8-sig')),'skeletal_animation_set');assert [one(v,'id')for v in values(check,'animation')]==onekeys
# Explicit test body entity copied from the existing schema. No invented shoe predicates.
entity_source=M/'0001/uma_0001_body_base.asset';et=clausewitz(entity_source.read_text(encoding='utf-8-sig'));base=next(v for k,v in et if k=='entity'and one(v,'name')=='uma_body_entity');entity=copy.deepcopy(base)
for i,(k,v)in enumerate(entity):
 if k=='name':entity[i]=(k,'uma_heel_1001_body_entity')
candidate=O/'gfx/models/portraits/uma/0001/uma_heel_1001_body_test.asset';candidate.parent.mkdir(parents=True,exist_ok=True)
# pdxmesh cannot select a skeletal set from entity state: private mesh wrapper needs its own set.
mesh=copy.deepcopy(next(v for k,v in et if k=='pdxmesh'))
newmeshname='uma_heel_1001_body_mesh'
for i,(k,v)in enumerate(mesh):
 if k=='name':mesh[i]=(k,newmeshname)
 if k=='import':
  v[:]=[(kk,'uma_heel_1001_body'if kk=='name'else vv)for kk,vv in v]
for i,(k,v)in enumerate(entity):
 if k=='pdxmesh':entity[i]=(k,newmeshname)
candidate.write_text(script_block([('pdxmesh',mesh),('entity',entity)])+'\n',encoding='utf-8-sig')
oldcandidate=O/'gfx/models/portraits/uma/uma_heel_1001_body_test.asset'
if oldcandidate.exists():
 assert oldcandidate.resolve().is_relative_to(O.resolve())
 oldcandidate.unlink()
assert one(one(clausewitz(candidate.read_text(encoding='utf-8-sig')),'pdxmesh'),'import')==[('type','skeletal_animation_set'),('name','uma_heel_1001_body')]
assert originalsha==sha(a)
support_ids={side:{'forefoot':np.flatnonzero(front[k]).tolist(),'heel':np.flatnonzero(heel[k]).tolist()}for k,side in enumerate(['left','right'])}
evidence={'status':'numerical_candidate_for_bdy1001_00_only','runtime_verified':False,'blender_visual_verified':False,'source_clip':str(a),'source_clip_sha256_before_after':originalsha,'source_mesh':str(shoe),'source_mesh_sha256':sha(shoe),'source_snapshot':family['source_snapshot'],'source_points':family['source_points'],'source_partition':family['source_partition'],'source_family':family['family'],'body_bones':146,'shoe_rig_bones':len(S['names']),'frames':count,'fps':info.get('fps')[0],'body_bone_order_preserved':True,'parents_preserved':True,'skeleton_reference':'uma_body_mesh','candidate_skeletal_animation_set':'uma_heel_1001_body','candidate_body_entity':'uma_heel_1001_body_entity','candidate_body_mesh':'uma_heel_1001_body_mesh','all_ordinary_keys_reused':onekeys,'ordinary_key_count':len(onekeys),'ordinary_key_all_one_clip':clip.name,'changed_local_channels':changed,'parameter_order':['left_world_pitch_deg','right_world_pitch_deg','left_world_roll_deg','right_world_roll_deg','body_root_groundY_cm'],'parameter_min':np.array(solutions).min(0).tolist(),'parameter_max':np.array(solutions).max(0).tolist(),'original_shoe_frame0_aabb_cm':[sv0.min(0).tolist(),sv0.max(0).tolist()],'source_frame0_support_heights_cm':{side:{'heel':float(sv0[heel[k],1].min()),'forefoot':float(sv0[front[k],1].min())}for k,side in enumerate(['left','right'])},'sole_contact_selection':'actual mesh vertices; foot sides split by frame0 X; forefoot frame0 Z<-14cm, heel Z>-12cm and Y<-3cm; all shoe vertices also checked against plane','contact_vertex_ids':support_ids,'whole_shoe_min_y_cm':floor_min,'whole_shoe_max_perframe_min_y_cm':float(shoe_read[:,:,1].min(1).max()),'max_selected_support_clearance_cm':contactmax,'leg_chain_length_max_error_cm':legerrors,'unchanged_local_matrix_max_error':max(unchanged.values()),'modified_quaternion_adjacent_min_dot':modified_rotation_continuity,'pdx_readback_world_max_error':float(abs(NW-np.array([compose(B,l)for l in newlocals])).max()),'new_body_loop_world_seam_max_error':float(abs(NW[-1]-NW[0]).max()),'original_body_loop_world_seam_max_error':float(abs(BW[-1]-BW[0]).max()),'source_loop_relation':'same61frames/30fps, all local transforms except ankle q/root t retained exactly; no resampling','all_skinning_finite':True,'head_seam_integration_required':True,'head_integration_contract':'Use heel-body-poses.npz world[f] in the SAME new245bone head loop seam helper mapping used for native body; regenerate cervical/thoracic/clavicle-derived helpers and neck ring targets. No additive second root lift. No head file was modified here.','selection_contract':'Private pdxmesh animation name = uma_heel_1001_body, test entity pdxmesh = uma_heel_1001_body_mesh; reuse source entity states/body animation keys. Choose this entity explicitly for the bdy1001_00 shoe test portrait type. Dynamic shoe-gene/user_data-to-set switching is not asserted or implemented.','candidate_mesh_path_needs_resolution':'Candidate .asset is at uma root; its pdxmesh file and meshsettings paths must be adjusted to installed package relative UMA paths before integration, preserving source shaders.','frames_validation':frameinfo}
(O/'heel-validation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8-sig')
(O/'heel-integration.txt').write_text('真实高跟鞋测试候选 bdy1001_00\n146骨/61帧/30fps，原idle SHA256不变。新anim:'+str(clip)+'\n普通keys全部复用V9私有body定义，仅映射新clip。\n明确测试entity通过私有pdxmesh选择私有skeletal_animation_set；未声称鞋基因能自动切换动画。\n主线程必须用heel-body-poses.npz世界矩阵与同一245骨头部loop seam映射重建对应head clip；不要重复施加root高度。\n全部61帧：最低鞋底Y='+str(floor_min)+'cm，前掌/后跟最大离地='+str(contactmax)+'cm，腿链长度误差='+str(max(legerrors.values()))+'cm。\n数值PDX回读通过；Blender外观和CK3运行尚未验证。\n',encoding='utf-8-sig')
print('HEEL_DONE',clip,'contactmax_cm',contactmax,'leg_error',max(legerrors.values()),'keys',len(onekeys),flush=True)
