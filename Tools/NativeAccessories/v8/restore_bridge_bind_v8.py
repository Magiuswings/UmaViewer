"""Preserve deliberate thoracic-local bridge inverse bind; all standard head roots remain -d."""
import json,copy
from paths_v8 import ROOT,MOD,V7
from apply_models_v8 import P,geometry
rejected=ROOT/'Reports/rest-attachment-validation.json'
if rejected.exists()and not json.loads(rejected.read_text())['passed']:
    (ROOT/'Reports/bridge-root-normalization-rejected.json').write_bytes(rejected.read_bytes())
records=[]
for actor in ['1001','1002']:
    rel=f'gfx/models/portraits/uma/{actor}/uma_{actor}_neck_base.mesh';file=MOD/rel;original=P.read_meshfile(str(V7/'UMA-V7'/rel));source=next(b for b in original.find('object')[0].find('skeleton')if b.tag=='head_root');tree=P.read_meshfile(str(file));before=geometry(tree)
    for o in tree.find('object'):
        b=next(b for b in o.find('skeleton')if b.tag=='head_root');b.set('tx',copy.deepcopy(source.get('tx')))
    assert geometry(tree)==before;P.write_meshfile(str(file),tree);records.append(dict(file=rel,bridge_inverse_bind_restored_exact=source.get('tx'),reason='Lower ring coordinates are thoracic-local; source inverse bind differs deliberately from common head root. Actual three-joint match compensates current head root offset. No geometry moved.'))
(ROOT/'Reports/bridge-bind-exception.json').write_text(json.dumps(records,indent=2),encoding='utf8');print('NECK_SPECIALIZED_BIND_RESTORED',len(records),flush=True)
