"""Build a single-character, empty-head/shared-pose accessory CK3 test mod.

Only writes a new directory under the explicitly requested E: repair root.
Original archives, staged inputs and installed game assets remain unchanged.
"""
import argparse,copy,hashlib,json,os,posixpath,re,shutil
from collections import defaultdict
from pathlib import Path
import sys
import numpy as np
from PIL import Image

EXPECTED=Path('E:/UmaViewer-Exports/2026-10-10-Head-Accessory-1001').resolve()
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def write(f,v):f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def spans(text,key):
    tokens=list(re.finditer(r'#[^\n]*|"(?:\\.|[^"\\])*"|[{}=]|[A-Za-z_][A-Za-z_0-9]*',text));out=[]
    for i,t in enumerate(tokens[:-2]):
        if t.group()!=key or tokens[i+1].group()!='='or tokens[i+2].group()!='{':continue
        depth=1;j=i+3
        while depth:
            depth+=(tokens[j].group()=='{')-(tokens[j].group()=='}');j+=1
        out.append((t.start(),tokens[j-1].end()))
    return out
def alpha255(file):
    """Change only BC3 alpha blocks; keep compressed RGB and mipmaps exact."""
    before=file.read_bytes();assert before[:4]==b'DDS 'and before[84:88]==b'DXT5'and(len(before)-128)%16==0
    pixels=np.array(Image.open(file).convert('RGBA'));data=bytearray(before)
    for i in range(128,len(data),16):data[i:i+8]=b'\xff\xff'+b'\0'*6
    file.write_bytes(data);after=np.array(Image.open(file).convert('RGBA'));assert np.array_equal(pixels[:,:,:3],after[:,:,:3])and np.all(after[:,:,3]==255)
    return dict(file=file.name,alpha_before=[int(pixels[:,:,3].min()),int(pixels[:,:,3].max())],alpha_after=[255,255],rgb_pixels_exact=True,compressed_rgb_blocks_exact=all(before[i+8:i+16]==data[i+8:i+16]for i in range(128,len(data),16)))

