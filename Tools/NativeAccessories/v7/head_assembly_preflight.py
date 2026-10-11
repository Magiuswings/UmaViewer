import os
import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,compose,readlocals
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));MOD=ROOT/'UMA-V7';BASE=MOD/'gfx/models/portraits/uma/0001';OUT=ROOT/'HeadSources/AssemblyQA';OUT.mkdir(exist_ok=True);P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))))
def readrig(p):return rigdata(P.read_meshfile(str(p)).find('object')[0].find('skeleton'))
body=readrig(BASE/'uma_0001_body_base.mesh');addfile=ROOT/'Rigs/uma_1002_head_points.anim';a0=readlocals(P,addfile,0);a1=readlocals(P,addfile,1);delta={n:(a1[n][:3,3]-m[:3,3])for n,m in a0.items()if np.abs(a1[n][:3,3]-m[:3,3]).max()>1e-8};results=[]
for sex in ['female','male']:
    carrier=readrig(BASE/f'uma_0001_head_{sex}.mesh')
    for actor in ['1001','1002']:
        expect=readrig(ROOT/f'Rigs/head_{actor}.mesh');cw=compose(carrier,delta=delta if actor=='1002'else{});differences={}
        for n in delta:
            if n in expect['names']:differences[n]=float(np.linalg.norm(cw[carrier['names'].index(n),:3,3]-expect['bind'][expect['names'].index(n),:3,3]))
        bw=body['bind'];headroot=cw[carrier['names'].index('head_root')];parent=bw[body['names'].index('bn_sp_thoracic')];attach=parent@np.linalg.inv(headroot);neck=(attach@cw[carrier['names'].index('bn_h_neck_1')])[:3,3];target=bw[body['names'].index('bn_sp_cervical'),:3,3];poses=[]
        for label,bpath,hpath in [('idle',Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body/female_body_idle_1.anim')),MOD/'gfx/models/portraits/uma/animation/uma_female_head_idle_1.anim'),('court',Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body/female_body_throneRoom_ruler3_1.anim')),MOD/'gfx/models/portraits/uma/animation/uma_female_head_throneRoom_ruler3_1.anim')]:
            bc=P.read_meshfile(str(bpath)).find('info').get('sa')[0];hc=P.read_meshfile(str(hpath)).find('info').get('sa')[0]
            for fraction in [0,.5,1]:
                bf=round((bc-1)*fraction);hf=round((hc-1)*fraction);bw=compose(body,readlocals(P,bpath,bf));cw=compose(carrier,readlocals(P,hpath,hf),delta if actor=='1002'else{});attach=bw[body['names'].index('bn_sp_thoracic')]@np.linalg.inv(cw[carrier['names'].index('head_root')]);neck=(attach@cw[carrier['names'].index('bn_h_neck_1')])[:3,3];target=bw[body['names'].index('bn_sp_cervical'),:3,3];poses.append({'context':label,'fraction':fraction,'body_frame':bf,'head_frame':hf,'neck_joint_error_cm':float(np.linalg.norm(neck-target)),'head_neck_world':neck.tolist(),'body_cervical_world':target.tolist()})
        rec={'actor':actor,'carrier_sex':sex,'carrier_bones':len(carrier['names']),'body_bones':len(body['names']),'additive_translation_bones':len(delta),'rest_target_bind_core_point_errors_cm':differences,'maximum_rest_bind_point_error_cm':max(differences.values(),default=0),'rest_neck_error_cm':float(np.linalg.norm((parent@np.linalg.inv(headroot)@compose(carrier,delta=delta if actor=='1002'else{})[carrier['names'].index('bn_h_neck_1')])[:3,3]-body['bind'][body['names'].index('bn_sp_cervical'),:3,3])),'animated_neck':poses};results.append(rec)
out={'additive_file':str(addfile),'actual_translation_delta_by_bone_cm':{n:v.tolist()for n,v in delta.items()},'cases':results,'connection_rule':'headObjectWorld=bodyThoracicCurrentWorld * inverse(head_root current localWorld); static uma_head_base bind-local offset inherits once.'};(OUT/'assembly-preflight.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps({'delta_count':len(delta),'cases':[{'actor':r['actor'],'sex':r['carrier_sex'],'point_error':r['maximum_rest_bind_point_error_cm'],'rest_neck':r['rest_neck_error_cm'],'animated_neck':[(p['context'],p['fraction'],round(p['neck_joint_error_cm'],5))for p in r['animated_neck']]}for r in results]},indent=2))
