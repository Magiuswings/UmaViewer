"""Global basename resource lookup and stock color keys loaded before human defaults."""
import sys,json,hashlib,copy
import numpy as np
from PIL import Image
from pathlib import Path
from paths_v9 import ROOT,MOD,REPO,GAME,PLUGIN,V8
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v8')]
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
from configure_assets_v8 import render
P=parser_only(PLUGIN);KEYS={f'uma_{c}_color':f'{c}_color'for c in ['skin','hair','eye']}
def lab(rgb):
    a=np.asarray(rgb,float)/255;a=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4);xyz=a@np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])/np.array([.95047,1,1.08883]);v=np.where(xyz>.008856,np.cbrt(xyz),7.787*xyz+16/116);return np.stack([116*v[...,1]-16,500*(v[...,0]-v[...,1]),200*(v[...,1]-v[...,2])],axis=-1)
def names(tree):
    for i,(k,v)in enumerate(tree):
        nk=KEYS.get(k,k)
        if isinstance(v,list):names(v)
        else:v=KEYS.get(v,v)
        tree[i]=(nk,v)
def resources(tree):
    n=0
    for i,(k,v)in enumerate(tree):
        if isinstance(v,list):n+=resources(v)
        elif isinstance(v,str)and v.lower().endswith(('.dds','.anim','.mesh'))and k!='shader_file':
            new=Path(v.replace('\\','/')).name;n+=v!=new;tree[i]=(k,new)
    return n
def main():
    presetfile=ROOT/'Reports/palette-presets.json';presets=json.loads(presetfile.read_text());colorrows={};quant=[]
    for row in presets:
        actor=row['actor'];colorrows[actor]={}
        for kind,data in row['colors'].items():
            file=GAME/data['palette'];pix=np.asarray(Image.open(file).convert('RGB'));size=pix.shape[0];grid=np.arange(1,100,dtype=float)/100;coords=np.array([(x,y)for y in grid for x in grid]);idx=np.clip(np.floor(coords*size).astype(int),0,size-1);rgb=pix[idx[:,1],idx[:,0]];error=np.linalg.norm(lab(rgb)-lab(data['target_rgb_255']),axis=1);choose=int(error.argmin());xy=coords[choose].tolist();colorrows[actor][kind]=xy;previous=copy.deepcopy(data);data.update(xy=xy,rectangle=xy+xy,pixel=idx[choose].tolist(),palette_rgb_255=rgb[choose].tolist(),delta_e76=float(error[choose]),coordinate_precision=2,coordinate_selection='Closest fixed original palette color on the representable 0.01 XY grid; original palette unchanged');quant.append(dict(actor=actor,color=kind,old=previous,new=data))
    presetfile.write_text(json.dumps(presets,ensure_ascii=False,indent=2),encoding='utf8')
    for file in MOD.rglob('*.txt'):
        if file.name=='uma_colors.txt':continue
        tree=clausewitz(file.read_text(encoding='utf-8-sig'));names(tree)
        if file.name=='uma_ethnicity.txt':
            for ethnicity,entry in tree:
                actor='1002'if ethnicity=='uma_1002_ethnicity'else'1001'
                for i,(k,v)in enumerate(entry):
                    kind=k.removesuffix('_color')if k in KEYS.values()else None
                    if kind:entry[i]=(k,[('100',[(None,f'{a:.2f}')for a in colorrows[actor][kind]*2])])
        elif file.name=='uma_customization.txt':
            for k,group in tree:
                if k!='uma_custom_character':continue
                for choice,item in group:
                    if choice not in ['uma_character_1001','uma_character_1002']:continue
                    actor=choice[-4:]
                    for color in values(one(item,'dna_modifiers'),'color'):
                        kind=one(color,'gene').removesuffix('_color');xy=colorrows[actor][kind];color[:]=[(a,f'{xy[0 if a=="x"else 1]:.2f}'if a in ['x','y']else b)for a,b in color]
        file.write_text(script_block(tree)+'\n',encoding='utf-8-sig')
    color=clausewitz((GAME/'common/genes/00_genes_color.txt').read_text(encoding='utf-8-sig'));one(color,'color_genes').insert(0,('portrait_group','uma'));(MOD/'common/genes/000_uma_genes_color.txt').write_text(script_block(color)+'\n',encoding='utf-8-sig')
    old=MOD/'common/genes/uma_colors.txt'
    if old.exists():old.unlink()
    old=MOD/'common/portrait_types/uma_portrait_types.txt';new=old.with_name('000_uma_portrait_types.txt')
    if old.exists():old.rename(new)
    # Root-only attachment; merged seam helpers supply the real body-follow frames.
    types=clausewitz(new.read_text(encoding='utf-8-sig'));attach=one(one(types,'uma'),'attach');attach[:]=[(k,v)for k,v in attach if k!='joint_attachment'or one(v,'child_joint')=='head_root'];new.write_text(script_block(types)+'\n',encoding='utf-8-sig')
    changed=0
    for file in(MOD/'gfx').rglob('*.asset'):
        tree=clausewitz(file.read_text(encoding='utf-8-sig'));changed+=resources(tree);file.write_text(render(tree)+'\n',encoding='utf8')
    binary=0
    for file in(MOD/'gfx').rglob('*.mesh'):
        tree=P.read_meshfile(str(file));n=0
        for m in tree.iter('material'):
            for k,v in list(m.attrib.items()):
                nv=[Path(a.replace('\\','/')).name if isinstance(a,str)and a.endswith('.dds')else a for a in v];n+=v!=nv;m.set(k,nv)
        if n:P.write_meshfile(str(file),tree);binary+=1
    (ROOT/'Reports/path-color-order-repair.json').write_text(json.dumps(dict(asset_references_rewritten=changed,binary_files_rewritten=binary,original_color_keys=list(KEYS.values()),uma_colors_removed=True,early_files=['000_uma_genes_color.txt','000_uma_portrait_types.txt'],shader_paths_kept=True,original_palette_files_modified=False,coordinate_precision=2,palette_grid_selection=quant),indent=2),encoding='utf8');print('V9_PATH_COLOR_PATCH',changed,binary,colorrows,flush=True)
if __name__=='__main__':main()
