"""Publish only audit/contract artifacts under authorized V9 Reports, never finalmod."""
import json,shutil,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));from designer_dedup_audit import parse,children,value
SRC=Path(__file__).parent;R=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9');M=R/'UMA-V9';OUT=R/'Reports';CON=OUT/'contracts';CON.mkdir(parents=True,exist_ok=True)
names=['designer-dedup-audit.json','v9-final-designer-audit.json','v9-postmerge-registration-closure.json','designer-dedup-audit.md']
for n in names:shutil.copy2(SRC/n,OUT/n)
for p in SRC.glob('*.diff'):shutil.copy2(p,CON/p.name)
for p in SRC.glob('*.contract.txt'):shutil.copy2(p,CON/p.name)
for n in['minimal_designer_contract.py','minimal-designer-contract.json','000_uma_genes_color.txt','uma_ethnicity.color-contract.txt']:shutil.copy2(SRC/n,CON/n)
ab=SRC/'AB-config-drafts';dest=CON/'AB-config-drafts';
for p in ab.rglob('*'):
 if p.is_file():target=dest/p.relative_to(ab);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
color=M/'common/genes/000_uma_genes_color.txt';c=parse(color.read_text(encoding='utf-8-sig'));block=children(c,'color_genes')[0]['children'];precision=[]
for p in[M/'common/ethnicities/uma_ethnicity.txt',color]:
 # Only these files' numeric values are color/preset numbers; morph decimals are deliberately untouched.
 for i,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
  if re.search(r'(?<![A-Za-z_])(?:0?\.\d{3,}|\d+\.\d{3,})',line):precision.append(dict(file=str(p),line=i,text=line))
current=json.loads((SRC/'v9-final-designer-audit.json').read_text());closed=json.loads((SRC/'v9-postmerge-registration-closure.json').read_text());original=json.loads((SRC/'designer-dedup-audit.json').read_text());summary=dict(final_model_not_modified=True,exact_diff_artifacts=[str(CON/Path(r['diff']).name)for r in original['exact_diffs']],V7_V8_V9=dict(V7=dict(UMAface_gene=True,color_key_prefix='uma_',body_index_gaps_preexisting=True),V8=dict(UMAface_gene=False,stale_face_UIcategory=True,visible_empty_shape_templates=11,identical_UIpairs=8,model_definitions=267),V9=dict(empty_categories=len(current['group_problems']),duplicate_UIpairs=len(current['duplicate_choices']),unknown_template_references=len(current['unknown_template_references']),mode_violations=len(current['mode_violations']),index_gaps=len(current['index_issues']),model_definitions=closed['counts']['pdxmesh'],entity_definitions=closed['counts']['entity'],closure_violations=closed['counts']['closure_violations'],cheek_models=closed['counts']['cheek_models'],nonshader_path_refs=closed['counts']['nonshader_path_refs'])),color_contract=dict(keys=[n['key']for n in block if n['children']is not None],scope=value(block,'portrait_group'),filename=color.name,legacy_uma_colors_file_exists=(M/'common/genes/uma_colors.txt').exists(),precision_violations=precision,static_prefix_order_verified=True,live_human_color_and_load_behavior_not_verified=True),age18=current['age18_types'],headwear_own_imports=closed['headwear_imports'],AB_plan=str(CON/'AB-config-drafts/AB-plan.json'),no_live_crash_fix_claim=True)
(OUT/'independent-v9-audit-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print('V9_INDEPENDENT_SUMMARY',summary['V7_V8_V9']['V9'],summary['color_contract'],'Reports only')
