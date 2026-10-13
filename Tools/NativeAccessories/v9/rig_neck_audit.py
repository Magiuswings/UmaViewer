"""Evidence-only V8 attachment assumptions and V9 seam repair candidates."""
import json,sys,copy,hashlib
from pathlib import Path
import numpy as np
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,shared_pose,deform
V8=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');OUT=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9/RigRepair');OUT.mkdir(parents=True,exist_ok=True)
P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');BASE=V8/'UMA-V8/gfx/models/portraits/uma'
def load(p):
 o=P.read_meshfile(str(p)).find('object')[0];return o,rigdata(o.find('skeleton'))
bo,B=load(BASE/'0001/uma_0001_body_base.mesh');ho,H=load(BASE/'0001/uma_0001_head_female.mesh')
BW=np.load(V8/'MotionSources/body-final-pose-evidence.npz')['world'];HW=np.load(V8/'MotionSources/head-final-pose-evidence.npz')['world'];root=H['names'].index('head_root');thor=B['names'].index('bn_sp_thoracic')
def apply(p,x):return p@x[:3,:3].T+x[:3,3]
bridgeindex=json.loads((V8/'Reports/neck-delivery-source.json').read_text());records=[]
for actor in ['1001','1002']:
 o,D=load(BASE/f'{actor}/uma_{actor}_neck_base.mesh');ring=next(x for x in bridgeindex['actors']if x['row']['actor']==actor);ids=ring['lower_ring_body_vertex_ids'];m=o.find('mesh');p=np.array(m.get('p')).reshape(-1,3);face,FD=load(BASE/f'{actor}/uma_{actor}_face_80.mesh');patch,PD=load(BASE/f'{actor}/uma_{actor}_neck_patch_80.mesh')
 cases={k:[]for k in ['legacy_three_full','legacy_root_full_only','legacy_root_translation_only','root_full_rigid_lower','root_translation_rigid_lower']}
 Xbind=B['bind'][thor]@np.linalg.inv(H['bind'][root]);Tb=np.eye(4);Tb[:3,3]=B['bind'][thor,:3,3]-H['bind'][root,:3,3]
 bp=np.array(bo.find('mesh').get('p')).reshape(-1,3)[ids];full_p=apply(bp,np.linalg.inv(Xbind));trans_p=apply(bp,np.linalg.inv(Tb))
 for f in range(len(BW)):
  body=deform(bo.find('mesh'),B,BW[f])[ids];x=BW[f,thor]@np.linalg.inv(HW[f,root]);t=np.eye(4);t[:3,3]=BW[f,thor,:3,3]-HW[f,root,:3,3];three=HW[f].copy()
  for b,h in [('bn_l_clavicle','bn_h_l_clavicle'),('bn_r_clavicle','bn_h_r_clavicle')]:three[H['names'].index(h)]=np.linalg.inv(x)@BW[f,B['names'].index(b)]
  for label,ext,pose in [('legacy_three_full',x,three),('legacy_root_full_only',x,HW[f]),('legacy_root_translation_only',t,HW[f])]:
   q=apply(deform(m,D,shared_pose(D,H,pose)),ext);upper=np.vstack([apply(deform(obj.find('mesh'),r,shared_pose(r,H,pose)),ext)for obj,r in [(face,FD),(patch,PD)]]);cases[label].append({'frame':f,'lower_gap_cm':float(np.linalg.norm(q[:6]-body,axis=1).max()),'upper_gap_cm':float(max(np.linalg.norm(upper-v,axis=1).min()for v in q[6:]))})
  cases['root_full_rigid_lower'].append({'frame':f,'lower_gap_cm':float(np.linalg.norm(apply(full_p,x)-body,axis=1).max())})
  cases['root_translation_rigid_lower'].append({'frame':f,'lower_gap_cm':float(np.linalg.norm(apply(trans_p,t)-body,axis=1).max())})
 summary={k:{'lower_max_cm':max(z['lower_gap_cm']for z in a),'upper_max_cm':max(z.get('upper_gap_cm',0)for z in a),'frames':a}for k,a in cases.items()};records.append({'actor':actor,'body_ring_ids':ids,'cases':summary,'rigid_lower_candidate_header_points_full':full_p.tolist(),'rigid_lower_candidate_header_points_translation':trans_p.tolist()});print('CASES',actor,{k:round(z['lower_max_cm'],6)for k,z in summary.items()},flush=True)
out={'engine_matrix_semantics_unverified':True,'prior_python_validation_explicitly_assumed_full_three_joint_overrides':str(Path('C:/Users/33775/Desktop/网页制作/UmaV8Scripts/assembly_math_v8.py')),'screenshot':str(Path('C:/Users/33775/AppData/Local/Temp/codex-clipboard-9b6f69bf-8742-4350-af3e-c2a536cf7527.png')),'screenshot_proves_visible_rear_neck_discontinuity_but_not_matrix_semantics':True,'all61_frames_from_actual_body_head_pdx_readback':True,'cases':records}
(OUT/'neck-attachment-assumption-audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
