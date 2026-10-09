"""Improve a median face with topology-preserving vertex collapse/split edits."""
import argparse,copy,json,pickle
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from face_graph import network,network_distance,median_scores
from optimize_face_network import surface_signature

def write(path,v):path.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def graph_parts(faces,ids):
    return dict(nodes={int(ids[v])for t in faces for v in t},edges={tuple(sorted((int(ids[a]),int(ids[b]))))for t in faces for a,b in zip(t,np.roll(t,-1))},triangles={tuple(sorted(int(ids[v])for v in t))for t in faces})
def gain(old,new,frequency,n):
    return sum(n*(len(old[k])-len(new[k]))+2*(sum(frequency[k][v]for v in new[k]-old[k])-sum(frequency[k][v]for v in old[k]-new[k]))for k in old)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    with(a.input/'best-state.pkl').open('rb')as f:state=pickle.load(f)
    for m in state['source_models']:m.pop('source_data',None);m.pop('source_mesh',None)
    report=json.loads((a.input/'optimization.json').read_text());models=state['source_models'];base=copy.copy(models[state['candidate_index']]);ids=state['global_ids'][state['candidate_index']].copy();faces=state['faces'].copy();points=base['points'].copy()
    roles=base['roles'].copy();weights=list(base['weights']);uv=base['uv'].copy();used=list(base['used']);_,frequency,_=median_scores(state['graphs']);n=len(models)
    minimum=min(len(m['points'])for m in models);maximum=max(len(m['points'])for m in models);signature=surface_signature(faces);edits=[];previous=state['score']
    for iteration in range(100):
        active=set(int(v)for t in faces for v in t)
        owners=defaultdict(list);adj=defaultdict(set);incident=defaultdict(list)
        for fi,t in enumerate(faces):
            for v in t:incident[int(v)].append(fi)
            for x,y in zip(t,np.roll(t,-1)):owners[tuple(sorted((int(x),int(y))))].append(fi);adj[int(x)].add(int(y));adj[int(y)].add(int(x))
        boundary={v for edge,fs in owners.items()if len(fs)==1 for v in edge};current=graph_parts(faces,ids);proposals=[]
        if len(active)>minimum:
            # Try the interior vertices whose incident entries are least shared
            # across input networks. Facial controls and all boundary loops stay.
            candidates=[]
            for v in active-boundary:
                dominant=max(weights[v],key=weights[v].get)
                if dominant not in ('Head','__root')or len(adj[v])<4 or len(adj[v])>8:continue
                support=frequency['nodes'][int(ids[v])]+sum(frequency['edges'][tuple(sorted((int(ids[v]),int(ids[j]))))]for j in adj[v])
                candidates.append((support,v))
            for _,v in sorted(candidates)[:100]:
                for u in adj[v]-boundary:
                    if roles[u]!=roles[v]or len(adj[u]&adj[v])!=2 or len(owners[tuple(sorted((u,v)))])!=2:continue
                    oldtri=[tuple(map(int,faces[i]))for i in incident[v]];newtri=[];valid=True
                    existing={tuple(sorted(map(int,t)))for fi,t in enumerate(faces)if fi not in incident[v]}
                    for t in oldtri:
                        replaced=tuple(u if j==v else j for j in t)
                        if len(set(replaced))<3:continue
                        if tuple(sorted(replaced))in existing:valid=False;break
                        oldn=np.cross(points[t[1]]-points[t[0]],points[t[2]]-points[t[0]]);newn=np.cross(points[replaced[1]]-points[replaced[0]],points[replaced[2]]-points[replaced[0]])
                        if np.linalg.norm(newn)<1e-10 or oldn@newn/max(np.linalg.norm(oldn)*np.linalg.norm(newn),1e-20)<.70:valid=False;break
                        newtri.append(replaced)
                    if not valid:continue
                    oldparts=graph_parts(oldtri,ids);newparts=graph_parts(newtri,ids)
                    # Other incident vertices remain even if an empty local
                    # star would misleadingly count them as deleted.
                    oldparts['nodes']={int(ids[v])};newparts['nodes']=set()
                    benefit=gain(oldparts,newparts,frequency,n)
                    if benefit>0:proposals.append((benefit,'collapse',v,u,newtri,list(incident[v])))
        # Insertion is attempted for source-supported residual vertices on a
        # common interior edge, rather than arbitrary extra subdivisions.
        pool=[(freq,g)for g,freq in frequency['nodes'].items()if g not in current['nodes']and freq>n*.20]
        for _,g in sorted(pool,reverse=True)[:50]:
            neighbors={other for edge,freq in frequency['edges'].items()if g in edge and freq>n*.12 for other in edge if other!=g}
            local={int(ids[v]):v for v in active}
            for(x,y),fs in owners.items():
                if len(fs)!=2 or int(ids[x])not in neighbors or int(ids[y])not in neighbors:continue
                t1,t2=faces[fs];c=next(int(v)for v in t1 if v not in(x,y));d=next(int(v)for v in t2 if v not in(x,y))
                if int(ids[c])not in neighbors or int(ids[d])not in neighbors:continue
                z=len(points);trialids=np.r_[ids,g];oldtri=[tuple(t1),tuple(t2)];newtri=[]
                for t in oldtri:
                    for k in range(3):
                        aa,bb,cc=int(t[k]),int(t[(k+1)%3]),int(t[(k+2)%3])
                        if {aa,bb}=={x,y}:newtri.extend([(aa,z,cc),(z,bb,cc)]);break
                oldparts=graph_parts(oldtri,trialids);newparts=graph_parts(newtri,trialids);oldparts['nodes']=set();newparts['nodes']={g};benefit=gain(oldparts,newparts,frequency,n)
                if benefit>0 and len(active)<maximum:proposals.append((benefit,'split',x,y,newtri,fs,g))
        if not proposals:break
        best=max(proposals,key=lambda x:x[0]);benefit,kind,x,y,newtri,remove=best[:6];keep=[tuple(map(int,t))for i,t in enumerate(faces)if i not in set(remove)]
        if kind=='split':
            g=best[6];points=np.vstack((points,(points[x]+points[y])*.5));ids=np.r_[ids,g];roles=np.r_[roles,roles[x]];uv=np.vstack((uv,(uv[x]+uv[y])*.5));weights.append({k:(weights[x].get(k,0)+weights[y].get(k,0))*.5 for k in set(weights[x])|set(weights[y])});used.append(-1)
        faces=np.array(keep+newtri);after=surface_signature(faces)
        assert all(after[k]==signature[k]for k in ('components','euler','boundary_edges','nonmanifold_edges')),(kind,signature,after)
        score=sum(network_distance(graph_parts(faces,ids),g)['total']for g in state['graphs']);assert previous-score==benefit,(previous,score,benefit)
        edits.append(dict(kind=kind,removed_vertex=int(x)if kind=='collapse'else None,retained_vertex=int(y)if kind=='collapse'else None,inserted_global_vertex=int(best[6])if kind=='split'else None,objective_reduction=int(benefit),resulting_vertices=after['vertices']))
        previous=score
        if(iteration+1)%10==0:print('CONSTRAINED_VERTEX_EDITS',iteration+1,'vertices',after['vertices'],'objective',score,flush=True)
    active=sorted(set(int(v)for t in faces for v in t));lookup={v:i for i,v in enumerate(active)};compactfaces=np.array([[lookup[int(v)]for v in t]for t in faces]);canonical=dict(base,points=points[active],faces=compactfaces,roles=roles[active],weights=[weights[v]for v in active],uv=uv[active],used=[used[v]for v in active])
    state.update(canonical_model=canonical,canonical_global_ids=ids[active],faces=compactfaces,score=previous,vertex_edits=edits)
    with(a.output/'best-state.pkl').open('wb')as f:pickle.dump(state,f,protocol=5)
    report.update(total_objective=previous,canonical_vertices=len(active),canonical_triangles=len(compactfaces),vertex_edit_search_attempted=True,vertex_edits=edits,
        objective_before_vertex_edits=report['total_objective'],vertex_budget=[minimum,maximum],surface_signature_after=surface_signature(compactfaces),
        topological_components_holes_boundaries_preserved=True,globally_optimal_proven=False)
    report['differences']=[dict(id=m['id'],**network_distance(graph_parts(compactfaces,ids[active]),g))for m,g in zip(models,state['graphs'])]
    write(a.output/'optimization.json',report);print('MEDIAN_VERTEX_REFINEMENT_COMPLETE',len(edits),len(active),previous,flush=True)

if __name__=='__main__':main()
