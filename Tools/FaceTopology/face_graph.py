"""Source vertex networks and a geometry-independent edit-count objective."""
from collections import Counter,defaultdict,deque
import hashlib,json
from pathlib import Path
import numpy as np

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def load_models(root,scope='whole'):
    manifest=json.loads((root/'face-inputs/manifest.json').read_text(encoding='utf8'));models=[]
    for job in manifest['jobs']:
        data=json.loads((root/'face-inputs'/job['snapshot']).read_text(encoding='utf8'));mesh=data['meshes'][0]
        rawfaces=[t for f in mesh['faces']for t in np.array(f['triangles']).reshape(-1,3).tolist()];used=sorted(set(v for t in rawfaces for v in t));compact={v:i for i,v in enumerate(used)}
        faces=np.array([[compact[v]for v in t]for t in rawfaces]);bones={b['id']:b['name']for b in data['bones']}
        head=next((b for b in data['bones']if b['name']=='Head'),None);anchor=np.linalg.inv(np.array(head['matrix']).reshape(4,4))if head else np.eye(4)
        p=np.array([[mesh['vertices'][v][k]for k in 'xyz']+[1.]for v in used])@anchor.T;p=p[:,:3]
        normal=np.array([[mesh['normals'][v][k]for k in 'xyz']for v in used]);normal=normal@np.linalg.inv(anchor[:3,:3]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12)
        weights=[defaultdict(float)for _ in used]
        for w in mesh['weights']:
            if w['vertex']in compact:
                name=bones[w['bone']];name='__root'if name.startswith('pfb_')else name;weights[compact[w['vertex']]][name]+=w['weight']
        roles=np.zeros(len(used),np.int8);face_roles=[]
        for section in mesh['faces']:
            for tri in np.array(section['triangles']).reshape(-1,3):
                if section['category']=='eyes':roles[[compact[v]for v in tri]]=2
                face_roles.append(2 if section['category']=='eyes'else 0)
        for i,ws in enumerate(weights):
            if roles[i]!=2 and sum(w for n,w in ws.items()if n.lower().startswith(('tooth','tongue','mouth_in')))>.5:roles[i]=1
        if scope=='skin':
            # Skin only; keep eye/teeth/tongue sections in the immutable input
            # snapshot rather than forcing them into another component's graph.
            keep=np.all(roles[faces]==0,axis=1);faces=faces[keep];face_roles=np.array(face_roles)[keep].tolist()
            selected=sorted(set(int(v)for t in faces for v in t));remap={v:i for i,v in enumerate(selected)}
            faces=np.array([[remap[int(v)]for v in t]for t in faces]);used=[used[i]for i in selected];p=p[selected];normal=normal[selected];weights=[weights[i]for i in selected];roles=roles[selected]
            # The face material also includes physically separate eye whites,
            # eyelid/crease patches and other overlays. Keep the largest
            # geometrically connected skin shell; retain every other source
            # part in the immutable M_Face snapshot.
            _,weld=np.unique(np.round(p,6),axis=0,return_inverse=True);wadj=defaultdict(set)
            for t in weld[faces]:
                for aa,bb in zip(t,np.roll(t,-1)):wadj[int(aa)].add(int(bb));wadj[int(bb)].add(int(aa))
            seen=set();components=[]
            for start in wadj:
                if start in seen:continue
                todo=[start];seen.add(start);part=[]
                while todo:
                    v=todo.pop();part.append(v)
                    for j in wadj[v]:
                        if j not in seen:seen.add(j);todo.append(j)
                components.append(part)
            largest=max(components,key=lambda part:sum(np.isin(weld,part)));selected=np.flatnonzero(np.isin(weld,largest));active=set(map(int,selected));keep=np.array([all(int(v)in active for v in t)for t in faces]);faces=faces[keep];face_roles=np.array(face_roles)[keep].tolist();remap={int(v):i for i,v in enumerate(selected)};faces=np.array([[remap[int(v)]for v in t]for t in faces]);used=[used[i]for i in selected];p=p[selected];normal=normal[selected];weights=[weights[i]for i in selected];roles=roles[selected]
        adj=[set()for _ in used];edgecounts=Counter()
        for t in faces:
            for a,b in zip(t,np.roll(t,-1)):
                adj[a].add(int(b));adj[b].add(int(a));edgecounts[tuple(sorted((int(a),int(b))))]+=1
        boundaries=np.array([sum(edgecounts[tuple(sorted((i,j)))]==1 for j in adj[i])for i in range(len(used))])
        degree=np.array([len(a)for a in adj]);local=np.zeros((len(used),12))
        for i,neighbors in enumerate(adj):
            for j in neighbors:local[i,min(int(degree[j]),11)]+=1
        components=[];seen=set()
        for i in range(len(used)):
            if i in seen:continue
            stack=[i];seen.add(i);part=[]
            while stack:
                v=stack.pop();part.append(v)
                for j in adj[v]:
                    if j not in seen:seen.add(j);stack.append(j)
            components.append(part)
        component=np.zeros(len(used),int)
        for ci,vs in enumerate(components):component[vs]=ci
        # Positional left/right tags and UVs describe anatomical identity only;
        # they never enter network_distance or the median graph objective.
        sides=np.where(p[:,0]<-.0005,-1,np.where(p[:,0]>.0005,1,0)).astype(np.int8)
        labels=[str(roles[i])+':'+str(sides[i])for i in range(len(used))]
        wl=[str(int(roles[i]))+':'+str(degree[i])+':'+str(boundaries[i])for i in range(len(used))]
        for _ in range(3):wl=[hashlib.sha256((wl[i]+'|'+'|'.join(sorted(wl[j]for j in adj[i]))).encode()).hexdigest()[:16]for i in range(len(used))]
        uv=np.array([[mesh['uvs'][0]['values'][v][k]for k in 'xy']for v in used])
        models.append(dict(id=job['id'],job=job,points=p,normals=normal,faces=faces,weights=weights,roles=roles,face_roles=np.array(face_roles),labels=labels,sides=sides,degree=degree,boundaries=boundaries,local=local,adj=adj,components=components,component=component,edges=set(edgecounts),triangles={tuple(sorted(t))for t in faces},used=used,uv=uv,
            topology_hash=digest(dict(vertex_count=len(used),wl=sorted(wl),triangles=len(faces)))))
    return models

