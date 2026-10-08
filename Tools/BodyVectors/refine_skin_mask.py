"""Use actual skin pigment plus surrounded dark-feature components, rejecting garment seams."""
from collections import defaultdict,Counter
import json
from pathlib import Path
import sys
from PIL import Image

SAMPLES=((1,0,0),(0,1,0),(0,0,1),(.5,.5,0),(0,.5,.5),(.5,0,.5),(1/3,1/3,1/3))
def main():
    root=Path(sys.argv[1]);config=json.loads((root/'config.json').read_text(encoding='utf8'))
    images=[Image.frombytes('RGBA',(t['width'],t['height']),(root/t['file']).read_bytes()) for t in config['textures']]
    target=(255,231,203)
    for record in config['records']:
        if record['profile']['costume_id']!='0009':continue
        data=json.loads(Path(record['snapshot']).read_text(encoding='utf8'));mesh=next(m for m in data['meshes'] if m['name']=='M_Body');uv=next(l['values'] for l in mesh['uvs'] if l['channel']==0)
        primary=[];dark=[];edges=defaultdict(list);keys=[tuple(round(v[k],5) for k in 'xyz') for v in mesh['vertices']]
        for ti,tri in enumerate(record['triangles']):
            image=images[tri[4]];skin=shadow=0
            for weights in SAMPLES:
                u=sum(w*uv[v]['x'] for w,v in zip(weights,tri[:3]))%1;v=sum(w*uv[i]['y'] for w,i in zip(weights,tri[:3]))%1
                r,g,b,a=image.getpixel((min(image.width-1,int(u*image.width)),min(image.height-1,int((1-v)*image.height))))
                skin+=a>=128 and sum((c-t)**2 for c,t in zip((r,g,b),target))<=25**2
                shadow+=a>=128 and r>=g>=b and r-g>=7 and g-b>=5 and g>45 and .09<(r-b)/max(r,1)<.6 and r<210
            primary.append(skin>=5);dark.append(shadow>=5)
            for a,b in zip(tri[:3],tri[1:3]+tri[:1]):edges[tuple(sorted((keys[a],keys[b])))].append(ti)
        adjacent=defaultdict(set)
        for members in edges.values():
            for a in members:adjacent[a].update(set(members)-{a})
        accepted=set();seen=set();components=[]
        for start,flag in enumerate(dark):
            if not flag or start in seen:continue
            stack=[start];group=set();seen.add(start)
            while stack:
                i=stack.pop();group.add(i)
                for j in adjacent[i]:
                    if dark[j] and j not in seen:seen.add(j);stack.append(j)
            boundary={j for i in group for j in adjacent[i] if j not in group}
            ratio=sum(primary[j] for j in boundary)/max(len(boundary),1)
            if boundary and ratio>=.85 and len(group)<=120:accepted.update(group)
            components.append(dict(triangles=len(group),skin_boundary_fraction=ratio,accepted=bool(boundary and ratio>=.85 and len(group)<=120)))
        record['skin']=[primary[i] or i in accepted for i in range(len(primary))]
        record['feature_components']=components;record['counts']['true_skin_after_context']=sum(record['skin']);record['counts']['dark_skin_features_kept']=len(accepted)
    (root/'config.json').write_text(json.dumps(config,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print('SKIN_CONTEXT_REFINED',[(r['job'],r['counts']['true_skin_after_context'],r['counts']['dark_skin_features_kept']) for r in config['records'] if r['profile']['costume_id']=='0009' and (r['profile']['height'],r['profile']['shape'],r['profile']['bust'])==('1','0','2')])

if __name__=='__main__':main()
