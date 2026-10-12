"""Install independent native ear/tail union rigs without reverting schemas or shared textures."""
import json
from pathlib import Path
from paths_v8 import ROOT,MOD,V7
from apply_models_v8 import P,geometry,material_remap
contract=json.loads((ROOT/'Rigs/ear-tail-rig-contract.json').read_text());manifest=json.loads((ROOT/'Reports/texture-sharing.json').read_text());records=[]
for module in ['ear','tail']:
    for r in contract[module]['independent_components']:
        source=Path(r['source']);relative=source.relative_to(V7/'UMA-V7');file=MOD/relative;before=P.read_meshfile(str(file));tree=P.read_meshfile(r['output_mesh']);assert geometry(before)==geometry(tree),file
        assert [[m.find('skin').get('w')for m in o.findall('mesh')]for o in before.find('object')]==[[m.find('skin').get('w')for m in o.findall('mesh')]for o in tree.find('object')]
        for obj in tree.find('object'):
            obj.tag=obj.tag.removesuffix('Shape');obj.set('lod',[0]);nodes=list(obj);obj[:]=[n for n in nodes if n.tag=='mesh']+[n for n in nodes if n.tag!='mesh']
        count=material_remap(tree,file,manifest);P.write_meshfile(str(file),tree);records.append(dict(module=module,file=relative.as_posix(),bones=contract[module]['bones'],texture_references_remapped=count,geometry_and_weights_exact=True))
(ROOT/'Reports/ear-tail-rig-application.json').write_text(json.dumps(records,indent=2),encoding='utf8');print('EAR_TAIL_MODULE_RIGS_APPLIED',len(records),flush=True)
