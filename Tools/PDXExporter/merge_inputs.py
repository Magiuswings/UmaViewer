"""Merge decoded manifests without overwriting source evidence or inventing owners."""
import argparse
import hashlib
import json
import os
from pathlib import Path

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',action='append',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();out=args.output.resolve()
    if any(out==m.resolve().parent or out.is_relative_to(m.resolve().parent) for m in args.manifest):p.error('Separate output required')
    out.mkdir(parents=True,exist_ok=True);(out/'snapshots').mkdir(exist_ok=True)
    merged=dict(version=1,resources='resources',characters=[],jobs=[],body_bases=[],errors=[],inputs=[],duplicate_jobs=[])
    names={};bases=set()
    for source in args.manifest:
        source=source.resolve();m=json.loads(source.read_text(encoding='utf8'))
        merged['inputs'].append(dict(manifest=str(source),manifest_sha256=digest(source),input=m['input'],input_sha256=m.get('input_sha256')))
        chars=m.get('characters',{})
        if isinstance(chars,(dict,list)):
            merged['characters']=sorted(set(merged['characters'])|set(chars))
        if m.get('errors'):raise ValueError('Source manifest has unresolved export errors: '+str(source))
        for file in (source.parent/m['resources']).rglob('*'):
            if not file.is_file():continue
            target=out/'resources'/file.relative_to(source.parent/m['resources']);target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if digest(file)!=digest(target):raise ValueError('Texture conflict: '+str(file))
            else:os.link(file,target)
        renamed={}
        for job in m['jobs']:
            data=json.loads((source.parent/job['snapshot']).read_text(encoding='utf8'))
            signature=hashlib.sha256(json.dumps({k:data[k] for k in ('bones','meshes','materials','attachment') if k in data},sort_keys=True).encode()).hexdigest()
            name=job['name']
            if name in names and names[name]==signature:
                merged['duplicate_jobs'].append(dict(name=name,manifest=str(source),same_geometry_binding_materials=True))
                renamed[name]=name;continue
            if name in names:name+='__input'+str(len(merged['inputs']))
            renamed[job['name']]=name;names[name]=signature
            new=dict(job,name=name,snapshot='snapshots/'+name+'.uma.json',source_manifest=str(source))
            (out/new['snapshot']).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8')
            merged['jobs'].append(new)
        for base in m.get('body_bases',[]):
            name=renamed[base['name']]
            if name not in bases:merged['body_bases'].append(dict(base,name=name));bases.add(name)
    (out/'manifest.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf8')
    print('MERGED jobs='+str(len(merged['jobs']))+' duplicates='+str(len(merged['duplicate_jobs'])))

if __name__=='__main__':main()
