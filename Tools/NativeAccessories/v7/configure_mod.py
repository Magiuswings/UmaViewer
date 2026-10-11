import os
"""Register V7 components without globally forcing clothes or body shrink."""
import copy,json,sys
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import clausewitz,one,values,script_block
def opt(node,key):
    found=values(node,key);return found[0]if found else None
mod=R/'UMA-V7';heads=json.loads((R/'Reports/head-registration.json').read_text());palette={x['actor']:x for x in json.loads((R/'Reports/palette-presets.json').read_text())};types=['uma_male','uma_female','uma_boy','uma_girl'];registrations=copy.deepcopy(heads)
clothfile=R/'Reports/clothing-registration.json'
if not clothfile.exists():raise FileNotFoundError('Clothing registration must be complete before final configuration')
cloth=json.loads(clothfile.read_text());families=cloth['families']
for family in families:
    for element,row in family['parts'].items():
        variants=row.get('actor_variants')or[]
        if isinstance(variants,dict):variants=[dict(v,actor=k)for k,v in variants.items()]
        covered={str(c)for v in variants for c in v.get('characters',[v['actor']]if v.get('actor')else[])}
        base_characters=[c for c in family['characters']if str(c)not in covered]or family['characters']
        variants=[{'entity':row['entity'],'template':'uma_'+family['family']+'_'+element,'characters':base_characters},*variants]
        for variant in variants:
            variant_actor=variant.get('actor',variant.get('characters',['base'])[0]);name=variant.get('template')or'uma_'+family['family']+'_'+element+'_'+str(variant_actor);registrations.append({'element':element,'entity':variant.get('entity',row['entity']),'template':name,'accessory_id':name,'gene':'uma_'+element,'shared_pose':'torso','node':None,'family':family['family'],'characters':variant.get('characters',[variant['actor']]if variant.get('actor')else family['characters']),'variant':family['family'],'actor':variant.get('actor','shared'),'optional':False})
def write(rel,node):
    (mod/rel).write_text(script_block(node)+'\n',encoding='utf-8-sig')
elements=sorted({x['element']for x in registrations}|{'clothes','shoes','socks','headwear'})
genes=[];accessories=[]
for element in elements:
    empty='uma_'+element+'_none';templates=[(empty,[('index','0'),*[(kind,[('1','empty')])for kind in types]])]
    for i,row in enumerate([r for r in registrations if r['element']==element],1):
        templates.append((row['template'],[('index',str(i)),*[(kind,[('1',row['accessory_id'])])for kind in types]]))
        binding=[('node',row['node'])]if row.get('node')else[('shared_pose_entity',row.get('shared_pose')or'head')]
        accessories.append((row['accessory_id'],[('portrait_group','uma'),('entity',[('entity',row['entity']),*binding])]))
    genes.append(('uma_'+element,templates))
write('common/genes/uma_parts.txt',[('special_genes',[('accessory_genes',[('portrait_group','uma'),*genes])])])
write('gfx/portraits/accessories/uma_parts.txt',accessories)
# Names of color genes are independent from shader color channel names.
write('common/genes/uma_colors.txt',[('color_genes',[('portrait_group','uma'),("uma_hair_color",[('group','hair'),('color','hair'),('blend_range',[(None,'0.0'),(None,'0.0')])]),('uma_skin_color',[('sync_inheritance_with','uma_hair_color'),('group','body'),('color','skin'),('blend_range',[(None,'0.55'),(None,'0.65')])]),('uma_eye_color',[('sync_inheritance_with','uma_hair_color'),('group','eyes'),('color','eye'),('blend_range',[(None,'0.0'),(None,'0.0')])])])])
pointtemplates=[]
for actor in ['1001','1002']:
    setting=[('setting',[('attribute','uma_head_points_1002'),('value',[('min','0.0'),('max','1.0')])])]if actor=='1002'else[]
    pointtemplates.append(('uma_head_points_'+actor,[('index',str(int(actor)-1001)),('uma_male',setting),*[(kind,'uma_male')for kind in types[1:]]]))
