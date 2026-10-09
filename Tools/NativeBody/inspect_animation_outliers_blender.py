"""Locate strain outliers by absolute edge length and skin weights."""
import argparse,json,sys
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser()
for name in ('repo','plugin','root','stock'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));sys.path.insert(0,str(Path(__file__).parent))
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import mesh_info
from verify_canonical_rest_blender import clip_world,skin
pdx=parser_only(a.plugin);stock=pdx.read_meshfile(str(a.stock));sk=stock.find('object')[0].find('skeleton');names=[n.tag for n in sk]
data=pdx.read_meshfile(str(a.root/'meshes/uma_0001_body_base.mesh'));_,parts,bind=mesh_info(data);points,ix,w,_=parts[0];tri=np.array(data.find('object')[0].find('mesh').attrib['tri']).reshape(-1,3)
edges=np.unique(np.sort(np.concatenate((tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]])),axis=1),axis=0);length=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1);keep=length>.05;edges=edges[keep];length=length[keep];reports=[]
for clip in ('female_body_praying_standing.anim','female_body_idle_1.anim'):
    anim=pdx.read_meshfile(str(a.stock.parent/clip));world=clip_world(anim,sk);worst=[]
    for start in range(0,len(world),32):
        output=skin(points,ix,w,(world@bind)[start:start+32]);actual=np.linalg.norm(output[:,edges[:,0]]-output[:,edges[:,1]],axis=2);ratio=actual/length[None]
        for fi,ei in zip(*np.where(ratio>4)):
            ids=edges[ei];worst.append(dict(frame=int(start+fi),ratio=float(ratio[fi,ei]),rest_length_cm=float(length[ei]),posed_length_cm=float(actual[fi,ei]),source_positions_cm=points[ids].tolist(),weights=[[(names[ix[v,s]],float(w[v,s]))for s in range(4)if w[v,s]>.0001]for v in ids]))
    reports.append(dict(clip=clip,edges_exceeding_4x=len(worst),worst=sorted(worst,key=lambda x:x['ratio'],reverse=True)[:12]))
(a.root/'animation-outliers.json').write_text(json.dumps(reports,indent=2),encoding='utf8');print(json.dumps(reports,indent=2))
