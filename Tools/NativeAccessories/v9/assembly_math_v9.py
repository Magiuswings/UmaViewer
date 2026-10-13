"""Explicit single root attachment emulation using final files; no implicit rig fallback proof."""
import sys,json
import numpy as np
from pathlib import Path
from paths_v9 import ROOT,MOD,REPO,PLUGIN,V8
V7=V8
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7')]
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,compose,shared_pose,deform,readlocals
P=parser_only(PLUGIN);BASE=MOD/'gfx/models/portraits/uma/0001'
def data(path):
    o=P.read_meshfile(str(path)).find('object')[0];return o,rigdata(o.find('skeleton'))
def head_attachment(B,BW,H,HW):
    external=BW[B['names'].index('bn_sp_thoracic')]@np.linalg.inv(HW[H['names'].index('head_root')]);HW=HW.copy()
    return external,HW
def external(p,x):return p@x[:3,:3].T+x[:3,3]
def main(rest_only=False):
    bridgefile=ROOT/'Reports/neck-delivery-source.json';registry=json.loads((ROOT/'Reports/head-registration.json').read_text());bridges=json.loads((bridgefile if bridgefile.exists()else V7/'HeadSources/NeckBridge/neck-delivery.json').read_text());bo,B=data(BASE/'uma_0001_body_base.mesh');ho,H=data(BASE/'uma_0001_head_female.mesh');records=[]
    bc=MOD/'gfx/models/portraits/uma/animation/body/uma_body_native_idle.anim';hc=MOD/'gfx/models/portraits/uma/animation/head/uma_head_native_idle.anim'
    frames=[None]if rest_only else range(P.read_meshfile(str(bc)).find('info').get('sa')[0])
    for actor in ['1001','1002']:
        for variant in ['00','80']:
            rows=[r for r in registry if r['actor']==actor and r.get('shared_pose')=='head'and(r['variant']==variant or r['element']=='head')];parts=[(r,*data(Path(r['mesh'])))for r in rows];ring=next(r for r in bridges['actors']if r['row']['actor']==actor);maxlower=maxupper=maxroot=maxneck=0.;fdata=[]
            for frame in frames:
                BW=compose(B,readlocals(P,bc,frame))if frame is not None else B['bind'];HW=compose(H,readlocals(P,hc,frame))if frame is not None else H['bind'];x,HW=head_attachment(B,BW,H,HW);body=deform(bo.find('mesh'),B,BW);skin={}
                for r,o,D in parts:skin[r['element']]=np.vstack([external(deform(m,D,shared_pose(D,H,HW)),x)for m in o.findall('mesh')])
                bridge=skin['head'][-16:];lower=float(np.linalg.norm(bridge[:6]-body[ring['lower_ring_body_vertex_ids']],axis=1).max());uppermesh=skin['head'][:-16];upper=float(max(np.linalg.norm(uppermesh-v,axis=1).min()for v in bridge[6:]));root=float(np.linalg.norm(external(HW[H['names'].index('head_root'),:3,3][None],x)[0]-BW[B['names'].index('bn_sp_thoracic'),:3,3]));neckname=('uma_1002_'if actor=='1002'else'')+'bn_h_neck_1';neck=float(np.linalg.norm(external(HW[H['names'].index(neckname),:3,3][None],x)[0]-BW[B['names'].index('bn_sp_cervical'),:3,3]));maxlower=max(maxlower,lower);maxupper=max(maxupper,upper);maxroot=max(maxroot,root);maxneck=max(maxneck,neck);fdata.append(dict(frame=frame,lower_cm=lower,upper_cm=upper,root_joint_cm=root,neck_joint_cm=neck))
            rec=dict(actor=actor,variant=variant,frames=len(fdata),lower_ring_max_error_cm=maxlower,upper_ring_max_error_cm=maxupper,root_joint_max_error_cm=maxroot,neck_joint_max_error_cm=maxneck,samples=fdata);records.append(rec);print('ASSEMBLY_ATTACHMENT',actor,variant,maxlower,maxupper,maxroot,maxneck,flush=True)
    passed=all(r['lower_ring_max_error_cm']<.005 and r['upper_ring_max_error_cm']<.005 and r['root_joint_max_error_cm']<.001 and r['neck_joint_max_error_cm']<.02 for r in records)
    dest=ROOT/'Reports'/('rest-attachment-validation.json'if rest_only else'native-attachment-validation.json');dest.write_text(json.dumps(dict(passed=passed,cases=records,single_root_attachment_only=True,game_engine_executed=False,bridge_root_binding='Unified245 bind space with three dedicated body-follow seam helpers; no clavicle override or independent neck entity.'),indent=2),encoding='utf8');assert passed,'head/neck attachment failed; see '+str(dest)
if __name__=='__main__':main('--rest-only'in sys.argv)
