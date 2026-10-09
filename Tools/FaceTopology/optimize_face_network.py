"""Multi-start constrained median vertex network, followed by legal edge edits.

The optimization objective contains only counts of differing vertices, edges
and triangles. Coordinate/semantic features initialize anatomical matching;
coordinates never contribute to the reported network objective or candidate
median selection. This is a heuristic search, not a global optimality proof.
"""
import argparse,json,pickle,time
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
from face_graph import load_models,network,network_distance,median_scores,topology_audit

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def feature_weights(a,b):
    names=sorted(set(n for ws in a['weights']+b['weights']for n in ws));lookup={n:i for i,n in enumerate(names)}
    arrays=[]
    for m in (a,b):
        v=np.zeros((len(m['points']),len(names)),np.float32)
        for i,ws in enumerate(m['weights']):
            for n,w in ws.items():v[i,lookup[n]]=w
        arrays.append(v)
    return arrays

def alignment(reference,target,rounds=2):
    n=len(reference['points']);m=len(target['points']);mapping=np.full(n,-1,int)
    if reference['id']==target['id']:return np.arange(n),dict(swaps=0,seed='identity',seconds=0.)
    start=time.monotonic();wa,wb=feature_weights(reference,target)
    for role in sorted(set(reference['roles'])):
        for side in (-1,0,1):
            aa=np.flatnonzero((reference['roles']==role)&(reference['sides']==side));bb=np.flatnonzero((target['roles']==role)&(target['sides']==side))
            if not len(aa)or not len(bb):continue
            p=reference['points'][aa];q=target['points'][bb]
            distance=np.linalg.norm(p[:,None]-q[None],axis=2)
            degree=np.abs(reference['degree'][aa,None]-target['degree'][None,bb])
            boundary=np.abs(reference['boundaries'][aa,None]-target['boundaries'][None,bb])
            neighbor=np.sum(np.abs(reference['local'][aa,None]-target['local'][None,bb]),axis=2)
            weight=np.maximum(0,1-wa[aa]@wb[bb].T)
            # An anatomical assignment seed, not the median graph score.
            # Bone/left-right identity and locality prevent eye/neck swaps.
            cost=distance/.006+.20*degree+.40*boundary+.06*neighbor+.6*weight
            ai,bi=linear_sum_assignment(cost);mapping[aa[ai]]=bb[bi]
    reverse={int(j):i for i,j in enumerate(mapping)if j>=0};target_tri=target['triangles'];ref_inc=[[]for _ in range(n)]
    for t in reference['faces']:
        tri=tuple(map(int,t))
        for i in tri:ref_inc[i].append(tri)
    def delta(i,h,k):
        oldi=int(mapping[i]);oldh=int(mapping[h])if h is not None else -1
        affected={tuple(sorted((v,j)))for v in (i,h)if v is not None for j in reference['adj'][v]}
        tris=set(t for v in (i,h)if v is not None for t in ref_inc[v])
        def value(swap):
            def target_id(v):
                if swap and v==i:return k
                if swap and v==h:return oldi
                return int(mapping[v])
            e=sum(tuple(sorted((target_id(a),target_id(b))))in target['edges']for a,b in affected if target_id(a)>=0 and target_id(b)>=0)
            f=sum(tuple(sorted(target_id(v)for v in t))in target_tri for t in tris if all(target_id(v)>=0 for v in t))
            return e+f
        return value(True)-value(False)
    swaps=0
    for _ in range(rounds):
        changes=0
        for i,j in enumerate(mapping):
            if j<0:continue
            candidates=Counter(k for v in reference['adj'][i]if mapping[v]>=0 for k in target['adj'][mapping[v]])
            best=None
            for k,hits in candidates.most_common(12):
                if k==j or hits<2 or target['roles'][k]!=reference['roles'][i]or target['sides'][k]!=reference['sides'][i]:continue
                h=reverse.get(k)
                if h is not None and(reference['roles'][h]!=reference['roles'][i]or reference['sides'][h]!=reference['sides'][i]):continue
                current=float(np.linalg.norm(reference['points'][i]-target['points'][j]));trial=float(np.linalg.norm(reference['points'][i]-target['points'][k]))
                if trial>max(.016,current+.004):continue
                if h is not None:
                    curh=np.linalg.norm(reference['points'][h]-target['points'][k]);newh=np.linalg.norm(reference['points'][h]-target['points'][j])
                    if newh>max(.016,curh+.004):continue
                gain=delta(i,h,k)
                if gain>0 and(best is None or gain>best[0]):best=(gain,k,h)
            if best:
                _,k,h=best;old=int(mapping[i]);mapping[i]=k;reverse[k]=i
                if h is not None:mapping[h]=old;reverse[old]=h
                else:reverse.pop(old)
                changes+=1;swaps+=1
        if not changes:break
    assert len(set(mapping[mapping>=0]))==sum(mapping>=0)
    return mapping,dict(swaps=swaps,matched=int(sum(mapping>=0)),seed='Bone/side/locality constrained assignment, followed by strict edge+triangle reward improvement',seconds=time.monotonic()-start)

