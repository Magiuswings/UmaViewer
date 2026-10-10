"""Landmark-preserving forehead correspondence, independent of whole-loop phase."""
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import factorized
from scipy.optimize import linear_sum_assignment
from arap_registration import loops

def top_path(points,chain):
    values=points[chain];a=int(np.argmax(values[:,0]));b=int(np.argmin(values[:,0]));n=len(chain)
    forward=[chain[(a+k)%n]for k in range((b-a)%n+1)];backward=[chain[(a-k)%n]for k in range((a-b)%n+1)]
    path=max((forward,backward),key=lambda c:float(points[c,1].mean()))
    p=points[path];height=float(p[:,1].max()-points[chain,1].min());band=np.flatnonzero(p[:,1]>=p[:,1].max()-.15*height)
    left=int(band[np.argmax(p[band,0])]);right=int(band[np.argmin(p[band,0])])
    if left>right:left,right=right,left
    return path,[0,left,right,len(path)-1]

def sample_open(points,chain,parameters):
    p=points[chain];length=np.linalg.norm(np.diff(p,axis=0),axis=1);cumulative=np.r_[0,np.cumsum(length)];distance=np.asarray(parameters)*cumulative[-1]
    segment=np.clip(np.searchsorted(cumulative,distance,side='right')-1,0,len(p)-2);coef=(distance-cumulative[segment])/np.maximum(length[segment],1e-15)
    return p[segment]+coef[:,None]*(p[segment+1]-p[segment])

def point_segment_distance(points,a,b):
    edge=b-a;t=np.clip((points-a)@edge/max(edge@edge,1e-20),0,1);return np.linalg.norm(points-(a+t[:,None]*edge),axis=1)

def preserve_knots(template_points,source_points,count,protected):
    if len(source_points)==count:return source_points.copy(),list(range(count)),0.
    if len(source_points)>count:
        active=list(range(len(source_points)));protected=set(protected)
        while len(active)>count:
            trials=[]
            for k in range(1,len(active)-1):
                if active[k]in protected:continue
                a,b=active[k-1],active[k+1];error=float(point_segment_distance(source_points[a:b+1],source_points[a],source_points[b]).max());trials.append((error,k))
            if not trials:raise ValueError('More protected contour landmarks than template slots')
            _,k=min(trials);active.pop(k)
        error=max(float(point_segment_distance(source_points[a:b+1],source_points[a],source_points[b]).max())for a,b in zip(active,active[1:]))
        return source_points[active],active,error
    # Assign every original source corner to a unique ordered template slot;
    # any extra template nodes sample the intervening original edge exactly.
    def parameters(p):
        length=np.linalg.norm(np.diff(p,axis=0),axis=1);return np.r_[0,np.cumsum(length)]/max(sum(length),1e-15)
    tp=parameters(template_points);sp=parameters(source_points);cost=(sp[:,None]-tp[None])**2;cost[0]=1e6;cost[0,0]=0;cost[-1]=1e6;cost[-1,-1]=0
    rows,cols=linear_sum_assignment(cost);slots=cols[np.argsort(rows)];assert np.all(np.diff(slots)>0)
    result=np.zeros((count,3))
    for j in range(len(slots)-1):
        a,b=int(slots[j]),int(slots[j+1]);t=(tp[a:b+1]-tp[a])/max(tp[b]-tp[a],1e-15);result[a:b+1]=source_points[j]*(1-t[:,None])+source_points[j+1]*t[:,None]
    return result,slots.tolist(),0.

def forehead_targets(template,faces,source_points,source_faces):
    p,inverse,pl=loops(template,faces);q,source_inverse,ql=loops(source_points,source_faces)
    perimeter=lambda a,c:float(np.linalg.norm(a[c]-np.roll(a[c],-1,axis=0),axis=1).sum())
    pc=max(pl,key=lambda c:perimeter(p,c));qc=max(ql,key=lambda c:perimeter(q,c));pp,pa=top_path(p,pc);qp,qa=top_path(q,qc);targets={}
    positions,retained,error=preserve_knots(p[pp],q[qp],len(pp),qa)
    for v,point in zip(pp,positions):targets[int(v)]=point
    return p,inverse,targets,dict(template_top_nodes=pp,source_anchor_positions=[q[qp[i]].tolist()for i in qa],source_top_nodes=qp,source_contour_nodes=len(qp),retained_contour_knots=retained,source_contour_simplification_error_m=error)

def repair(template,faces,old_target,source_points,source_faces):
    p,inverse,goals,details=forehead_targets(template,faces,source_points,source_faces);n=len(p);counts=np.bincount(inverse);old=np.zeros((n,3));np.add.at(old,inverse,old_target);old/=counts[:,None]
    f=inverse[faces];edges=np.array(sorted({tuple(sorted((int(a),int(b))))for t in f for a,b in zip(t,np.roll(t,-1))if a!=b}));a=np.r_[edges[:,0],edges[:,1]];b=np.r_[edges[:,1],edges[:,0]]
    degree=np.bincount(a,minlength=n).astype(float);L=sparse.diags(degree)-sparse.coo_matrix((np.ones(len(a)),(a,b)),shape=(n,n)).tocsr()
    fixed=np.array(sorted(goals));free=np.array(sorted(set(range(n))-set(fixed)));desired=np.array([goals[int(v)]for v in fixed]);displacement=desired-old[fixed]
    # Screened biharmonic displacement: exact upper boundary, smooth interior,
    # and strong retention around eyes/mouth/lower face.
    y=old[:,1];toplow=float(old[fixed,1].min());retention=np.where(y<toplow-.020,400.,np.where(y<toplow,.5,.015))
    A=(L.T@L+sparse.diags(retention)).tocsc();rhs=-A[free][:,fixed]@displacement;solve=factorized(A[free][:,free]);delta=np.zeros_like(old);delta[fixed]=displacement
    for axis in range(3):delta[free,axis]=solve(rhs[:,axis])
    result=old+delta;t=result[f];area=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)*.5
    details.update(forehead_constraints=len(fixed),maximum_boundary_error_m=float(np.linalg.norm(result[fixed]-desired,axis=1).max()),maximum_displacement_m=float(np.linalg.norm(delta,axis=1).max()),degenerate_faces=int(sum(area<1e-12)),topology_changed=False)
    return result[inverse],details
