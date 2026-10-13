"""Unified head seam bind and source-derived helper clips, with two explicit root semantics."""
import sys,json,copy,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,deform,shared_pose,readlocals,compose
V8=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');OUT=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9/RigRepair');OUT.mkdir(parents=True,exist_ok=True);BASE=V8/'UMA-V8/gfx/models/portraits/uma';P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')
def load(path):
 tree=P.read_meshfile(str(path));o=tree.find('object')[0];return tree,o,rigdata(o.find('skeleton'))
bt,bo,B=load(BASE/'0001/uma_0001_body_base.mesh');ht,ho,H=load(BASE/'0001/uma_0001_head_female.mesh');sourceclip=V8/'MotionSources/Final/animation/head/uma_head_native_idle.anim';orig=P.read_meshfile(str(sourceclip));BW=np.load(V8/'MotionSources/body-final-pose-evidence.npz')['world'];HW=np.load(V8/'MotionSources/head-final-pose-evidence.npz')['world'];root=H['names'].index('head_root');thor=B['names'].index('bn_sp_thoracic');bodymesh=bo.find('mesh');bodyp=np.array(bodymesh.get('p')).reshape(-1,3);bodyn=np.array(bodymesh.get('n')).reshape(-1,3);bodyix=np.array(bodymesh.find('skin').get('ix')).reshape(-1,4);bodyw=np.array(bodymesh.find('skin').get('w')).reshape(-1,4);bridgeindex=json.loads((V8/'Reports/neck-delivery-source.json').read_text());extras=[('uma_neck_body_thoracic','bn_sp_thoracic'),('uma_neck_body_clavicle_l','bn_l_clavicle'),('uma_neck_body_clavicle_r','bn_r_clavicle')];delivery=[]
def apply(p,m):return p@m[:3,:3].T+m[:3,3]
def ext(b,h,mode):
 if mode=='full_root':return b[thor]@np.linalg.inv(h[root])
 m=np.eye(4);m[:3,3]=b[thor,:3,3]-h[root,:3,3];return m
def newclip(rig,desired,path):
 count=len(desired);local=[]
 for i,pa in enumerate(rig['parents']):local.append(np.linalg.inv(desired[:,pa])@desired[:,i]if pa is not None else desired[:,i])
 local=np.stack(local,axis=1);info=ET.Element('info',{'fps':[30.],'sa':[count],'j':[len(rig['names'])]});samples=ET.Element('samples');blocks={c:[]for c in 'tqs'}
 for i,n in enumerate(rig['names']):
  m=local[:,i];u,s,v=np.linalg.svd(m[:,:3,:3]);r=u@v;q=Rotation.from_matrix(r).as_quat();scale=np.diagonal(np.transpose(r,(0,2,1))@m[:,:3,:3],axis1=1,axis2=2).copy()
  for f in range(1,count):
   if q[f]@q[f-1]<0:q[f]*=-1
  data={'t':m[:,:3,3],'q':q,'s':scale};active=''.join(c for c in 'tqs'if abs(data[c]-data[c][0]).max()>1e-7);ET.SubElement(info,n,{'sa':[active],**{c:a[0].tolist()for c,a in data.items()}})
  for c in active:blocks[c].append(data[c])
 for c,a in blocks.items():
  if a:samples.set(c,np.stack(a,axis=1).ravel().tolist())
 tree=ET.Element('File',{'pdxasset':[1,0]});tree.extend([info,samples]);P.write_animfile(str(path),tree);parsed=P.read_meshfile(str(path));assert parsed.find('info').get('j')==[245]and[b.tag for b in parsed.find('info')]==rig['names'];D={'names':rig['names'],'parents':rig['parents'],'bind':np.array(rig['world']),'local':np.array(rig['bind_local'])};return np.array([compose(D,readlocals(P,path,f))for f in range(count)])
