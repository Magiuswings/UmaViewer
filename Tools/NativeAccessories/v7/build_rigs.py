import os
"""Retain native auxiliary joints and correct the head's attachment reference."""
import copy,json,sys
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as ET
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));OLD=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));PLUGIN=Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))))
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
pdx=parser_only(PLUGIN);out=R/'Rigs';out.mkdir(parents=True,exist_ok=True);S=np.array([[1,0,0],[0,0,1],[0,1,0]])
def tx(world):
    b=np.linalg.inv(world);return b[:3,:].reshape(-1,order='F').tolist()
def append(sk,name,parent,world):
    names=[b.tag for b in sk];assert name not in names;attrs={'ix':[len(sk)],'tx':tx(world)}
    if parent is not None:attrs['pa']=[names.index(parent)]
    ET.SubElement(sk,name,attrs);return name
def save(label,sk):
    template=pdx.read_meshfile(str(OLD/'UMA-V6-1001/gfx/models/portraits/uma/0001/uma_0001_head_empty.mesh'));obj=template.find('object')[0];old=obj.find('skeleton');obj.remove(old);obj.append(copy.deepcopy(sk));pdx.write_meshfile(str(out/(label+'.mesh')),template)
    world=np.linalg.inv(inverse_bind(sk));result={'names':[b.tag for b in sk],'parents':{b.tag:sk[b.attrib['pa'][0]].tag if b.attrib.get('pa')else None for b in sk},'world':{b.tag:w.tolist()for b,w in zip(sk,world)},'bones':len(sk)};(out/(label+'.json')).write_text(json.dumps(result,indent=2),encoding='utf8');return result
bodyfile=OLD/'UMA-V6-1001/gfx/models/portraits/uma/0001/uma_0001_body_base.mesh';body=pdx.read_meshfile(str(bodyfile)).find('object')[0].find('skeleton');bsk=copy.deepcopy(body)
N=json.loads(Path(str(Path(os.environ.get('UMA_V7_CANONICAL','E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3')) / 'native-bone-transforms.json')).read_text());semantic={'Position':'ground_joint','Hip':'body_root','Waist':'bn_sp_lumbar','Spine':'bn_sp_thoracic','Neck':'bn_sp_cervical'}
for side in ['L','R']:
    s=side.lower()
    for old,new in [('Shoulder','clavicle'),('Arm','shoulder'),('Elbow','elbow'),('ArmRoll','forearm'),('Wrist','wrist'),('ShoulderRoll','deltoid'),('Hand_Attach','prop'),('Thigh','hip'),('Knee','knee'),('Ankle','ankle'),('Toe','ftBall')]:semantic[old+'_'+side]='bn_'+s+'_'+new
    for old,new in [('Thumb','thumb'),('Index','index'),('Middle','mid'),('Ring','ring'),('Pinky','pinky')]:
        for i in range(1,4):semantic[f'{old}_{i:02}_{side}']=f'bn_{s}_fi_{new}{i}'
mapping={};pending=list(N['names'])
while pending:
    progress=False
    for name in pending[:]:
        parent=N['parents'][name]
        if parent and parent not in mapping:continue
        if name in semantic:mapping[name]=semantic[name]
        else:
            w=np.array(N['posed'][name]);eng=np.eye(4);eng[:3,:3]=S@w[:3,:3]@S;eng[:3,3]=S@w[:3,3]*100.;label='uma_src_'+('body_origin'if name.startswith('pfb_')else name);mapping[name]=append(bsk,label,mapping.get(parent,'ground_joint'),eng)
        pending.remove(name);progress=True
    assert progress
