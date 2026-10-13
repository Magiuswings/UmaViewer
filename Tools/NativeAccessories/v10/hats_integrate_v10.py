import sys,json,shutil
from pathlib import Path
from paths_v10 import ROOT,MOD,REPO
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v8')]
from build_ck3_mod import clausewitz,one,values
from configure_assets_v8 import render
source=ROOT/'HatRepair/SharedBody';contract=json.loads((source/'hat-shared-install-contract.json').read_text(encoding='utf-8-sig'));assert contract['no_own_animation']
folder=source/'gfx/models/portraits/uma/0001';target=MOD/'gfx/models/portraits/uma/0001';count=0
for c in contract['candidates']:
    family=c['family'];code=family[3:];names=set(c['replace_existing_wardrobe_blocks_by_name']);dst=target/f'uma_0001_wardrobe_{code}.asset';tree=clausewitz(dst.read_text(encoding='utf-8-sig'));candidates=[]
    for af in folder.glob(f'*{code}*.asset'):
        candidates+=clausewitz(af.read_text(encoding='utf-8-sig'))
    replacements={one(v,'name'):(k,v)for k,v in candidates if k in ['pdxmesh','entity']and values(v,'name')and one(v,'name')in names};assert set(replacements)==names
    tree=[replacements[one(v,'name')]if k in ['pdxmesh','entity']and values(v,'name')and one(v,'name')in names else(k,v)for k,v in tree];dst.write_text(render(tree)+'\n',encoding='utf8')
    for f in [Path(c['base'])]+[Path(b['candidate'])for b in c['BS']]:shutil.copy2(f,target/f.name);count+=1
print('V10_HATS_INSTALLED',count,'meshes',flush=True)