for mode in ['full_root','translation_only']:
 folder=OUT/'Head245'/mode;folder.mkdir(parents=True,exist_ok=True);rig=json.loads((V8/'Rigs/headcarrier.json').read_text());Xbind=ext(B['bind'],H['bind'],mode);X=np.array([ext(b,h,mode)for b,h in zip(BW,HW)]);extraBind=[np.linalg.inv(Xbind)@B['bind'][B['names'].index(b)]for n,b in extras];allbind=np.concatenate([np.array(rig['world']),extraBind]);desired=HW.copy()
 if mode=='translation_only':
  full=np.array([ext(b,h,'full_root')for b,h in zip(BW,HW)]);desired=np.linalg.inv(X)[:,None]@full[:,None]@desired;desired[:,root]=HW[:,root]
 desired=np.concatenate([desired,np.stack([np.linalg.inv(X)@BW[:,B['names'].index(b)]for n,b in extras],axis=1)],axis=1)
 skeleton=copy.deepcopy(ho.find('skeleton'))
 for i,((n,b),w)in enumerate(zip(extras,extraBind),start=242):
  rig['names'].append(n);rig['parents'].append(root);rig['world'].append(w.tolist());rig['inverse_bind'].append(np.linalg.inv(w).tolist());rig['bind_local'].append((np.linalg.inv(allbind[root])@w).tolist());rig['index_by_name'][n]=i;attrs={'ix':[i],'pa':[root],'tx':np.linalg.inv(w)[:3].T.ravel().tolist()};rig.setdefault('skeleton_attributes',[])
  ET.SubElement(skeleton,n,attrs)
 rig['joint_count']=245;rig['seam_helper_semantics']=mode;rig['skeleton_attributes']=[{'name':b.tag,'attributes':dict(b.attrib)}for b in skeleton]
 (folder/'headcarrier_seam.json').write_text(json.dumps(rig,indent=2)+'\n',encoding='utf8');template=copy.deepcopy(ht);obj=template.find('object')[0];obj.remove(obj.find('skeleton'));obj.append(copy.deepcopy(skeleton));P.write_meshfile(str(folder/'headcarrier_seam.mesh'),template)
 pose=newclip(rig,desired,folder/'uma_head_native_idle_seam.anim');DR=rigdata(skeleton);checks=[];roundtrip=float(np.linalg.norm(pose[:,:,:3,3]-desired[:,:,:3,3],axis=2).max());assert roundtrip<.01,(mode,roundtrip)
 for actor in ['1001','1002']:
  source=BASE/f'{actor}/uma_{actor}_neck_base.mesh';tree,o,D=load(source);m=o.find('mesh');p=np.array(m.get('p')).reshape(-1,3);normal=np.array(m.get('n')).reshape(-1,3);skin=m.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);w=np.array(skin.get('w')).reshape(-1,4);oldp=p.copy();ids=next(r['lower_ring_body_vertex_ids']for r in bridgeindex['actors']if r['row']['actor']==actor);p[:6]=apply(bodyp[ids],np.linalg.inv(Xbind));normal[:6]=bodyn[ids]@Xbind[:3,:3];normal[:6]/=np.linalg.norm(normal[:6],axis=1)[:,None];newix=np.full_like(ix,-1);neww=np.zeros_like(w);lower_residual=[]
  for i in range(6):
   weights={n:0. for n,b in extras}
   for j,a in zip(bodyix[ids[i]],bodyw[ids[i]]):
    if a<=0:continue
    bn=B['names'][j];target=dict((b,n)for n,b in extras).get(bn,'uma_neck_body_thoracic');weights[target]+=float(a)
   values=[(rig['index_by_name'][n],v)for n,v in weights.items()if v>0];total=sum(v for j,v in values)
   for slot,(j,a)in enumerate(values):newix[i,slot]=j;neww[i,slot]=a/total
  for i in range(6,len(p)):
   for slot,(j,a)in enumerate(zip(ix[i],w[i])):
    if a>0:newix[i,slot]=rig['index_by_name'][D['names'][j]];neww[i,slot]=a
  m.set('p',p.ravel().tolist());m.set('n',normal.ravel().tolist());skin.set('ix',newix.ravel().tolist());skin.set('w',neww.ravel().tolist());aabb=m.find('aabb')
  if aabb is None:aabb=ET.SubElement(m,'aabb')
  aabb.set('min',p.min(0).tolist());aabb.set('max',p.max(0).tolist());center=(p.min(0)+p.max(0))*.5;m.set('boundingsphere',center.tolist()+[float(np.linalg.norm(p-center,axis=1).max())]);o.remove(o.find('skeleton'));o.append(copy.deepcopy(skeleton));out=folder/f'uma_{actor}_neck_unified.mesh';P.write_meshfile(str(out),tree);_,ro,RD=load(out);maxlower=maxupper=0.
  for f in range(len(pose)):
   q=apply(deform(ro.find('mesh'),RD,pose[f]),X[f]);body=deform(bodymesh,B,BW[f])[ids];maxlower=max(maxlower,float(np.linalg.norm(q[:6]-body,axis=1).max()))
   original=apply(deform(m,D,shared_pose(D,H,HW[f])),ext(BW[f],HW[f],'full_root')) if False else None
   oldupper=np.zeros((10,3));olds=P.read_meshfile(str(source)).find('object')[0].find('mesh');oldq=apply(deform(olds,D,shared_pose(D,H,HW[f])),ext(BW[f],HW[f],'full_root'));maxupper=max(maxupper,float(np.linalg.norm(q[6:]-oldq[6:],axis=1).max()))
  assert maxlower<.005 and maxupper<.005,(mode,actor,maxlower,maxupper);checks.append({'actor':actor,'mesh':str(out),'frames':len(pose),'lower_body_ring_max_error_cm':maxlower,'upper_original_face_patch_world_max_error_cm':maxupper,'upper10_p_n_uv_tri_weights_unchanged':True,'lower6_normals_from_actual_body':True,'lower6_bind_space_rebased':True,'source_mesh_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bounds_header_cm':[p.min(0).tolist(),p.max(0).tolist()]});print('UNIFIED_SEAM',mode,actor,maxlower,maxupper,flush=True)
 delivery.append({'mode':mode,'head_joint_count':245,'reference_mesh':str(folder/'headcarrier_seam.mesh'),'rig_json':str(folder/'headcarrier_seam.json'),'clip':str(folder/'uma_head_native_idle_seam.anim'),'clip_sha256':hashlib.sha256((folder/'uma_head_native_idle_seam.anim').read_bytes()).hexdigest(),'added_helper_keys':[n for n,b in extras],'no_clavicle_joint_override_assumed':True,'all245_bone_worldpoint_pdx_roundtrip_max_cm':roundtrip,'checks':checks,'source_body_sha256':hashlib.sha256((V8/'MotionSources/Final/animation/body/uma_body_native_idle.anim').read_bytes()).hexdigest(),'source_head_sha256':hashlib.sha256(sourceclip.read_bytes()).hexdigest()})
out={'status':'ready_numeric_two_explicit_root_semantics','game_engine_validated':False,'preferred_mode_pending_root_actual_engine_evidence':True,'common242_original_names_points_retained':True,'carrier_requires_245_reference_and_j':True,'attachment_contract':'head to torso root only; remove extra clavicle joint attachments for these candidates. Seam helpers explicitly follow actual body pose inside header clip. Ear/tail remain independent.','merge_contract':'Use chosen mode headcarrier_seam skeleton for unified actor head; old242 indices unchanged. Source face/patch p/n/UV/tri untouched; bridge lower6 use supplied rebased coordinates+new helper skin. Bridge upper10 original points/weights preserved. Remove independent neck entity.','candidates':delivery,'source_provenance':json.loads((V8/'MotionSources/native-animation-delivery.json').read_text())['modules'][0]['source_provenance']}
(OUT/'rig-neck-unified-contract.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