write('common/genes/uma_head_points.txt',[('morph_genes',[('portrait_group','uma'),('uma_head_points',[('group','face'),*pointtemplates])])])
# Keep native body gene keys; retain only real body/additive settings. No-op BS
# remain in the asset for diagnostics, but do not become meaningless genes.
gene_file=mod/'common/genes/uma_body_morphs.txt';bodygenes=clausewitz(gene_file.read_text(encoding='utf-8-sig'));asset=clausewitz((mod/'gfx/models/portraits/uma/0001/uma_0001_body_base.asset').read_text());pdxmesh=one(asset,'pdxmesh');realbs={one(x,'id')for x in values(pdxmesh,'blend_shape')if not one(x,'type').endswith('_none.mesh')};entity=one(asset,'entity');validattrs={one(x,'name')for x in values(entity,'attribute')if opt(x,'blend_shape')in realbs or opt(x,'additive_animation')is not None};validattrs.add('head_body_height')
def clean(node):
    out=[]
    for key,val in node:
        if key=='setting'and one(val,'attribute')not in validattrs:continue
        out.append((key,clean(val)if isinstance(val,list)else val))
    return out
bodygenes=clean(bodygenes);morphs=one(bodygenes,'morph_genes')
def has_setting(node):return any(k=='setting'or(isinstance(v,list)and has_setting(v))for k,v in node)
neutral_templates={'body_average','body_shape_average','bust_default'}
for key,gene in morphs:
    if isinstance(gene,list):gene[:]=[(k,v)for k,v in gene if not(isinstance(v,list)and opt(v,'index')is not None and k not in neutral_templates and not has_setting(v))]
bodytype=one(morphs,'gene_bs_body_type');bodytype[:]=[(k,v)for k,v in bodytype if k!='uma_body_s1']
bodytype.append(('uma_body_s1',[('index','5'),('uma_male',[]),('uma_female',[('setting',[('attribute','bs_body_gaunt_1'),('value',[('min','0.0'),('max','1.0')])])]),('uma_boy','uma_male'),('uma_girl','uma_female')]))
gene_file.write_text(script_block(bodygenes)+'\n',encoding='utf-8-sig')
ethnicities=[]
for actor in ['1001','1002']:
    entries=[('portrait_group','uma'),('uma_height',[('100',[('name','normal_height'),('range',[(None,'.5'),(None,'.5')])])]),('gene_bs_body_type',[('100',[('name','body_average'if actor=='1001'else'uma_body_s1'),('range',[(None,'1'),(None,'1')])])]),('gene_bs_body_shape',[('100',[('name','body_shape_average'),('range',[(None,'.5'),(None,'.5')])])]),('gene_bs_bust',[('100',[('name','bust_default'if actor=='1001'else'bust_shape_1_full'),('range',[(None,'1'),(None,'1')])])]),('uma_head_points',[('100',[('name','uma_head_points_'+actor),('range',[(None,'1'),(None,'1')])])])]
    for category in ['skin','hair','eye']:entries.append(('uma_'+category+'_color',[('100',[(None,format(v,'.9f'))for v in palette[actor]['colors'][category]['rectangle']])]))
    for element in elements:
        options=[r for r in registrations if r['element']==element and((r.get('actor')==actor and r.get('variant')==('base'if element in['tail','neck']else'00'))or(r.get('family')in[actor+'_00','bdy'+actor+'_00']and actor in list(map(str,r.get('characters',[])))))]
        choice=options[0]['template']if options and not options[0].get('optional')else'uma_'+element+'_none';entries.append(('uma_'+element,[('100',[('name',choice),('range',[(None,'1'),(None,'1')])])]))
    ethnicities.append(('uma_ethnicity'if actor=='1001'else'uma_1002_ethnicity',entries))
