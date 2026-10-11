import os
import json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));OUT=ROOT/'motion-parts'
delivery=json.loads((OUT/'motion-delivery.json').read_text());source=np.load(ROOT/'native-motion-frames.npz');C=np.diag([-97.6403989,97.6403989,-97.6403989,1.]);CI=np.linalg.inv(C)
for part in delivery['parts']:
    d=json.loads((OUT/f'{part["kind"]}-rig-prepared.json').read_text());sw=np.array(d['source_world']);bw=np.array(d['world_bind']);parents=d['parents'];K=np.array(part['accessory_convert_matrix'])@CI;v=np.array(d['geometry']);ix=np.array(d['skinix']);w=np.array(d['skinw'])
    for rec in part['animations']:
        world=[]
        for i,n in enumerate(d['bones']):
            pa=parents[i];sl=np.linalg.inv(sw[pa])@sw[i]if pa is not None else sw[i];key=rec['source_key']+'__'+n;local=source[key][[0,-1]]if key in source else np.tile(sl,(2,1,1));converted=C@local@CI
            if pa is None:converted=K@converted
            world.append(world[pa]@converted if pa is not None else converted)
        mats=np.stack(world,axis=1)@np.linalg.inv(bw)[None];posed=np.zeros((2,len(v),3))
        for j in range(4):
            good=ix[:,j]>=0;M=mats[:,ix[good,j]];posed[:,good]+=w[good,j][None,:,None]*(np.einsum('fvij,vj->fvi',M[:,:,:3,:3],v[good])+M[:,:,:3,3])
        seam=float(np.linalg.norm(posed[1]-posed[0],axis=1).max());rec['loop_endpoint_vertex_difference_cm']=seam
        print('NATIVE_SEAM',part['kind'],rec['state'],seam)
    part['textures_authored_by_root']=True
delivery['ear_material_source_regions']='ear-material-source-regions.json';delivery['ear_uv_evidence']='ear-source-uv-components.png'
delivery['acceptance_scope']='Unity source exact transform conversion; PDX binary parse; original IO PDX Mesh import/export; Blender deformed first/peak/end frame comparison. CK3 in-game dispatch not run.'
delivery['files']=[{'path':str(p.relative_to(OUT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(OUT.rglob('*'))if p.is_file()and p.suffix in ['.mesh','.anim','.png','.json']and p.name!='motion-delivery.json']
(OUT/'motion-delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
