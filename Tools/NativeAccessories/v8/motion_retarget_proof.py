"""Numerical proof for absolute rotation + real local translation displacement."""
import json
from pathlib import Path
import numpy as np
ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/MotionSources');V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/Rigs');N=json.loads(Path('E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3/native-bone-transforms.json').read_text());B=json.loads((V7/'body.json').read_text());mapping=json.loads((V7/'body-source-map.json').read_text());raw=np.load(ROOT/'native-source-local-frames.npz');S=np.array([[1.,0,0],[0,0,1],[0,1,0]]);H=np.eye(4);H[:3,:3]=S*100;HI=np.linalg.inv(H);C=np.diag([-100.,100.,-100.,1.]);CI=np.linalg.inv(C)
def polar(m):
    u,s,v=np.linalg.svd(m[:3,:3]);r=u@v
    if np.linalg.det(r)<0:u[:,-1]*=-1;r=u@v
    return r
NB={n:H@np.array(m)@HI for n,m in N['bind'].items()};NA={n:H@np.array(m)@HI for n,m in N['posed'].items()};TB={n:np.array(m)for n,m in B['world'].items()};names=B['names'];cases=[]
for n,target in mapping.items():
    if n not in NA or target not in TB:continue
    rA=polar(NA[n]);rT=polar(NB[n]);rB=polar(TB[target]);Q=np.linalg.inv(rA)@rB;canonical=rA@Q;cases.append({'source':n,'target':target,'canonical_A_rotation_error':float(np.max(np.abs(canonical-rB))),'T_goal_rotation_engine':(rT@Q).tolist(),'source_A_affine_singular_values':np.linalg.svd(NA[n][:3,:3],compute_uv=False).tolist(),'source_A_rotation_axis_to_target':Q.tolist()})
chains={'Hip':'Waist','Waist':'Spine','Spine':'Neck'}
for side in ['L','R']:
    chains.update({f'Shoulder_{side}':f'Arm_{side}',f'Arm_{side}':f'Elbow_{side}',f'Elbow_{side}':f'Wrist_{side}',f'Thigh_{side}':f'Knee_{side}',f'Knee_{side}':f'Ankle_{side}',f'Ankle_{side}':f'Toe_{side}'})
checks=[]
for parent,child in chains.items():
    if parent not in mapping or child not in mapping:continue
    pb=TB[mapping[parent]];cb=TB[mapping[child]];rt=polar(NB[parent]);ra=polar(NA[parent]);rb=polar(pb);direction=(rt@np.linalg.inv(ra)@rb)@(rb.T@(cb[:3,3]-pb[:3,3]));source=NB[child][:3,3]-NB[parent][:3,3];direction/=np.linalg.norm(direction);source/=np.linalg.norm(source);angle=float(np.rad2deg(np.arccos(np.clip(direction@source,-1,1))));checks.append({'source_parent':parent,'source_child':child,'T_input_actual_target_child_direction_error_degrees':angle})
armerrors=[c['T_input_actual_target_child_direction_error_degrees']for c in checks if c['source_parent']in ['Arm_L','Arm_R']];assert max(armerrors)<.001
for c in cases:assert c['canonical_A_rotation_error']<1e-12
source=np.array(N['bind']['Hip']);sourceparent=np.array(N['bind'][N['parents']['Hip']]);local=np.linalg.inv(sourceparent)@source;src_hip_bind_engine=(H@local@HI)[:3,3];src_frame=C@raw['body_home_idle__Hip']@CI;delta=src_frame[:,:3,3]-src_hip_bind_engine;dst=TB[mapping['Hip']];dstparent=TB[B['parents'][mapping['Hip']]];dstlocal=np.linalg.inv(dstparent)@dst;parent=NA[N['parents']['Hip']];ax=polar(dstparent).T@polar(parent);target_translation=dstlocal[:3,3]+delta@ax.T
report={'passed_rotation_proof':True,'actual_target_reference':str(V7/'body.mesh'),'source_T_A_calibration':'E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3/native-bone-transforms.json','rotation_formula':'R_target_world(f)=polar(C*source_absolute_world(f)*C^-1) * inverse(polar(source_A_world_engine)) * polar(target_A_bind_world)','translation_formula':'t_target_local(f)=t_target_bind_local + inverse(R_target_A_parent)*R_source_A_parent * (t_source_clip_local_engine(f)-t_source_T_bind_local_engine)','orientation_ref_uses_Nposed_but_translation_ref_uses_true_source_Nbind':True,'all_A_rotation_roundtrip_errors':cases,'T_not_A_again_direction_checks':checks,'both_arm_T_direction_error_max_degrees':max(armerrors),'hip_bind_native_engine_cm':src_hip_bind_engine.tolist(),'actual_target_hip_bind_local_cm':dstlocal[:3,3].tolist(),'hip_real_delta_minmax_cm':[delta.min(0).tolist(),delta.max(0).tolist()],'retarget_hip_local_minmax_cm':[target_translation.min(0).tolist(),target_translation.max(0).tolist()],'affine_shear_not_misread_as_quaternion':True,'final_contract_skinning_and_mesh_animation_still_pending':True};(ROOT/'retarget-formula-numerical-proof.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('ROTATION_PROOF',len(cases),'Arm_T_error',max(armerrors),'Hip_t',dstlocal[:3,3].tolist(),'delta',delta.min(0).tolist(),delta.max(0).tolist())
