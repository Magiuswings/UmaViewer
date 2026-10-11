import os
import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))));ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));OUT=ROOT/'HeadSources';contract=json.loads((ROOT/'rig-contract.json').read_text());C=np.array(contract['head_source_to_engine']);anchor=np.array(contract['head_anchor']);result=[]
mapping={'Head':'bn_h_head','Neck':'bn_h_neck_1'}
for side in ['L','R']:
    s=side.lower();mapping|={f'Eye_{side}':f'bn_h_eye_{s}_rotate',f'Eye_up_02_{side}':f'bn_h_eye_{s}_lidUpper',f'Eye_bottom_02_{side}':f'bn_h_eye_{s}_lidLower',f'Eyebrow_01_{side}':f'bn_h_forehead_{s}_browInner',f'Eyebrow_02_{side}':f'bn_h_forehead_{s}_browOuter'}
for char in ['1001','1002']:
    sk=P.read_meshfile(str(ROOT/f'Rigs/head_{char}.mesh')).find('object')[0].find('skeleton');world={}
    for b in sk:
        inv=np.eye(4);inv[:3]=np.array(b.get('tx')).reshape(4,3).T;world[b.tag]=np.linalg.inv(inv)
    source=json.loads((OUT/f'parsed/chr{char}_80/head.json').read_text());bones={b['name']:np.array(b['matrix']).reshape(4,4)for b in source['bones']};H=bones['Head'][:3,3];rows=[]
    for old,new in mapping.items():
        p=C@(bones[old][:3,3]-H)+anchor;cp=world[new][:3,3];rows.append({'source':old,'core_target':new,'native_point_engine_cm':p.tolist(),'core_bind_point_cm':cp.tolist(),'native_minus_core_cm':(p-cp).tolist(),'distance_cm':float(np.linalg.norm(p-cp))})
    result.append({'actor':char,'source_head_origin':H.tolist(),'points':rows,'maximum_eye_pivot_difference_cm':max(r['distance_cm']for r in rows if r['source'].startswith('Eye_')),'maximum_brow_difference_cm':max(r['distance_cm']for r in rows if r['source'].startswith('Eyebrow_'))})
(OUT/'head-core-point-compatibility.json').write_text(json.dumps({'actors':result,'recommendation':'Keep common 61 named animation interface but use actor-specific rotating-eye pivot helper if mapped stock eye rotation point differs materially. Match source eye centroid/pivot to native point, not by scaling eyeball around 1001 core point. Static bind preservation alone does not prove rotating-eye quality.'},indent=2)+'\n',encoding='utf8')
print(json.dumps(result,indent=2))
