import os
import copy,json,sys
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as X
from scipy.spatial.transform import Rotation
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
pdx=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));file=R/'Rigs/head_1002.mesh';d=pdx.read_meshfile(str(file));sk=d.find('object')[0].find('skeleton');names=[b.tag for b in sk];old=np.linalg.inv(inverse_bind(sk));new=old.copy();compat=json.loads((R/'HeadSources/head-core-point-compatibility.json').read_text());row=next(x for x in compat['actors']if x['actor']=='1002');changed=[]
for point in row['points']:
    tag=point['core_target'];index=names.index(tag);new[index,:3,3]=point['native_point_engine_cm'];changed.append(tag)
for side in ['l','r']:
    new[names.index('bn_h_eye_'+side+'_main'),:3,3]=new[names.index('bn_h_eye_'+side+'_rotate'),:3,3];changed.append('bn_h_eye_'+side+'_main')
for i,b in enumerate(sk):b.attrib['tx']=np.linalg.inv(new[i])[:3,:].reshape(-1,order='F').tolist()
pdx.write_meshfile(str(file),d);meta=json.loads((R/'Rigs/head_1002.json').read_text());meta['world']={b.tag:w.tolist()for b,w in zip(sk,new)};(R/'Rigs/head_1002.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
# Additive pose is stored in the original animation format: two complete local
# poses with source orientations intact, differing only in required translations.
root=X.Element('File',{'pdxasset':[1,0]});info=X.SubElement(root,'info',{'fps':[30.0],'sa':[2],'j':[len(sk)]});locals0=[];locals1=[];flags=[];deltas={}
for i,b in enumerate(sk):
    parent=b.attrib.get('pa');parent=parent[0]if parent else None;L0=np.linalg.inv(old[parent])@old[i]if parent is not None else old[i];L1=np.linalg.inv(new[parent])@new[i]if parent is not None else new[i];delta=L1[:3,3]-L0[:3,3];active=bool(np.linalg.norm(delta)>1e-6);flags.append(active);locals0.append(L0);locals1.append(L1);q=Rotation.from_matrix(L0[:3,:3]).as_quat().tolist();X.SubElement(info,b.tag,{'sa':['t'if active else''],'t':L0[:3,3].tolist(),'q':q,'s':[1.0,1.0,1.0]})
    if active:deltas[b.tag]=delta.tolist()
samples=X.SubElement(root,'samples');samples.attrib['t']=[float(x)for poses in [locals0,locals1]for L,active in zip(poses,flags)if active for x in L[:3,3]]
anim=R/'Rigs/uma_1002_head_points.anim';pdx.write_animfile(str(anim),root)
report={'actor':'1002','changed_stock_points':sorted(set(changed)),'local_translation_deltas_cm':deltas,'animation':str(anim),'attribute':'uma_head_points_1002','gene':'uma_head_points','neutral_value':0.0,'actor1002_value':1.0,'mesh_positions_changed':False,'purpose':'Source-specific bone pivots, not a face mesh identity BS','carrier_reference_actor':'1001','requires_additive_pose_on_carrier':True}
(R/'Rigs/head-points-controller.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('HEAD_1002_SOURCE_PIVOTS',len(changed),len(deltas),flush=True)
