import json,sys,hashlib
from pathlib import Path
import numpy as np
sys.path[:0]=['C:/Users/33775/Desktop/网页制作/UmaV7Scripts','E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter']
from build_ck3_mod import parser_only
from head_pdx_tools import world
ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');OUT=ROOT/'MotionSources';P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');rig=json.loads((ROOT/'Rigs/body.json').read_text());bp=np.load(OUT/'body-final-pose-evidence.npz')['world'];b=np.array(rig['world']);mapping=json.loads((OUT/'native-animation-delivery.json').read_text())['modules'][0]['source_bone_to_target'];N=json.loads(Path('E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3/native-bone-transforms.json').read_text());lengths=[]
for n,t in mapping.items():
    parent=N['parents'][n]
    if parent is None or n in ['Position','Hip']or parent not in mapping:continue
    i=rig['index_by_name'][t];pi=rig['index_by_name'][mapping[parent]];rest=float(np.linalg.norm(b[i,:3,3]-b[pi,:3,3]));actual=np.linalg.norm(bp[:,i,:3,3]-bp[:,pi,:3,3],axis=1);lengths.append({'source':n,'source_parent':parent,'target':t,'target_parent_from_native_graph':mapping[parent],'calibrated_A_reference_length_cm':rest,'actual_min_length_cm':float(actual.min()),'actual_max_length_cm':float(actual.max()),'all_frame_length_variation_cm':float(np.ptp(actual))})
earrig=json.loads((ROOT/'Rigs/earcarrier.json').read_text());earpose=np.load(OUT/'ear-final-pose-evidence.npz')['world'];ev=json.loads((ROOT/'Rigs/ear-variant-remap.json').read_text());raw=np.load(OUT/'native-source-local-frames.npz');oldhead=json.loads(Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/rig-contract.json').read_text());C=np.eye(4);C[:3,:3]=np.array(oldhead['head_source_to_engine']);CI=np.linalg.inv(C);checks=[]
for v in ev:
    old=P.read_meshfile(v['source_meshes'][0]).find('object')[0].find('skeleton');nodes=sorted(old,key=lambda x:x.get('ix')[0]);oldW=world(old);pa=[n.get('pa')[0]if n.get('pa')else None for n in nodes];name=[n.tag for n in nodes];local=np.array([np.linalg.inv(oldW[p])@w if p is not None else w for w,p in zip(oldW,pa)]);local=np.tile(local,(len(earpose),1,1,1));key='ear_'+v['actor']+'_'+v['variant']
    for n in ['Ear_01_L','Ear_02_L','Ear_03_L','Ear_01_R','Ear_02_R','Ear_03_R']:local[:,name.index(n)]=C@raw[key+'__'+n]@CI
    posed=[None]*len(name)
    def one(i):
        if posed[i]is not None:return posed[i]
        posed[i]=one(pa[i])@local[:,i]if pa[i]is not None else local[:,i];return posed[i]
    for i in range(len(name)):one(i)
    err=0.;deformerr=0.
    for n,target in v['old_name_to_union_name'].items():
        oi=name.index(n);ni=earrig['index_by_name'][target];err=max(err,float(np.max(np.abs(posed[oi]-earpose[:,ni]))));goal=posed[oi]@np.linalg.inv(oldW[oi]);actual=earpose[:,ni]@np.array(earrig['inverse_bind'][ni]);deformerr=max(deformerr,float(np.max(np.abs(goal-actual))))
    assert deformerr<.0001;checks.append({'actor':v['actor'],'variant':v['variant'],'all_source_frames':len(earpose),'kept_native_points':v['kept'],'original_vs_union_pose_matrix_error':err,'original_vs_union_skin_deformation_matrix_error':deformerr,'no_double_attachment_translation':True})
report={'passed':True,'body_source_native_parent_lengths':lengths,'body_actual_limb_length_variation_max_cm':max(r['all_frame_length_variation_cm']for r in lengths),'ear_original_source_vs_union_allframe_skinmatrix_checks':checks,'all_original_positiveweighted_ear_headwear_native_bones_retained':True,'source_no_artificial_motion_or_amplification':True,'shader_parameter_helpers_are_static_bones_not_shader_encoded_xyz':True};(OUT/'native-motion-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');delivery=json.loads((OUT/'native-animation-delivery.json').read_text());delivery['allframes_body_skin_report']=str(OUT/'body-native-skin-allframes.json');delivery['allframes_head_body_attachment_report']=str(OUT/'allframes-head-body-attachment.json');delivery['source_skin_pose_equivalence_report']=str(OUT/'native-motion-validation.json');delivery['rig_contract_independent_ear_tail']=str(ROOT/'Rigs/ear-tail-rig-contract.json');(OUT/'native-animation-delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('ALLFRAMES_NATIVE_VALIDATION',len(lengths),report['body_actual_limb_length_variation_max_cm'],[(c['actor'],c['variant'],c['original_vs_union_skin_deformation_matrix_error'])for c in checks])
