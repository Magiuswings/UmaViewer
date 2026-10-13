"""Generate a reviewable registration-only draft; never write the formal UMA mod."""
import re,json,copy,hashlib,csv,shutil,datetime
from pathlib import Path
V10=Path(r'E:\UmaViewer-Exports\2026-10-13-UMA-V10')
ROOT=V10/'UMA-V10';OUT=V10/'RegistrationDraft';DRAFT=OUT/'UMA-V10'
GAME=Path(r'D:\steam\steamapps\common\Crusader Kings III\game')
PM=Path('gfx/portraits/portrait_modifiers/uma_customization.txt')
RULE=Path('gfx/portraits/customization_rules/uma_portrait_customization.txt')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(p):return p.read_text(encoding='utf-8-sig')
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8-sig')
def report(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def parse(s):
    s=re.sub(r'#[^\n]*','',s);ts=re.findall(r'"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=]+',s);i=0
    def block(end=False):
        nonlocal i
        out=[]
        while i<len(ts):
            t=ts[i];i+=1
            if t=='}':
                assert end;return out
            if t=='{':out.append((None,block(True)));continue
            if i<len(ts) and ts[i]=='=':
                i+=1;value=ts[i];i+=1
                out.append((t,block(True) if value=='{' else value))
            else:out.append((None,t))
        assert not end;return out
    return block()
def get(n,k):return next((v for a,v in n if a==k),None)
def setv(n,k,v):
    for i,(a,b) in enumerate(n):
        if a==k:n[i]=(k,v);return
    n.append((k,v))
def emit(n,depth=0):
    lines=[];ind='\t'*depth
    for k,v in n:
        lead=(k+' = ') if k else ''
        if isinstance(v,list):lines.extend([ind+lead+'{',emit(v,depth+1),ind+'}'])
        else:lines.append(ind+lead+v)
    return '\n'.join(lines)
def modifiers(group):return [(k,v) for k,v in group if isinstance(v,list) and get(v,'dna_modifiers') is not None]
def dna_modifier(gene,template):return ('accessory',[('mode','add'),('gene',gene),('template',template),('value','1.0')])
formal_paths=[ROOT/PM,ROOT/RULE,*sorted((ROOT/'common/genes').glob('*.txt')),*sorted((ROOT/'common/portrait_types').glob('*.txt'))]
before={str(p):sha(p) for p in formal_paths}
original=parse(text(ROOT/PM));rules=parse(text(ROOT/RULE));uma_rule=get(rules,'uma');assert uma_rule
old_groups=dict(original);old_head=old_groups['uma_custom_headwear'];old_actor=old_groups['uma_custom_character']
head_mods=dict(modifiers(old_head));actor_mods=dict(modifiers(old_actor))
parts=get(get(parse(text(ROOT/'common/genes/uma_parts.txt')),'special_genes'),'accessory_genes')
templates={k:[a for a,b in v if a and isinstance(b,list)] for k,v in parts if k!='portrait_group' and isinstance(v,list)}
body=get(parse(text(ROOT/'common/genes/uma_body_morphs.txt')),'morph_genes')
morph_templates={k:[a for a,b in v if a and isinstance(b,list) and a!='blend_range'] for k,v in body if k!='portrait_group' and isinstance(v,list)}
registrations=json.loads(text(V10/'Reports/configuration.json'))['registrations'];heads=json.loads(text(V10/'Reports/head-registration.json'))
runtime=[];custom=[];runtime_map={};wardrobe_genes=['uma_clothes','uma_headwear','uma_shoes','uma_socks']
actor_group=[('portrait_group','uma'),('usage','customization'),('interface_position','0'),('priority','30'),('selection_behavior','max')]
actor_options=[]
for old_name,old_opt in modifiers(old_head):
    m=re.fullmatch(r'uma_(\d+)_headwear_(\d+|none)',old_name)
    if not m:
        assert all(get(d,'gene')=='uma_headwear' for k,d in get(old_opt,'dna_modifiers')),old_name
        continue
    actor,variant=m.groups();name=f'uma_actor_{actor}_{variant}';component_dna=[copy.deepcopy((kind,dna)) for kind,dna in get(old_opt,'dna_modifiers') if get(dna,'gene') not in wardrobe_genes]
    color_body=copy.deepcopy(get(actor_mods['uma_character_'+actor],'dna_modifiers'))
    actor_group.append((name,[('dna_modifiers',component_dna+color_body),('weight',[('base','1')])]))
    actor_options.append(dict(option=name,actor=actor,variant=variant,genes=[get(d,'gene') for k,d in component_dna+color_body]))
custom.append(('uma_custom_character',actor_group))

# Existing flag/default logic remains game-only. Head components move to the actor group.
game_actor=copy.deepcopy(old_actor);setv(game_actor,'usage','game');setv(game_actor,'priority','1')
game_actor=[(k,v) for k,v in game_actor if k!='interface_position']
for name,opt in modifiers(game_actor):
    actor=name.rsplit('_',1)[-1];components=copy.deepcopy(get(head_mods[f'uma_{actor}_headwear_00'],'dna_modifiers'))
    components=[(k,d) for k,d in components if get(d,'gene') not in wardrobe_genes]
    setv(opt,'dna_modifiers',components+get(opt,'dna_modifiers'))
designer_actor=copy.deepcopy(dict(modifiers(game_actor))['uma_character_1001']);setv(designer_actor,'weight',[('base','1')])
game_actor.append(('uma_designer_default_actor',designer_actor));runtime.append(('uma_game_character',game_actor));runtime_map['uma_game_character']='uma_designer_default_actor'
for position,gene in enumerate(wardrobe_genes,2):
    suffix=gene.removeprefix('uma_');old_key='uma_custom_'+suffix;game_key='uma_game_'+suffix
    group=copy.deepcopy(old_groups[old_key]);setv(group,'usage','game');group=[(k,v) for k,v in group if k!='interface_position']
    for name,opt in modifiers(group):
        setv(opt,'dna_modifiers',[(k,d) for k,d in get(opt,'dna_modifiers') if get(d,'gene')==gene])
        assert len(get(opt,'dna_modifiers'))==1,(gene,name)
    fallback=get(group,'fallback');default=copy.deepcopy(dict(modifiers(group))[fallback]);setv(default,'weight',[('base','1')])
    designer='uma_designer_default_'+suffix;group.append((designer,default));runtime.append((game_key,group));runtime_map[game_key]=designer
    cg=[('portrait_group','uma'),('usage','customization'),('interface_position',str(position)),('priority',str(30+position))]
    for template in templates[gene]:cg.append(('add_accessory_modifiers',[('gene',gene),('template',template)]))
    custom.append((old_key,cg))
all_groups=runtime+custom
write(DRAFT/PM,'# Draft: game defaults and editor choices deliberately have separate usage.\n'+emit(all_groups)+'\n')
setv(uma_rule,'modifier_overrides',list(runtime_map.items()))
setv(uma_rule,'accessories',[('uma_head','uma_custom_character')]+[(g,'uma_custom_'+g.removeprefix('uma_')) for g in wardrobe_genes])
setv(uma_rule,'color_genes',[('hair','uma_custom_character')])
write(DRAFT/RULE,emit(rules)+'\n')
for p in sorted((ROOT/'common/genes').glob('*.txt')):
    target=DRAFT/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)

