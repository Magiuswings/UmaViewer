"""Sample actual Unity transform/locator clips; no synthetic oscillations."""
import struct,zlib
import numpy as np
from scipy.spatial.transform import Rotation

EAR_TAGS=['Base','Base_N','Kanasi','Dere_N','Dere','Yure','Biku_N','Biku','Ikari','Tanosi','Up_N','Up','Down','Front','Side','Back','Roll']
def path_hash(path):return zlib.crc32(path.encode())&0xffffffff
def vector(v):return np.array([v[k]for k in 'xyz'],float)if isinstance(v,dict)else np.array([v.x,v.y,v.z],float)

def sample_clip(clip,fps=30):
    muscle=clip.m_MuscleClip;data=muscle.m_Clip.data;stream=data.m_StreamedClip;dense=data.m_DenseClip;constant=data.m_ConstantClip;start=float(muscle.m_StartTime);stop=float(muscle.m_StopTime);times=np.arange(round((stop-start)*fps)+1)/fps+start
    count=stream.curveCount+dense.m_CurveCount+len(constant.data);values=np.zeros((len(times),count),float);records=[[]for _ in range(stream.curveCount)]
    raw=np.array(stream.data,dtype='<u4').tobytes();offset=0
    while offset+8<=len(raw):
        t,n=struct.unpack_from('<fi',raw,offset);offset+=8
        for _ in range(n):
            i,*coeff=struct.unpack_from('<i4f',raw,offset);offset+=20;records[i].append((t,np.array(coeff)))
    for i,keys in enumerate(records):
        usable=[(t,c)for t,c in keys if np.isfinite(t)]
        if not usable:continue
        kt=np.array([t for t,c in usable]);coef=np.array([c for t,c in usable]);ix=np.clip(np.searchsorted(kt,times,side='right')-1,0,len(kt)-1);dt=np.maximum(times-kt[ix],0);c=coef[ix];values[:,i]=((c[:,0]*dt+c[:,1])*dt+c[:,2])*dt+c[:,3]
    if dense.m_CurveCount:
        samples=np.array(dense.m_SampleArray).reshape(dense.m_FrameCount,dense.m_CurveCount);t=dense.m_BeginTime+np.arange(dense.m_FrameCount)/dense.m_SampleRate
        for i in range(dense.m_CurveCount):values[:,stream.curveCount+i]=np.interp(times,t,samples[:,i])
    if constant.data:values[:,stream.curveCount+dense.m_CurveCount:]=constant.data
    tracks=[];offset=0
    for b in clip.m_ClipBindingConstant.genericBindings:
        size={1:3,2:4,3:3,4:3}.get(b.attribute,1);tracks.append(dict(hash=b.path,attribute=b.attribute,values=values[:,offset:offset+size]));offset+=size
    assert offset==count,(clip.m_Name,offset,count)
    return times,tracks

def transform_paths(env):
    transforms={};objects={}
    for o in env.objects:
        if o.type.name=='Transform':transforms[o.path_id]=o.read()
        elif o.type.name=='GameObject':objects[o.path_id]=o.read().m_Name
    cache={}
    def path(i):
        if i not in cache:
            t=transforms[i];parent=t.m_Father.path_id;cache[i]=(path(parent)+'/'if parent in transforms else'')+objects[t.m_GameObject.path_id]
        return cache[i]
    result={}
    for i in transforms:
        full=path(i);parts=full.split('/')
        for cut in range(len(parts)):result[path_hash('/'.join(parts[cut:]))]='/'.join(parts[cut:])
    return result

def ear_local_frames(times,tracks,hashes,targets):
    table=targets['_targetFaces'];names=sorted({x['_path']for side in table[0]['_faceGroupInfo']for x in side['_trsArray']});base={x['_path']:x for side in table[0]['_faceGroupInfo']for x in side['_trsArray']};t={n:np.tile(vector(base[n]['_position']),(len(times),1))for n in names};s={n:np.tile(vector(base[n]['_scale']),(len(times),1))for n in names};angles={n:np.tile(vector(base[n]['_rotation']),(len(times),1))for n in names};used=[]
    for track in tracks:
        path=hashes.get(track['hash']);assert path is not None,('Unresolved locator',track['hash']);name=path.rsplit('/',1)[-1]
        if track['attribute']!=1:continue
        matches=[i for i,tag in enumerate(EAR_TAGS)if i and name.endswith(tag)];assert matches,(path,name);index=max(matches,key=lambda i:len(EAR_TAGS[i]));side=1 if'Ear_L_Ctrl'in path else 0;weight=track['values'][:,0]*-100;used.append(path)
        for item in table[index]['_faceGroupInfo'][side]['_trsArray']:
            n=item['_path'];t[n]+=weight[:,None]*vector(item['_position']);s[n]+=weight[:,None]*vector(item['_scale']);angles[n]+=weight[:,None]*vector(item['_rotation'])
    frames={}
    for n in names:
        r=Rotation.from_euler('xyz',angles[n],degrees=True).as_matrix();m=np.tile(np.eye(4),(len(times),1,1));m[:,:3,:3]=r*s[n][:,None,:];m[:,:3,3]=t[n];frames[n]=m
    return frames,used

def tail_local_frames(times,tracks,data):
    byid={b['id']:b for b in data['bones']};hashes={};world={b['name']:np.array(b['matrix']).reshape(4,4)for b in data['bones']};parents={b['name']:byid[b['parent']]['name']if b.get('parent')else None for b in data['bones']};frames={}
    def path(b):return(path(byid[b['parent']])+'/'if b.get('parent')else'')+b['name']
    for b in data['bones']:
        full=path(b).split('/')
        for cut in range(len(full)):
            suffix='/'.join(full[cut:]);hashes[path_hash(suffix)]=b['name'];hashes[path_hash('Position/'+suffix)]=b['name']
        local=np.linalg.inv(world[parents[b['name']]])@world[b['name']]if parents[b['name']]else world[b['name']];frames[b['name']]=np.tile(local,(len(times),1,1))
    hashes[0]=data['bones'][0]['name'];mapped=[]
    for tr in tracks:
        name=hashes.get(tr['hash']);assert name,('Unknown tail transform path',tr['hash']);mapped.append(name);m=frames[name]
        if tr['attribute']==2:m[:,:3,:3]=Rotation.from_quat(tr['values']).as_matrix()
        elif tr['attribute']==1:m[:,:3,3]=tr['values']
        elif tr['attribute']==3:
            m[:,:3,:3]*=tr['values'][:,None,:]
        else:raise ValueError(tr['attribute'])
    return frames,parents,mapped
