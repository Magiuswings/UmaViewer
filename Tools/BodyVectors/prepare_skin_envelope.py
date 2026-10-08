"""Classify real skin in selected common inputs and prepare inward-envelope reconstruction."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from PIL import Image

SAMPLES=((1,0,0),(0,1,0),(0,0,1),(.5,.5,0),(0,.5,.5),(.5,0,.5),(1/3,1/3,1/3))
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
def warm(rgb,alpha):
    r,g,b=rgb
    return alpha>=128 and r>=g>=b and r-g>=7 and g-b>=5 and g>45 and .085<(r-b)/max(r,1)<.60
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'texture-data').mkdir()
    manifest=json.loads(args.input.read_text(encoding='utf8'));records=[];images={};textures={}
    for job in manifest['jobs']:
        profile=job['body_profile']
        if profile['costume_id'] not in ('0004','0009'):continue
        data=json.loads((args.input.parent/job['snapshot']).read_text(encoding='utf8'))
        mesh=next(m for m in data['meshes'] if m['name']=='M_Body');uv=next(u['values'] for u in mesh['uvs'] if u['channel']==0)
        triangles=[];skin=[];wrapped=[];sample_types=Counter()
        for face in mesh['faces']:
            prop=next(x for x in data['materials'][face['material']]['properties'] if x['name']=='_MainTex')
            texture=args.input.parent/manifest['resources']/prop['texture'];key=str(texture)
            if key not in images:
                image=Image.open(texture).convert('RGBA');images[key]=image
                rawname=hashlib.sha256(key.encode()).hexdigest()[:12]+'.rgba';(out/'texture-data'/rawname).write_bytes(image.tobytes())
                textures[key]=dict(file='texture-data/'+rawname,width=image.width,height=image.height,source=str(texture))
            image=images[key]
            for i in range(0,len(face['triangles']),3):
                tri=face['triangles'][i:i+3];votes=0;white=0
                for weights in SAMPLES:
                    u=sum(a*uv[v]['x'] for a,v in zip(weights,tri));v=sum(a*uv[j]['y'] for a,j in zip(weights,tri))
                    u=(u*prop.get('scale',[1,1])[0]+prop.get('offset',[0,0])[0])%1;v=(v*prop.get('scale',[1,1])[1]+prop.get('offset',[0,0])[1])%1
                    rgba=image.getpixel((min(image.width-1,int(u*image.width)),min(image.height-1,int((1-v)*image.height))))
                    votes+=warm(rgba[:3],rgba[3]);white+=min(rgba[:3])>=240
                triangles.append(dict(vertices=tri,material=face['material'],texture=key,scale=prop.get('scale',[1,1]),offset=prop.get('offset',[0,0])))
                skin.append(votes>=5)
                wrapped.append(profile['costume_id']=='0004' and face['category'] in ('clothing','body_clothing_mixed') and votes<5)
                sample_types['skin' if votes>=5 else 'non_skin']+=1
                if white>=5:sample_types['white_cloth_rejected']+=int(votes<5)
        records.append(dict(job=job['name'],profile=profile,snapshot=str(args.input.parent/job['snapshot']),mesh='M_Body',triangles=triangles,skin=skin,wrapped=wrapped,counts=dict(sample_types)))
    texture_keys=list(textures);lookup={key:i for i,key in enumerate(texture_keys)}
    for record in records:
        for tri in record['triangles']:assert tri['scale']==[1,1] and tri['offset']==[0,0]
        record['triangles']=[tri['vertices']+[tri['material'],lookup[tri['texture']]] for tri in record['triangles']]
    config=dict(input=str(args.input),output=str(out),records=records,textures=[textures[key] for key in texture_keys],levels=2,max_distance=.03,normal_dot=.55,
                policy='0004 is the outer envelope; sample actual non-white exposed skin; only inward corrections throughout wrapped regions; fixed correspondence across profiles; no global registration')
    (out/'config.json').write_text(json.dumps(config,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print('PREPARED_INWARD_ENVELOPE',len(records),'records',flush=True)
    print('BASIS_REFERENCE',[(r['job'],r['counts']) for r in records if all(r['profile'][f]==v for f,v in zip(('height','shape','bust'),('1','0','2')))],flush=True)

if __name__=='__main__':main()
