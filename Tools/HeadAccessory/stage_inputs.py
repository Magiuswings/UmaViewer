"""Stage only 1001, common body, head animation and configuration inputs."""
import argparse,hashlib,json,zipfile
from pathlib import Path,PurePosixPath

def main():
    p=argparse.ArgumentParser();p.add_argument('--broken',type=Path,required=True);p.add_argument('--palette',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    expected=Path('E:/UmaViewer-Exports/2026-10-10-Head-Accessory-1001').resolve()
    assert a.output.resolve()==expected and not expected.exists();expected.mkdir(parents=True)
    sources=[]
    for label,file in [('source',a.broken),('palette-reference',a.palette)]:
        saved=[]
        with zipfile.ZipFile(file)as z:
            names=[n for n in z.namelist()if not n.endswith('/')]
            selected=[]
            if label=='source':
                selected=[n for n in names if n.startswith(('common/','gfx/portraits/','gfx/FX/','gfx/models/portraits/uma/0001/','gfx/models/portraits/uma/1001/','gfx/models/portraits/uma/animation/'))or n in ['descriptor.mod','character-body-bindings.json','character-face-bindings.json']]
            else:
                asset=next(n for n in names if n.endswith('/uma_body.asset'));selected=[asset]
                import re
                text=z.read(asset).decode('utf-8-sig');refs=re.findall(r'(?:texture_diffuse|texture_normal|texture_specular)\s*=\s*"([^"]+)"',text)
                for ref in refs:
                    candidates=[n for n in names if n.endswith('/'+ref.rsplit('/',1)[-1])]
                    if candidates:selected.append(candidates[0])
                selected.extend(n for n in names if n.endswith('uma_portrait.shader'))
            for n in dict.fromkeys(selected):
                rel=PurePosixPath(n);assert not rel.is_absolute()and'..'not in rel.parts;target=expected/label/n;target.parent.mkdir(parents=True,exist_ok=True);data=z.read(n);target.write_bytes(data);saved.append(dict(path=n,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        sources.append(dict(label=label,archive=str(file),archive_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),staged=saved))
    (expected/'input-manifest.json').write_text(json.dumps(dict(sources=sources,scope='1001 only; no other identity meshes extracted or verified'),ensure_ascii=False,indent=2),encoding='utf8');print('STAGED_SINGLE_CHARACTER_INPUTS',[(s['label'],len(s['staged']))for s in sources])

if __name__=='__main__':main()
