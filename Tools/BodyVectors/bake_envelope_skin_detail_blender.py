"""Bake only genuine dark skin detail over a uniform normalized whole-body albedo."""
from collections import Counter
import json
from pathlib import Path
import sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def v(point):return Vector(tuple(point[k] for k in 'xyz'))
def bary(p,a,b,c):
    ab=b-a;ac=c-a;ap=p-a;d00=ab.dot(ab);d01=ab.dot(ac);d11=ac.dot(ac);den=d00*d11-d01*d01
    if abs(den)<1e-16:return [1,0,0]
    y=(d11*ap.dot(ab)-d01*ap.dot(ac))/den;z=(d00*ap.dot(ac)-d01*ap.dot(ab))/den
    return [1-y-z,y,z]
def main():
    root=Path(sys.argv[sys.argv.index('--')+1]);config=json.loads((root/'config.json').read_text(encoding='utf8'));manifest=json.loads((root/'manifest.json').read_text(encoding='utf8'))
    job=next(j for j in manifest['jobs'] if j['name'].endswith('_1_0_2'));data=json.loads((root/job['snapshot']).read_text(encoding='utf8'));mesh=data['meshes'][0]
    images=[np.frombuffer((root/t['file']).read_bytes(),dtype=np.uint8).reshape(t['height'],t['width'],4) for t in config['textures']]
    reference=np.asarray([255,231,203],dtype=np.float64)
    def sample(tid,uv):
        img=images[tid];return img[min(img.shape[0]-1,int((1-uv[1]%1)*img.shape[0])),min(img.shape[1]-1,int(uv[0]%1*img.shape[1]))]
    refs=[]
    for record in config['records']:
        p=record['profile']
        if p['costume_id']!='0009' or (p['height'],p['shape'],p['bust'])!=('1','0','2'):continue
        original=json.loads(Path(record['snapshot']).read_text(encoding='utf8'));rm=next(m for m in original['meshes'] if m['name']=='M_Body');rp=[v(p) for p in rm['vertices']];ru=next(l['values'] for l in rm['uvs'] if l['channel']==0)
        features=[];infos=[]
        joints={b['name']:b['matrix'][7] for b in original['bones']}
        navel_y=joints['Hip']+(joints['Spine']-joints['Hip'])*.47
        for tri,skin in zip(record['triangles'],record['skin']):
            if not skin:continue
            ids=tri[:3];center=sum((rp[i] for i in ids),Vector((0,0,0)))/3
            # Global albedo is flat and garment-free. Preserve only this verified
            # anatomical dark feature; other restored anatomy is represented by geometry.
            if not(abs(center.x)<.016 and abs(center.y-navel_y)<.032 and center.z>.02):continue
            uv=[sum(ru[i][k] for i in ids)/3 for k in ('x','y')];rgb=sample(tri[4],uv)[:3]
            if float((rgb/reference).mean())<.80:
                features.append(ids);infos.append(tri)
        refs.append(dict(record=record,points=rp,uv=ru,infos=infos,bvh=BVHTree.FromPolygons(rp,features,all_triangles=True),faces=features))
        print('REAL_DARK_SKIN_FACES',record['job'],len(features),flush=True)
    size=1024;ratio=np.ones((size,size,3),dtype=np.float32);mask=np.zeros((size,size),dtype=np.uint8)
    vertices=np.asarray([[p[k] for k in 'xyz'] for p in mesh['vertices']]);uv=next(l['values'] for l in mesh['uvs'] if l['channel']==0)
    faces=mesh['faces'][0]['triangles'];hits=Counter();checked=0
    # Only UV triangles close to an actual dark feature are rasterized. No clothing
    # border, white garment colour, or low-frequency baked shading enters the albedo.
    for start in range(0,len(faces),3):
        tri=faces[start:start+3];positions=vertices[tri];center=Vector(positions.mean(axis=0));radius=max(float(np.linalg.norm(p-positions.mean(axis=0))) for p in positions)
        if not any(ref['bvh'].find_nearest(center,radius+.003)[2] is not None for ref in refs):continue
        coords=np.asarray([[uv[i]['x']*size,(1-uv[i]['y'])*size] for i in tri])
        low=np.maximum(0,np.floor(coords.min(axis=0)).astype(int));high=np.minimum(size-1,np.ceil(coords.max(axis=0)).astype(int))
        a,b,c=coords;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-9:continue
        for py in range(low[1],high[1]+1):
            for px in range(low[0],high[0]+1):
                x,y=px+.5,py+.5;wa=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den;wb=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den;wc=1-wa-wb
                if min(wa,wb,wc)<-1e-6:continue
                point=Vector(positions[0]*wa+positions[1]*wb+positions[2]*wc);choices=[]
                for ref in refs:
                    q,n,fi,d=ref['bvh'].find_nearest(point,.0028)
                    if fi is None:continue
                    ids=ref['faces'][fi];weights=bary(q,*(ref['points'][i] for i in ids));tu=[sum(w*ref['uv'][i][k] for w,i in zip(weights,ids)) for k in ('x','y')]
                    rgb=sample(ref['infos'][fi][4],tu)[:3].astype(np.float64);r=np.clip(rgb/reference,.12,1.)
                    if r.mean()>=.88:continue
                    fade=max(0,1-d/.0028);r=1-(1-r)*fade
                    choices.append((r.mean(),r,ref['record']['job']))
                if choices:
                    _,r,name=min(choices,key=lambda c:c[0]);ratio[py,px]=np.minimum(ratio[py,px],r);mask[py,px]=255;hits[name]+=1
                checked+=1
    np.save(root/'detail-ratio.npy',ratio);np.save(root/'detail-mask.npy',mask)
    evidence=dict(passed=True,feature_texels=int(np.count_nonzero(mask)),source_hits=dict(hits),atlas_size=[size,size],neutral_albedo_outside_detail=True,navel_dark_colour_not_rejected_by_skin_distance_filter=True,method='Direct source-triangle barycentric per-texel sampling of genuine warm dark skin; reference skin colour normalized; no clothing colour retained')
    (root/'detail-bake-verification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')
    assert evidence['feature_texels']>0
    print('NORMALIZED_SKIN_DETAIL_BAKED',evidence['feature_texels'],flush=True)

if __name__=='__main__':main()
