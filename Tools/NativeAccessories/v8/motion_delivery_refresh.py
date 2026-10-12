"""Attach final numeric foot-plant evidence without rewriting animation bytes."""
import json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');O=R/'MotionSources'
d=json.loads((O/'native-animation-delivery.json').read_text())
for module,count in [('body',146),('head',242),('ear',169),('tail',9)]:
    row=next(x for x in d['modules']if x['module']==module)
    assert row['j']==count
    assert hashlib.sha256(Path(row['file']).read_bytes()).hexdigest()==row['file_sha256']
body=next(x for x in d['modules']if x['module']=='body')
source=json.loads(Path(body['source_provenance'][0]['source_bind_snapshot']).read_text())
byid={b['id']:b['name']for b in source['bones']}
parents={b['name']:byid.get(b['parent'])for b in source['bones']}
raw=np.load(O/'native-source-local-frames.npz');world={}
def one(n):
    if n not in world:
        m=raw['body_home_idle__'+n];p=parents[n]
        world[n]=one(p)@m if p else m
    return world[n]
def polar(a):
    u,s,v=np.linalg.svd(a[:,:3,:3]);return u@v
actual=np.load(O/'body-final-pose-evidence.npz')['world']
rig=json.loads((R/'Rigs/body.json').read_text());C=np.diag([-1.,1.,-1.]);checks=[]
for rec in body['foot_rest_reference_corrections']:
    n=rec['source'];t=rec['target'];src=C@polar(one(n))@C
    dst=polar(actual[:,rig['index_by_name'][t]])
    source_delta=src@src[0].T;actual_delta=dst@dst[0].T
    error=float(np.rad2deg(Rotation.from_matrix(actual_delta@np.transpose(source_delta,(0,2,1))).magnitude()).max())
    assert error<.001,(n,error)
    checks.append({'source':n,'target':t,'all_frames_source_variation_error_degrees':error,'real_variation_max_degrees':float(np.rad2deg(Rotation.from_matrix(source_delta).magnitude()).max())})
foot=json.loads((O/'flatfoot-heel-forefoot-allframes.json').read_text())
foot['source_foot_world_rotation_variation_allframes_checks']=checks
(O/'flatfoot-heel-forefoot-allframes.json').write_text(json.dumps(foot,indent=2)+'\n',encoding='utf8')
d['allframes_flatfoot_heel_forefoot_contact_report']=str(O/'flatfoot-heel-forefoot-allframes.json')
d['final_flatfoot_body_head_clips_ready_for_SDK_render']=True
d['final_clip_bytes_not_changed_by_report_refresh']=True
(O/'native-animation-delivery.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('SOURCE_FOOT_VARIATION_PRESERVED',[(x['source'],x['all_frames_source_variation_error_degrees'])for x in checks])
print('FINAL_FILES',[(x['module'],x['j'],x['frames'],x['file_sha256'])for x in d['modules']])
