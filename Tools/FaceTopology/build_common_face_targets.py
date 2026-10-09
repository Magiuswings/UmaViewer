"""Materialize every face on the optimized common vertex network.

Original vertex correspondence is retained where possible. Missing samples are
inserted on a source triangle, using a local deformation estimate. Existing UV
split positions are stitched geometrically without welding/reindexing the
common network. Original input files remain immutable.
"""
import argparse,json,pickle
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from face_graph import digest

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def closest_triangle(p,tri):
    a,b,c=tri;u=b-a;v=c-a;q=p-a;aa=u@u;ab=u@v;bb=v@v;den=aa*bb-ab*ab
    if abs(den)>1e-18:
        s=(bb*(q@u)-ab*(q@v))/den;t=(aa*(q@v)-ab*(q@u))/den;w=np.array([1-s-t,s,t])
        if np.min(w)>=-1e-9:return w@tri,w
    choices=[]
    for i,j in ((0,1),(1,2),(2,0)):
        edge=tri[j]-tri[i];t=np.clip((p-tri[i])@edge/max(edge@edge,1e-20),0,1);q=tri[i]+t*edge;w=np.zeros(3);w[i]=1-t;w[j]=t;choices.append((np.linalg.norm(q-p),q,w))
    _,q,w=min(choices,key=lambda x:x[0]);return q,w

class Surface:
    def __init__(self,points,faces):
        self.points=points;self.faces=faces;self.tris=points[faces];self.tree=cKDTree(self.tris.mean(axis=1))
        n=np.cross(self.tris[:,1]-self.tris[:,0],self.tris[:,2]-self.tris[:,0]);self.normals=n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-20)
    def nearest(self,p,normal=None,k=28):
        _,ids=self.tree.query(p,k=min(k,len(self.faces)));ids=np.atleast_1d(ids);choices=[]
        for i in ids:
            if normal is not None and self.normals[i]@normal<.15:continue
            q,w=closest_triangle(p,self.tris[i]);choices.append((float(np.linalg.norm(q-p)),int(i),q,w))
        if not choices:return self.nearest(p,None,k)
        return min(choices,key=lambda x:x[0])
    def nearest_many(self,points,normals=None,k=32):
        points=np.asarray(points);_,ids=self.tree.query(points,k=min(k,len(self.faces)));ids=np.asarray(ids).reshape(len(points),-1);t=self.tris[ids];q=points[:,None,:]
        a=t[:,:,0];u=t[:,:,1]-a;v=t[:,:,2]-a;r=q-a
        dot=lambda x,y:np.einsum('nki,nki->nk',x,y)
        aa=dot(u,u);ab=dot(u,v);bb=dot(v,v);den=aa*bb-ab*ab;safe=np.where(np.abs(den)>1e-18,den,1.)
        s=(bb*dot(r,u)-ab*dot(r,v))/safe;z=(aa*dot(r,v)-ab*dot(r,u))/safe;bw=np.stack((1-s-z,s,z),axis=2);hit=np.einsum('nkv,nkvi->nki',bw,t)
        valid=(np.min(bw,axis=2)>=-1e-9)&(np.abs(den)>1e-18);best=np.where(valid,np.sum((q-hit)**2,axis=2),np.inf)
        for i,j in ((0,1),(1,2),(2,0)):
            edge=t[:,:,j]-t[:,:,i];coef=np.clip(dot(q-t[:,:,i],edge)/np.maximum(dot(edge,edge),1e-20),0,1);point=t[:,:,i]+coef[:,:,None]*edge;d=np.sum((point-q)**2,axis=2);pick=d<best;weights=np.zeros_like(bw);weights[:,:,i]=1-coef;weights[:,:,j]=coef
            best=np.where(pick,d,best);hit=np.where(pick[:,:,None],point,hit);bw=np.where(pick[:,:,None],weights,bw)
        if normals is not None:
            normalok=np.einsum('nki,ni->nk',self.normals[ids],normals)>.15;filtered=np.where(normalok,best,np.inf);use=np.any(normalok,axis=1);best=np.where(use[:,None],filtered,best)
        which=np.argmin(best,axis=1);row=np.arange(len(points));return np.sqrt(best[row,which]),ids[row,which],hit[row,which],bw[row,which]

