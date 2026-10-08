"""Calibrate skin normals to the native idle pose without moving any mesh vertex.

Retargeted joints can change the effective geometry through weight gradients.
The usual weighted normal rotation does not include these translation gradients.
This creates a lighting boundary even when the diffuse is uniform. Reconstruct
the smooth geometric normals in the native neutral pose, then solve the inverse
normal transform. Bone data, positions, topology, UVs and weights stay unchanged.
"""
import argparse,copy,json,re,sys
from collections import defaultdict
from pathlib import Path
import numpy as np

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['repo','plugin','game','source','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));sys.path.insert(0,str(Path(__file__).parent));import build_ck3_mod as b
    from test_vanilla_body_animation_blender import inverse_bind,globals_for
    pdx=b.parser_only(a.plugin);stock=a.game/'gfx/models/portraits/female_body';sk=pdx.read_meshfile(str(stock/'female_body.mesh')).find('object')[0].find('skeleton');anim=pdx.read_meshfile(str(stock/'female_body_idle_1.anim'));world=globals_for(anim.find('info'),anim.find('samples'),0,sk)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True);rows=[]
    for file in sorted(a.source.glob('*body_*.mesh')):
        data=pdx.read_meshfile(str(file));original=copy.deepcopy(data);obj=data.find('object')[0];bind=inverse_bind(obj.find('skeleton'));mat=world@bind
        for mesh in obj.findall('mesh'):
            points=np.asarray(mesh.attrib['p']).reshape(-1,3);old=np.asarray(mesh.attrib['n']).reshape(-1,3);tri=np.asarray(mesh.attrib['tri']).reshape(-1,3);skin=mesh.find('skin');ix=np.asarray(skin.attrib['ix']).reshape(-1,4);w=np.asarray(skin.attrib['w']).reshape(-1,4);posed=np.zeros_like(points);normalmat=np.zeros((len(points),3,3))
            for slot in range(4):
                ids=np.maximum(ix[:,slot],0);posed+=np.einsum('nij,nj->ni',mat[ids],np.column_stack((points,np.ones(len(points)))))[:,:3]*w[:,slot,None];normalmat+=mat[ids,:3,:3]*w[:,slot,None,None]
            oldposed=np.einsum('nij,nj->ni',normalmat,old);oldposed/=np.linalg.norm(oldposed,axis=1)[:,None];area=np.cross(posed[tri[:,1]]-posed[tri[:,0]],posed[tri[:,2]]-posed[tri[:,0]]);geo=np.zeros_like(points)
            for slot in range(3):np.add.at(geo,tri[:,slot],area)
            if np.mean(np.sum(geo*oldposed,axis=1))<0:geo*=-1
            groups=defaultdict(list)
            for i,v in enumerate(points):groups[tuple(np.round(v,4))].append(i)
            welded=0
            for ids in groups.values():
                if len(ids)>1 and np.min(oldposed[ids]@oldposed[ids].T)>.5:
                    geo[ids]=np.sum(geo[ids],axis=0);welded+=1
            geo/=np.maximum(np.linalg.norm(geo,axis=1)[:,None],1e-12);new=np.linalg.solve(normalmat,geo[...,None])[...,0];new/=np.maximum(np.linalg.norm(new,axis=1)[:,None],1e-12)
            # Protect tiny folded/internal surfaces with contradictory normals.
            valid=(np.sum(geo*oldposed,axis=1)>0)&(np.linalg.norm(geo,axis=1)>.5);new[~valid]=old[~valid]
            mesh.attrib['n']=new.astype(np.float32).reshape(-1).tolist()
            if mesh.attrib.get('ta'):
                tang=np.asarray(mesh.attrib['ta']).reshape(-1,4);t=tang[:,:3]-new*np.sum(tang[:,:3]*new,axis=1)[:,None];t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-12);tang[:,:3]=t;mesh.attrib['ta']=tang.astype(np.float32).reshape(-1).tolist()
            restored=np.einsum('nij,nj->ni',normalmat,new);restored/=np.linalg.norm(restored,axis=1)[:,None];oldangle=np.degrees(np.arccos(np.clip(np.sum(oldposed*geo,axis=1),-1,1)));newangle=np.degrees(np.arccos(np.clip(np.sum(restored*geo,axis=1),-1,1)));leg=(points[:,1]>55)&(points[:,1]<90)&(np.abs(points[:,0])>4)&(np.abs(points[:,0])<20)
            rows.append(dict(file=file.name,vertices=len(points),positions_unchanged=True,weights_uv_topology_bones_unchanged=True,smooth_coincident_groups=welded,leg_normal_error_before_p99_deg=float(np.quantile(oldangle[leg],.99)),leg_normal_error_after_p99_deg=float(np.quantile(newangle[leg],.99)),protected_vertices=int(np.count_nonzero(~valid))))
        name=re.sub(r'^1001_body_','uma_0001_body_',file.name);target=a.output/name;pdx.write_meshfile(str(target),data);reread=pdx.read_meshfile(str(target));assert [(n.tag,n.attrib)for n in reread.find('object')[0].find('skeleton')]==[(n.tag,n.attrib)for n in original.find('object')[0].find('skeleton')]
        for old,new in zip(original.find('object')[0].findall('mesh'),reread.find('object')[0].findall('mesh')):
            for key in old.attrib:
                if key not in ['n','ta']:assert old.attrib[key]==new.attrib[key],key
            assert old.find('skin').attrib==new.find('skin').attrib
    (a.output/'normal-correction.json').write_text(json.dumps(dict(passed=True,policy='Native neutral-pose geometric normals inverted through the existing skin matrices; no mesh displacement',records=rows,ck3_runtime_verified=False),ensure_ascii=False,indent=2),encoding='utf8');print('POSED_SKIN_NORMALS_CORRECTED',[(r['file'],round(r['leg_normal_error_before_p99_deg'],3),round(r['leg_normal_error_after_p99_deg'],3))for r in rows],flush=True)

if __name__=='__main__':main()