def lift_models(models,reference,mappings):
    pool={};graphs=[];global_ids=[];nr=len(reference['points'])
    for model,mapping in zip(models,mappings):
        inverse={int(j):int(i)for i,j in enumerate(mapping)if j>=0};ids=np.full(len(model['points']),-1,int)
        for j,i in inverse.items():ids[j]=i
        localcount=Counter()
        for j in np.flatnonzero(ids<0):
            anchors=sorted(inverse[k]for k in model['adj'][j]if k in inverse)
            if not anchors:
                next_ring=set(k for v in model['adj'][j]for k in model['adj'][v]);anchors=sorted(inverse[k]for k in next_ring if k in inverse)
            dominant=max(model['weights'][j],key=model['weights'][j].get)
            token=(int(model['roles'][j]),int(model['sides'][j]),tuple(anchors),dominant,int(model['degree'][j]))
            ordinal=localcount[token];localcount[token]+=1;token=token+(ordinal,)
            if token not in pool:pool[token]=nr+len(pool)
            ids[j]=pool[token]
        assert len(set(ids))==len(ids)
        global_ids.append(ids);graphs.append(network(model,ids))
    return graphs,global_ids

def surface_signature(faces):
    edges=Counter(tuple(sorted((int(a),int(b))))for t in faces for a,b in zip(t,np.roll(t,-1)));vertices=set(int(v)for t in faces for v in t)
    adj=defaultdict(set)
    for a,b in edges:adj[a].add(b);adj[b].add(a)
    seen=set();components=0
    for i in vertices:
        if i in seen:continue
        components+=1;stack=[i];seen.add(i)
        while stack:
            v=stack.pop()
            for j in adj[v]:
                if j not in seen:seen.add(j);stack.append(j)
    return dict(vertices=len(vertices),edges=len(edges),triangles=len(faces),components=components,euler=len(vertices)-len(edges)+len(faces),boundary_edges=sum(c==1 for c in edges.values()),nonmanifold_edges=sum(c>2 for c in edges.values()))