write('common/ethnicities/uma_ethnicity.txt',ethnicities)
# One visible line per palette rectangle, as requested.
f=mod/'common/ethnicities/uma_ethnicity.txt';s=f.read_text(encoding='utf-8-sig')
import re
s=re.sub(r'(uma_(?:skin|hair|eye)_color) = \{\s+100 = \{\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+\}\s+\}',r'\1 = { 100 = { \2 \3 \4 \5 } }',s);f.write_text(s,encoding='utf-8-sig')
def selection(gene,template):return('accessory',[('mode','replace'),('gene',gene),('template',template),('value','1.0')])
mods=[]
for position,element in enumerate(['clothes','headwear','shoes','socks'],2):
    block=[('portrait_group','uma'),('usage','customization'),('interface_position',str(position)),('add_accessory_modifiers',[('gene','uma_'+element),('template','uma_'+element+'_none')])]
    if element!='headwear':
        for row in registrations:
            if row['element']==element:block.append(('add_accessory_modifiers',[('gene','uma_'+element),('template',row['template'])]))
    else:
        # A source headwear prefab also replaces hairstyle/ear geometry. Switch
        # matching components together; never put variant 80 hair underneath.
        for actor,variant in sorted({(r['actor'],r['variant'])for r in heads if r['element']=='face'}):
            selections=[]
            for part in ['face','face_parts','eye','brow','hair','ear','headwear','cheek','tear','neck','neck_patch']:
                partvariant='base'if part=='neck'else variant;row=next((r for r in heads if r['actor']==actor and r['variant']==partvariant and r['element']==part),None);template=row['template']if row and not row['optional']else'uma_'+part+'_none';selections.append(selection('uma_'+part,template))
            selections.append(('morph',[('mode','replace'),('gene','uma_head_points'),('template','uma_head_points_'+actor),('value','1.0')]))
            block.append(('uma_'+actor+'_headwear_'+variant,[('dna_modifiers',selections),('weight',[('base','1')])]))
        # Body-prefab headwear is added separately by the clothing exporter.
        for row in registrations:
            if row['element']=='headwear'and row.get('family'):block.append(('add_accessory_modifiers',[('gene','uma_headwear'),('template',row['template'])]))
    mods.append(('uma_custom_'+element,block))
hair=[('portrait_group','uma'),('usage','customization'),('interface_position','0')]
for row in heads:
    if row['element']=='hair':hair.append(('add_accessory_modifiers',[('gene','uma_hair'),('template',row['template'])]))
mods.append(('uma_custom_hair',hair));write('gfx/portraits/portrait_modifiers/uma_customization.txt',mods)
rules=[('default_age','25'),('min_age_for_sexuality','10'),('accessories',[("uma_"+part,"uma_custom_"+part)for part in ['hair','clothes','headwear','shoes','socks']]),('sex_only_genes',[('female',[(None,'gene_bs_bust')])]),('hidden_slider_genes',[(None,'uma_head_points')]),('gene_groups',[('anatomy',[('body','full_body'),('face','face')]),('hair',[('hair','face')])]),('color_genes',[('hair','uma_custom_hair')]),*[("accessory_color_override_block_"+str(i),'uma_custom_'+part)for i,part in enumerate(['clothes','headwear','shoes','socks'])]]
write('gfx/portraits/customization_rules/uma_portrait_customization.txt',[('uma',rules)])
report={'head_component_records':len(heads),'registered_records':len(registrations),'families':len(families),'wardrobe_groups':['uma_custom_clothes','uma_custom_headwear','uma_custom_shoes','uma_custom_socks'],'fixed_global_component_modifiers':False,'unsupported_body_gene_attributes_removed':True,'supported_body_attributes':sorted(validattrs),'custom_gene_names':[g[0]for g in genes]+['uma_skin_color','uma_hair_color','uma_eye_color','uma_height','uma_head_points'],'ethnicities':[e[0]for e in ethnicities],'registrations':registrations};(R/'Reports/configuration.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('CONFIGURED',len(registrations),'records',len(families),'families',flush=True)
