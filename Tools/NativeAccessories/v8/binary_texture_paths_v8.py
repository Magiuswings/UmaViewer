"""Use file-relative binary material paths; .asset references remain game-root relative."""
import os,json
from paths_v8 import ROOT,MOD
from apply_models_v8 import P
records=[]
for file in(MOD/'gfx').rglob('*.mesh'):
    tree=P.read_meshfile(str(file));changed=[]
    for mat in tree.iter('material'):
        for k,v in list(mat.attrib.items()):
            if not isinstance(v,list):continue
            new=[]
            for ref in v:
                if isinstance(ref,str)and ref.startswith('gfx/')and ref.endswith('.dds'):
                    actual=(MOD/ref).resolve();assert actual.exists();relative=os.path.relpath(actual,file.parent).replace('\\','/');assert (file.parent/relative).resolve()==actual;new.append(relative);changed.append(dict(key=k,old=ref,new=relative))
                else:new.append(ref)
            mat.set(k,new)
    if changed:P.write_meshfile(str(file),tree);records.append(dict(file=file.relative_to(MOD).as_posix(),texture_changes=changed))
(ROOT/'Reports/binary-texture-path-compatibility.json').write_text(json.dumps(dict(binary_material_path='relative to .mesh file',asset_texture_path='relative to game root',same_physical_DDS=True,updated_models=records),indent=2),encoding='utf8');print('SDK_BINARY_TEXTURE_RELATIVE_PATHS',len(records),flush=True)
