"""Emit reversible one-factor designer diagnosis config drafts; no finalmod/UI changes."""
import sys,json,copy,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));from minimal_designer_contract import clausewitz,script_block,fields,one,setfield
R=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9');M=R/'UMA-V9';OUT=Path(__file__).parent/'AB-config-drafts'
def main():
 OUT.mkdir(exist_ok=True);records=[];baseline=OUT/'baseline';baseline.mkdir(exist_ok=True);rule=M/'gfx/portraits/customization_rules/uma_portrait_customization.txt';files=[rule,*sorted((M/'gfx/models/portraits/uma/0001').glob('uma_0001_head_*.asset'))];files=[p for p in files if p.name in['uma_portrait_customization.txt','uma_0001_head_male.asset','uma_0001_head_female.asset']]
 for source in files:(baseline/source.name).write_bytes(source.read_bytes())
 tree=clausewitz(rule.read_text(encoding='utf-8-sig'));tree=copy.deepcopy(tree);setfield(fields(tree,'uma'),'gene_groups',[('hair',[('hair','face')])]);a=OUT/'A-UMA-color-only-categories';a.mkdir(exist_ok=True);(a/rule.name).write_text(script_block(tree)+'\n',encoding='utf-8-sig');records.append(dict(test='A',factor='Only UMA gene_groups reduced to declared haircolor category; keep a validnonempty category, colorbinding/accessories/body genes/models/motions/age unchanged',replace_files=[dict(source=str(a/rule.name),target=str(rule),original_sha256=hashlib.sha256(rule.read_bytes()).hexdigest())],inference='If currentV9 exits but A does not, body/eyes slidercategory construction is implicated; still need exact UI cause. If both exit, do not attribute solely to those sliders.'))
 b=OUT/'B-UMA-carrier-no-placeholder-BS';b.mkdir(exist_ok=True);replacements=[]
 for file in files[1:]:
  tree=clausewitz(file.read_text(encoding='utf-8-sig'));removed=set()
  for k,block in tree:
   if k=='pdxmesh':
    for key,item in block:
     if key=='blend_shape':removed.add(one(item,'id'))
    block[:]=[(key,v)for key,v in block if key!='blend_shape']
   if k=='entity':block[:]=[(key,v)for key,v in block if not(key=='attribute'and one(v,'blend_shape')in removed)]
  dest=b/file.name;dest.write_text(script_block(tree)+'\n',encoding='utf8');replacements.append(dict(source=str(dest),target=str(file),original_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),placeholder_BS_removed=len(removed)))
 records.append(dict(test='B',factor='Only two UMA placeholder carrier BS declarations/linkedattributes removed; preserve carrier rig245/import/entities/materials/realhead+cheek+tear/bodyallBS andcurrentGUIrules',replace_files=replacements,inference='If B alone changesexit behavior, carrier placeholder morph setup/cache becomescandidate. Missing-target handling itself might alterbehavior; not proof of globalblend-ID collision.'))
 manifest=dict(drafts_only=True,final_mod_modified=False,baseline_backup=str(baseline),tests=records,instructions=['Test currentfinalV9 baseline first, sameDNA/template/age/sex/portraitgroup/camera/settings; record exact step and whether menu remains alive.','Close game before temporarily replacing onlylistedfile(s); use currentbaseline bytes to restore beforenexttest.','Do NOT enable two duplicatefullmods or move loadorder during these tests; that adds confounders.','Run A and B independently, never stackthem; aftereach restorelistedbaselinefiles.','No automatic game UI execution in this audit; root/user performsruntime tests.'],not_claimed='Silent ruler-designer exit fixed or attributed. Static closed registries are not a runtime fix proof.');(OUT/'AB-plan.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');print('AB_DRAFTS',[(r['test'],len(r['replace_files']))for r in records],str(OUT))
if __name__=='__main__':main()