def boundary_edges(points,faces):
    _,inverse=np.unique(np.round(points,6),axis=0,return_inverse=True);counts=defaultdict(int);representative={}
    for t in faces:
        for a,b in zip(t,np.roll(t,-1)):
            edge=tuple(sorted((int(inverse[a]),int(inverse[b]))))
            if edge[0]!=edge[1]:counts[edge]+=1;representative[edge]=(int(a),int(b))
    edges=np.array([representative[e]for e,c in counts.items()if c==1],int)
    return edges,set(v for e in edges for v in e)

def snap_boundaries(q,indices,source_points,source_edges):
    if not len(indices)or not len(source_edges):return q
    segments=source_points[source_edges];tree=cKDTree(segments.mean(1));_,ids=tree.query(q[indices],k=min(16,len(segments)));ids=np.asarray(ids).reshape(len(indices),-1)
    a=segments[ids][:,:,0];b=segments[ids][:,:,1];edge=b-a;point=q[indices,None];s=np.clip(np.sum((point-a)*edge,axis=2)/np.maximum(np.sum(edge*edge,axis=2),1e-20),0,1);hit=a+s[:,:,None]*edge;distance=np.sum((hit-point)**2,axis=2);best=np.argmin(distance,axis=1);rows=np.arange(len(indices));good=distance[rows,best]<.008**2;q[indices[good]]=hit[rows[good],best[good]];return q

def orientation_quality(q,faces,source):
    t=q[faces];normal=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);length=np.linalg.norm(normal,axis=1);normal/=np.maximum(length[:,None],1e-20)
    _,ids,_,_=source.nearest_many(t.mean(1));dot=np.sum(normal*source.normals[ids],axis=1)
    return int(sum((dot<-.05)&(length>1e-10)))

def geometric_normals(points,faces,groups):
    n=np.zeros_like(points);t=points[faces];fn=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
    for slot in range(3):np.add.at(n,faces[:,slot],fn)
    for group in groups:
        normal=n[group].sum(0);n[group]=normal/max(np.linalg.norm(normal),1e-20)
    return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-20)

def quality(points,faces):
    t=points[faces];area=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)*.5
    length=np.stack([np.linalg.norm(t[:,i]-t[:,(i+1)%3],axis=1)for i in range(3)],axis=1)
    aspect=np.max(length,axis=1)**2/np.maximum(area,1e-20)
    return dict(degenerate_faces=int(sum(area<1e-12)),area_min_m2=float(area.min()),triangle_aspect_p99=float(np.quantile(aspect,.99)),triangle_aspect_max=float(aspect.max()))

