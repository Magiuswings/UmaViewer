"""ARAP source-surface registration after a vertex network has been selected."""
from collections import Counter,defaultdict
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import factorized
from scipy.spatial import cKDTree
from scipy.optimize import minimize_scalar

def loops(points,faces):
    _,inverse=np.unique(np.round(points,6),axis=0,return_inverse=True);weld=np.zeros((int(inverse.max())+1,3));count=np.bincount(inverse);np.add.at(weld,inverse,points);weld/=count[:,None]
    edges=Counter(tuple(sorted((int(a),int(b))))for t in inverse[faces]for a,b in zip(t,np.roll(t,-1))if a!=b);adj=defaultdict(set)
    for(a,b),n in edges.items():
        if n==1:adj[a].add(b);adj[b].add(a)
    result=[];visited=set()
    for first in adj:
        if first in visited or len(adj[first])!=2:continue
        chain=[];old=None;now=first
        for _ in range(len(adj)+1):
            if now in visited or len(adj[now])!=2:break
            chain.append(now);visited.add(now);nexts=adj[now]-({old}if old is not None else set());nxt=min(nexts)
            old,now=now,nxt
            if now==first:
                if len(chain)>=3:result.append(chain)
                break
    return weld,inverse,result

def sample_loop(points,chain,parameter):
    p=points[chain];after=np.roll(p,-1,axis=0);length=np.linalg.norm(after-p,axis=1);cumulative=np.r_[0,np.cumsum(length)];total=cumulative[-1]
    distance=(np.asarray(parameter)%1)*total;segment=np.searchsorted(cumulative,distance,side='right')-1;segment=np.clip(segment,0,len(p)-1);coef=(distance-cumulative[segment])/np.maximum(length[segment],1e-15)
    return p[segment]+coef[:,None]*(after[segment]-p[segment])

