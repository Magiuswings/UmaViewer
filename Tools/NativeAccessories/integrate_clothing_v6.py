"""Append the verified broad clothing/footwear partition and native clothed BS key."""
import argparse,copy,json,re,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image

def main():
    p=argparse.ArgumentParser()
    for n in ['root','repo','plugin']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();r=a.root;mod=r/'UMA-V6-1001';models=mod/'gfx/models/portraits/uma';char=models/'1001';shared=models/'0001';sys.path.insert(0,str(a.repo/'Tools/PDXExporter'))
    from build_ck3_mod import parser_only,clausewitz,one,values,script_block
    pdx=parser_only(a.plugin);plan=json.loads((r/'integration.json').read_text());split=json.loads((r/'clothing-parts/split-delivery.json').read_text());delivery=json.loads((r/'clothing-parts/clothing-delivery.json').read_text())
    def txt(f,value):f.write_text(script_block(value)+'\n',encoding='utf-8-sig')
    palette=json.loads((r/'head-materials.json').read_text());next(row for row in palette if row['element']=='eye')['palette_mask']='diffuse alpha';(r/'head-materials.json').write_text(json.dumps(palette,ensure_ascii=False,indent=2),encoding='utf8')
    for f in Path(split['output']).glob('*.dds'):shutil.copy2(f,char/f.name)
    prefix_tex='uma_1001_clothing_00';Image.fromarray(np.tile([255,255,255,96],(32,32,1)).astype(np.uint8),'RGBA').save(char/(prefix_tex+'_ssao.dds'),pixel_format='DXT5')
    genesfile=mod/'common/genes/uma_accessories.txt';genes=clausewitz(genesfile.read_text(encoding='utf-8-sig'));bank=one(one(genes,'special_genes'),'accessory_genes');accfile=mod/'gfx/portraits/accessories/uma_1001_accessories.txt';acc=clausewitz(accfile.read_text(encoding='utf-8-sig'));modsfile=mod/'gfx/portraits/portrait_modifiers/uma_1001_modifiers.txt';mods=clausewitz(modsfile.read_text(encoding='utf-8-sig'))
    plan['parts']=[row for row in plan['parts']if row['element']not in ['clothing','footwear']];bank[:]=[(k,v)for k,v in bank if k not in ['uma_clothing_accessory','uma_footwear_accessory']];acc[:]=[(k,v)for k,v in acc if k not in ['uma_1001_clothing','uma_1001_footwear']]
    for _,modifier in mods:
        dna=one(one(modifier,'uma_1001'),'dna_modifiers');dna[:]=[(k,v)for k,v in dna if dict(v).get('gene')not in ['uma_clothing_accessory','uma_footwear_accessory']]
    for name,sec in split['sections'].items():
        prefix='uma_1001_'+name+'_00';entity=prefix+'_entity';shader='portrait_attachment';base=next(v for v in sec['variants']if v['variant']=='base');definitions=[];attrs=[]
        for v in sec['variants']:
            shutil.copy2(v['file'],char/Path(v['file']).name)
            if v['key']:
                bid=prefix+'_'+v['variant'];definitions.append('\tblend_shape = { id = "'+bid+'"\t\t\ttype = "'+Path(v['file']).name+'" }');attrs.append('\tattribute = { name = "'+v['key']+'"\t\t\tblend_shape = "'+bid+'" }')
        s='pdxmesh = {\n\tname = "'+prefix+'_mesh"\n\tfile = "'+Path(base['file']).name+'"\n\tstreaming = Never\n\n\tmeshsettings = {\n\t\tname = "'+sec['mesh_shape']+'"\n\t\tindex = 0\n'
        for k,end in [('texture_diffuse','diffuse'),('texture_normal','normal'),('texture_specular','properties')]:s+='\t\t'+k+' = "'+prefix_tex+'_'+end+'.dds"\n'
        s+='\t\ttexture = { file = "'+prefix_tex+'_ssao.dds" index = 3 }\n\t\tshader = "portrait_attachment"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n\n'+'\n'.join(definitions)+'\n}\n\nentity = {\n\tname = "'+entity+'"\n\tpdxmesh = "'+prefix+'_mesh"\n\tgame_data = {\n\t\tportrait_entity_user_data = {\n\t\t\tcolor_mask_remap_interval = { interval = { 0.0 1.0 } }\n\t\t}\n\t}\n\n'+'\n'.join(attrs)+'\n}\n';(char/(prefix+'.asset')).write_text(s,encoding='utf8')
        accessory='uma_1001_'+name;gene='uma_'+name+'_accessory';choices=[('uma_'+kind,[('1',accessory)])for kind in ['male','female','boy','girl']];bank.append((gene,[(accessory,[('index','0'),*choices])]))
        acc.append((accessory,[('portrait_group','uma'),('entity',[('entity',entity),('shared_pose_entity','torso')])]))
        for _,modifier in mods:
            one(one(modifier,'uma_1001'),'dna_modifiers').append(('accessory',[('mode','add'),('gene',gene),('template',accessory),('value','1')]))
        plan['parts'].append(dict(element=name,file=(char/Path(base['file']).name).relative_to(mod).as_posix(),vertices=sec['vertices'],triangles=sec['triangles'],shape=sec['mesh_shape'],shader=shader,prefix=prefix,entity=entity,accessory=accessory,gene=gene,template=accessory,shared_pose_entity='torso',bones=134,body_shape_keys=[v['key']for v in sec['variants']if v['key']]))
    txt(genesfile,genes);txt(accfile,acc);txt(modsfile,mods)
    # Use the original body BS key and existing gene interface. Only the
    # clothed target gains a real delta; existing body Basis/shape keys remain.
    shrink=shared/'uma_0001_body_clothed.mesh';shutil.copy2(r/'clothing-parts/uma_0001_body_clothed.mesh',shrink);bodyasset=shared/'uma_0001_body_base.asset';bodytext=bodyasset.read_text(encoding='utf-8-sig');pattern=r'(blend_shape\s*=\s*\{\s*id\s*=\s*"female_bs_body_clothed"\s+type\s*=\s*")[^"]+(\")';bodytext,count=re.subn(pattern,r'\1uma_0001_body_clothed.mesh\2',bodytext);assert count==1;bodyasset.write_text(bodytext,encoding='utf8')
    bodygenesfile=mod/'common/genes/uma_genes_morph.txt';bodygenes=clausewitz(bodygenesfile.read_text(encoding='utf-8-sig'));gene=one(one(bodygenes,'morph_genes'),'gene_bs_body_type');changed=[]
    for template,node in gene:
        if not isinstance(node,list)or template=='no_portrait':continue
        female=dict(node).get('uma_female')
        if not isinstance(female,list):continue
        if not any(k=='setting'and dict(v).get('attribute')=='bs_body_clothed'for k,v in female):female.append(('setting',[('attribute','bs_body_clothed'),('value',[('min','1.0'),('max','1.0')])]))
        changed.append(template)
    txt(bodygenesfile,bodygenes)
    # Stock references quote node names; mirror that convention.
    for name,node in acc:
        entity=dict(node).get('entity')
        if isinstance(entity,list):
            for i,(k,v)in enumerate(entity):
                if k=='node':entity[i]=(k,str(v).strip('"'))
    rendered=script_block(acc)+'\n';rendered=re.sub(r'(\bnode\s*=\s*)([A-Za-z_0-9]+)',r'\1"\2"',rendered);accfile.write_text(rendered,encoding='utf-8-sig')
    plan['clothing']=dict(source=delivery['source']['source'],split_triangles_complete=True,source_triangles=8736,body_clothed_key='bs_body_clothed',body_clothed_enabled_templates=changed,protected_body_vertices=1645,body_clothed_topology_unchanged=True,remaining_court_body_intersections=True,fullkit_report=str(r/'clothing-parts/clothing-delivery.json'),split_report=str(r/'clothing-parts/split-delivery.json'))
    (r/'integration.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8');print('V6_CLOTHING_AND_FOOTWEAR_REGISTERED',len(plan['parts']),changed,flush=True)
if __name__=='__main__':main()
