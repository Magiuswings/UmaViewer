"""Restore readable shared resources and patch stock asset text in place.

The source mod is immutable. Body animations use explicit virtual relative paths
to the installed vanilla female body. Resource validation follows this path in
the mod/base-game overlay; it never silently substitutes a matching basename.
"""
import argparse,copy,json,posixpath,re,shutil,sys
from collections import defaultdict
from pathlib import Path,PurePosixPath

def replace_assignment(text,key,old,new):
    pattern=re.compile(r'(\b'+re.escape(key)+r'\s*=\s*)(?:"'+re.escape(old)+r'"|'+re.escape(old)+r'(?=\s|\}|$))')
    return pattern.sub(lambda m:m[1]+json.dumps(new),text)

def resource_path(asset_relative,reference):
    value=reference.replace('\\','/')
    if value.startswith('gfx/'):joined=value
    else:joined=posixpath.join(str(PurePosixPath(asset_relative).parent),value)
    result=posixpath.normpath(joined)
    if result.startswith('../')or result.startswith('/')or ':'in result:raise ValueError('Resource escapes virtual game root: '+reference)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['repo','plugin','game','source-mod','legacy-mod','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--body-meshes',type=Path);p.add_argument('--character-id',default='1001');a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b;pdx=b.parser_only(a.plugin)
    src=a.source_mod/'gfx/models/portraits/uma'/a.character_id;old=a.legacy_mod/'gfx/models/portraits/uma';shared=a.output/'gfx/models/portraits/uma/0001';headroot=a.output/'gfx/models/portraits/uma'/a.character_id;animroot=a.output/'gfx/models/portraits/uma/animation'
    for folder in [shared,headroot,animroot]:folder.mkdir(parents=True,exist_ok=True)
    bodymap={};headmap={}
    for file in sorted(src.iterdir()):
        if not file.is_file()or file.suffix.lower()not in ['.mesh','.dds']:continue
        if file.name.startswith(a.character_id+'_body_'):
            target='uma_0001_body_'+file.name.removeprefix(a.character_id+'_body_');bodymap[file.name]=target;folder=shared;replacement=a.body_meshes/target if a.body_meshes and file.suffix=='.mesh'else None
        else:target='uma_'+file.name;headmap[file.name]=target;folder=headroot;replacement=None
        shutil.copy2(replacement if replacement and replacement.exists()else file,folder/target)
    # Update embedded standalone material references without changing geometry.
    for folder,mapping in [(shared,bodymap),(headroot,headmap)]:
        for file in folder.glob('*.mesh'):
            data=pdx.read_meshfile(str(file))
            for obj in data.find('object'):
                for mesh in obj.findall('mesh'):
                    material=mesh.find('material')
                    if material is not None:
                        for key,values in list(material.attrib.items()):material.attrib[key]=[mapping.get(Path(v).name,v)if isinstance(v,str)else v for v in values]
            pdx.write_meshfile(str(file),data)
    stockfile=a.game/'gfx/models/portraits/female_body/female_body.asset';stocktext=stockfile.read_text(encoding='utf-8-sig');current=b.clausewitz((src/(a.character_id+'_body_base.asset')).read_text(encoding='utf-8-sig'));body=b.one(current,'pdxmesh');entity=b.one(current,'entity');settings=b.one(body,'meshsettings')
    fx=a.output/'gfx/FX';fx.mkdir();shader_source=a.source_mod/b.one(settings,'shader_file');assert shader_source.is_file();shutil.copy2(shader_source,fx/'uma_portrait.shader')
    text=stocktext
    for key,oldvalue,newvalue in [('name','female_body_mesh','uma_body_mesh'),('name','female_body_entity','uma_body_entity'),('pdxmesh','female_body_mesh','uma_body_mesh'),('file','female_body.mesh','uma_0001_body_base.mesh'),('name','female_bodyShape',b.one(settings,'name')),('texture_diffuse','female_body_diffuse.dds',bodymap[b.one(settings,'texture_diffuse')]),('texture_normal','female_body_normal.dds',bodymap[b.one(settings,'texture_normal')]),('texture_specular','female_body_properties.dds',bodymap[b.one(settings,'texture_specular')]),('file','female_body_ssao_color.dds',bodymap[b.one(b.one(settings,'texture'),'file')]),('shader_file','gfx/FX/jomini/portrait.shader','gfx/FX/uma_portrait.shader')]:text=replace_assignment(text,key,oldvalue,newvalue)
    # No generic AST serialization: keep stock tabs, compact definitions, comments,
    # line order, quotation marks and state/attribute layout.
    shapemap={b.one(v,'id'):bodymap[b.one(v,'type')]for v in b.values(body,'blend_shape')}
    def shape(match):return match[1]+shapemap[match[2]]+match[4]
    pattern=re.compile(r'(\bblend_shape\s*=\s*\{\s*id\s*=\s*"([^"]+)"\s+type\s*=\s*")([^"]+)("[^\n]*\})')
    text,count=pattern.subn(shape,text);assert count==26
    def animation(match):return match[1]+'../../female_body/'+match[2]+match[3]
    text,animcount=re.subn(r'(^[ \t]*(?:animation|additive_animation)\s*=\s*\{[^\n]*?\btype\s*=\s*")([^"/]+\.anim)(")',animation,text,flags=re.M);assert animcount==188,animcount
    bodyasset=shared/'uma_0001_body_base.asset';bodyasset.write_text(text,encoding='utf8')
    # Keep readable action names in one shared column, independent of characters.
    # The uma_ namespace is the only addition, avoiding replacement of vanilla
    # female/male head animation basenames with the retargeted UMA versions.
    oldheadtext=(old/'uma_head.asset').read_text(encoding='utf-8-sig');oldsettext=(old/'uma_natural_common_head.asset').read_text(encoding='utf-8-sig');animations=sorted(set(re.findall(r'\btype\s*=\s*"([^"]+\.anim)"',oldheadtext+oldsettext)));animationmap={}
    for relative in animations:
        name='uma_'+Path(relative).name;source=old/relative;assert source.is_file();destination=animroot/name
        if destination.exists():assert b.sha(destination)==b.sha(source)
        else:shutil.copy2(source,destination)
        animationmap[relative]=name
    replacements={'uma_head.mesh':'uma_'+a.character_id+'_head_base.mesh','uma_head_neutral.mesh':'uma_'+a.character_id+'_head_none.mesh','uma_face_diffuse.dds':'uma_'+a.character_id+'_face_base_diffuse.dds','uma_hair_diffuse.dds':'uma_'+a.character_id+'_hair_base_diffuse.dds','uma_eyes_diffuse.dds':'uma_'+a.character_id+'_eye_base_diffuse.dds','uma_head_normal.dds':'uma_'+a.character_id+'_head_base_normal.dds','uma_head_properties.dds':'uma_'+a.character_id+'_head_base_properties.dds'}
    def readable_head(text,prefix):
        for relative,name in animationmap.items():text=text.replace('"'+relative+'"','"'+prefix+name+'"')
        for source,target in replacements.items():text=text.replace('"'+source+'"','"'+target+'"')
        return text
    headasset=headroot/('uma_'+a.character_id+'_head_base.asset');headasset.write_text(readable_head(oldheadtext,'../animation/'),encoding='utf8');commonasset=animroot/'uma_common_head.asset';commonasset.write_text(readable_head(oldsettext,''),encoding='utf8')
    for folder in ['common/genes','common/ethnicities','common/portrait_types']:
        shutil.copytree(a.source_mod/folder,a.output/folder)
        for file in (a.output/folder).glob('*.txt'):file.write_text(file.read_text(encoding='utf-8-sig'),encoding='utf-8-sig')
    for name in ['character-body-bindings.json','skin-colors.json']:
        value=json.loads((a.source_mod/name).read_text(encoding='utf8'))
        def rename(value):
            if isinstance(value,dict):return{k:rename(v)for k,v in value.items()}
            if isinstance(value,list):return[rename(v)for v in value]
            if isinstance(value,str):return bodymap.get(value,value)
            return value
        b.write_json(a.output/name,rename(value))
    # Actual virtual-path resolution in mod/base-game overlay. No basename fallback.
    resources=[]
    def refs(node):
        for key,value in node:
            if isinstance(value,list):yield from refs(value)
            elif key in ['type','file','texture_diffuse','texture_normal','texture_specular','shader_file']and Path(str(value)).suffix in ['.mesh','.anim','.dds','.shader']:yield value
    for asset in [bodyasset,headasset,commonasset]:
        for reference in refs(b.clausewitz(asset.read_text(encoding='utf-8-sig'))):
            virtual=resource_path(asset.relative_to(a.output).as_posix(),reference);found=next((root/virtual for root in [a.output,a.game,a.game.parent/'jomini',a.game.parent/'clausewitz']if(root/virtual).is_file()),None);assert found,dict(asset=str(asset),reference=reference,virtual=virtual)
            resources.append(dict(asset=asset.relative_to(a.output).as_posix(),reference=reference,virtual_path=virtual,resolved_file=str(found)))
    parsed=b.clausewitz(bodyasset.read_text(encoding='utf8'));stock=b.clausewitz(stocktext);newbody=b.one(parsed,'pdxmesh');stockbody=b.one(stock,'pdxmesh');newentity=b.one(parsed,'entity');stockentity=b.one(stock,'entity')
    for key in ['animation','additive_animation']:
        normalized=[[(k,v.removeprefix('../../female_body/')if k=='type'else v)for k,v in row]for row in b.values(newbody,key)];assert normalized==b.values(stockbody,key)
    for key in ['state','default_state']:assert b.values(newentity,key)==b.values(stockentity,key)
    assert b.values(newbody,'import')==b.values(stockbody,'import')
    source_lines=[line for line in stocktext.splitlines()if re.match(r'\s*(animation|additive_animation|blend_shape)\s*=',line)];new_lines=[line for line in text.splitlines()if re.match(r'\s*(animation|additive_animation|blend_shape)\s*=',line)]
    striptype=lambda s:re.sub(r'(\btype\s*=\s*")[^"]+("\s*\})',r'\1RESOURCE\2',s);assert [striptype(s)for s in source_lines]==[striptype(s)for s in new_lines]
    names=defaultdict(list)
    for file in(a.output/'gfx').rglob('*'):
        if file.is_file():names[file.name.casefold()].append(file.relative_to(a.output).as_posix())
    assert all(len(v)==1 for v in names.values());assert not list(shared.glob('*.anim'));assert not list(headroot.glob('*.anim'));assert all(f.read_bytes().startswith(b'\xef\xbb\xbf')for f in a.output.rglob('*.txt'))
    report=dict(passed=True,shared_body_folder='0001',character_folder=a.character_id,resource_prefix='uma_',body_animation_paths_resolved=animcount,body_animation_and_bs_layout_verbatim_except_type_paths=True,stock_import_states_additive_defaults_preserved=True,head_animations_shared_readable=len(animations),head_animation_folder=animroot.relative_to(a.output).as_posix(),head_animation_original_basenames_preserved_after_uma_namespace=True,shader_name='uma_portrait.shader',all_virtual_references_resolve=True,resources=resources,gfx_global_basenames_unique=True,txt_utf8_bom=True,ck3_visual_runtime_verified=False)
    b.write_json(a.output/'validation.json',report);b.write_json(a.output/'filename-index.json',dict(body=bodymap,head=headmap,animations=animationmap));(a.output/'descriptor.mod').write_text('name="UMA Shared Body Repair"\nsupported_version="1.20.*"\n',encoding='utf8');(a.output.parent/(a.output.name+'.mod')).write_text('name="UMA Shared Body Repair"\npath="'+a.output.as_posix()+'"\nsupported_version="1.20.*"\n',encoding='utf8');print('READABLE_SHARED_ASSETS_REBUILT',animcount,'stock body refs',len(animations),'shared head animations',flush=True)

if __name__=='__main__':main()