sources=[]
def evidence(rel,needles):
    p=GAME/rel;lines=text(p).splitlines()
    for needle,meaning in needles:
        hits=[i+1 for i,line in enumerate(lines) if needle in line]
        assert hits,(rel,needle)
        sources.append(dict(file=str(p),sha256=sha(p),line=hits[0],matched=lines[hits[0]-1].strip(),meaning=meaning))
evidence(Path('gfx/portraits/portrait_modifiers/_portrait_modifiers.info'),[
    ('usage = customization/game/both/none','group usage enum'),('portrait_group = human','portrait group is set before modifiers/helpers'),('priority = 2','higher priority applies later and overwrites previous ones'),('dna_modifiers = {','selected option applies a list of DNA operations'),('mode = add\t/replace','morph operation modes'),('mode = add','authored accessory operation supports add'),('add_accessory_modifiers = {','expands all accessory variants from gene/template')])
evidence(Path('gfx/portraits/customization_rules/_customization_rules.info'),[
    ('Portrait modifiers (from','modifier_overrides is forced ruler designer defaults, not runtime-editor mapping'),('root: not set','ruler designer weights have no character root'),('An entry is only applied','forced modifier weight must be positive'),('Each entry is','group=modifier reference shape'),('For each accessory gene','accessories maps accessory gene to the custom option group'),('All four are required','four accessory color override groups required')])
