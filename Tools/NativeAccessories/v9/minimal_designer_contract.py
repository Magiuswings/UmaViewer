"""Reviewable V9 definition patch API. Drafts only; never touches final mod.

Input/output are build_ck3_mod.clausewitz list-of-(key,value) trees.
Hide confirmed no-binding visible body templates, restore hidden reserved noops,
remove explicit empty face category, keep original color keys and deduplicate UI only.
"""
import sys,json,copy,re
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter')
from build_ck3_mod import clausewitz,script_block,values
OUT=Path(__file__).parent;GAME=Path('D:/steam/steamapps/common/Crusader Kings III/game');V8=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/UMA-V8')
COLOR_ALIASES={'uma_hair_color':'hair_color','uma_skin_color':'skin_color','uma_eye_color':'eye_color'};COLOR_KEYS=set(COLOR_ALIASES)|set(COLOR_ALIASES.values());BODY_GENES=('gene_bs_body_type','gene_bs_body_shape','gene_bs_bust')
def one(tree,key):
 result=values(tree,key)
 if len(result)>1:raise ValueError('duplicate scalar '+key)
 return result[0]if result else None
def setfield(tree,key,value):
 matches=[i for i,(k,v)in enumerate(tree)if k==key]
 if matches:tree[matches[0]]=(key,value)
 else:tree.append((key,value))
def fields(tree,key):return next((v for k,v in tree if k==key and isinstance(v,list)),None)
def has_model_binding(tree):
 for k,v in tree:
  if k in ['setting','decal']and isinstance(v,list):return True
  if isinstance(v,list)and has_model_binding(v):return True
 return False
def noop_template(index):return [('index',str(index)),('visible','no'),('uma_male',[]),('uma_female',[]),('uma_boy','uma_male'),('uma_girl','uma_female')]
def apply_body_compatibility(tree):
 """Preserve original template names/indexes; hidden noops do not drive models or fixed shrink."""
 tree=copy.deepcopy(tree);changes=[];root=fields(tree,'morph_genes')
 if root is None:raise ValueError('installed-stock regular body root is morph_genes')
 for gene in BODY_GENES:
  block=fields(root,gene)
  if block is None:continue
  for name,item in block:
   if isinstance(item,list)and one(item,'index')is not None and not has_model_binding(item):
    if one(item,'visible')!='no':setfield(item,'visible','no');changes.append(dict(action='hide_no_binding_template',gene=gene,template=name,index=one(item,'index')))
  reserved={'gene_bs_body_type':[(4,'no_portrait')],'gene_bs_body_shape':[(0,'body_shape_average_clothed')],'gene_bs_bust':[(0,'bust_clothes'),(1,'bust_clothes_light')]}[gene]
  byindex={int(one(item,'index')):name for name,item in block if isinstance(item,list)and one(item,'index')is not None}
  for index,name in reserved:
   if fields(block,name)is not None:continue
   if index in byindex:raise ValueError('reserved index occupied: '+gene+':'+str(index))
   block.append((name,noop_template(index)));changes.append(dict(action='add_hidden_reserved_noop',gene=gene,template=name,index=index,model_attributes=[],fixed_body_clothed=False))
 return tree,changes
def apply_minimal_rules(tree,declared_groups=('body','hair','eyes'),hair_modifier_group='uma_custom_headwear'):
 tree=copy.deepcopy(tree);changes=[];root=fields(tree,'uma')
 if root is None:raise ValueError('UMA customization group missing')
 categories=fields(root,'gene_groups')or[]
 for panel,groups in categories:
  if not isinstance(groups,list):continue
  dropped=[k for k,v in groups if k not in declared_groups];groups[:]=[(k,v)for k,v in groups if k in declared_groups]
  for k in dropped:changes.append(dict(action='remove_unrepresented_gene_group',panel=panel,group=k,runtime_crash_causality_unverified=True))
  if panel=='anatomy'and'eyes'in declared_groups and not any(k=='eyes'for k,v in groups):groups.append(('eyes','face'));changes.append(dict(action='expose_declared_eye_color_group',group='eyes',camera='face'))
 color=fields(root,'color_genes')
 if color is None:color=[];root.append(('color_genes',color))
 setfield(color,'hair',hair_modifier_group);changes.append(dict(action='bind_hair_color_to_existing_choice_group',modifier_group=hair_modifier_group))
 return tree,changes
def build_original_color_tree(stock_tree):
 tree=copy.deepcopy(stock_tree);block=fields(tree,'color_genes')
 if block is None:raise ValueError('stock color root missing')
 assert [k for k,v in block if isinstance(v,list)]==['hair_color','skin_color','eye_color']
 block.insert(0,('portrait_group','uma'));return tree