bodyreport=save('body',bsk);(out/'body-source-map.json').write_text(json.dumps(mapping,indent=2),encoding='utf8')
headold=pdx.read_meshfile(str(OLD/'UMA-V6-1001/gfx/models/portraits/uma/0001/uma_0001_head_empty.mesh')).find('object')[0].find('skeleton');hworld=np.linalg.inv(inverse_bind(headold));bnames=[b.tag for b in body];bw=np.linalg.inv(inverse_bind(body));thor=bw[bnames.index('bn_sp_thoracic')];cerv=bw[bnames.index('bn_sp_cervical')];hnames=[b.tag for b in headold];neck=hworld[hnames.index('bn_h_neck_1')];d=(np.linalg.inv(thor)@np.r_[cerv[:3,3],1])[:3]-neck[:3,3]
index=json.loads((R/'HeadSources/head-parts-index.json').read_text());reports=[]
for actor in ['1001','1002']:
    record=next(row for row in index['records']if row['kind']=='head'and row['character_id']==actor and row['variant']=='80');raw=json.loads(Path(record['parsed_json']).read_text());sk=copy.deepcopy(headold);root=sk[0];newroot=np.eye(4);newroot[:3,3]=-d;root.attrib['tx']=tx(newroot);helper=append(sk,'uma_head_base','head_root',np.eye(4));helperidx=len(sk)-1
    for bone in list(sk)[:-1]:
        if bone.attrib.get('pa')==[0]:bone.attrib['pa']=[helperidx]
    byid={b['id']:b for b in raw['bones']};byname={b['name']:b for b in raw['bones']};H=np.array(byname['Head']['matrix']).reshape(4,4)[:3,3];C=np.diag([-97.6403989,97.6403989,-97.6403989]);anchor=hworld[hnames.index('bn_h_head'),:3,3]
    sem={'Neck':'bn_h_neck_1','Head':'bn_h_head','Mouth_Root':'bn_h_face_lower','Chin':'bn_h_jaw_low','Nose':'bn_h_nose_main','Mouth_up_01_C':'bn_h_mouth_upperLip','Mouth_bottom_01_C':'bn_h_mouth_lowerLip'}
    for side in ['L','R']:
        s=side.lower()
        for old,new in [('Cheek',f'bn_h_cheek_{s}_main'),('Eye_locator',f'bn_h_eye_{s}_main'),('Eye',f'bn_h_eye_{s}_rotate'),('Eye_up_02',f'bn_h_eye_{s}_lidUpper'),('Eye_bottom_02',f'bn_h_eye_{s}_lidLower'),('Eyebrow_01',f'bn_h_forehead_{s}_browInner'),('Eyebrow_02',f'bn_h_forehead_{s}_browOuter'),('Mouth_middle',f'bn_h_mouth_{s}_corner'),('Mouth_up_02',f'bn_h_mouth_{s}_upperLip'),('Mouth_bottom_02',f'bn_h_mouth_{s}_lowerLip'),('Ear_01',f'bn_h_ear_{s}_main'),('Shoulder',f'bn_h_{s}_clavicle')]:sem[old+'_'+side]=new
    smap={};pending=list(raw['bones'])
    while pending:
        progress=False
        for b in pending[:]:
            parent=b.get('parent')
            if parent and parent not in smap:continue
            name=b['name']
            if parent is None:smap[b['id']]='uma_head_base'
            elif name in sem:smap[b['id']]=sem[name]
            else:
                w=np.array(b['matrix']).reshape(4,4);eng=np.eye(4);eng[:3,:3]=C@w[:3,:3]@np.linalg.inv(C);eng[:3,3]=C@(w[:3,3]-H)+anchor;label='uma_src_'+name
                if label in [n.tag for n in sk]:label+='_'+str(len(sk))
                smap[b['id']]=append(sk,label,smap[parent],eng)
            pending.remove(b);progress=True
        assert progress
    hr=save('head_'+actor,sk);(out/('head_'+actor+'-source-map.json')).write_text(json.dumps(smap,indent=2),encoding='utf8');reports.append({'actor':actor,'bones':len(sk),'source_bones':len(raw['bones']),'source_bones_dropped':0,'core_binds_preserved_except_attachment_root':True})
contract={'body_bones':len(bsk),'body_original_stock_indices_preserved':134,'body_source_bones':len(N['names']),'body_source_bones_dropped':0,'heads':reports,'head_root_offset_cm':(-d).tolist(),'head_static_compensation_cm':d.tolist(),'helper':'uma_head_base','face_mesh_coordinates_changed':False,'head_source_to_engine':C.tolist(),'head_anchor':anchor.tolist(),'body_rig':str(out/'body.mesh'),'neck_alignment_error_cm':float(np.linalg.norm((thor@np.r_[d+neck[:3,3],1])[:3]-cerv[:3,3]))}
(R/'rig-contract.json').write_text(json.dumps(contract,indent=2),encoding='utf8');print('NEW_RIG_CONTRACT',json.dumps(contract),flush=True)