evidence(Path('gfx/portraits/portrait_modifiers/00_custom_clothes.txt'),[('usage = customization','stock customization group usage'),('add_accessory_modifiers = {','stock clothing helper syntax')])
evidence(Path('gfx/portraits/portrait_modifiers/01_clothes_base.txt'),[('Special group for the ruler designer only','stock separate game group for designer override'),('ruler_designer_clothes = {','stock no-character designer override item')])
evidence(Path('gfx/portraits/customization_rules/00_portrait_customization.txt'),[('clothes = ruler_designer_clothes','actual stock group=modifier override')])
evidence(Path('gui/window_barbershop.gui'),[('BarbershopAccessoryCategory.OnSelectFiltered','temporary option selection enters native UI API'),('BarbershopWindow.ApplyAndClose','apply button submits appearance through native API'),('BarbershopWindow.CloseWithoutSave','cancel path closes without saving')])
report(OUT/'api_sources.json',sources)
write(OUT/'api_sources.txt','\n'.join(f'{s["file"]}:{s["line"]}\n{s["matched"]}\n{s["meaning"]}\n' for s in sources))

errors=[];refs=[];helper_count=0
for groupname,group in all_groups:
    usage=get(group,'usage');assert usage in ('game','customization')
    if usage=='customization':
        s=emit(group);assert 'has_character_flag' not in s and 'is_valid_custom' not in s and 'scope:' not in s
    for key,value in group:
        if key=='add_accessory_modifiers':
            helper_count+=1;g=get(value,'gene');t=get(value,'template');assert t in templates.get(g,[])
            refs.append(dict(group=groupname,usage=usage,source='add_accessory_modifiers',gene=g,template=t,valid=True))
    for name,opt in modifiers(group):
        for kind,d in get(opt,'dna_modifiers'):
            gene=get(d,'gene');template=get(d,'template');mode=get(d,'mode')
            if kind=='accessory':assert template in templates.get(gene,[]) and mode=='add'
            elif kind=='morph':assert template in morph_templates.get(gene,[])
            elif kind=='color':
                assert gene in ('skin_color','hair_color','eye_color')
                for coord in ('x','y'):assert abs(float(get(d,coord))*100-round(float(get(d,coord))*100))<1e-8
            refs.append(dict(group=groupname,usage=usage,option=name,kind=kind,gene=gene,template=template,mode=mode,valid=True))
all_names=dict(all_groups)
for g,m in get(uma_rule,'modifier_overrides'):
    assert g in all_names and m in dict(modifiers(all_names[g]));opt=dict(modifiers(all_names[g]))[m]
    assert get(get(opt,'weight'),'base')=='1' and 'has_character_flag' not in emit(opt)
