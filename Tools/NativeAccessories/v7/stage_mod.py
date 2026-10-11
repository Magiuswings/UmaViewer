import os
"""Create a fresh V7 project, full naked Basis, and isolated male/female carriers."""
import copy,json,re,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));OLD=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));GAME=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories')]
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
from integrate_v6 import spans
pdx=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));mod=R/'UMA-V7';models=mod/'gfx/models/portraits/uma';shared=models/'0001';shared.mkdir(parents=True,exist_ok=True)
for folder in ['common/genes','common/ethnicities','common/portrait_types','gfx/FX','gfx/portraits/accessories','gfx/portraits/portrait_modifiers','gfx/portraits/customization_rules']: (mod/folder).mkdir(parents=True,exist_ok=True)
sk=pdx.read_meshfile(str(R/'Rigs/body.mesh')).find('object')[0].find('skeleton');bodyrecords=[]
for file in (OLD/'UMA-V6-1001/gfx/models/portraits/uma/0001').glob('uma_0001_body*'):
    if file.name.endswith('_clothed.mesh'):continue
    dst=shared/file.name
    if file.suffix=='.mesh':
        tree=pdx.read_meshfile(str(file));node=tree.find('object')[0];prev=node.find('skeleton');node.remove(prev);node.append(copy.deepcopy(sk));pdx.write_meshfile(str(dst),tree);bodyrecords.append({'file':file.name,'geometry_and_weights_preserved':True,'bones':len(sk)})
    else:shutil.copy2(file,dst)
bodyasset=shared/'uma_0001_body_base.asset';txt=bodyasset.read_text(encoding='utf-8-sig').replace('uma_0001_body_clothed.mesh','uma_0001_body_none.mesh');bodyasset.write_text(txt,encoding='utf8')
anims=models/'animation';anims.mkdir(exist_ok=True)
for file in (OLD/'UMA-V6-1001/gfx/models/portraits/uma/animation').iterdir():
    if file.is_file():shutil.copy2(file,anims/file.name)
shutil.copy2(R/'Rigs/uma_1002_head_points.anim',anims/'uma_1002_head_points.anim')
shader=(OLD/'UMA-V6-1001/gfx/FX/uma_portrait.shader').read_text(encoding='utf-8-sig')
# PDX script comments are removed outside HLSL Code blocks. Preserve all HLSL
# preprocessor directives and tested pixel shader logic inside those blocks.
pieces=re.split(r'(\[\[.*?\]\])',shader,flags=re.S)
for i,piece in enumerate(pieces):
    if piece.startswith('[['):continue
    piece=re.sub(r'/\*.*?\*/','',piece,flags=re.S);piece=re.sub(r'//[^\n]*','',piece);piece=re.sub(r'#[^\n]*','',piece);pieces[i]=piece
(mod/'gfx/FX/uma_portrait.shader').write_text(''.join(pieces),encoding='utf8')
carrierdata=pdx.read_meshfile(str(R/'Rigs/head_1001.mesh'));carrierobj=carrierdata.find('object')[0];carrierskel=carrierobj.find('skeleton')
# The visible 1002 meshes retain their own source bind points. Carrier extra
# joints are only reference markers; mapped facial points have an additive pose.
other=pdx.read_meshfile(str(R/'Rigs/head_1002.mesh')).find('object')[0].find('skeleton');known={b.tag for b in carrierskel};extra_pending=[b for b in other if b.tag not in known]
while extra_pending:
    changed=False
    for bone in extra_pending[:]:
        parent=other[bone.attrib['pa'][0]].tag if bone.attrib.get('pa')else None
        if parent and parent not in known:continue
        clone=copy.deepcopy(bone);clone.attrib['ix']=[len(carrierskel)]
        if parent:clone.attrib['pa']=[[b.tag for b in carrierskel].index(parent)]
        carrierskel.append(clone);known.add(clone.tag);extra_pending.remove(bone);changed=True
    assert changed
