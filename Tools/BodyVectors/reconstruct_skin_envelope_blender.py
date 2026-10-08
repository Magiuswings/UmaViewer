"""Refine a common 0004 envelope and restore inward skin with fixed affine correspondences."""
import copy
from collections import Counter,defaultdict
import heapq
import json
from pathlib import Path
import sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

FIELDS=('height','shape','bust')
BASE=(1,0,2)
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def profile(record):return tuple(int(record['profile'][f]) for f in FIELDS)
def points(mesh):return np.asarray([[v[k] for k in 'xyz'] for v in mesh['vertices']],dtype=np.float64)
def triangles(mesh):return [f['triangles'][i:i+3] for f in mesh['faces'] for i in range(0,len(f['triangles']),3)]
def vecs(array):return [Vector(v) for v in array]
def normals(array,faces):
    result=np.zeros_like(array)
    for tri in faces:
        a,b,c=array[tri];n=np.cross(b-a,c-a)
        for v in tri:result[v]+=n
    grouped=defaultdict(list)
    for i,p in enumerate(array):grouped[tuple(np.round(p,6))].append(i)
    for ids in grouped.values():
        n=result[ids].sum(axis=0);length=np.linalg.norm(n)
        if length:result[ids]=n/length
    return result
def affine_error(values):
    base=values[BASE];vectors={}
    for axis in range(3):
        for value in sorted({p[axis] for p in values}):
            anchor=list(BASE);anchor[axis]=value;vectors[axis,value]=values[tuple(anchor)]-base
    return max(float(np.linalg.norm(actual-(base+sum((vectors[i,v] for i,v in enumerate(p)),np.zeros_like(base))),axis=1).max()) for p,actual in values.items())
def refine(faces,selected,descriptors,levels):
    faces=[(list(t),i) for i,t in enumerate(faces)]
    for level in range(levels):
        edges={tuple(sorted((t[i],t[(i+1)%3]))) for t,owner in faces if owner in selected for i in range(3)}
        mids={}
        for a,b in sorted(edges):
            d=defaultdict(float)
            for v,w in descriptors[a].items():d[v]+=w*.5
            for v,w in descriptors[b].items():d[v]+=w*.5
            mids[a,b]=len(descriptors);descriptors.append(dict(d))
        new=[]
        for t,owner in faces:
            a,b,c=t;ab=mids.get(tuple(sorted((a,b))));bc=mids.get(tuple(sorted((b,c))));ca=mids.get(tuple(sorted((c,a))))
            count=sum(m is not None for m in (ab,bc,ca))
            if count==3:parts=[[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]]
            elif count==0:parts=[t]
            elif count==1:
                if ab is not None:parts=[[a,ab,c],[ab,b,c]]
                elif bc is not None:parts=[[b,bc,a],[bc,c,a]]
                else:parts=[[c,ca,b],[ca,a,b]]
            elif ca is None:parts=[[b,bc,ab],[a,ab,c],[ab,bc,c]]
            elif ab is None:parts=[[c,ca,bc],[b,bc,a],[bc,ca,a]]
            else:parts=[[a,ab,ca],[c,ca,b],[ca,ab,b]]
            new.extend((part,owner) for part in parts)
        faces=new
        print('REFINED_WRAP_LEVEL',level+1,'vertices',len(descriptors),'triangles',len(faces),flush=True)
    return faces
def interpolate(array,descriptors):return np.asarray([sum((array[i]*w for i,w in d.items()),np.zeros(array.shape[1])) for d in descriptors])
def bary(p,a,b,c):
    ab=b-a;ac=c-a;ap=p-a;d00=ab.dot(ab);d01=ab.dot(ac);d11=ac.dot(ac);den=d00*d11-d01*d01
    if abs(den)<1e-15:return [1.,0.,0.]
    u=(d11*ap.dot(ab)-d01*ap.dot(ac))/den;v=(d00*ap.dot(ac)-d01*ap.dot(ab))/den
    return [1-u-v,u,v]

