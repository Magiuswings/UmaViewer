"""Repair each original forehead contour on one uniformly expanded BS network."""
import argparse,copy,json,shutil
from collections import defaultdict
from pathlib import Path
import numpy as np
from arap_registration import loops
from forehead_boundary import top_path,repair
from build_common_face_targets import Surface,quality,geometric_normals
from face_graph import digest

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def expand_boundary(points,faces,uv):
    p,inverse,ls=loops(points,faces);chain=max(ls,key=lambda c:np.linalg.norm(p[c]-np.roll(p[c],-1,axis=0),axis=1).sum());path,anchors=top_path(p,chain)
    selected={tuple(sorted((int(a),int(b))))for a,b in zip(path,path[1:])};vertices=points.tolist();texture=uv.tolist();newfaces=[];descriptors=[];used=set()
    for tri in faces:
        split=False
        for k in range(3):
            a,b,c=map(int,(tri[k],tri[(k+1)%3],tri[(k+2)%3]));edge=tuple(sorted((int(inverse[a]),int(inverse[b]))))
            if edge not in selected:continue
            ids=[]
            for fraction in (1/3,2/3):
                ids.append(len(vertices));vertices.append((points[a]*(1-fraction)+points[b]*fraction).tolist());texture.append((uv[a]*(1-fraction)+uv[b]*fraction).tolist());descriptors.append(dict(a=a,b=b,fraction=fraction))
            v,w=ids;newfaces.extend([(a,v,c),(v,w,c),(w,b,c)]);used.add(edge);split=True;break
        if not split:newfaces.append(tuple(map(int,tri)))
    assert used==selected and len(descriptors)==20
    return np.array(vertices),np.array(newfaces),np.array(texture),descriptors

def expand_values(p,descriptors):return np.vstack((p,np.array([p[d['a']]*(1-d['fraction'])+p[d['b']]*d['fraction']for d in descriptors])))

def polyline_error(source,output):
    distances=[]
    for a,b in zip(source,source[1:]):
        sample=a+(b-a)*np.linspace(0,1,12)[:,None];best=np.full(len(sample),np.inf)
        for x,y in zip(output,output[1:]):
            e=y-x;t=np.clip((sample-x)@e/max(e@e,1e-20),0,1);best=np.minimum(best,np.linalg.norm(sample-(x+t[:,None]*e),axis=1))
        distances.extend(best)
    return dict(max_mm=float(max(distances)*1000),rms_mm=float(np.sqrt(np.mean(np.array(distances)**2))*1000))