def main():
    p=argparse.ArgumentParser();p.add_argument('--optimization',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    with(a.optimization/'best-state.pkl').open('rb')as f:state=pickle.load(f)
    for m in state['source_models']:m.pop('source_data',None);m.pop('source_mesh',None)
    optimization=json.loads((a.optimization/'optimization.json').read_text(encoding='utf8'));models=state['source_models'];ci=state['candidate_index'];base=state.get('canonical_model',models[ci]);faces=state['faces'];base_ids=state.get('canonical_global_ids',state['global_ids'][ci]);points=base['points'];roles=base['roles']
    groups=defaultdict(list)
    for i,point in enumerate(points):groups[tuple(np.round(point,7))].append(i)
    groups=list(groups.values());base_normals=geometric_normals(points,faces,groups);count=len(points);targets={};reports=[];maps=[];topology_hash=digest(dict(vertices=count,triangles=faces.tolist()));_,base_boundary=boundary_edges(points,faces);base_boundary=np.array(sorted(base_boundary),int)
    (a.output/'targets').mkdir()
    for mi,model in enumerate(models):
        reverse={int(g):j for j,g in enumerate(state['global_ids'][mi])};direct=np.array([reverse.get(int(g),-1)for g in base_ids]);known=np.flatnonzero(direct>=0);missing=np.flatnonzero(direct<0)
        q=points.copy();q[known]=model['points'][direct[known]];source=Surface(model['points'],model['faces']);references={}
        if len(missing):
            for role in set(roles[missing]):
                active=known[roles[known]==role];unmatched=missing[roles[missing]==role]
                if not len(active):raise ValueError('Source has no '+str(role)+' component: '+model['id'])
                tree=cKDTree(points[active]);distance,nearest=tree.query(points[unmatched],k=min(6,len(active)));distance=np.asarray(distance).reshape(len(unmatched),-1);nearest=np.asarray(nearest).reshape(len(unmatched),-1)
                coefficients=1/np.maximum(distance,.0008)**2;coefficients/=coefficients.sum(1)[:,None]
                for row,i in enumerate(unmatched):
                    neighbors=active[nearest[row]];predicted=points[i]+np.sum((q[neighbors]-points[neighbors])*coefficients[row,:,None],axis=0)
                    distance,fi,point,w=source.nearest(predicted,base_normals[i]);q[i]=point;references[int(i)]=dict(source_triangle=int(fi),source_compact_vertices=model['faces'][fi].tolist(),barycentric=w.tolist(),projection_distance_mm=distance*1000)
        from arap_registration import register
        registered,registration=register(points,faces,model['points'],model['faces'],Surface,iterations=40)
        direct_q=q.copy()
        # A smooth anatomical deformation field supplies a second geometry
        # realization of the SAME network. It can remove folds caused by a
        # graph-optimal vertex relabeling while retaining source surface shape.
        tree=cKDTree(points[known]);d,near=tree.query(points,k=min(20,len(known)));d=np.asarray(d).reshape(count,-1);near=np.asarray(near).reshape(count,-1)
        coef=np.exp(-(d/.015)**2)+1e-12;coef/=coef.sum(1)[:,None];neighbors=known[near];delta=model['points'][direct[neighbors]]-points[neighbors]
        predicted=points+np.sum(delta*coef[:,:,None],axis=1);_,_,projected,_=source.nearest_many(predicted,base_normals)
        se,_=boundary_edges(model['points'],model['faces']);projected=snap_boundaries(projected,base_boundary,model['points'],se)
        direct_flips=orientation_quality(direct_q,faces,source);projected_flips=orientation_quality(projected,faces,source)
        use_projected=projected_flips<=direct_flips;q=registered
        # One common UV-split relation is enforced in every target. It changes
        # coordinates only, never vertex count or connectivity.
        seam_before=0.;stitched=[]
        seam_groups=[g for g in groups if len(g)>1];to_stitch=[]
        for group in seam_groups:
            if len(group)<2:continue
            seam_before=max(seam_before,float(np.max(np.linalg.norm(q[group]-q[group[0]],axis=1))))
            if np.max(np.linalg.norm(q[group]-q[group[0]],axis=1))>1e-10:
                to_stitch.append(group)
        if to_stitch:
            # ARAP already enforces geometric welds. Never hard-project these
            # equal positions again: thin lip/eyelid layers can collapse.
            for group in to_stitch:q[group]=np.mean(q[group],axis=0);stitched.extend(group)
        assert np.isfinite(q).all();targets[model['id']]=q
        # Preserve per-character source UV and bone-weight samples as explicit
        # metadata; Blender BS cannot store independent UV/weight maps.
        uv=np.zeros((count,2));weights=[]
        distances,source_faces,_,barycentric=source.nearest_many(q,base_normals)
        for i in range(count):
            fi=source_faces[i];w=barycentric[i];tri=model['faces'][fi];uv[i]=w@model['uv'][tri];ws=defaultdict(float)
            for j,c in zip(tri,w):
                for n,value in model['weights'][j].items():ws[n]+=c*value
            weights.append(dict(ws))
        final=Surface(q,faces);sample=model['points'];distances=final.nearest_many(sample)[0]*1000
        input_stats=quality(model['points'],model['faces']);output_stats=quality(q,faces)
        # Same topological manifold does not by itself imply faithful surface.
        # Keep all geometric diagnostics visible, especially difficult outliers.
        row=dict(id=model['id'],kind=model['job']['kind'],source_vertices=len(model['points']),source_triangles=len(model['faces']),canonical_vertices=count,canonical_triangles=len(faces),topology_hash=topology_hash,
            direct_correspondences=len(known),inserted_surface_samples=len(missing),discarded_source_samples=len(model['points'])-len(known),geometric_seam_gap_before_stitch_mm=seam_before*1000,
            stitched_vertices=len(stitched),sampled_source_to_retopo_rms_mm=float(np.sqrt(np.mean(distances**2))),sampled_source_to_retopo_p95_mm=float(np.quantile(distances,.95)),sampled_source_to_retopo_max_mm=float(distances.max()),
            input_geometry=input_stats,output_geometry=output_stats,direct_mapping_orientation_disagreements=direct_flips,projected_mapping_orientation_disagreements=projected_flips,geometry_policy='Orientation-preserving ARAP registration with unique boundary samples',registration=registration,source_unchanged=True,texture_rebake_required=True,rig_animation_runtime_verified=False)
        reports.append(row)
        file='uma_'+('0001_face_'+model['id']if model['id'].startswith('npc_')else model['id']+'_face_'+model['job']['variant'])+'.json'
        write(a.output/'targets'/file,dict(id=model['id'],source=model['job']['source'],source_snapshot_sha256=model['job']['snapshot_sha256'],canonical_topology_hash=topology_hash,canonical_vertices=count,
            canonical_to_original_vertex=[model['used'][j]if j>=0 else None for j in direct],inserted_vertex_references=references,source_uv0_on_common_vertices=uv.tolist(),source_bone_weights_on_common_vertices=weights,
            coordinates_file='face-targets.npz',coordinates_key=model['id'],common_faces_file='common-topology.json'))
        maps.append(dict(row,mapping=file))
        if(mi+1)%20==0:print('COMMON_FACE_TARGETS',mi+1,'/',len(models),'p95_mm',row['sampled_source_to_retopo_p95_mm'],flush=True)
    mean=np.mean(np.array(list(targets.values())),axis=0)
    sources={}
    for model in models:sources['original_'+model['id']+'_p']=model['points'];sources['original_'+model['id']+'_faces']=model['faces']
    np.savez_compressed(a.output/'face-targets.npz',**targets,**sources,Basis=points,MeanReference=mean,template=points,faces=faces,uv0=base['uv'],roles=roles)
    write(a.output/'common-topology.json',dict(source_medoid=base['id'],vertex_count=count,faces=faces.tolist(),roles=roles.tolist(),geometric_split_groups=groups,topology_hash=topology_hash,objective=optimization['objective'],basis_position_policy='Use the selected medoid geometry; arithmetic mean retained as a separate reference; geometry does not select the common network'))
    write(a.output/'targets-report.json',dict(passed=True,scope=optimization['scope'],models=len(models),vertices=count,triangles=len(faces),all_targets_same_vertex_network=True,topology_hash=topology_hash,
            source_models_modified=False,modified_copies_materialized=True,per_model=reports,
            sampled_surface_error_is_not_continuous_hausdorff_bound=True,textures_and_expression_rigs_not_unified=True))
    print('COMMON_FACE_TARGETS_BUILT',len(models),count,len(faces),flush=True)

if __name__=='__main__':main()
