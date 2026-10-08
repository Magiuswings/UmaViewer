"""Write normalized palettes, preserve baked anatomical detail, and bind the new snapshots."""
import argparse
import array
import ast
import json
from pathlib import Path
import struct
from PIL import Image,ImageFilter

def npy_bytes(path):
    with path.open('rb') as f:
        assert f.read(6)==b'\x93NUMPY';major,minor=f.read(2);length=struct.unpack('<H' if major==1 else '<I',f.read(2 if major==1 else 4))[0]
        meta=ast.literal_eval(f.read(length).decode('latin1'));return meta,f.read()
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--palettes',type=Path,required=True);args=p.parse_args()
    root=args.root;meta,raw=npy_bytes(root/'detail-ratio.npy');assert meta['descr']=='<f4'
    values=array.array('f');values.frombytes(raw);rgb=bytes(max(0,min(255,round(v*255))) for v in values)
    ratio=Image.frombytes('RGB',(1024,1024),rgb).filter(ImageFilter.GaussianBlur(.65))
    palettes=json.loads(args.palettes.read_text(encoding='utf8'))['palettes'];tex=root/'resources/textures';tex.mkdir(parents=True,exist_ok=True)
    names={};reports=[]
    for palette in palettes:
        color=palette['fill_rgb_srgb_255'];skin=palette['skin'];name='uma_envelope_skin_'+str(skin)+'.png'
        channels=[c.point([round(i*color[k]/255) for i in range(256)]) for k,c in enumerate(ratio.split())]
        img=Image.merge('RGB',channels).convert('RGBA');img.save(tex/name)
        names[str(skin)]='textures/'+name;reports.append(dict(skin=skin,base_rgb=color,source_default_diffuse_statistics=palette['statistics'],diffuse=names[str(skin)]))
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf8'));manifest['normalized_skin_textures']=names
    for job in manifest['jobs']:
        file=root/job['snapshot'];data=json.loads(file.read_text(encoding='utf8'));main=next(p for p in data['materials'][0]['properties'] if p['name']=='_MainTex');main['texture']=names['1'];main['scale']=[1,1];main['offset']=[0,0]
        data['materials'][0]['properties']=[p for p in data['materials'][0]['properties'] if p['type']!='Texture' or p['name']=='_MainTex']
        data['skin_completion']=dict(method='Inward-only envelope geometry + globally normalized skin albedo + original dark anatomical features',separate_swimsuit_material=False,fill_rgb_srgb_255=palettes[1]['fill_rgb_srgb_255'])
        file.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    manifest['body_bases']=[dict(name=j['name']) for j in manifest['jobs']]
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    (root/'normalized-skin-colors.json').write_text(json.dumps(dict(palettes=reports,colour_boundaries_from_clothing_removed=True,default_skin=1,source='Same area-weighted default 0004 diffuse pigments; real 0009 skin detail colour ratio'),ensure_ascii=False,indent=2),encoding='utf8')
    ratio.save(root/'detail-ratio-preview.png');print('NORMALIZED_SKIN_TEXTURES_COMPLETE',flush=True)

if __name__=='__main__':main()
