import os
"""Create one readable CK3 asset per unique wardrobe family."""
import copy,json,shutil,sys
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import parser_only
pdx=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));root=R/'UMA-V7/gfx/models/portraits/uma';source=json.loads((R/'ClothingParts/clothing-registration.json').read_text());out=copy.deepcopy(source)
def rename(name):return name.replace('_clothing_','_clothes_')
for num,family in enumerate(out['families']):
    actor='0001'if len(family['characters'])>1 else str(family['characters'][0]);dst=root/actor;dst.mkdir(exist_ok=True);asset=[]
    for kind,part in family['parts'].items():
        files=[part['base_mesh'],*part['shape_targets'].values()]
        for source_file in files:
            file=Path(source_file);data=pdx.read_meshfile(str(file))
            for obj in data.find('object'):
                obj.tag=rename(obj.tag)
                for mesh in obj.findall('mesh'):
                    mat=mesh.find('material')
                    for k in ['diff','n','spec']:
                        ref=mat.attrib[k][0];texture=file.parent/ref;assert texture.is_file(),texture;target=dst/rename(ref)
                        if not target.exists():shutil.copy2(texture,target)
                        mat.attrib[k]=[target.name]
            pdx.write_meshfile(str(dst/rename(file.name)),data)
        part['base_mesh']=str(dst/rename(Path(part['base_mesh']).name));part['shape_targets']={k:str(dst/rename(Path(v).name))for k,v in part['shape_targets'].items()};part['mesh_name']=rename(part['mesh_name']);part['entity']=rename(part['entity'])
        for setting in part['meshsettings']:
            setting['shape']=rename(setting['shape'])
            for key in ['diffuse','normal','properties']:
                old=Path(setting[key]);new=dst/rename(old.name)
                if not new.exists():shutil.copy2(old,new)
                setting[key]=str(new)
        # Material aliases can select source character colors while sharing a
        # family asset. Exporter-provided alternate meshes remain source sized.
        variants=part.get('actor_variants')or[]
        if isinstance(variants,dict):variants=[dict(v,actor=k)for k,v in variants.items()]
        for variant in variants:
            for key in ['entity','mesh_name','template']:
                if key in variant:variant[key]=rename(variant[key])
            if variant.get('base_mesh'):
                file=Path(variant['base_mesh']);data=pdx.read_meshfile(str(file))
                for obj in data.find('object'):
                    obj.tag=rename(obj.tag)
                    for mesh in obj.findall('mesh'):
                        mat=mesh.find('material')
                        for k in ['diff','n','spec']:
                            ref=mat.attrib[k][0];shutil.copy2(file.parent/ref,dst/rename(ref));mat.attrib[k]=[rename(ref)]
                new=dst/rename(file.name);pdx.write_meshfile(str(new),data);variant['base_mesh']=str(new)
            for setting in variant.get('meshsettings',[]):
                setting['shape']=rename(setting['shape'])
                for key in ['diffuse','normal','properties']:
                    old=Path(setting[key]);new=dst/rename(old.name);shutil.copy2(old,new);setting[key]=str(new)
        def define(mesh_name,entity,base_mesh,settings):
            prefix=mesh_name.removesuffix('_mesh');text='pdxmesh = {\n\tname = "'+mesh_name+'"\n\tfile = "'+Path(base_mesh).name+'"\n\tstreaming = Never\n\n'
            for attr,target in part['shape_targets'].items():text+='\tblend_shape = { id = "'+prefix+'_'+attr+'"\t\t\ttype = "'+Path(target).name+'" }\n'
            for setting in settings:
                text+='\n\tmeshsettings = {\n\t\tname = "'+setting['shape']+'"\n\t\tindex = '+str(setting['index'])+'\n'
                for key,label in [('diffuse','texture_diffuse'),('normal','texture_normal'),('properties','texture_specular')]:text+='\t\t'+label+' = "'+Path(setting[key]).name+'"\n'
                text+='\t\tshader = "'+setting['shader']+'"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n'
            text+='}\n\nentity = {\n\tname = "'+entity+'"\n\tpdxmesh = "'+mesh_name+'"\n\n'
            for attr in part['shape_targets']:text+='\tattribute = { name = "'+attr+'"\t\t\tblend_shape = "'+prefix+'_'+attr+'" }\n'
            text+='\n\tgame_data = {\n\t\tportrait_entity_user_data = {\n\t\t\tcolor_mask_remap_interval = { interval = { 0.0 1.0 } }\n\t\t}\n\t}\n}\n';return text
        asset.append(define(part['mesh_name'],part['entity'],part['base_mesh'],part['meshsettings']))
        for variant in variants:
            if variant['entity']==part['entity']:continue
            mesh_name=variant.get('mesh_name',part['mesh_name'])
            if mesh_name==part['mesh_name']:
                # No new mesh definition is needed when only entity/template
                # identity differs. Reuse the original family pdxmesh.
                text='entity = {\n\tname = "'+variant['entity']+'"\n\tpdxmesh = "'+mesh_name+'"\n'
                for attr in part['shape_targets']:text+='\tattribute = { name = "'+attr+'"\t\t\tblend_shape = "'+part['mesh_name'].removesuffix('_mesh')+'_'+attr+'" }\n'
                asset.append(text+'}\n')
            else:asset.append(define(mesh_name,variant['entity'],variant.get('base_mesh',part['base_mesh']),variant.get('meshsettings',part['meshsettings'])))
        part['actor_variants']=variants
    asset_path=dst/rename(Path(family['asset_path']).name);asset_path.write_text('\n'.join(asset),encoding='utf8');family['asset_path']=str(asset_path);family['directory']=str(dst)
    if(num+1)%10==0:print('WARDROBE_INTEGRATED',num+1,'/',len(out['families']),flush=True)
(R/'Reports/clothing-registration.json').write_text(json.dumps(out,indent=2),encoding='utf8');print('WARDROBE_ALL_REGISTERED',len(out['families']),flush=True)