def rename_round_color_references(tree):
 tree=copy.deepcopy(tree);changes=[]
 def visit(nodes,color_scope=False,path=[]):
  for i,(key,val)in enumerate(nodes):
   mapped=COLOR_ALIASES.get(key,key);scope=color_scope or mapped in COLOR_ALIASES.values()or key=='color_genes';now=path+[str(mapped)]
   if mapped!=key:changes.append(dict(action='restore_original_color_key',path=now,old=key,new=mapped))
   if isinstance(val,list):visit(val,scope,now)
   else:
    if isinstance(val,str)and val in COLOR_ALIASES:val=COLOR_ALIASES[val]
    if scope and isinstance(val,str)and re.fullmatch(r'[+-]?(?:\d+\.\d+|\.\d+)',val):
     rounded=format(Decimal(val).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'f').rstrip('0').rstrip('.')
     if rounded in['','-0']:rounded='0'
     if val!=rounded:changes.append(dict(action='color_decimal_at_most2',path=now,old=val,new=rounded))
     val=rounded
   nodes[i]=(mapped,val)
 visit(tree);return tree,changes
def dna_signature(item):
 dna=fields(item,'dna_modifiers');return json.dumps(dna,separators=(',',':'),sort_keys=True)if dna is not None else None
def deduplicate_ui_choices(tree):
 """Preserve runtime gene templates. Move default weight onto ordinary00 survivor and rewire fallback."""
 tree=copy.deepcopy(tree);changes=[]
 for group,block in tree:
  if not isinstance(block,list):continue
  pairs=[]
  for actor in['1001','1002']:
   if group=='uma_custom_headwear':pairs.append((f'uma_{actor}_headwear_80',f'uma_{actor}_headwear_none',False))
   else:
    kind={'uma_custom_clothes':'clothes','uma_custom_shoes':'shoes','uma_custom_socks':'socks'}.get(group)
    if kind:pairs.append((f'uma_default_{actor}_{kind}',f'uma_bdy{actor}_00_{kind}',True))
  for drop,keep,move_weight in pairs:
   old=fields(block,drop);new=fields(block,keep)
   if old is None or new is None or dna_signature(old)!=dna_signature(new):continue
   if move_weight and fields(old,'weight')is not None:setfield(new,'weight',copy.deepcopy(fields(old,'weight')))
   if one(block,'fallback')==drop:setfield(block,'fallback',keep)
   block[:]=[(k,v)for k,v in block if k!=drop];changes.append(dict(action='remove_duplicate_UI_choice_only',group=group,removed=drop,survivor=keep,default_weight_transferred=move_weight,runtime_gene_templates_deleted=False))
 return tree,changes
def main():
 OUT.mkdir(exist_ok=True);changes={};drafts={}
 stock=clausewitz((GAME/'common/genes/00_genes_color.txt').read_text(encoding='utf-8-sig'));drafts['000_uma_genes_color.txt']=build_original_color_tree(stock)
 for relative,dest,apply in [('common/genes/uma_body_morphs.txt','uma_body_morphs.contract.txt',apply_body_compatibility),('gfx/portraits/customization_rules/uma_portrait_customization.txt','uma_portrait_customization.contract.txt',apply_minimal_rules),('gfx/portraits/portrait_modifiers/uma_customization.txt','uma_customization.contract.txt',deduplicate_ui_choices),('common/ethnicities/uma_ethnicity.txt','uma_ethnicity.color-contract.txt',rename_round_color_references)]:
  result,notes=apply(clausewitz((V8/relative).read_text(encoding='utf-8-sig')));drafts[dest]=result;changes[dest]=notes
 for file,tree in drafts.items():(OUT/file).write_text(script_block(tree)+'\n',encoding='utf-8-sig')
 contract=dict(source_v8_read_only=True,final_mod_modified=False,apply_api=['apply_body_compatibility(tree)','apply_minimal_rules(tree, declared_groups, hair_modifier_group)','build_original_color_tree(stock_tree)','rename_round_color_references(tree)','deduplicate_ui_choices(tree)'],changes=changes,drafts={k:str(OUT/k)for k in drafts},color=dict(keys=['hair_color','skin_color','eye_color'],filename='000_uma_genes_color.txt',scope='portrait_group=uma only; retain original00_genes_color.txt exactly forhuman later load',max_decimal_digits=2,legacy_uma_color_file_must_be_removed_from_v9=True),portrait_types=dict(filename='000_uma_portrait_types.txt',stock_human_filename='00_human_types.txt',uma_all4_age18_unchanged=True),body=dict(regular_root='morph_genes (matches original)',hidden_reserved_noops_drive_no_model=True,body_shape_average_preserved=True,no_fixed_body_clothed=True,index_holes_preexisted_v7_and_are_not_claimed_crash_cause=True),unverified='No live game/ruler designer reproduction; face-empty/new no-binding visible shapes are concrete definition differences, not proven silent exit cause.')
 (OUT/'minimal-designer-contract.json').write_text(json.dumps(contract,indent=2),encoding='utf8');print('MINIMAL_CONTRACT',[(k,len(v))for k,v in changes.items()],list(drafts))
if __name__=='__main__':main()
