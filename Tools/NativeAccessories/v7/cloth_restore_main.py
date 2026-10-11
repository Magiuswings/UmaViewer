import os
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));import cloth_fit_export as c
regfile=c.OUT/'clothing-registration.json';reg=json.loads(regfile.read_text());index=json.loads((c.SRC/'cloth-source-index.json').read_text(encoding='utf8'))
for name in ['bdy1001_00','bdy1002_00']:
 record=next(r for r in index['records']if r['family']==name);entry=next(r for r in reg['families']if r['family']==name);source=next(x for x in record['selected_prefabs']if x['prefab']==record['basis_prefab']);data=json.loads(Path(source['parsed_path']).read_text());archive=c.np.load(c.SRC/'partitions'/name/'source-parts.npz');sk,t,mapping,points,bones=c.make_skeleton(data);actor=next(a for a in index['characters']if a['id']==record['characters'][0]);profile=f"h{actor['height']}_s{actor['shape']}_b{actor['bust']}";prepared={mi:c.prepare_mesh(m,profile,t,bones)for mi,m in enumerate(data['meshes'])};textures={int(k):v for k,v in entry['material_provenance'].items()};path=Path(entry['parts']['clothes']['base_mesh']);stem=path.stem.removesuffix('_base');entry['parts']['clothes']=c.make_part(data,archive,'clothes',1,sk,prepared,path.parent,stem,textures);entry['main_global_projection_reverted']=True;print('RESTORED_SOURCE_MAIN',name,flush=True)
tmp=regfile.with_suffix('.tmp');tmp.write_text(json.dumps(reg,indent=2));tmp.replace(regfile)