def top_coordinates(p,f):
    w,iv,ls=loops(p,f);chain=max(ls,key=lambda c:np.linalg.norm(w[c]-np.roll(w[c],-1,axis=0),axis=1).sum());path,anchors=top_path(w,chain);return w[path]

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    d=np.load(a.source/'face-targets.npz');oldreport=json.loads((a.source/'targets-report.json').read_text(encoding='utf8'));oldtop=json.loads((a.source/'common-topology.json').read_text(encoding='utf8'))
    template,faces,uv,desc=expand_boundary(d['template'],d['faces'],d['uv0']);assert len(template)==875 and len(faces)==1334
    groups=defaultdict(list)
    for i,point in enumerate(template):groups[tuple(np.round(point,7))].append(i)
    groups=list(groups.values());normals=geometric_normals(template,faces,groups);topology_hash=digest(dict(vertices=len(template),triangles=faces.tolist()));rows=[];targets={};boundaries={};mapsdir=a.output/'targets';mapsdir.mkdir()
    for index,row in enumerate(oldreport['per_model']):
        ident=row['id'];source=d['original_'+ident+'_p'];sf=d['original_'+ident+'_faces'];old=expand_values(d[ident],desc);q,details=repair(template,faces,old,source,sf)
        assert details['degenerate_faces']==0,(ident,details)
        source_top=top_coordinates(source,sf);output_top=top_coordinates(q,faces);before=polyline_error(source_top,top_coordinates(d[ident],d['faces']));after=polyline_error(source_top,output_top)
        assert after['max_mm']<=.51,(ident,after);targets[ident]=q
        # Preserve the previous transfer metadata and interpolate the common
        # UV/weight samples for inserted nodes. Material rebaking remains a
        # separate task, as in the original topology prototype.
        original_map=next((a.source/'targets').glob('*'+ident+'*.json'))if ident.startswith('npc_')else next((a.source/'targets').glob('uma_'+ident+'_face_*.json'))
        mapping=json.loads(original_map.read_text(encoding='utf8'));old_uv=np.array(mapping['source_uv0_on_common_vertices']);old_weights=mapping['source_bone_weights_on_common_vertices'];new_uv=expand_values(np.column_stack((old_uv,np.zeros(len(old_uv)))),desc)[:,:2];newweights=list(old_weights)
        for item in desc:
            x,y,t=item['a'],item['b'],item['fraction'];newweights.append({name:old_weights[x].get(name,0)*(1-t)+old_weights[y].get(name,0)*t for name in set(old_weights[x])|set(old_weights[y])})
        mapping.update(canonical_topology_hash=topology_hash,canonical_vertices=len(template),canonical_to_original_vertex=mapping['canonical_to_original_vertex']+[None]*len(desc),source_uv0_on_common_vertices=new_uv.tolist(),source_bone_weights_on_common_vertices=newweights,
                       forehead_repair=details,new_boundary_vertex_descriptors=desc)
        write(mapsdir/original_map.name,mapping)
        updated=dict(row);final=Surface(q,faces);error=final.nearest_many(source)[0]*1000
        updated.update(canonical_vertices=len(template),canonical_triangles=len(faces),topology_hash=topology_hash,output_geometry=quality(q,faces),sampled_source_to_retopo_rms_mm=float(np.sqrt(np.mean(error**2))),sampled_source_to_retopo_p95_mm=float(np.quantile(error,.95)),sampled_source_to_retopo_max_mm=float(error.max()),forehead_repair=details,forehead_contour_before=before,forehead_contour_after=after)
        rows.append(updated);boundaries[ident]=dict(before=before,after=after,**details)
        if(index+1)%20==0:print('FOREHEAD_REPAIRED',index+1,'/',len(oldreport['per_model']),'error_mm',after['max_mm'],flush=True)
    originals={k:d[k]for k in d.files if k.startswith('original_')};np.savez_compressed(a.output/'face-targets.npz',**targets,**originals,Basis=targets['1003'],MeanReference=np.mean(np.array(list(targets.values())),axis=0),template=template,faces=faces,uv0=uv,roles=np.zeros(len(template),np.int8))
    write(a.output/'common-topology.json',dict(oldtop,vertex_count=len(template),faces=faces.tolist(),roles=[0]*len(template),geometric_split_groups=groups,topology_hash=topology_hash,
                                            basis_position_policy='Corrected 1003 geometry for a complete upper outline; topology still derives from the optimized 1001 network',geometry_basis_identity='1003',boundary_expansion=dict(new_vertices=len(desc),new_triangles=len(faces)-len(d['faces']),descriptors=desc)))
    write(a.output/'targets-report.json',dict(oldreport,vertices=len(template),triangles=len(faces),topology_hash=topology_hash,per_model=rows,forehead_boundary_verified=True))
    write(a.output/'forehead-verification.json',dict(passed=True,models=len(rows),original_vertices=855,final_vertices=len(template),original_triangles=1314,final_triangles=len(faces),all_endpoint_zero_degenerate_faces=True,
        maximum_forehead_contour_error_mm=max(x['after']['max_mm']for x in boundaries.values()),common_vertex_network_preserved_across_all_bs=True,source_faces_unmodified=True,per_model=boundaries))
    print('ALL_FOREHEAD_CONTOURS_REPAIRED',len(rows),len(template),len(faces),flush=True)

if __name__=='__main__':main()