def register(template,faces,source_points,source_faces,Surface,iterations=25):
    p,inverse,pl=loops(template,faces);target,ti,tl=loops(source_points,source_faces);n=len(p);f=inverse[faces]
    edge=np.array(sorted({tuple(sorted((int(a),int(b))))for t in f for a,b in zip(t,np.roll(t,-1))if a!=b}));a=np.r_[edge[:,0],edge[:,1]];b=np.r_[edge[:,1],edge[:,0]];delta=p[a]-p[b]
    degree=np.bincount(a,minlength=n).astype(float);L=sparse.diags(degree)-sparse.coo_matrix((np.ones(len(a)),(a,b)),shape=(n,n)).tocsr()
    # Robust initial scale/translation helps the sparse vertex-only anatomy,
    # while leaving outlying accessory vertices out of this initialization.
    lo,hi=np.quantile(p,[.05,.95],axis=0);tlo,thi=np.quantile(target,[.05,.95],axis=0);scale=np.clip((thi-tlo)/np.maximum(hi-lo,1e-8),.65,1.5)
    q=(p-(lo+hi)*.5)*scale+(tlo+thi)*.5
    # Baseline for ARAP is the scaled template, so ordinary face size changes
    # do not fight the local edge-preservation term.
    rest=q.copy();delta=rest[a]-rest[b];constraints={};matches=[];used=set()
    perimeter=lambda pts,chain:float(np.linalg.norm(pts[chain]-np.roll(pts[chain],-1,axis=0),axis=1).sum())
    for chain in sorted(pl,key=lambda c:-perimeter(q,c)):
        source_center=q[chain].mean(0);source_perimeter=sum(np.linalg.norm(q[chain]-np.roll(q[chain],-1,axis=0),axis=1));candidates=[]
        for j,tc in enumerate(tl):
            if j in used:continue
            center=target[tc].mean(0);perimeter=sum(np.linalg.norm(target[tc]-np.roll(target[tc],-1,axis=0),axis=1));distance=np.linalg.norm(center-source_center)
            ratio=perimeter/max(source_perimeter,1e-12)
            template_side=0 if abs(source_center[0])<.006 else np.sign(source_center[0]);target_side=0 if abs(center[0])<.006 else np.sign(center[0])
            if distance>(.055 if source_perimeter>.20 else .028)or not .40<ratio<2.5 or template_side!=target_side:continue
            candidates.append((distance+.006*abs(np.log(max(perimeter,1e-12)/max(source_perimeter,1e-12))),j))
        if not candidates:continue
        _,j=min(candidates);tc=tl[j];used.add(j)
        lengths=np.linalg.norm(q[chain]-np.roll(q[chain],-1,axis=0),axis=1);parameter=np.r_[0,np.cumsum(lengths[:-1])]/max(sum(lengths),1e-12);best=None
        for direction in (1,-1):
            order=tc if direction==1 else list(reversed(tc))
            for shift in np.linspace(0,1,64,endpoint=False):
                samples=sample_loop(target,order,parameter+shift);error=float(np.mean(np.sum((samples-q[chain])**2,axis=1)))
                if best is None or error<best[0]:best=(error,samples,order,shift)
        def error_for_shift(shift):return float(np.mean(np.sum((sample_loop(target,best[2],parameter+shift)-q[chain])**2,axis=1)))
        refined=minimize_scalar(error_for_shift,bounds=(best[3]-1/64,best[3]+1/64),method='bounded',options={'xatol':1e-7})
        if refined.fun<best[0]:best=(float(refined.fun),sample_loop(target,best[2],parameter+refined.x),best[2],float(refined.x))
        # Nearby real boundary loops get unique arc-length samples; several
        # template vertices may not snap to the same source edge endpoint.
        if np.sqrt(best[0])<.025:
            for v,point in zip(chain,best[1]):constraints[v]=point
            matches.append(dict(template_vertices=len(chain),source_vertices=len(tc),rms_initial_mm=float(np.sqrt(best[0])*1000)))
    surface=Surface(source_points,source_faces);initial=q.copy();records=[]
    for stage,lam in enumerate((.015,.04,.12,.35,.75)):
        dataweight=np.full(n,lam)
        if constraints:dataweight[list(constraints)]=15.
        solve=factorized((L+sparse.diags(dataweight)+sparse.eye(n)*1e-8).tocsc())
        for step in range(max(1,iterations//5)):
            normals=np.zeros_like(q);t=q[f];fn=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
            for slot in range(3):np.add.at(normals,f[:,slot],fn)
            normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-20)
            _,_,goal,_=surface.nearest_many(q,normals)
            for v,point in constraints.items():goal[v]=point
            deformed=q[a]-q[b];cov=np.zeros((n,3,3));np.add.at(cov,a,np.einsum('ni,nj->nij',deformed,delta))
            u,s,vh=np.linalg.svd(cov);rotation=u@vh;bad=np.linalg.det(rotation)<0;u[bad,:,2]*=-1;rotation=u@vh
            rhs=np.zeros((n,3));value=np.einsum('nij,nj->ni',(rotation[a]+rotation[b])*.5,delta);np.add.at(rhs,a,value);rhs+=dataweight[:,None]*goal
            trial=np.column_stack([solve(rhs[:,k])for k in range(3)])
            # A bounded step avoids one nearest-surface switch collapsing a
            # loop or jumping across a thin eyelid/mouth layer.
            movement=trial-q;length=np.linalg.norm(movement,axis=1);movement*=np.minimum(1,.004/np.maximum(length,1e-15))[:,None]
            old=t;oldn=fn;oldarea=np.linalg.norm(oldn,axis=1);alpha=1.
            for _ in range(10):
                candidate=q+alpha*movement;new=candidate[f];newn=np.cross(new[:,1]-new[:,0],new[:,2]-new[:,0]);newarea=np.linalg.norm(newn,axis=1)
                if np.all(newarea>np.maximum(oldarea*.02,1e-11))and np.all(np.sum(newn*oldn,axis=1)>0):break
                alpha*=.5
            q+=alpha*movement
        records.append(dict(stage=stage,surface_weight=lam))
    report=dict(method='ARAP local/global registration on geometric weld classes, unique boundary arc samples, bounded surface steps',iterations=iterations,geometric_vertices=n,matched_boundary_loops=matches,stages=records)
    return q[inverse],report
