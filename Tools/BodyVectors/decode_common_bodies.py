"""Decode selected common-body bundles without requiring a character head palette."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--named',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    sys.path.insert(0,str(args.repo/'Tools/HeadlessExporter'))
    from export_assets import Package,Extractor,write_json
    from body_profiles import body_profile,select_body_bases
    from segmentation import classify
    if args.output.exists():raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    package=Package(args.named)
    palette=[];palette_sources=[]
    for o in package.objects:
        if o.type.name!='Texture2D':continue
        data=package.read(o)
        if not re.fullmatch(r'tex_bdy0004_00_00_0_[0-4]_diff',data.m_Name):continue
        counts=Counter()
        image=data.image.convert('RGB')
        for r,g,b in image.getdata():
            if r>=g>=b and r-g>=8 and g-b>=5 and g>70 and (r-b)/max(r,1)<.55:
                counts[(r//8*8+4,g//8*8+4,b//8*8+4)]+=1
        if not counts:raise ValueError('No exposed-skin palette in reference atlas '+data.m_Name)
        color=counts.most_common(1)[0][0];palette.append(color)
        palette_sources.append(dict(texture=data.m_Name,rgb=color,method='Most common warm skin texel bin from real reference skin=0 diffuse; same RGB-bin selection as existing face palette extractor'))
    palette=list(dict.fromkeys(palette))
    if not palette:raise ValueError('Missing skin=0 classification atlases')
    settings=SimpleNamespace(names={},generic_skin='1',generic_skin_reference='0',skin_mode='auto',skin_tolerance=42.)
    extractor=Extractor(package,args.output,settings);jobs=[]
    for source in sorted(package.bundles):
        profile=body_profile(source)
        if not profile:continue
        assert profile['costume_id'].startswith('00')
        data=extractor.prefab(source,'body',source.rsplit('/',1)[-1][4:],'shared',palette)
        classify(data,None,extractor.resources)
        path=args.output/'snapshots'/(data['name']+'.uma.json');write_json(path,data)
        counts={c:sum(len(f['triangles'])//3 for m in data['meshes'] for f in m['faces'] if f['category']==c) for c in {f['category'] for m in data['meshes'] for f in m['faces']}}
        jobs.append(dict(name=data['name'],snapshot=path.relative_to(args.output).as_posix(),character_id='shared',source=source,kind='body',body_profile=profile,categories=sorted(counts),category_triangles=counts,skin_palette=palette))
        print('DECODED_COMMON',data['name'],counts,flush=True)
    # Preserve all actual swimsuit skin palettes for the four database skin values.
    for o in package.objects:
        if o.type.name=='Texture2D' and re.fullmatch(r'tex_bdy0004_00_00_[0-3]_[0-4]_diff',package.read(o).m_Name):extractor.texture(o)
    manifest=dict(version=1,input=str(args.named.resolve()),resources='resources',jobs=jobs,characters=[],errors=extractor.errors,warnings=sorted(set(extractor.warnings)),
                  generic_skin='1',generic_skin_reference='0',classification_palette_sources=palette_sources,textures=list(extractor.textures.values()),body_bases=select_body_bases(jobs,lambda j:json.loads((args.output/j['snapshot']).read_text(encoding='utf8'))))
    write_json(args.output/'manifest.json',manifest)
    if extractor.errors:raise RuntimeError(json.dumps(extractor.errors[:20],ensure_ascii=False))
    print('COMMON_BODY_DECODE_COMPLETE',len(jobs),'jobs',len(extractor.errors),'errors',palette,flush=True)

if __name__=='__main__':main()
