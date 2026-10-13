"""Closed actor/head choices, no costume-specific facial duplicates, public attachment keys."""
import sys,json,copy
from paths_v9 import ROOT,MOD,REPO
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import clausewitz,one,values,script_block
def write(rel,t):p=MOD/rel;p.write_text(script_block(t)+'\n',encoding='utf-8-sig')
def choice(gene,template):return('accessory',[('mode','add'),('gene',gene),('template',template),('value','1.0')])
def weight(actor,default=False):
    w=[('base','100'if default else'0')]
    if actor=='1002':w.append(('modifier',[('add','1000'),('has_character_flag','uma_actor_1002')]))
    else:w.append(('modifier',[('factor','0'),('has_character_flag','uma_actor_1002')]))
    return('weight',w)
def main():
    conf=json.loads((ROOT/'Reports/configuration.json').read_text());heads=json.loads((ROOT/'Reports/head-registration.json').read_text());wardrobe=[r for r in conf['registrations']if r.get('family')];rows=heads+wardrobe;genes=[];accessories=[]
    for gene in sorted({r['gene']for r in rows}):
        group=[];elements=[r for r in rows if r['gene']==gene];part=elements[0]['element'];none='uma_'+part+'_none';group.append((none,[('index','0')]+[(t,[('1','empty')])for t in ['uma_male','uma_female','uma_boy','uma_girl']]))
        for i,r in enumerate(elements,1):
            group.append((r['template'],[('index',str(i))]+[(t,[('1',r['accessory_id'])])for t in ['uma_male','uma_female','uma_boy','uma_girl']]))
            e=[('entity',r['entity'])]
            if r.get('node'):e.append(('node','body_root'if part=='tail'else'bn_h_head'))
            else:e.append(('shared_pose_entity',r.get('shared_pose','head')))
            accessories.append((r['accessory_id'],[('portrait_group','uma'),('entity',e)]))
        genes.append((gene,group))
    write('common/genes/uma_parts.txt',[('special_genes',[('accessory_genes',[('portrait_group','uma')]+genes)])]);write('gfx/portraits/accessories/uma_parts.txt',accessories)
    mods=clausewitz((MOD/'gfx/portraits/portrait_modifiers/uma_customization.txt').read_text(encoding='utf-8-sig'));headgroup=one(mods,'uma_custom_headwear');header=[(k,v)for k,v in headgroup if k in ['portrait_group','usage','interface_position','priority','selection_behavior','fallback']];newhead=header
    for actor in ['1001','1002']:
        variants=[r['variant']for r in heads if r['actor']==actor and r['element']=='hair']
        for variant in variants:
            # 80 and none had identical DNA. Only the explicit no-headgear option remains.
            key=f'uma_{actor}_headwear_'+('none'if variant=='80'else variant);selections=[]
            for part,var in [('head','00'),('eye','00'),('brow','00'),('hair',variant),('ear',variant),('headwear',variant),('tail','base')]:
                r=next((r for r in heads if r['actor']==actor and r['element']==part and r['variant']==var),None);selections.append(choice('uma_'+part,r['template']if r else'uma_'+part+'_none'))
            selections.extend([choice('uma_cheek','uma_cheek_none'),choice('uma_tear','uma_tear_none')]);w=weight(actor,actor=='1001')if variant=='00'else('weight',[('base','0')]);newhead.append((key,[('dna_modifiers',selections),w]))
    for r in wardrobe:
        if r['element']=='headwear':newhead.append((r['template'],[('dna_modifiers',[choice(r['gene'],r['template'])]),('weight',[('base','0')])]))
    mods[:]=[(k,newhead if k=='uma_custom_headwear'else v)for k,v in mods]
    removed=[]
    for part in ['clothes','shoes','socks']:
        group=one(mods,'uma_custom_'+part);defaults={}
        for k,v in group:
            if k and k.startswith('uma_default_'):
                for d in values(v,'dna_modifiers'):
                    for a in values(d,'accessory'):defaults[one(a,'template')]=k
        clean=[]
        for k,v in group:
            if isinstance(v,list)and values(v,'dna_modifiers')and not str(k).startswith('uma_default_'):
                aa=values(one(v,'dna_modifiers'),'accessory')
                if len(aa)==1 and one(aa[0],'template')in defaults:removed.append(k);continue
            clean.append((k,v))
        group[:]=clean
    write('gfx/portraits/portrait_modifiers/uma_customization.txt',mods)
    rules=[('default_age','25'),('min_age_for_sexuality','10'),('accessories',[(f'uma_{p}',f'uma_custom_{p}')for p in ['clothes','headwear','shoes','socks']]),('sex_only_genes',[('female',[(None,'gene_bs_bust')])]),('hidden_slider_genes',[(None,'gene_bs_body_shape')]),('gene_groups',[('anatomy',[('body','full_body'),('eyes','face')]),('hair',[('hair','face')])]),('color_genes',[('hair','uma_custom_headwear')])]+[(f'accessory_color_override_block_{i}',f'uma_custom_{p}')for i,p in enumerate(['clothes','headwear','shoes','socks'])]
    write('gfx/portraits/customization_rules/uma_portrait_customization.txt',[('uma',rules)])
    conf.update(version=9,registrations=rows,registered_records=len(rows),head_component_records=len(heads),custom_gene_names=[k for k,v in genes],supported_color_keys=['hair_color','skin_color','eye_color']);(ROOT/'Reports/configuration.json').write_text(json.dumps(conf,indent=2),encoding='utf8');(ROOT/'Reports/registration-repair.json').write_text(json.dumps(dict(head_records=len(heads),all_records=len(rows),removed_identical_UI_choices=removed,headwear80_and_none_coalesced=True,invalid_custom_1002_nodes_removed=True,empty_face_category_removed=True,color_group_keys=['body','hair','eyes'],game_ruler_designer_execution=False),indent=2),encoding='utf8');print('V9_REGISTERED',len(rows),'choices removed',len(removed),flush=True)
if __name__=='__main__':main()
