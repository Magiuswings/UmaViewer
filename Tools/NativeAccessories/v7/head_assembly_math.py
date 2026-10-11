from pathlib import Path
import os
import numpy as np

def trs(t,q,s):
    q=np.array(q,float);q/=np.linalg.norm(q);x,y,z,w=q
    r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    ss=np.array(s if len(s)==3 else s*3,float);m=np.eye(4);m[:3,:3]=r*ss[None];m[:3,3]=t;return m
def readlocals(P,path,frame):
    data=P.read_meshfile(str(path));info=data.find('info');samples=data.find('samples');offset={c:0 for c in 'tqs'};count={c:sum(c in b.get('sa')[0]for b in info)for c in'tqs'};local={}
    for b in info:
        d={c:list(b.get(c))for c in'tqs'}
        for c in'tqs':
            if c not in b.get('sa')[0]:continue
            width=3 if c=='t'else 4 if c=='q'else len(d[c]);start=(frame*count[c]+offset[c])*width;d[c]=samples.get(c)[start:start+width];offset[c]+=1
        local[b.tag]=trs(d['t'],d['q'],d['s'])
    return local
def rigdata(sk):
    nodes=sorted(sk,key=lambda b:b.get('ix')[0]);names=[b.tag for b in nodes];parents=[b.get('pa')[0]if b.get('pa')else None for b in nodes];inv=[]
    for b in nodes:m=np.eye(4);m[:3]=np.array(b.get('tx')).reshape(4,3).T;inv.append(m)
    inv=np.array(inv);bind=np.linalg.inv(inv);local=[np.linalg.inv(bind[p])@bind[i]if p is not None else bind[i]for i,p in enumerate(parents)]
    return {'names':names,'parents':parents,'inv':inv,'bind':bind,'local':local}
def compose(rig,clips=None,delta=None):
    clips=clips or{};delta=delta or{};world=[]
    for i,n in enumerate(rig['names']):
        m=clips.get(n,rig['local'][i]).copy();m[:3,3]+=delta.get(n,np.zeros(3));p=rig['parents'][i];world.append(world[p]@m if p is not None else m)
    return np.array(world)
def shared_pose(rig,carrier,carrierworld):
    lookup={n:i for i,n in enumerate(carrier['names'])};world=[]
    for i,n in enumerate(rig['names']):
        p=rig['parents'][i]
        if n in lookup:world.append(carrierworld[lookup[n]])
        else:world.append(world[p]@rig['local'][i]if p is not None else rig['local'][i])
    return np.array(world)
def deform(node,rig,worlds):
    p=np.column_stack([np.array(node.get('p')).reshape(-1,3),np.ones(len(node.get('p'))//3)]);skin=node.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);w=np.array(skin.get('w')).reshape(-1,4);m=worlds@rig['inv'];result=np.zeros((len(p),3))
    for slot in range(4):result+=np.einsum('vij,vj->vi',m[np.maximum(ix[:,slot],0)],p)[:,:3]*w[:,slot,None]
    return result
