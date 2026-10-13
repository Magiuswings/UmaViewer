import sys,json
from paths_v9 import ROOT,MOD,REPO
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import clausewitz,script_block
from minimal_designer_contract import apply_body_compatibility,apply_minimal_rules
changes={}
for rel,fn in [('common/genes/uma_body_morphs.txt',apply_body_compatibility),('gfx/portraits/customization_rules/uma_portrait_customization.txt',apply_minimal_rules)]:
    file=MOD/rel;tree,notes=fn(clausewitz(file.read_text(encoding='utf-8-sig')));file.write_text(script_block(tree)+'\n',encoding='utf-8-sig');changes[rel]=notes
(ROOT/'Reports/designer-configuration-repair.json').write_text(json.dumps(dict(changes=changes,confirmed_empty_templates_hidden=True,original_reserved_indexes_present=True,silent_crash_cause_confirmed=False,game_ruler_designer_executed=False),indent=2),encoding='utf8');print('DESIGNER_CONTRACT_APPLIED',[(k,len(v))for k,v in changes.items()],flush=True)