def network(model,ids=None):
    if ids is None:ids=np.arange(len(model['points']))
    ids=np.asarray(ids);return dict(nodes=set(map(int,ids)),edges={tuple(sorted((int(ids[a]),int(ids[b]))))for a,b in model['edges']},triangles={tuple(sorted(int(ids[v])for v in t))for t in model['triangles']})

def network_distance(a,b):
    result={k:len(a[k]^b[k])for k in ('nodes','edges','triangles')};result['total']=sum(result.values());return result

def median_scores(graphs):
    n=len(graphs);frequency={k:Counter(x for g in graphs for x in g[k])for k in ('nodes','edges','triangles')};totals={k:sum(len(g[k])for g in graphs)for k in frequency}
    scores=[sum(totals[k]+n*len(g[k])-2*sum(frequency[k][x]for x in g[k])for k in frequency)for g in graphs]
    return scores,frequency,totals

def topology_audit(models):
    groups=defaultdict(list)
    for m in models:groups[m['topology_hash']].append(m['id'])
    return dict(model_count=len(models),exact_count_range=[min(len(m['points'])for m in models),max(len(m['points'])for m in models)],
        coarse_wl_topology_groups=[dict(hash=h,models=ids,count=len(ids))for h,ids in sorted(groups.items(),key=lambda x:-len(x[1]))],
        wl_hash_is_candidate_group_not_isomorphism_proof=True,
        models=[dict(id=m['id'],vertices=len(m['points']),triangles=len(m['faces']),edges=len(m['edges']),roles={r:int(sum(m['roles']==i))for i,r in enumerate(('skin','oral','eye'))},components=len(m['components']),boundary_edges=int(sum(m['boundaries'])//2),nonmanifold_edges=0)for m in models])
