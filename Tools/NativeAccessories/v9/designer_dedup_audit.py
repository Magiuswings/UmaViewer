"""Readonly V7/V8/installed-game designer/color/duplicate-head audit. No final mod edits."""
import os,sys,json,re,hashlib,difflib,copy
from pathlib import Path
from collections import defaultdict,Counter
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
BASE=Path('E:/UmaViewer-Exports');V7=BASE/'2026-10-11-UMA-V7/UMA-V7';V8=BASE/'2026-10-12-UMA-V8/UMA-V8';GAME=Path('D:/steam/steamapps/common/Crusader Kings III/game');OUT=Path(__file__).parent
sys.path[:0]=[str(OUT.parent/'UmaV8Scripts'),'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter'];from asset_registration_audit import parse,children,value
from build_ck3_mod import parser_only
P=parser_only(Path('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))
FILES=['common/genes/uma_colors.txt','common/genes/uma_body_morphs.txt','common/genes/uma_parts.txt','common/portrait_types/uma_portrait_types.txt','gfx/portraits/customization_rules/uma_portrait_customization.txt','gfx/portraits/portrait_modifiers/uma_customization.txt']
def sha(data):return hashlib.sha256(data).hexdigest()
def canon(nodes):return[(n['key'],canon(n['children'])if n['children']is not None else n['value'])for n in nodes]
def walk(nodes,path=[]):
 for n in nodes:
  now=path+[n['key']]if n['key']is not None else path
  yield now,n
  if n['children']is not None:yield from walk(n['children'],now)
def gene_index(root):
 genes={};groups=defaultdict(list);indexes=[];files=list((root/'common/genes').glob('*.txt'))
 for file in sorted(files):
  t=parse(file.read_text(encoding='utf-8-sig'));containers=[]
  containers+=children(t,'morph_genes')+children(t,'color_genes')
  for special in children(t,'special_genes'):containers+=children(special['children'],'accessory_genes')
  for container in containers:
   kind=container['key'];scope=value(container['children'],'portrait_group','human')
   for g in container['children']:
    if g['children']is None:continue
    templates=[n for n in g['children']if n['children']is not None and value(n['children'],'index')is not None];summary=dict(name=g['key'],kind=kind,scope=scope,group=value(g['children'],'group'),file=str(file),line=g['line'],templates=[dict(name=n['key'],index=int(value(n['children'],'index')),visible=value(n['children'],'visible','yes'),line=n['line'])for n in templates]);genes[g['key']]=summary
    if summary['group']:groups[summary['group']].append(g['key'])
    ix=[n['index']for n in summary['templates']]
    if len(ix)!=len(set(ix)):indexes.append(dict(gene=g['key'],problem='duplicate_template_index',indexes=ix))
    if ix and sorted(ix)!=list(range(max(ix)+1)):indexes.append(dict(gene=g['key'],problem='non_contiguous_template_indices',indexes=ix))
 return genes,dict(groups),indexes
def designer(root):
 genes,groups,indexissues=gene_index(root);rulesfile=root/'gfx/portraits/customization_rules/uma_portrait_customization.txt';rules=children(parse(rulesfile.read_text(encoding='utf-8-sig')),'uma')[0]['children'];modfile=root/'gfx/portraits/portrait_modifiers/uma_customization.txt';mods=parse(modfile.read_text(encoding='utf-8-sig'));modnames={n['key']for n in mods};problems=[];sliders=[]
 for category in children(rules,'gene_groups'):
  for panel in category['children']:
   for group in panel['children']or[]:
    row=dict(panel=panel['key'],group=group['key'],camera=group['value'],declared_UMA_genes=groups.get(group['key'],[]),line=group['line']);sliders.append(row)
    if not row['declared_UMA_genes']:problems.append(dict(kind='configured_empty_gene_group',**row))
 for accesses in children(rules,'accessories'):
  for n in accesses['children']:
   if n['value']not in modnames:problems.append(dict(kind='unknown_customization_group',gene=n['key'],group=n['value'],line=n['line']))
 for n in rules:
  if n['key']and n['key'].startswith('accessory_color_override_block_')and n['value']not in modnames:problems.append(dict(kind='unknown_color_override_group',key=n['key'],group=n['value']))
 duplicatechoices=[];emptychoices=[];mode=[];groupstats=[];template_map={g:set(n['name']for n in d['templates'])for g,d in genes.items()};unknown=[]
 for group in mods:
  if group['children']is None:continue
  signatures=defaultdict(list);count=0
  for item in group['children']:
   if item['children']is None:continue
   if item['key']=='add_accessory_modifiers':
    gene=value(item['children'],'gene');template=value(item['children'],'template')
    if gene not in template_map or template not in template_map[gene]:unknown.append(dict(group=group['key'],line=item['line'],gene=gene,template=template,kind='auto_template_reference_missing'))
    continue
   dn=children(item['children'],'dna_modifiers')
   if not dn:continue
   count+=1;signatures[json.dumps(canon(dn[0]['children']),sort_keys=True)].append(dict(item=item['key'],line=item['line']));actions=children(dn[0]['children'],'accessory')
   if not dn[0]['children']:emptychoices.append(dict(group=group['key'],item=item['key'],line=item['line'],kind='empty_dna_modifiers'))
   allnone=bool(actions)
   for action in actions:
    f=action['children'];gene=value(f,'gene');template=value(f,'template');m=value(f,'mode');allnone&=bool(template and(template.endswith('_none')or template.startswith('no_')))
    if m!='add':mode.append(dict(group=group['key'],item=item['key'],line=action['line'],mode=m,gene=gene))
    if gene not in template_map or template not in template_map[gene]:unknown.append(dict(group=group['key'],item=item['key'],line=action['line'],gene=gene,template=template,kind='template_reference_missing'))
   if allnone:emptychoices.append(dict(group=group['key'],item=item['key'],line=item['line'],kind='explicit_none_only_valid_empty_choice'))
  duplicatechoices += [dict(group=group['key'],choices=items,kind='identical_dna_modifiers')for items in signatures.values()if len(items)>1]
  groupstats.append(dict(group=group['key'],usage=value(group['children'],'usage','both'),priority=value(group['children'],'priority','0'),fallback=value(group['children'],'fallback'),explicit_choices=count))
 body=genes.get('gene_bs_body_type');typesfile=root/'common/portrait_types/uma_portrait_types.txt'
 if not typesfile.exists():typesfile=root/'common/portrait_types/000_uma_portrait_types.txt'
 types=parse(typesfile.read_text(encoding='utf-8-sig'));types=children(types,'uma')[0]['children'];ages=[dict(type=n['key'],minimum_age=value(n['children'],'minimum_age'),maximum_age=value(n['children'],'maximum_age'),head=value(n['children'],'head'),torso=value(n['children'],'torso'))for n in types if n['key']in['uma_male','uma_female','uma_boy','uma_girl']]
 return dict(genes=genes,declared_groups=groups,index_issues=indexissues,configured_sliders=sliders,group_problems=problems,modifier_groups=groupstats,duplicate_choices=duplicatechoices,empty_choices=emptychoices,mode_violations=mode,unknown_template_references=unknown,body_regular_root='morph_genes',body_regular_gene=body,age18_types=ages,rules_color_binding=children(rules,'color_genes'))
def mesh_signature(file):
 tree=P.read_meshfile(str(file));full=[];render=[]
 for obj in tree.find('object'):
  sk=obj.find('skeleton');names=[b.tag for b in sk]if sk is not None else[]
  for m in obj.findall('mesh'):
   skin=m.find('skin');weighted=[]
   if skin is not None:
    ix=np.array(skin.attrib['ix']);w=np.array(skin.attrib['w']);weighted=sorted(set(ix[w>0].tolist()))
   record=dict(attributes=m.attrib,material=m.find('material').attrib if m.find('material')is not None else{},skin=skin.attrib if skin is not None else None)
   full.append(dict(**record,skeleton=[dict(name=b.tag,attributes=b.attrib)for b in sk]if sk is not None else None))
   reduced=dict(**record,weighted_bind=[dict(name=names[i],tx=sk[i].get('tx'))for i in weighted]);render.append(reduced)
 return dict(full_file_sha256=sha(file.read_bytes()),normalized_all_data_sha256=sha(json.dumps(full,sort_keys=True).encode()),render_payload_sha256=sha(json.dumps(render,sort_keys=True).encode()))
def models(root):
 parts=defaultdict(list);entity_defs=defaultdict(list);mesh_defs=defaultdict(list);blend_ids=defaultdict(list);refs=[]
 for file in sorted(root.rglob('*.asset')):
  t=parse(file.read_text(encoding='utf-8-sig'))
  for pdx in children(t,'pdxmesh'):
   fields=pdx['children'];name=value(fields,'name');mesh_defs[name].append(str(file))
   for b in children(fields,'blend_shape'):blend_ids[value(b['children'],'id')].append(dict(mesh=name,type=value(b['children'],'type'),asset=str(file)))
   for path,n in walk(fields):
    if n['children']is None and n['key']in['file','type','texture_diffuse','texture_normal','texture_specular']and n['value']and('/'in n['value']or'\\'in n['value']):refs.append(dict(asset=str(file),line=n['line'],path=path,reference=n['value'],violation='new_v9_basename_only_contract'))
  for e in children(t,'entity'):entity_defs[value(e['children'],'name')].append(str(file))
  actor=file.parent.name
  for part in['face','face_parts','cheek','tear','neck','neck_patch']:
   if re.match(r'uma_100[12]_'+part+r'_(?:\d+|base)\.asset$',file.name):parts[(actor,part)].append(str(file))
 registration=root.parent/'Reports/head-registration.json';rows=json.loads(registration.read_text())if registration.exists()else[];cheeks=[]
 for row in rows:
  if row['element']=='cheek':
   file=Path(row.get('mesh',row.get('mesh_path','')))
   if file.is_file():cheeks.append(dict(actor=str(row['actor']),variant=row['variant'],prefix=row['prefix'],mesh=str(file),**mesh_signature(file)))
 duplicates={}
 for key in['full_file_sha256','normalized_all_data_sha256','render_payload_sha256']:
  groups=defaultdict(list)
  for row in cheeks:groups[(row['actor'],row[key])].append(row)
  duplicates[key]=[dict(actor=actor,hash=h,meshes=items)for(actor,h),items in groups.items()if len(items)>1]
 missing=[]
 accessoryfile=root/'gfx/portraits/accessories/uma_parts.txt';acc=parse(accessoryfile.read_text(encoding='utf-8-sig'));accnames={n['key']for n in acc};
 for a in acc:
  for entity in children(a['children'],'entity'):
   name=value(entity['children'],'entity')
   if name and name not in entity_defs:missing.append(dict(kind='accessory_entity_missing',accessory=a['key'],entity=name,line=entity['line']))
 for file in sorted((root/'common/genes').glob('*.txt')):
  for path,n in walk(parse(file.read_text(encoding='utf-8-sig'))):
   if n['key']is None or not n['key'].isdigit()or n['children']is not None:continue
   if'uma_male'in path or'uma_female'in path or'uma_boy'in path or'uma_girl'in path:
    if n['value']!='empty'and n['value']not in accnames:missing.append(dict(kind='gene_accessory_id_missing',file=str(file),path=path,reference=n['value']))
 return dict(asset_count=len(list(root.rglob('*.asset'))),pdxmesh_count=len(mesh_defs),entity_count=len(entity_defs),duplicate_pdxmesh=[dict(name=n,files=f)for n,f in mesh_defs.items()if len(f)>1],duplicate_entity=[dict(name=n,files=f)for n,f in entity_defs.items()if len(f)>1],registration_closure_missing=missing,head_assets_by_actor_part=[dict(actor=a,part=p,assets=f,count=len(f),v9_requires_one_asset=True)for(a,p),f in sorted(parts.items())],cheeks=cheeks,cheek_duplicates=duplicates,nonshader_path_references=refs,blend_ids=blend_ids)
def main():
 OUT.mkdir(exist_ok=True);diffs=[]
 for relative in FILES:
  p=V7/relative;q=V8/relative
  if p.exists()and q.exists():
   old=p.read_text(encoding='utf-8-sig');new=q.read_text(encoding='utf-8-sig');diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='V7/'+relative,tofile='V8/'+relative));target=OUT/(relative.replace('/','__')+'.diff');target.write_text(diff,encoding='utf8');diffs.append(dict(file=relative,byte_identical=p.read_bytes()==q.read_bytes(),semantic_identical=canon(parse(old))==canon(parse(new)),diff=str(target),old_sha256=sha(p.read_bytes()),new_sha256=sha(q.read_bytes())))
 stockcolor=GAME/'common/genes/00_genes_color.txt';text=stockcolor.read_text(encoding='utf-8-sig');color=children(parse(text),'color_genes')[0];keys=[n['key']for n in color['children']if n['children']is not None];proposal=text.replace('color_genes = {','color_genes = {\n\tportrait_group = uma',1);(OUT/'000_uma_genes_color.contract.txt').write_text(proposal,encoding='utf-8-sig');stock_types=GAME/'common/portrait_types/00_human_types.txt';order=[dict(folder='common/genes',expected=['000_uma_genes_color.txt','00_genes_color.txt'],sort_check=sorted(['000_uma_genes_color.txt','00_genes_color.txt'])==['000_uma_genes_color.txt','00_genes_color.txt']),dict(folder='common/portrait_types',expected=['000_uma_portrait_types.txt','00_human_types.txt'],sort_check=sorted(['000_uma_portrait_types.txt','00_human_types.txt'])==['000_uma_portrait_types.txt','00_human_types.txt'])];seven=designer(V7);eight=designer(V8);m7=models(V7);m8=models(V8);stockgenes,stockgroups,stockix=gene_index(GAME);stockblend={}
 for file in[GAME/'gfx/models/portraits/female_head/female_head.asset',GAME/'gfx/models/portraits/male_head/male_head.asset']:
  if file.exists():
   for block in children(parse(file.read_text(encoding='utf-8-sig')),'pdxmesh'):
    for n in children(block['children'],'blend_shape'):stockblend[value(n['children'],'id')]=dict(file=str(file),type=value(n['children'],'type'))
 collided=[dict(id=n,UMA=refs,stock=stockblend[n],global_scope_not_proven=True)for n,refs in m8['blend_ids'].items()if n in stockblend];decimals=[]
 for file in(V8/'common').rglob('*.txt'):
  for i,line in enumerate(file.read_text(encoding='utf-8-sig').splitlines(),1):
   for match in re.finditer(r'(?<![A-Za-z_])(?:0?\.\d{3,}|\d+\.\d{3,})',line):
    if file.name=='uma_colors.txt'or file.parent.name=='ethnicities':decimals.append(dict(file=str(file),line=i,value=match.group()))
 result=dict(scope=dict(V7=str(V7),V8=str(V8),stock=str(GAME)),readonly=True,exact_diffs=diffs,V7_designer=seven,V8_designer=eight,stock_color_file=str(stockcolor),stock_color_sha256=sha(stockcolor.read_bytes()),stock_color_keys=keys,proposed_color_file=str(OUT/'000_uma_genes_color.contract.txt'),proposed_color_tree=canon(parse(proposal)),load_order=order,color_numeric_precision_violations=decimals,V7_models=m7,V8_models=m8,placeholder_stock_blend_id_reuse=collided,confirmed=['V7/V8 exact diffs saved; regular body root morph_genes matches installed stock syntax.','V8 declares no UMA morph gene group face, but customization_rules still lists anatomy.face.','V7/V8 custom color keys differ from original hair_color/skin_color/eye_color; input decimals exceed requested2digits.','Current V8 head assets are split pervariant; V9 requires peractor perelement one asset with multiple definitions if needed.'],inferences=['Empty configured UMA face group after deleting uma_head_points is a concrete new designer-input mismatch, candidate silent-exit trigger; no engine stacktrace proves causality.','Late UMA portrait type + dummy targets reusing stock blend IDs may affect default shape/UI caches; initialization/global scope behavior not verified by static reuse alone.'],unverified=['No live ruler-designer reproduction/stacktrace/game UI in this audit.','Ordinary-human white coloring cause requires fresh engine after key/order correction; same color file existed in V7, so rename alone is not a V8-only code delta.'])
 # Keep the large per-model blend map only in comparative JSON, never mutate stage/registration.
 (OUT/'designer-dedup-audit.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('DESIGNER_AUDIT','V7groups',seven['declared_groups'],'V8groups',eight['declared_groups'],'V8empty',eight['group_problems'],'duplicate_choices',eight['duplicate_choices'],'indices',eight['index_issues'],'unknownrefs',len(eight['unknown_template_references']));print('CHEEK_DUP',[(k,len(v))for k,v in m8['cheek_duplicates'].items()]);print('MODELS',m8['pdxmesh_count'],m8['entity_count'],'closure',len(m8['registration_closure_missing']),'pathrefs',len(m8['nonshader_path_references']),'stockblend_reuse',len(collided),'color_decimals',len(decimals))
if __name__=='__main__':main()
