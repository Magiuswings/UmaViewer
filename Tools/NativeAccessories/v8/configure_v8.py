"""Accessory choices belong to portrait modifiers; ethnicity contains regular genes only."""
import json,sys,copy,re
from paths_v8 import ROOT,V7,REPO,MOD
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import clausewitz,one,values,script_block
def write(rel,tree):
    file=MOD/rel;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(script_block(tree)+'\n',encoding='utf-8-sig'if file.suffix=='.txt'else'utf8')
conf=json.loads((ROOT/'Reports/configuration.json').read_text());rows=conf['registrations'];heads=[r for r in rows if not r.get('family')];colors={r['actor']:r['colors']for r in json.loads((ROOT/'Reports/palette-presets.json').read_text())}
accessory_genes=one(one(clausewitz((MOD/'common/genes/uma_parts.txt').read_text(encoding='utf-8-sig')),'special_genes'),'accessory_genes');custom_names={k for k,v in accessory_genes if isinstance(v,list)}
ethnicity=clausewitz((MOD/'common/ethnicities/uma_ethnicity.txt').read_text(encoding='utf-8-sig'))
for name,entry in ethnicity:entry[:]=[(k,v)for k,v in entry if k not in custom_names and k not in ['uma_head_points','uma_height']]
write('common/ethnicities/uma_ethnicity.txt',ethnicity)
headpoints=MOD/'common/genes/uma_head_points.txt'
if headpoints.exists():headpoints.unlink()
genefile=MOD/'common/genes/uma_body_morphs.txt';genes=clausewitz(genefile.read_text(encoding='utf-8-sig'));morph=one(genes,'morph_genes');supported={'bs_body_fat_1','bs_body_gaunt_1',*['bs_body_breast_shape_'+str(i)for i in range(1,5)]}
def clean(node):
    out=[]
    for k,v in node:
        if k=='uma_height':continue
        if k=='setting'and one(v,'attribute')not in supported:continue
        out.append((k,clean(v)if isinstance(v,list)else v))
    return out
write('common/genes/uma_body_morphs.txt',clean(genes))
def choice(gene,template):return('accessory',[('mode','add'),('gene',gene),('template',template),('value','1.0')])
def weight(actor,default=False):
    base='100'if default else'0';result=[('base',base)]
    if actor=='1002':result.append(('modifier',[('add','1000'),('has_character_flag','uma_actor_1002')]))
    elif actor=='1001':result.append(('modifier',[('factor','0'),('has_character_flag','uma_actor_1002')]))
    return('weight',result)
mods=[]
headset=[('portrait_group','uma'),('usage','both'),('interface_position','1'),('priority','10'),('selection_behavior','max'),('fallback','uma_1001_headwear_00')]
for actor,variant in sorted({(r['actor'],r['variant'])for r in heads if r['element']=='face'}):
    selections=[]
    for part in ['face','face_parts','eye','brow','hair','ear','headwear','cheek','tear','neck','neck_patch']:
        pv='base'if part=='neck'else variant;r=next((r for r in heads if r['actor']==actor and r['variant']==pv and r['element']==part),None);template=r['template']if r and not r.get('optional')else'uma_'+part+'_none';selections.append(choice('uma_'+part,template))
    selections.append(choice('uma_tail','uma_'+actor+'_tail_base'))
    headitem=[('dna_modifiers',selections),weight(actor,actor=='1001'and variant=='00')]
    if variant!='00':headitem[-1]=('weight',[('base','0')])
    headset.append(('uma_'+actor+'_headwear_'+variant,headitem))
for actor in ['1001','1002']:
    source_item=next(v for k,v in headset if k=='uma_'+actor+'_headwear_80')
    headset.append(('uma_'+actor+'_headwear_none',copy.deepcopy(source_item)))
for r in rows:
    if r['element']=='headwear'and r.get('family'):headset.append((r['template'],[('dna_modifiers',[choice(r['gene'],r['template'])]),('weight',[('base','0')])]))
mods.append(('uma_custom_headwear',headset))
for i,part in enumerate(['clothes','shoes','socks'],2):
    group=[('portrait_group','uma'),('usage','both'),('interface_position',str(i)),('priority',str(10+i)),('selection_behavior','max'),('fallback','uma_default_1001_'+part)]
    for actor in ['1001','1002']:
        template='uma_bdy'+actor+'_00_'+part;group.append(('uma_default_'+actor+'_'+part,[('dna_modifiers',[choice('uma_'+part,template)]),weight(actor,actor=='1001')]))
    group.append(('uma_'+part+'_none',[('dna_modifiers',[choice('uma_'+part,'uma_'+part+'_none')]),('weight',[('base','0')])]))
    for r in rows:
        if r['element']==part:group.append((r['template'],[('dna_modifiers',[choice(r['gene'],r['template'])]),('weight',[('base','0')])]))
    mods.append(('uma_custom_'+part,group))
# Actor preset is regular color/body DNA only, so replace is legal here.
actors=[('portrait_group','uma'),('usage','both'),('interface_position','0'),('priority','1'),('selection_behavior','max'),('fallback','uma_character_1001')]
for actor in ['1001','1002']:
    regular=[]
    for kind in ['skin','hair','eye']:
        xy=colors[actor][kind]['xy'];regular.append(('color',[('mode','replace'),('gene','uma_'+kind+'_color'),('x',str(xy[0])),('y',str(xy[1]))]))
    for gene,temp in [('gene_bs_body_type','body_average'if actor=='1001'else'uma_body_s1'),('gene_bs_body_shape','body_shape_average'),('gene_bs_bust','bust_default'if actor=='1001'else'bust_shape_1_full')]:regular.append(('morph',[('mode','replace'),('gene',gene),('template',temp),('value','1.0')]))
    actors.append(('uma_character_'+actor,[('dna_modifiers',regular),weight(actor,actor=='1001')]))
mods.append(('uma_custom_character',actors));write('gfx/portraits/portrait_modifiers/uma_customization.txt',mods)
write('common/scripted_effects/uma_character_test.txt',[("uma_select_1001_effect",[('remove_character_flag','uma_actor_1002'),('set_ethnicity','uma_ethnicity')]),('uma_select_1002_effect',[('set_character_flag','uma_actor_1002'),('set_ethnicity','uma_1002_ethnicity')])])
rules=one(clausewitz((MOD/'gfx/portraits/customization_rules/uma_portrait_customization.txt').read_text(encoding='utf-8-sig')),'uma')
rules[:]=[(k,v)for k,v in rules if k not in ['hidden_slider_genes','color_genes']]
for k,v in rules:
    if k=='accessories':v[:]=[(a,b)for a,b in v if a!='uma_hair']
write('gfx/portraits/customization_rules/uma_portrait_customization.txt',[('uma',rules)])
for f in MOD.rglob('*.txt'):
    s=f.read_text(encoding='utf-8-sig');assert not re.search(r'uma_head_points|uma_height',s),f
(ROOT/'Reports/modifier-registration.json').write_text(json.dumps({'accessory_mode':'add','ethnicity_accessories_removed':True,'head_additive_gene_removed':True,'height_additive_test_disabled':True,'defaults':'usage both/max/fallback; flag uma_actor_1002','test_effects':['uma_select_1001_effect','uma_select_1002_effect']},indent=2),encoding='utf8')
print('V8_CUSTOMIZATION_REGISTERED',len(mods),'groups',flush=True)
