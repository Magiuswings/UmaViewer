"""Independent file-level checks for RegistrationDraft (no builder import)."""
import re,json,hashlib,collections
from pathlib import Path
V=Path(r'E:\UmaViewer-Exports\2026-10-13-UMA-V10');O=V/'RegistrationDraft';D=O/'UMA-V10';R=V/'UMA-V10'
PM=Path('gfx/portraits/portrait_modifiers/uma_customization.txt');RULE=Path('gfx/portraits/customization_rules/uma_portrait_customization.txt')
def read(p):return p.read_text(encoding='utf-8-sig')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def children(s):
    # Recover direct assigned blocks, independently of the builder's token parser.
    s=re.sub(r'#[^\n]*','',s);out=[];i=0
    while i<len(s):
        m=re.search(r'([\w.@-]+)\s*=\s*\{',s[i:])
        if not m:break
        start=i+m.start();op=i+m.end()-1;j=op+1;depth=1
        while depth:
            if s[j]=='{':depth+=1
            elif s[j]=='}':depth-=1
            j+=1
        out.append((m[1],s[op+1:j-1]));i=j
    return out
def scalar(s,k):
    # Caller supplies a leaf block or scalar metadata before option blocks.
    m=re.search(r'(?m)^\s*'+re.escape(k)+r'\s*=\s*([^\s{}]+)',s);return m[1] if m else None
def leaf_dna(s):
    dna=dict(children(s)).get('dna_modifiers','')
    return [(kind,dict(re.findall(r'([\w.]+)\s*=\s*([^\s{}]+)',leaf))) for kind,leaf in children(dna)]
actual=read(D/PM);groups=dict(children(actual));assert len(groups)==10 and not re.search(r'usage\s*=\s*both',actual)
custom={g:b for g,b in groups.items() if scalar(b,'usage')=='customization'}
game={g:b for g,b in groups.items() if scalar(b,'usage')=='game'}
assert len(custom)==len(game)==5
for g,b in custom.items():assert not re.search(r'has_character_flag|is_valid_custom|scope:|is_adult|is_female|has_trait|has_culture',b),g
parts=dict(children(read(R/'common/genes/uma_parts.txt')));ac=dict(children(parts['special_genes']))['accessory_genes'];genes=dict(children(ac));template_index={g:set(dict(children(b))) for g,b in genes.items()}
wardrobe=['uma_clothes','uma_headwear','uma_shoes','uma_socks'];counts={}
for gene in wardrobe:
    key='uma_custom_'+gene.removeprefix('uma_');pairs=[(scalar(b,'gene'),scalar(b,'template')) for k,b in children(custom[key]) if k=='add_accessory_modifiers']
    assert len(pairs)==len(set(pairs)) and {t for g,t in pairs}==template_index[gene] and {g for g,t in pairs}=={gene}
    assert 'dna_modifiers' not in custom[key];counts[gene]=len(pairs)
orig=dict(children(read(R/PM)));old_head=dict(children(orig['uma_custom_headwear']));old_actor=dict(children(orig['uma_custom_character']));new_actor=dict(children(custom['uma_custom_character']))
actor_rows=[]
for old_name,option in old_head.items():
    m=re.fullmatch(r'uma_(\d+)_headwear_(\d+|none)',old_name)
    if not m:continue
    actor,variant=m.groups();new_name=f'uma_actor_{actor}_{variant}';assert new_name in new_actor
    expected=[x for x in leaf_dna(option) if x[1].get('gene') not in wardrobe]+leaf_dna(old_actor['uma_character_'+actor])
    got=leaf_dna(new_actor[new_name]);assert got==expected,new_name
    assert all(x[1].get('gene') not in wardrobe for x in got)
    assert {'uma_head','uma_eye','uma_brow','uma_hair','uma_ear','uma_tail'}<={x[1].get('gene') for x in got}
    actor_rows.append(dict(option=new_name,source_option=old_name,variant_preserved=True,dna_count=len(got)))
assert len(actor_rows)==8
for gene in wardrobe:
    g='uma_game_'+gene.removeprefix('uma_')
    for name,opt in children(game[g]):
        dna=leaf_dna(opt)
        if dna:assert len(dna)==1 and dna[0][1]['gene']==gene and dna[0][1]['mode']=='add'
rule=dict(children(read(D/RULE)))['uma'];rule_children=dict(children(rule));access=dict(re.findall(r'(uma_\w+)\s*=\s*(uma_\w+)',rule_children['accessories']))
assert access['uma_head']=='uma_custom_character'
for g in wardrobe:assert access[g]=='uma_custom_'+g.removeprefix('uma_')
overrides=dict(re.findall(r'(uma_\w+)\s*=\s*(uma_\w+)',rule_children['modifier_overrides']));assert len(overrides)==5
for group,modifier in overrides.items():
    opt=dict(children(game[group]))[modifier];weights=[b for k,b in children(opt) if k=='weight'];assert len(weights)==1 and re.sub(r'\s+','',weights[0])=='base=1'
    assert 'has_character_flag' not in opt
original_rule=dict(children(read(R/RULE)))['uma'];orig_children=dict(children(original_rule))
for field in ('gene_groups','sex_only_genes','hidden_slider_genes'):
    assert re.sub(r'\s+','',rule_children[field])==re.sub(r'\s+','',orig_children[field])
summary=json.loads(read(O/'closure_validation.json'))
for p,h in summary['input_hashes'].items():assert sha(Path(p))==h
for p in (R/'common/genes').glob('*.txt'):assert sha(p)==sha(D/p.relative_to(R))
types=read(R/'common/portrait_types/000_uma_portrait_types.txt');all_types=dict(children(dict(children(types))['uma']))
age_boundaries={}
for t in ('uma_male','uma_female','uma_boy','uma_girl'):
    b=all_types[t];age=scalar(b,'minimum_age') or scalar(b,'maximum_age');assert age=='18';age_boundaries[t]=age
for g,b in custom.items():
    for name,opt in children(b):
        for kind,attrs in leaf_dna(opt):
            if kind=='accessory':assert attrs['mode']=='add'
            if kind=='color':
                assert attrs['gene'] in ('skin_color','hair_color','eye_color')
                for k in ('x','y'):assert abs(float(attrs[k])*100-round(float(attrs[k])*100))<1e-8
for p in D.rglob('*.txt'):assert p.open('rb').read(3)==b'\xef\xbb\xbf'
result=dict(passed=True,formal_mod_hashes_unchanged=True,customization_groups=5,game_groups=5,usage_both_count=0,custom_character_conditions=0,helper_counts=counts,helper_template_coverage_exact=True,actor_variants=actor_rows,actor_dna_exact_preservation=True,wardrobe_headwear_no_head_components=True,designer_override_positive_no_character_weight=True,custom_rule_gene_groups_preserved=True,genes_byte_identical=True,age_boundaries=age_boundaries,stock_color_keys_and_precision_preserved=True,authored_accessory_mode_add=True,all_draft_txt_utf8_bom=True,runtime_save_verified=False)
(O/'independent_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
