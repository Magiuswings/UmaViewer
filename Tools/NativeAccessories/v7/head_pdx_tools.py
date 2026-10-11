from pathlib import Path
import os
import xml.etree.ElementTree as X
import numpy as np
from scipy.spatial.transform import Rotation

def pts(v):return np.array([[x[k]for k in 'xyz']for x in v],float)
def world(skel):
    result=[]
    for b in sorted(skel,key=lambda b:b.get('ix')[0]):
        inv=np.eye(4);inv[:3]=np.array(b.get('tx')).reshape(4,3).T;result.append(np.linalg.inv(inv))
    return np.array(result)
def skeleton(names,parents,worlds):
    sk=X.Element('skeleton')
    ordered=[];seen=set()
    def add(i):
        if i in seen:return
        if parents[i]is not None:add(parents[i])
        seen.add(i);ordered.append(i)
    for i in range(len(names)):add(i)
    for i in ordered:
        n,pa,w=names[i],parents[i],worlds[i]
        props={'ix':[i],'tx':np.linalg.inv(w)[:3].T.ravel().tolist()}
        if pa is not None:props['pa']=[pa]
        X.SubElement(sk,n,props)
    return sk
def make_mesh(P,path,shape,p,n,uv,tri,ix,w,sk,shader,prefix):
    assert np.isfinite(p).all()and np.isfinite(n).all()and np.isfinite(w).all();assert np.abs(w.sum(1)-1).max()<1e-5
    tangent=np.zeros_like(p)
    for row in tri:
        dp=p[row[1:]]-p[row[0]];du=uv[row[1:]]-uv[row[0]];det=np.linalg.det(du)
        if abs(det)>1e-12:tangent[row]+=(dp[0]*du[1,1]-dp[1]*du[0,1])/det
    tangent-=n*np.sum(n*tangent,axis=1)[:,None];length=np.linalg.norm(tangent,axis=1);bad=length<1e-8;tangent[bad]=np.cross(n[bad],[0.,1.,0.]);length=np.linalg.norm(tangent,axis=1);bad=length<1e-8;tangent[bad]=np.cross(n[bad],[1.,0.,0.]);tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-20)
    file=X.Element('File',{'pdxasset':[1,0]});obj=X.SubElement(file,'object');sh=X.SubElement(obj,shape,{'lod':[0]});m=X.SubElement(sh,'mesh')
    for key,val in [('p',p),('n',n),('ta',np.column_stack([tangent,np.ones(len(p))])),('u0',uv),('tri',tri)]:m.set(key,val.ravel().tolist())
    mid=(p.min(0)+p.max(0))/2;m.set('boundingsphere',np.r_[mid,np.linalg.norm(p-mid,axis=1).max()].tolist());X.SubElement(m,'aabb',{'min':p.min(0).tolist(),'max':p.max(0).tolist()})
    X.SubElement(m,'material',{'shader':[shader],'diff':[prefix+'_diffuse.dds'],'n':[prefix+'_normal.dds'],'spec':[prefix+'_properties.dds']});X.SubElement(m,'skin',{'bones':[4],'ix':ix.ravel().tolist(),'w':w.ravel().tolist()});sh.append(sk)
    P.write_meshfile(str(path),file);read=P.read_meshfile(str(path));actual=np.array(read.find('object')[0].find('mesh').get('p')).reshape(-1,3);error=float(np.abs(actual-p).max());assert error<1e-4
    return {'vertices':len(p),'triangles':len(tri),'bones':len(sk),'binary_position_error_cm':error,'shape':shape,'shader':shader,'texture_prefix':prefix}
def make_anim(P,path,names,parents,source_world,K,C,source_tracks,count):
    CI=np.linalg.inv(C);local=[];decomposed=[]
    for i,n in enumerate(names):
        pa=parents[i];sl=np.linalg.inv(source_world[pa])@source_world[i]if pa is not None else source_world[i];frames=source_tracks.get(n,np.tile(sl,(count,1,1)));matrix=C@frames@CI
        if pa is None:matrix=K@matrix
        s=np.linalg.norm(matrix[:,:3,:3],axis=1);r=matrix[:,:3,:3]/s[:,None,:];q=Rotation.from_matrix(r).as_quat()
        for f in range(1,count):
            if np.dot(q[f-1],q[f])<0:q[f]*=-1
        d={'t':matrix[:,:3,3],'q':q,'s':s};decomposed.append(d);local.append(matrix)
    file=X.Element('File',{'pdxasset':[1,0]});info=X.SubElement(file,'info',{'fps':[30.],'sa':[count],'j':[len(names)]});channels=[]
    for n,d in zip(names,decomposed):
        cs=''.join(c for c in ['t','q','s']if np.abs(d[c]-d[c][0]).max()>1e-7);channels.append(cs);X.SubElement(info,n,{'sa':[cs],**{c:d[c][0].tolist()for c in ['t','q','s']}})
    samples=X.SubElement(file,'samples')
    for c in ['t','q','s']:
        arrays=[d[c]for d,cs in zip(decomposed,channels)if c in cs]
        if arrays:samples.set(c,np.stack(arrays,axis=1).ravel().tolist())
    path.parent.mkdir(parents=True,exist_ok=True);P.write_animfile(str(path),file);read=P.read_meshfile(str(path));assert read.find('info').get('sa')==[count];maximum=0
    for c,width in [('t',3),('q',4),('s',3)]:
        active=[i for i,cs in enumerate(channels)if c in cs];packed=np.array(read.find('samples').get(c)or[]).reshape(count,len(active),width)if active else None
        for i,d in enumerate(decomposed):actual=packed[:,active.index(i)]if i in active else np.tile(read.find('info')[i].get(c),(count,1));maximum=max(maximum,float(np.abs(actual-d[c]).max()))
    assert maximum<2e-5
    world_frames=[]
    for i,L in enumerate(local):world_frames.append(world_frames[parents[i]]@L if parents[i]is not None else L)
    world_frames=np.stack(world_frames,axis=1);drift=float(np.linalg.norm(world_frames[:,0,:3,3]-world_frames[0,0,:3,3],axis=1).max());assert drift<1e-4
    amplitude=max(float(np.rad2deg((Rotation.from_quat(d['q'][0]).inv()*Rotation.from_quat(d['q'])).magnitude()).max())for d in decomposed)
    return {'frames':count,'fps':30,'bones':len(names),'amplitude_degrees':amplitude,'root_drift_cm':drift,'binary_sample_error':maximum,'animated_channels':{n:c for n,c in zip(names,channels)if c},'endpoint_matrix_difference':float(max(np.abs(l[-1]-l[0]).max()for l in local))}