for gene,group in get(uma_rule,'accessories'):assert gene in templates and group in all_names and get(all_names[group],'usage')=='customization'
for i in range(4):assert get(uma_rule,'accessory_color_override_block_'+str(i)) in all_names
assert len(runtime)==5 and len(custom)==5
assert len([r for r in refs if r.get('source')=='add_accessory_modifiers'])==sum(len(templates[g]) for g in wardrobe_genes)
assert before=={str(p):sha(p) for p in formal_paths},'Formal mod changed during candidate build'
preserved={str(p.relative_to(ROOT)):dict(source_sha256=sha(p),draft_sha256=sha(DRAFT/p.relative_to(ROOT)),same=sha(p)==sha(DRAFT/p.relative_to(ROOT))) for p in sorted((ROOT/'common/genes').glob('*.txt'))}
report(OUT/'reference_closure.json',refs)
result=dict(passed=True,formal_mod_unmodified=True,input_hashes=before,gene_files_byte_identical=preserved,game_groups=[k for k,v in runtime],custom_groups=[k for k,v in custom],usage_both_count=0,custom_character_condition_count=0,clothing_helpers=helper_count,wardrobe_template_counts={g:len(templates[g]) for g in wardrobe_genes},actor_presets=actor_options,designer_overrides=runtime_map,validated_references=len(refs),headwear_custom_contains_only_wardrobe_gene=True,actor_custom_contains_no_wardrobe_genes=True,character_flag_logic_preserved_only_in_game=True,ethnicity_files_modified=False,stock_color_keys_preserved=True,color_coordinate_precision=0.01,body_gene_file_preserved=True,portrait_type_file_sha256={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'common/portrait_types').glob('*.txt')},four_age_boundary_preserved=True,authored_accessory_mode='add',helper_generated_mode='engine internal; helper schema has no mode field; not fabricated',CK3_engine_executed=False,barber_save_roundtrip_executed=False,open_runtime_checks=['Ruler designer shows each accessory template with generated label and selects both actor presets.','Custom actor multi-DNA selection updates head/eye/brow/hair/ear/tail together while headwear changes only the hat accessory.','After ApplyAndClose and save/reload, native custom selections retain priority over game actor-flag defaults.','Confirm stock hair picker/individual morphology edits interact as intended with authored full actor preset modifiers.'])
report(OUT/'closure_validation.json',result)
write(OUT/'README.txt',f'''RegistrationDraft：独立候选，未写正式Mod\n\n静态闭包通过，四个custom服装组共 {helper_count} 个真实gene/template helper，每个模板来自当前uma_parts.txt；包括none。game/custom没有both；custom不含character flag、character作用域权重或is_valid_custom。\n\n输出 UMA-V10/gfx/portraits/portrait_modifiers/uma_customization.txt 与 customization_rules/uma_portrait_customization.txt 是待主线程审阅的替换候选。common/genes三个文件按字节复制，仅用于闭包复核，内容未修改。正式Mod原文件SHA-256前后一致。\n\n头组件从旧headwear组选项拆成独立uma_custom_character多基因preset，保留每个角色/发饰形态的head、eye、brow、hair、ear、tail，以及cheek/tear控制，附原stock颜色和身体BS模板。四组衣服、头饰、鞋、袜只注册本组gene，使用原版add_accessory_modifiers；头饰不再捆绑换角色。\n\n规则 accessories 的 uma_head→uma_custom_character 负责角色preset在编辑器中的入口。modifier_overrides是ruler designer专用group=modifier默认项，不能称为game/custom互相映射。候选将五个game组各加入无角色条件、weight base=1的designer default并在rules明确引用；游戏自动默认仍沿用原actor flag逻辑。custom优先级30及以上，game保留原优先级1、10、12、13、14，依据官方info的后应用覆盖说明。\n\nBarber源码证据仅确认 OnSelectFiltered → ApplyAndClose 提交与 CloseWithoutSave取消。具体存档字段、保存后重开是否按同一优先级覆盖actorflag，均为引擎内部行为；本次未运行CK3，不能作为已测试结果。下一步应实机完成创建1001、切1002、改四组附件、进入游戏、Barber提交、存档重载的验收。\n\n所有手写accessory DNA mode=add；add_accessory_modifiers官方schema不提供mode字段，候选不添加虚构参数，也不声称已看到引擎生成后的mode。原BS、stock color key、0.01色彩精度、四年龄18边界和ethnicity附件禁用均保持。\n\napi_sources.json/txt记录本机原版的实际文件、行号与SHA-256；reference_closure.json保留每个gene/template引用，closure_validation.json记录验证和实机未完成项。\n''')
print(json.dumps(dict(output=str(OUT),game_groups=5,custom_groups=5,actor_presets=len(actor_options),helpers=helper_count,templates=result['wardrobe_template_counts'],references=len(refs),formal_unmodified=True),ensure_ascii=False,indent=2))
