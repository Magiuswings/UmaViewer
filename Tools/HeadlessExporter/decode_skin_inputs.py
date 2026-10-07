"""Decode only real 0004/0009 body prefabs, preserving source transforms and weights."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--headless-tools',type=Path,required=True)
    parser.add_argument('--generic-skin',default='1',help='Default diffuse skin index; current provided characters use skin=1')
    parser.add_argument('--generic-skin-reference',default='0',help='Stable reference atlas for exposed-skin classification')
    args=parser.parse_args()
    sys.path.insert(0,str(args.headless_tools))
    import export_assets as ex
    from body_profiles import body_profile
    assert Path(ex.__file__).resolve()==(args.headless_tools/'export_assets.py').resolve()
    out=args.output.resolve()
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    package=ex.Package(args.package)
    owners=sorted({m[2][3:].split('_')[0] for n in package.bundles if (m:=ex.PREFAB.search(n)) and m[1] in ('head','body') and int(m[2][3:].split('_')[0])>=1000})
    palette=list(dict.fromkeys(c for owner in owners for c in ex.skin_palette(package,owner)))
    settings=SimpleNamespace(generic_skin=args.generic_skin,generic_skin_reference=args.generic_skin_reference,skin_mode='auto',skin_tolerance=42.,names={})
    extractor=ex.Extractor(package,out,settings)
    jobs=[]
    for source in package.bundles:
        profile=body_profile(source)
        if not profile or profile['costume_id'] not in ('0004','0009'):continue
        identifier=Path(source).name.removeprefix('pfb_')
        data=extractor.prefab(source,'body',identifier,'shared',palette)
        path=out/'snapshots'/(data['name']+'.uma.json')
        ex.write_json(path,data)
        counts={c:sum(len(f['triangles'])//3 for m in data['meshes'] for f in m['faces'] if f['category']==c) for c in {f['category'] for m in data['meshes'] for f in m['faces']}}
        job=dict(name=data['name'],snapshot=path.relative_to(out).as_posix(),character_id='shared',source=source,kind='body',body_profile=profile,categories=sorted(counts),category_triangles=counts,skin_palette=palette)
        jobs.append(job)
        print(data['name'],counts,flush=True)
    manifest=dict(version=1,input=str(args.package.resolve()),input_sha256=hashlib.sha256(args.package.read_bytes()).hexdigest(),jobs=jobs,resources='resources',characters=owners,textures=list(extractor.textures.values()),errors=extractor.errors,warnings=sorted(set(extractor.warnings)),body_bases=[])
    ex.write_json(out/'manifest.json',manifest)
    if extractor.errors:raise RuntimeError(json.dumps(extractor.errors,ensure_ascii=False))
    print('DECODE_SKIN_INPUTS_COMPLETE',flush=True)

if __name__=='__main__':main()
