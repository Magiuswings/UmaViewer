"""Actual final native motion skinning: feet height, edge stretch and morphology bind consistency."""
import sys,json
import numpy as np
from paths_v8 import ROOT,MOD,REPO,PLUGIN
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7')]
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,compose,readlocals,deform
P=parser_only(PLUGIN);base=MOD/'gfx/models/portraits/uma/0001';file=base/'uma_0001_body_base.mesh';obj=P.read_meshfile(str(file)).find('object')[0];m=obj.find('mesh');D=rigdata(obj.find('skeleton'));p=np.asarray(m.get('p')).reshape(-1,3);tri=np.asarray(m.get('tri')).reshape(-1,3);edges=np.vstack([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]);rest=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1);valid=rest>.01;footids=np.flatnonzero(p[:,1]<12);clip=MOD/'gfx/models/portraits/uma/animation/body/uma_body_native_idle.anim';count=P.read_meshfile(str(clip)).find('info').get('sa')[0];samples=[]
for f in range(count):
    world=compose(D,readlocals(P,clip,f));q=deform(m,D,world);ratio=np.linalg.norm(q[edges[:,0]]-q[edges[:,1]],axis=1)[valid]/rest[valid];samples.append(dict(frame=f,feet_min_cm=float(q[footids,1].min()),feet_p10_cm=float(np.percentile(q[footids,1],10)),feet_max_cm=float(q[footids,1].max()),edge_ratio_p99=float(np.percentile(ratio,99)),edge_ratio_max=float(ratio.max()),nonfinite=int((~np.isfinite(q)).sum()),body_bounds_cm=[q.min(0).tolist(),q.max(0).tolist()]))
targets=[]
for suffix in ['b0','b1','b3','b4','s1','s2','none']:
    ob=P.read_meshfile(str(base/f'uma_0001_body_{suffix}.mesh')).find('object')[0];rig=rigdata(ob.find('skeleton'));assert rig['names']==D['names'];assert np.array_equal(rig['inv'],D['inv']);targets.append(suffix)
passed=not any(s['nonfinite']for s in samples)and max(s['edge_ratio_p99']for s in samples)<1.4
report=dict(passed=passed,frames=count,body_BS_same_full146_inverse_bind=targets,neutral_feet_min_cm=float(p[footids,1].min()),native_feet_min_cm=min(s['feet_min_cm']for s in samples),native_feet_min_max_over_frames_cm=max(s['feet_min_cm']for s in samples),edge_ratio_p99_max=max(s['edge_ratio_p99']for s in samples),edge_ratio_peak=max(s['edge_ratio_max']for s in samples),samples=samples,CK3_engine_executed=False,feet_contact_runtime_claimed=False)
(ROOT/'Reports/body-native-motion.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('BODY_NATIVE_CHECK',passed,{k:v for k,v in report.items()if k not in ['samples']},flush=True);assert passed