def improve_edges(model,ids,frequency,n):
    faces=[tuple(map(int,t))for t in model['faces']];points=model['points'];roles=model['roles'];changes=[];before=surface_signature(faces)
    for iteration in range(8):
        owners=defaultdict(list)
        for ti,t in enumerate(faces):
            for a,b in zip(t,np.roll(t,-1)):owners[tuple(sorted((int(a),int(b))))].append(ti)
        proposals=[]
        for(a,b),fs in owners.items():
            if len(fs)!=2:continue
            t1,t2=faces[fs[0]],faces[fs[1]];c=next(v for v in t1 if v not in(a,b));d=next(v for v in t2 if v not in(a,b))
            if c==d or tuple(sorted((c,d)))in owners or len({int(roles[v])for v in (a,b,c,d)})!=1:continue
            # Orient both replacement triangles to the existing surface.
            oldnormal=np.cross(points[t1[1]]-points[t1[0]],points[t1[2]]-points[t1[0]])+np.cross(points[t2[1]]-points[t2[0]],points[t2[2]]-points[t2[0]])
            new=[];valid=True
            for tri in ((c,d,a),(d,c,b)):
                ns=np.cross(points[tri[1]]-points[tri[0]],points[tri[2]]-points[tri[0]])
                if np.linalg.norm(ns)<1e-10:valid=False;break
                if ns@oldnormal<0:tri=(tri[0],tri[2],tri[1]);ns=-ns
                if ns@oldnormal/max(np.linalg.norm(ns)*np.linalg.norm(oldnormal),1e-20)<.3:valid=False;break
                new.append(tri)
            if not valid:continue
            oldedge=tuple(sorted((int(ids[a]),int(ids[b]))));newedge=tuple(sorted((int(ids[c]),int(ids[d]))))
            oldtri=[tuple(sorted(int(ids[v])for v in t))for t in (t1,t2)];newtri=[tuple(sorted(int(ids[v])for v in t))for t in new]
            gain=2*(frequency['edges'][newedge]-frequency['edges'][oldedge]+sum(frequency['triangles'][t]for t in newtri)-sum(frequency['triangles'][t]for t in oldtri))
            if gain>0:proposals.append((gain,(a,b),fs,new))
        if not proposals:break
        used=set();used_vertices=set();count=0
        for gain,edge,fs,new in sorted(proposals,reverse=True):
            quad=set(v for t in [faces[i]for i in fs]for v in t)
            if any(v in used for v in fs)or quad&used_vertices:continue
            old=[faces[v]for v in fs]
            for fi,t in zip(fs,new):faces[fi]=t
            used.update(fs);used_vertices.update(quad);changes.append(dict(iteration=iteration,old_edge=edge,old_triangles=old,new_triangles=new,objective_reduction=int(gain)));count+=1
        if not count:break
    after=surface_signature(faces)
    # A triangulation change may not alter surface components, holes or counts.
    assert before==after,(before,after)
    return np.array(faces),changes,before

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True);p.add_argument('--scope',choices=['skin','whole'],default='skin');p.add_argument('--starts',type=int,default=5);p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');p.add_argument('--exclude-id',action='append',default=[])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=a.resume)
    if a.resume and(a.output/'best-state.pkl').exists():
        with(a.output/'best-state.pkl').open('rb')as f:best=pickle.load(f)
        models=best['source_models'];runs=json.loads((a.output/'optimization-progress.json').read_text())['runs']
    else:models=load_models(a.root,a.scope);runs=[];best=None
    models=[m for m in models if m['id']not in a.exclude_id];write(a.output/'topology-inventory.json',topology_audit(models));ids={m['id']:i for i,m in enumerate(models)}
    ranked=sorted(range(len(models)),key=lambda i:len(models[i]['points']));npcs=[i for i,m in enumerate(models)if m['job']['kind']=='npc'];npcs.sort(key=lambda i:len(models[i]['points']))
    starts=list(dict.fromkeys([ids['1001'],ranked[len(ranked)//2],ranked[0],ranked[-1],npcs[len(npcs)//2]]))[:a.starts]
    for si,ri in enumerate(starts):
        if si<len(runs):continue
        reference=models[ri];mapping=[];matching=[]
        for i,target in enumerate(models):
            m,r=alignment(reference,target);mapping.append(m);matching.append(r)
            if(i+1)%20==0:print('NETWORK_ALIGNMENT',si+1,'reference',reference['id'],i+1,'/',len(models),flush=True)
        graphs,global_ids=lift_models(models,reference,mapping);scores,frequency,totals=median_scores(graphs);ci=min(range(len(models)),key=lambda i:scores[i]);candidate=models[ci]
        faces,edits,signature=improve_edges(candidate,global_ids[ci],frequency,len(models));newmodel=dict(candidate,faces=faces,triangles={tuple(sorted(t))for t in faces},edges={tuple(sorted((int(x),int(y))))for t in faces for x,y in zip(t,np.roll(t,-1))})
        g=network(newmodel,global_ids[ci]);distance=[network_distance(g,other)for other in graphs];score=sum(d['total']for d in distance);assert score<=scores[ci]
        run=dict(reference=reference['id'],medoid=candidate['id'],initial_objective=int(scores[ci]),final_objective=int(score),legal_edge_flips=len(edits),vertices=len(candidate['points']),triangles=len(faces),candidate_scores=[dict(id=m['id'],score=int(s))for m,s in zip(models,scores)])
        runs.append(run);write(a.output/f'start-{si+1}.json',run);print('MEDIAN_CANDIDATE',run['reference'],run['medoid'],score,'flips',len(edits),flush=True)
        if best is None or score<best['score']:
            best=dict(score=score,reference_index=ri,candidate_index=ci,faces=faces,global_ids=global_ids,mappings=mapping,matching=matching,graphs=graphs,distance=distance,edits=edits,signature=signature,source_models=models)
            with(a.output/'best-state.pkl').open('wb')as f:pickle.dump(best,f,protocol=5)
        write(a.output/'optimization-progress.json',dict(runs=runs,best_score=best['score'],best_model=models[best['candidate_index']]['id']))
    candidate=models[best['candidate_index']]
    report=dict(passed=True,scope=a.scope,models=len(models),named_character_faces=sum(m['job']['kind']!='npc'for m in models),npc=sum(m['job']['kind']=='npc'for m in models),
        objective='Sum of differing vertex entries, undirected edges and triangles, each weight 1, under anatomical injective correspondence; no coordinate distance in objective',
        model_weighting='Every playable base and NPC base once, weight 1',multi_start_runs=runs,chosen_source=candidate['id'],chosen_reference=models[best['reference_index']]['id'],
        total_objective=best['score'],canonical_vertices=len(candidate['points']),canonical_triangles=len(best['faces']),legal_edge_flips=best['edits'],surface_signature=best['signature'],
        differences=[dict(id=m['id'],**d)for m,d in zip(models,best['distance'])],globally_optimal_proven=False,source_meshes_modified=False,
        excluded_ids=a.exclude_id,skin_scope='Largest geometrically connected skin shell; eye whites, eyelid patches and oral parts retained separately in source snapshots'if a.scope=='skin'else'Whole M_Face',
        limitations='Heuristic constrained graph median. Bone/side/locality seed uses coordinates to establish anatomical identity; only network edit counts select/improve the common topology. Retopologized output targets are a later stage.')
    write(a.output/'optimization.json',report);print('COMMON_FACE_NETWORK_OPTIMIZED',candidate['id'],best['score'],flush=True)

if __name__=='__main__':main()