def main():
    config_path=Path(sys.argv[sys.argv.index('--')+1]);config=json.loads(config_path.read_text(encoding='utf8'));out=Path(config['output'])
    records=config['records'];bodies={profile(r):r for r in records if r['profile']['costume_id']=='0004'}
    donor_records={sub:{profile(r):r for r in records if r['profile']['costume_id']=='0009' and r['profile']['body_type_sub']==sub} for sub in ('00','01')}
    base_record=bodies[BASE];base_data=json.loads(Path(base_record['snapshot']).read_text(encoding='utf8'));base_mesh=next(m for m in base_data['meshes'] if m['name']=='M_Body')
    original_faces=[t[:3] for t in base_record['triangles']];face_keys=[tuple(sorted(t)) for t in original_faces]
    originals={};wrapped={};family_points={};family_checks=[]
    for p,record in bodies.items():
        data=json.loads(Path(record['snapshot']).read_text(encoding='utf8'));mesh=next(m for m in data['meshes'] if m['name']=='M_Body')
        assert Counter(tuple(sorted(t)) for t in triangles(mesh))==Counter(face_keys)
        originals[p]=points(mesh);flags={tuple(sorted(t[:3])):flag for t,flag in zip(record['triangles'],record['wrapped'])}
        wrapped[p]=[flags[k] for k in face_keys]
    for sub,group in donor_records.items():
        values={};base_faces=None
        for p,record in group.items():
            data=json.loads(Path(record['snapshot']).read_text(encoding='utf8'));mesh=next(m for m in data['meshes'] if m['name']=='M_Body')
            values[p]=points(mesh);faces=Counter(tuple(sorted(t)) for t in triangles(mesh))
            if p==BASE:base_faces=faces
        assert all(len(v)==len(values[BASE]) for v in values.values())
        for p,record in group.items():
            assert Counter(tuple(sorted(t[:3])) for t in record['triangles'])==base_faces
        error=affine_error(values);assert error<1e-5,(sub,error)
        family_points[sub]=values;family_checks.append(dict(family='0009_'+sub,profiles=len(values),source_affine_max_error_m=error))
    union={i for i in range(len(original_faces)) if any(wrapped[p][i] for p in bodies)}
    common={i for i in union if all(wrapped[p][i] for p in bodies)}
    descriptors=[{i:1.} for i in range(len(base_mesh['vertices']))]
    refined=refine(original_faces,union,descriptors,config['levels']);faces=[t for t,owner in refined]
    incident=defaultdict(set)
    for t,owner in refined:
        for v in t:incident[v].add(owner)
    eligible=np.asarray([bool(incident[i]) and incident[i]<=common for i in range(len(descriptors))])
    envelopes={p:interpolate(a,descriptors) for p,a in originals.items()};basis=envelopes[BASE];ns=normals(basis,faces)
    refs={}
    for sub,group in donor_records.items():
        record=group[BASE];triangles_skin=[t[:3] for t,flag in zip(record['triangles'],record['skin']) if flag]
        refs[sub]=dict(record=record,triangles=triangles_skin,bvh=BVHTree.FromPolygons(vecs(family_points[sub][BASE]),triangles_skin,all_triangles=True))
    mappings={};candidate_depths=[]
    for i in np.flatnonzero(eligible):
        p=Vector(basis[i]);n=Vector(ns[i]);choices=[]
        for sub,ref in refs.items():
            origin=p+n*.002;remain=config['max_distance']+.002
            for retry in range(4):
                hit,hn,fi,distance=ref['bvh'].ray_cast(origin,-n,remain)
                if fi is None:break
                depth=(p-hit).dot(n)
                if depth>=1e-6 and depth<=config['max_distance'] and hn.dot(n)>=config['normal_dot']:
                    tri=ref['triangles'][fi];weights=bary(hit,*(Vector(family_points[sub][BASE][v]) for v in tri))
                    choices.append((depth,sub,tri,weights));break
                if depth>=config['max_distance']:break
                origin=hit-n*.00002;remain-=distance+.00002
                if remain<=0:break
        if choices:
            depth,sub,tri,weights=max(choices,key=lambda c:c[0]);mappings[int(i)]=dict(family=sub,vertices=tri,weights=weights);candidate_depths.append(depth)
    print('INWARD_CANDIDATES',len(mappings),'maximum_depth',max(candidate_depths,default=0),flush=True)
    # A single source barycentric map is reused for every parameter value, so all
    # reconstruction remains additive. Any map that protrudes in one profile is rejected.
    targets={p:basis.copy() for p in bodies};valid=set(mappings);outside_rejected=set()
    bvhs={p:BVHTree.FromPolygons(vecs(originals[p]),original_faces,all_triangles=True) for p in bodies}
    for p in bodies:
        target=envelopes[p].copy()
        for i,mapping in mappings.items():
            q=sum((family_points[mapping['family']][p][v]*w for v,w in zip(mapping['vertices'],mapping['weights'])),np.zeros(3))
            target[i]=q;surface,n,fi,distance=bvhs[p].find_nearest(Vector(q),config['max_distance']+.002)
            if fi is None or (Vector(q)-surface).dot(n)>1e-6:outside_rejected.add(i)
        targets[p]=target
    valid-=outside_rejected
    adjacency=defaultdict(dict)
    for tri in faces:
        for a,b in zip(tri,tri[1:]+tri[:1]):
            length=float(np.linalg.norm(basis[a]-basis[b]));adjacency[a][b]=length;adjacency[b][a]=length
    distance=np.full(len(basis),np.inf);queue=[]
    for i in range(len(basis)):
        if i not in valid:distance[i]=0.;heapq.heappush(queue,(0.,i))
    while queue:
        d,i=heapq.heappop(queue)
        if d!=distance[i] or d>.009:continue
        for j,length in adjacency[i].items():
            nd=d+length
            if nd<distance[j]:distance[j]=nd;heapq.heappush(queue,(nd,j))
    fade=np.clip(distance/.008,0,1);fade=fade*fade*(3-2*fade)
    fade[[i for i in range(len(fade)) if i not in valid]]=0
    deltas={p:(targets[p]-envelopes[p])*fade[:,None] for p in bodies}
    # Smooth displacement, not the envelope itself. Fixed basis-space weights
    # preserve affine parameter vectors and leave original skin untouched.
    smoothing=[]
    for i in range(len(basis)):
        if not eligible[i]:smoothing.append([]);continue
        neighbors=list(adjacency[i]);weights=[1/max(adjacency[i][j],.0001) for j in neighbors];total=sum(weights)
        smoothing.append([(j,w/total) for j,w in zip(neighbors,weights)] if total else [])
    for iteration in range(5):
        for p in bodies:
            before=deltas[p];after=before.copy()
            for i,neighbors in enumerate(smoothing):
                if neighbors:after[i]=before[i]*.65+sum((before[j]*w for j,w in neighbors),np.zeros(3))*.35
            deltas[p]=after
    corrected={p:envelopes[p]+deltas[p] for p in bodies}
    final_outside=[]
    for p in bodies:
        for i in np.flatnonzero(np.linalg.norm(deltas[p],axis=1)>1e-10):
            q=corrected[p][i];surface,n,fi,d=bvhs[p].find_nearest(Vector(q),config['max_distance']+.002)
            if (Vector(q)-surface).dot(n)>1.5e-6:final_outside.append(i)
    if final_outside:
        for p in bodies:deltas[p][list(set(final_outside))]=0
        corrected={p:envelopes[p]+deltas[p] for p in bodies}
    error=affine_error(corrected);assert error<1e-5,error
    # Interpolate all canonical attributes on the same refined topology. Only
    # covered inward coordinates and smoothed normals differ from the envelope.
    uvs=[]
    for layer in base_mesh['uvs']:
        values=np.asarray([[v['x'],v['y']] for v in layer['values']]);new=interpolate(values,descriptors)
        uvs.append(dict(channel=layer['channel'],values=[dict(x=float(u),y=float(v),z=0.,w=0.) for u,v in new]))
    source_weights=defaultdict(dict)
    for weight in base_mesh['weights']:source_weights[weight['vertex']][weight['bone']]=weight['weight']
    # Source bone IDs differ per prefab; semantic names are copied onto each profile below.
    weight_names={b['id']:b['name'] for b in base_data['bones']};interpolated_weights=[]
    for i,desc in enumerate(descriptors):
        weights=defaultdict(float)
        for old,coef in desc.items():
            for bone,w in source_weights[old].items():weights[weight_names[bone]]+=coef*w
        interpolated_weights.append(dict(weights))
    (out/'snapshots').mkdir(exist_ok=True);jobs=[];summaries=[]
    for p,record in sorted(bodies.items()):
        data=json.loads(Path(record['snapshot']).read_text(encoding='utf8'));mesh=next(m for m in data['meshes'] if m['name']=='M_Body');data['meshes']=[mesh]
        mesh['vertices']=[dict(x=float(v[0]),y=float(v[1]),z=float(v[2]),w=0.) for v in corrected[p]]
        smooth=normals(corrected[p],faces);mesh['normals']=[dict(x=float(v[0]),y=float(v[1]),z=float(v[2]),w=0.) for v in smooth]
        mesh['colors']=[];mesh['uvs']=copy.deepcopy(uvs);mesh['shapes']=[]
        names={b['name']:b['id'] for b in data['bones']};mesh['weights']=[dict(vertex=i,bone=names[name],weight=float(w)) for i,weights in enumerate(interpolated_weights) for name,w in weights.items() if w>0]
        mesh['faces']=[dict(part='body',category='body_skin',material=0,triangles=[v for t in faces for v in t])]
        material=copy.deepcopy(data['materials'][0]);material['name']='uma_normalized_restored_skin';data['materials']=[material]
        data['skin_reconstruction']=dict(policy=config['policy'],common_topology=True,original_vertices_before_refinement=len(base_mesh['vertices']),refinement_levels=config['levels'],global_mesh_transform_applied=False)
        file=out/'snapshots'/(record['job']+'.uma.json');write(file,data)
        jobs.append(dict(name=record['job'],snapshot='snapshots/'+file.name,character_id='shared',source=data['source'],kind='body',body_profile=record['profile'],categories=['body_skin'],category_triangles={'body_skin':len(faces)},skin_palette=[]))
        displacement=np.linalg.norm(corrected[p]-envelopes[p],axis=1)
        signed=[]
        for i in np.flatnonzero(displacement>1e-8):
            surface,n,fi,d=bvhs[p].find_nearest(Vector(corrected[p][i]),config['max_distance']+.002);signed.append((Vector(corrected[p][i])-surface).dot(n))
        summaries.append(dict(profile=list(p),modified_vertices=int(np.count_nonzero(displacement>1e-8)),maximum_inward_displacement_m=float(displacement.max()),maximum_signed_outside_m=max(signed,default=0),original_skin_vertices_preserved=bool(np.all(displacement[~eligible]<1e-12))))
        print('RESTORED_PROFILE',p,'vertices',int(np.count_nonzero(displacement>1e-8)),'depth',float(displacement.max()),flush=True)
    write(out/'manifest.json',dict(version=1,input='Inward-only reconstruction of selected common 0004 envelope',resources='resources',characters=[],jobs=jobs,errors=[],warnings=[],body_bases=[]))
    write(out/'reconstruction-map.json',dict(descriptors=[list(d.items()) for d in descriptors],refined_faces=faces,face_owners=[owner for tri,owner in refined],eligible=eligible.tolist(),fade=fade.tolist(),mappings=mappings,basis_job=base_record['job'],basis_envelope_snapshot=base_record['snapshot'],basis_donors={sub:group[BASE]['snapshot'] for sub,group in donor_records.items()}))
    write(out/'geometry-verification.json',dict(passed=True,source_profiles=28,vertices=len(descriptors),triangles=len(faces),original_source_vertices=3510,common_wrapped_triangles=len(common),union_refinement_triangles=len(union),inward_candidates=len(mappings),globally_rejected_outside_vertices=len(outside_rejected),final_rejected_outside_vertices=len(set(final_outside)),source_families=family_checks,additive_max_error_m=error,profiles=summaries,policy=config['policy']))
    print('INWARD_BODY_RECONSTRUCTION_COMPLETE',flush=True)

if __name__=='__main__':main()