def main():
    p=argparse.ArgumentParser()
    for n in ('root','repo','plugin','game'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--resume',action='store_true');a=p.parse_args();assert a.root.resolve()==EXPECTED;sys.path[:0]=[str(a.repo/'Tools/PDXExporter'),str(a.repo/'Tools/NativeBody')]
    from build_ck3_mod import parser_only,clausewitz,one,values,script_block
    from test_vanilla_body_animation_blender import inverse_bind
    pdx=parser_only(a.plugin);src=a.root/'source';mod=a.root/'Uma-1001-Accessory-Test'
    if a.resume:assert 'uma_0001_head_carrier_entity'in(mod/'gfx/models/portraits/uma/0001/uma_0001_head_empty.asset').read_text(encoding='utf8')
    mod.mkdir(exist_ok=a.resume);models=mod/'gfx/models/portraits/uma';shared=models/'0001';character=models/'1001';anim=models/'animation'
    for folder in [shared,character,anim,mod/'common/genes',mod/'common/ethnicities',mod/'common/portrait_types',mod/'gfx/portraits/accessories',mod/'gfx/portraits/portrait_modifiers',mod/'gfx/portraits/customization_rules',mod/'gfx/FX']:folder.mkdir(parents=True,exist_ok=True)
    # Body geometry, animation declarations and original key interface stay intact.
    for f in(src/'gfx/models/portraits/uma/0001').glob('uma_0001_body*'):shutil.copy2(f,shared/f.name)
    palette=[alpha255(f)for f in shared.glob('uma_0001_body_skin*_diffuse.dds')]
    shutil.copytree(src/'gfx/models/portraits/uma/animation',anim,dirs_exist_ok=True)
    base=pdx.read_meshfile(str(src/'gfx/models/portraits/uma/0001/uma_0001_head_base.mesh'));endpoint=pdx.read_meshfile(str(src/'gfx/models/portraits/uma/1001/uma_1001_head_80.mesh'));skeleton=copy.deepcopy(base.find('object')[0].find('skeleton'));names=[n.tag for n in skeleton]
    assert len(names)==61
    carrier=copy.deepcopy(base);container=carrier.find('object');first=container[0]
    for child in list(container)[1:]:container.remove(child)
    for child in list(first):first.remove(child)
    first.tag='uma_0001_head_carrierShape';first.append(copy.deepcopy(skeleton));pdx.write_meshfile(str(shared/'uma_0001_head_empty.mesh'),carrier)
    # One common face + one true 1001 endpoint, plus independent native-style
    # eye/brow/hair/face-part attachments. No other identity models are exported.
    definitions=[('face','0001','uma_0001_face_base','uma_0001_faceShape','portrait_skin_face','uma_0001_face_base_diffuse.dds'),('face_parts','1001','uma_1001_face_parts_base','uma_1001_face_partsShape','portrait_skin_face','uma_1001_face_parts_diffuse.dds'),('brow','1001','uma_1001_brow_base','uma_1001_browShape','portrait_hair','uma_1001_brow_base_diffuse.dds'),('hair','1001','uma_1001_hair_base','uma_1001_hairShape','portrait_hair','uma_1001_hair_base_diffuse.dds'),('eye','1001','uma_1001_eye_base','uma_1001_eyeShape','portrait_eye','uma_1001_eye_base_diffuse.dds')]
    texture_sources={
        'uma_0001_face_base_diffuse.dds':src/'gfx/models/portraits/uma/0001/uma_1001_face_base_diffuse.dds',
        'uma_1001_face_parts_diffuse.dds':src/'gfx/models/portraits/uma/1001/uma_1001_face_parts_diffuse.dds',
        'uma_1001_brow_base_diffuse.dds':src/'gfx/models/portraits/uma/0001/uma_1001_face_base_diffuse.dds',
        'uma_1001_hair_base_diffuse.dds':src/'gfx/models/portraits/uma/0001/uma_1001_hair_base_diffuse.dds',
        'uma_1001_eye_base_diffuse.dds':src/'gfx/models/portraits/uma/0001/uma_1001_eye_base_diffuse.dds'}
    for name,file in texture_sources.items():shutil.copy2(file,(shared if name.startswith('uma_0001')else character)/name)
    for ending in ['normal','properties','ssao']:shutil.copy2(src/('gfx/models/portraits/uma/0001/uma_0001_head_base_'+ending+'.dds'),shared/('uma_0001_head_base_'+ending+'.dds'))
    def part(data,shape,shader,diffuse,file):
        result=copy.deepcopy(data);objects=result.find('object')
        for obj in list(objects):
            if obj.tag!=shape:objects.remove(obj)
        assert len(objects)==1;obj=objects[0];assert [(n.tag,n.attrib)for n in obj.find('skeleton')]==[(n.tag,n.attrib)for n in skeleton]
        for mesh in obj.findall('mesh'):
            mat=mesh.find('material');mat.attrib['shader']=[shader]
            for key,name in [('diff',diffuse),('n','uma_0001_head_base_normal.dds'),('spec','uma_0001_head_base_properties.dds')]:mat.attrib[key]=[posixpath.relpath((shared if name.startswith('uma_0001')else character).relative_to(mod).as_posix()+'/'+name,file.parent.relative_to(mod).as_posix())]
        pdx.write_meshfile(str(file),result);return obj
    records=[];accessories=[]
    for element,folder,prefix,shape,shader,diffuse in definitions:
        directory=models/folder;file=directory/(prefix+'.mesh');obj=part(base,shape,shader,diffuse,file);mesh=obj.find('mesh');mat=mesh.find('material').attrib;meshname=prefix+'_mesh';entity=prefix+'_entity'
        text='pdxmesh = {\n\tname = "'+meshname+'"\n\tfile = "'+file.name+'"\n\tstreaming = Never\n\n\tmeshsettings = {\n\t\tname = "'+shape+'"\n\t\tindex = 0\n'
        for key,k in [('texture_diffuse','diff'),('texture_normal','n'),('texture_specular','spec')]:text+='\t\t'+key+' = "'+mat[k][0]+'"\n'
        text+='\t\ttexture = { file = "'+posixpath.relpath((shared/'uma_0001_head_base_ssao.dds').relative_to(mod).as_posix(),directory.relative_to(mod).as_posix())+'" index = 3 }\n\t\tshader = "'+shader+'"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n'
        if element=='face':
            target=character/'uma_1001_face_80.mesh';target_obj=part(endpoint,shape,shader,diffuse,target);assert mesh.attrib['tri']==target_obj.find('mesh').attrib['tri']and mesh.attrib['u0']==target_obj.find('mesh').attrib['u0'];assert mesh.find('skin').attrib==target_obj.find('mesh').find('skin').attrib
            text+='\n\tblend_shape = { id = "uma_bs_face_1001"\t\ttype = "../1001/uma_1001_face_80.mesh" }\n'
        text+='}\n\nentity = {\n\tname = "'+entity+'"\n\tpdxmesh = "'+meshname+'"\n'
        if element=='face':text+='\tattribute = { name = "uma_bs_face_1001"\t\tblend_shape = "uma_bs_face_1001" default = 0 }\n'
        text+='\tgame_data = {\n\t\tportrait_entity_user_data = {\n\t\t\tcolor_mask_remap_interval = { interval = { 0.0 1.0 } }\n\t\t}\n\t}\n}\n';(directory/(prefix+'.asset')).write_text(text,encoding='utf8')
        accessory='uma_1001_'+element;accessories.append(accessory+' = {\n\tportrait_group = uma\n\tentity = { entity = "'+entity+'" shared_pose_entity = head }\n}\n');records.append(dict(element=element,file=file.relative_to(mod).as_posix(),asset=(directory/(prefix+'.asset')).relative_to(mod).as_posix(),entity=entity,accessory=accessory,vertices=len(mesh.attrib['p'])//3,triangles=len(mesh.attrib['tri'])//3))
    # Carrier owns animations; accessories only consume its exact shared pose.
    text=(src/'gfx/models/portraits/uma/0001/uma_0001_head_base.asset').read_text(encoding='utf-8-sig')
    for key in ['meshsettings','blend_shape']:
        for start,end in reversed(spans(text,key)):text=text[:start]+text[end:]
    for start,end in reversed(spans(text,'attribute')):
        if re.search(r'\bblend_shape\s*=',text[start:end]):text=text[:start]+text[end:]
    text=text.replace('"uma_head_mesh"','"uma_0001_head_carrier_mesh"').replace('"uma_0001_head_base.mesh"','"uma_0001_head_empty.mesh"').replace('"uma_head_entity"','"uma_0001_head_carrier_entity"')
    animation_replacements=[]
    def animref(m):
        ref=m[2];name=Path(ref).name;candidate=name if name.startswith('uma_')else'uma_'+name
        assert (anim/candidate).is_file(),candidate;animation_replacements.append(dict(before=ref,after='../animation/'+candidate));return m[1]+'../animation/'+candidate+m[3]
    text=re.sub(r'(\btype\s*=\s*")([^"]+\.anim)(")',animref,text);(shared/'uma_0001_head_empty.asset').write_text(text,encoding='utf8')
    library=(src/'gfx/models/portraits/uma/0001/uma_natural_common_head.asset').read_text(encoding='utf-8-sig').replace('"uma_head_mesh"','"uma_0001_head_carrier_mesh"')
    def libref(m):
        name=Path(m[2]).name;candidate=name if name.startswith('uma_')else'uma_'+name;assert (anim/candidate).is_file();return m[1]+candidate+m[3]
    library=re.sub(r'(\btype\s*=\s*")([^"]+\.anim)(")',libref,library);(anim/'uma_common_head.asset').write_text(library,encoding='utf8')
    # Keep the shader filename/effect names; turn off face texture interception
    # only in this mod's face effect, not in any installed vanilla shader.
    shader=(src/'gfx/FX/uma_portrait.shader').read_text(encoding='utf8');pattern=r'(Effect\s+portrait_skin_face\s*\{.*?\n\})';matches=list(re.finditer(pattern,shader,re.S));assert len(matches)==1 and'"ENABLE_TEXTURE_OVERRIDE"'in matches[0][0];effect=matches[0][0].replace('"ENABLE_TEXTURE_OVERRIDE"','');shader=shader[:matches[0].start()]+effect+shader[matches[0].end():];(mod/'gfx/FX/uma_portrait.shader').write_text(shader,encoding='utf8')
    types=clausewitz((src/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig'));group=one(types,'uma')
    for kind in ['male','female','boy','girl']:
        branch=one(group,'uma_'+kind)
        for i,(key,value)in enumerate(branch):
            if key=='head':branch[i]=('head','uma_0001_head_carrier_entity')
    (mod/'common/portrait_types/uma_portrait_types.txt').write_text(script_block(types)+'\n',encoding='utf-8-sig')
    # Delete ineffective zero-to-zero morph settings rather than setting every
    # competing body shape to one simultaneously.
    bodygenes=clausewitz((src/'common/genes/uma_genes_morph.txt').read_text(encoding='utf-8-sig'));removed=[]
    def clean(node):
        result=[]
        for key,value in node:
            if key=='setting':
                interval=dict(value).get('value')
                if isinstance(interval,list)and str(dict(interval).get('min'))in ['0','0.0']and str(dict(interval).get('max'))in ['0','0.0']:removed.append(one(value,'attribute'));continue
            result.append((key,clean(value)if isinstance(value,list)else value))
        return result
    (mod/'common/genes/uma_genes_morph.txt').write_text(script_block(clean(bodygenes))+'\n',encoding='utf-8-sig')
    branches=[('uma_'+kind,[('setting',[('attribute','uma_bs_face_1001'),('value',[('min','0.0'),('max','1.0')])])])for kind in ['male','female','boy','girl']]
    morph=[('morph_genes',[('portrait_group','uma'),('gene_uma_face_identity',[('group','face'),('can_have_portrait_extremity_shift','no'),('uma_face_1001',[('index','0'),*branches])])])];(mod/'common/genes/uma_face_genes_morph.txt').write_text(script_block(morph)+'\n',encoding='utf-8-sig')
    accessorygenes=[];forced=[]
    for r in records:
        gene='eye_accessory'if r['element']=='eye'else'uma_'+r['element']+'_accessory';template='normal_eyes'if r['element']=='eye'else'uma_1001_'+r['element'];index='1'if r['element']=='eye'else'0';choices=[('uma_'+kind,[('1',r['accessory'])])for kind in ['male','female','boy','girl']];accessorygenes.append((gene,[('inheritable','no'),(template,[('index',index),*choices])]))
        forced.append(('accessory',[('mode','modify'),('gene',gene),('template',template),('value','1')]))
        r.update(gene=gene,template=template)
    (mod/'common/genes/uma_accessories.txt').write_text(script_block([('accessory_genes',[('portrait_group','uma'),*accessorygenes])])+'\n',encoding='utf-8-sig');(mod/'gfx/portraits/accessories/uma_1001_accessories.txt').write_text('\n'.join(accessories),encoding='utf-8-sig')
    # Morph applies explicitly in every portrait context, including events.
    forced.append(('morph',[('mode','modify'),('gene','gene_uma_face_identity'),('template','uma_face_1001'),('value','1')]))
    modifiers=[('uma_single_character',[('portrait_group','uma'),('uma_1001',[('dna_modifiers',forced),('weight',[('base','256')])])])];(mod/'gfx/portraits/portrait_modifiers/uma_1001_modifiers.txt').write_text(script_block(modifiers)+'\n',encoding='utf-8-sig')
    ethns=clausewitz((src/'common/ethnicities/uma_ethnicity.txt').read_text(encoding='utf-8-sig'))
    for _,ethn in ethns:
        ethn[:]=[(k,v)for k,v in ethn if k not in ['uma_1_group','gene_uma_face_identity']]
        for r in records:ethn.append((r['gene'],[('100',[('name',r['template']),('range',[(None,'1.0'),(None,'1.0')])])]))
        ethn.append(('gene_uma_face_identity',[('100',[('name','uma_face_1001'),('range',[(None,'1.0'),(None,'1.0')])])]))
    (mod/'common/ethnicities/uma_ethnicity.txt').write_text(script_block(ethns)+'\n',encoding='utf-8-sig');custom=src/'gfx/portraits/customization_rules/uma_portrait_customization.txt';shutil.copy2(custom,mod/'gfx/portraits/customization_rules'/custom.name)
    descriptor='name="UMA 1001 Accessory Test"\nsupported_version="1.20.*"\n';(mod/'descriptor.mod').write_text(descriptor,encoding='utf8');(a.root/'Uma-1001-Accessory-Test.mod').write_text(descriptor+'path="'+mod.as_posix()+'"\n',encoding='utf8')
    stock=pdx.read_meshfile(str(a.game/'gfx/models/portraits/female_head/female_head.mesh')).find('object')[0].find('skeleton');sw=np.linalg.inv(inverse_bind(stock));uw=np.linalg.inv(inverse_bind(skeleton));lookup={n.tag:i for i,n in enumerate(stock)};pivots=[]
    for i,n in enumerate(skeleton):
        if n.tag in ['bn_h_head','bn_h_eye_l_main','bn_h_eye_r_main','bn_h_eye_l_rotate','bn_h_eye_r_rotate']:pivots.append(dict(bone=n.tag,uma=uw[i,:3,3].tolist(),vanilla=sw[lookup[n.tag],:3,3].tolist(),distance_cm=float(np.linalg.norm(uw[i,:3,3]-sw[lookup[n.tag],:3,3]))))
    # Validate registration and binary sharing, without sweeping other identities.
    assert not first.findall('mesh');bodyhashes=[]
    for f in shared.glob('uma_0001_body*.mesh'):assert sha(f)==sha(src/'gfx/models/portraits/uma/0001'/f.name);bodyhashes.append(dict(file=f.name,sha256=sha(f)))
    assert (shared/'uma_0001_body_base.asset').read_bytes()==(src/'gfx/models/portraits/uma/0001/uma_0001_body_base.asset').read_bytes()
    for r in records:
        d=pdx.read_meshfile(str(mod/r['file']));assert [(n.tag,n.attrib)for n in d.find('object')[0].find('skeleton')]==[(n.tag,n.attrib)for n in skeleton]
        ent=one(clausewitz((mod/r['asset']).read_text()),'entity');ud=one(one(ent,'game_data'),'portrait_entity_user_data');assert not values(ud,'portrait_decal')
    inventory=defaultdict(list)
    for f in(mod/'gfx').rglob('*'):
        if f.is_file():inventory[f.name.casefold()].append(str(f))
    assert all(len(v)==1 for v in inventory.values());assert all(f.read_bytes().startswith(b'\xef\xbb\xbf')for f in mod.rglob('*.txt'));assert not any('/female_head/'in f.relative_to(mod).as_posix()for f in(mod/'gfx').rglob('*'))
    agegroup=one(clausewitz((mod/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig')),'uma')
    for kind,key in [('male','minimum_age'),('female','minimum_age'),('boy','maximum_age'),('girl','maximum_age')]:assert one(one(agegroup,'uma_'+kind),key)=='18'
    report=dict(passed=True,scope='1001 only',carrier_geometry_objects=0,carrier_bones=61,accessories=records,base_face_vertices=875,selected_face_id='1001',palette=palette,stock_vs_uma_pivots=pivots,all_accessories_exact_carrier_skeleton=True,texture_override_removed_from_local_face_effect=True,child_head_decal_marks_removed=True,body_geometry_and_asset_exact=True,body_mesh_hashes=bodyhashes,ineffective_zero_morph_settings_removed=len(removed),new_morph_interval=[0,1],all_txt_bom=True,global_gfx_basenames_unique=True,ages_unchanged=True,head_animation_path_changes=animation_replacements,maximum_absolute_path=max(len(str(f))for f in mod.rglob('*')if f.is_file()),original_files_modified=False,game_runtime_verified=False)
    assert report['maximum_absolute_path']<256;write(a.root/'build-verification.json',report);write(mod/'single-character-index.json',report);print('SINGLE_CHARACTER_ACCESSORY_MOD_BUILT',len(records),'attachments',len(palette),'palette masks',len(removed),'zero settings removed',flush=True)

if __name__=='__main__':main()