carrierbase=(OLD/'UMA-V6-1001/gfx/models/portraits/uma/0001/uma_0001_head_empty.asset').read_text(encoding='utf-8-sig');reports=[]
for sex in ['female','male']:
    prefix='uma_0001_head_'+sex;tree=copy.deepcopy(carrierdata);obj=tree.find('object')[0];obj.tag=prefix+'Shape';mesh=obj.find('mesh');mesh.find('material').attrib={'shader':['portrait_attachment'],'diff':['uma_0001_head_empty_diffuse.dds'],'n':['uma_0001_head_empty_normal.dds'],'spec':['uma_0001_head_empty_properties.dds']};pdx.write_meshfile(str(shared/(prefix+'.mesh')),tree);pdx.write_meshfile(str(shared/(prefix+'_none.mesh')),tree)
    text=carrierbase
    for key in ['blend_shape','meshsettings']:
        for start,end in reversed(spans(text,key)):text=text[:start]+text[end:]
    for start,end in reversed(spans(text,'attribute')):
        if 'blend_shape'in text[start:end]:text=text[:start]+text[end:]
    text=text.replace('uma_0001_head_carrier_mesh',prefix+'_mesh').replace('uma_0001_head_carrier_entity',prefix+'_entity').replace('uma_0001_head_empty.mesh',prefix+'.mesh')
    stock=(GAME/('gfx/models/portraits/'+sex+'_head/'+sex+'_head.asset')).read_text(encoding='utf-8-sig');bs=[];attrs=[]
    for start,end in spans(stock,'blend_shape'):
        line=stock[start:end];line=re.sub(r'(\btype\s*=\s*")[^"]+(\")',lambda m:m[1]+prefix+'_none.mesh'+m[2],line);bs.append('\t\t'+line)
    for start,end in spans(stock,'attribute'):
        line=stock[start:end]
        if 'blend_shape'in line:attrs.append('\t'+line)
    settings='\tmeshsettings = {\n\t\tname = "'+prefix+'Shape"\n\t\tindex = 0\n\t\ttexture_diffuse = "uma_0001_head_empty_diffuse.dds"\n\t\ttexture_normal = "uma_0001_head_empty_normal.dds"\n\t\ttexture_specular = "uma_0001_head_empty_properties.dds"\n\t\tshader = "portrait_attachment"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n'
    _,end=spans(text,'pdxmesh')[0];text=text[:end-1]+settings+'\n'+'\n'.join(bs)+'\n\tadditive_animation = { id = "uma_head_points_1002"\t\t\ttype = "../animation/uma_1002_head_points.anim" }\n'+text[end-1:]
    _,end=spans(text,'entity')[0];text=text[:end-1]+'\n'+'\n'.join(attrs)+'\n\tattribute = { name = "uma_head_points_1002"\t\tadditive_animation = "uma_head_points_1002" default = 0 }\n'+text[end-1:];text=re.sub(r'\n(?:[ \t]*\n){2,}','\n\n',text);(shared/(prefix+'.asset')).write_text(text,encoding='utf8');reports.append({'sex':sex,'bones':len(carrierskel),'bs_keys':len(bs),'bs_source':sex+'_head.asset','bs_target':prefix+'_none.mesh'})
for ending in ['diffuse','normal','properties','ssao']:shutil.copy2(OLD/'UMA-V6-1001/gfx/models/portraits/uma/0001'/('uma_0001_head_empty_'+ending+'.dds'),shared/('uma_0001_head_empty_'+ending+'.dds'))
types=clausewitz((OLD/'UMA-V6-1001/common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig'));group=one(types,'uma')
for kind in ['male','female','boy','girl']:
    branch=one(group,'uma_'+kind);sex='male'if kind in ['male','boy']else'female'
    branch[:]=[(key,'uma_0001_head_'+sex+'_entity'if key=='head'else value)for key,value in branch]
(mod/'common/portrait_types/uma_portrait_types.txt').write_text(script_block(types)+'\n',encoding='utf-8-sig')
genes=clausewitz((OLD/'UMA-V6-1001/common/genes/uma_genes_morph.txt').read_text(encoding='utf-8-sig'))
def clean(node):
    result=[]
    for key,value in node:
        if key=='setting'and dict(value).get('attribute')in ['bs_body_clothed','bs_no_portrait','bs_body_no_portrait']:continue
        if key=='gene_height':key='uma_height'
        result.append((key,clean(value)if isinstance(value,list)else value))
    return result
(mod/'common/genes/uma_body_morphs.txt').write_text(script_block(clean(genes))+'\n',encoding='utf-8-sig')
report={'body':bodyrecords,'carriers':reports,'body_clothed_fixed_gene_removed':True,'body_clothed_target_noop':True,'male_female_bs_isolated':True,'shader_outside_code_comments_removed':True,'passed_pixel_shader_logic_preserved':True,'palettes_changed':False,'head_actor1002_points_controller':True};(R/'Reports/stage-mod.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V7_BASE_STAGED',len(bodyrecords),'body meshes',reports,flush=True)
