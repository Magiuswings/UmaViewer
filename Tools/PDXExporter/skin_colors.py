"""Area weighted source-diffuse skin statistics; no renders or color-space guessing."""
import math
from pathlib import Path
from PIL import Image

def skin_average(data,job,category,resources,cache):
    if category not in ('body_skin','face','body_base'):return None
    palette=job.get('skin_palette',[])
    acc=[0.,0.,0.];linear=[0.,0.,0.];area=0.;sample_count=0
    def linearize(x):return x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4
    for mesh in data['meshes']:
        if not mesh.get('uvs'):continue
        uv=sorted(mesh['uvs'],key=lambda x:x['channel'])[0]['values']
        for face in mesh['faces']:
            if face['category'] not in ('body_skin','face') or (category!='body_base' and face['category']!=category):continue
            if face['material']<0:continue
            entry=data['materials'][face['material']]
            prop=next((p for p in entry['properties'] if p['name']=='_MainTex' and p.get('texture')),None)
            if not prop:continue
            path=Path(resources)/prop['texture']
            if path not in cache:
                with Image.open(path) as original:cache[path]=original.convert('RGBA')
            image=cache[path];w,h=image.size;pixels=image.load()
            scale=prop.get('scale',[1,1]);offset=prop.get('offset',[0,0])
            for start in range(0,len(face['triangles']),3):
                ids=face['triangles'][start:start+3]
                v=[tuple(mesh['vertices'][i][k] for k in ('x','y','z')) for i in ids]
                a=[v[1][i]-v[0][i] for i in range(3)];b=[v[2][i]-v[0][i] for i in range(3)]
                cross=(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
                tri_area=math.sqrt(sum(c*c for c in cross))/2
                coords=[(uv[i]['x'],uv[i]['y']) for i in ids]
                samples=coords+[((coords[a][0]+coords[b][0])/2,(coords[a][1]+coords[b][1])/2) for a,b in ((0,1),(1,2),(2,0))]
                samples.append((sum(q[0] for q in coords)/3,sum(q[1] for q in coords)/3))
                for u,v in samples:
                    u=(u*scale[0]+offset[0])%1;v=(v*scale[1]+offset[1])%1
                    x=min(w-1,int(u*w));y=min(h-1,int((1-v)*h))
                    r,g,b,alpha=pixels[x,y];rgb=(r,g,b)
                    if alpha<26:continue
                    if palette and not any(sum((c-b)**2 for c,b in zip(rgb,p))<=42**2 for p in palette):continue
                    if not palette and not (r>=g>=b and r-b>15 and g>70 and (r-b)/max(r,1)<.55):continue
                    weight=tri_area/len(samples)
                    for i,c in enumerate(rgb):acc[i]+=c/255*weight;linear[i]+=linearize(c/255)*weight
                    area+=weight;sample_count+=1
    if area==0:return dict(samples=0,status='no_skin_samples')
    return dict(status='sampled',method='7 UV samples per triangle, world-area weighted, alpha/source skin-color filter',
                samples=sample_count,sampled_area=area,rgb_srgb=[c/area for c in acc],
                rgb_srgb_255=[round(c/area*255,3) for c in acc],rgb_linear=[c/area for c in linear],
                palette_srgb_255=palette,threshold_rgb_distance=42,
                includes_lighting=False,color_source='Original PNG diffuse before DDS compression; sRGB encoded')

def collect_skin(manifest,root):
    import json
    records=[];cache={}
    for job in manifest['jobs']:
        data=json.loads((root/job['snapshot']).read_text(encoding='utf8'))
        categories=[c for c in job['categories'] if c in ('body_skin','face')]
        if any(b['name']==job['name'] for b in manifest.get('body_bases',[])):categories.append('body_base')
        for c in categories:
            avg=skin_average(data,job,c,root/manifest['resources'],cache)
            if avg:records.append(dict(character_id=data['character_id'],character_name=data.get('character_name',''),source=data['source'],variant=data['variant'],category=c,**avg))
    primary={}
    for record in records:
        cid=record['character_id']
        if record['category']=='face' and (cid not in primary or record['variant']=='80'):
            primary[cid]=record
    return dict(records=records,character_face_reference=primary,
                method='Area weighted diffuse skin texels, 7 samples per triangle; variant records kept separately')
