"""Use documented accessory variations and one common neck skin reference."""
import sys,json,copy,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from paths_v10 import ROOT,MOD,REPO,PLUGIN,GAME
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v8')]
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
from configure_assets_v8 import render
from resource_references_v10 import format_resource_references
P=parser_only(PLUGIN)
def dump(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf8')
def save_asset(p,t):p.write_text(format_resource_references(render(t)+'\n'),encoding='utf8')
def dds(path,rgba):Image.fromarray(np.asarray(rgba,np.uint8),'RGBA').save(path,pixel_format='DXT5')
def main():
    cat={f.name:f for f in MOD.rglob('*.dds')};common=MOD/'gfx/models/portraits/uma/0001/shared';base=MOD/'gfx/models/portraits/uma/0001/uma_0001_body_base.mesh';body=P.read_meshfile(str(base)).find('object')[0].find('mesh');uv=np.asarray(body.get('u0')).reshape(-1,2);atlas=np.array(Image.open(cat[body.find('material').get('diff')[0]]).convert('RGBA'));rings=json.loads((ROOT/'Reports/neck-delivery-source.json').read_text());ids=sorted(set(i for r in rings['actors']for i in r['lower_ring_body_vertex_ids']));u=uv[ids];x=np.clip(np.rint(u[:,0]*(atlas.shape[1]-1)).astype(int),0,atlas.shape[1]-1);y=np.clip(np.rint(u[:,1]*(atlas.shape[0]-1)).astype(int),0,atlas.shape[0]-1);reference=np.rint(atlas[y,x].mean(0)).astype(np.uint8);reference[3]=255
    neck=common/'uma_0001_neck_diffuse.dds';dds(neck,reference[None,None,:]);actual=np.array(Image.open(neck).convert('RGBA'))[0,0];assert np.array_equal(actual,reference)
    repaired=[]
    for actor in ['1001','1002']:
        file=MOD/f'gfx/models/portraits/uma/{actor}/uma_{actor}_head_00.mesh';t=P.read_meshfile(str(file));obj=t.find('object')[0]
        for slot,m in enumerate(obj.findall('mesh')):
            if slot<2:continue
            mat=m.find('material');old=copy.deepcopy(mat.attrib);mat.set('shader',['portrait_skin']);mat.set('diff',[neck.name]);mat.set('n',[body.find('material').get('n')[0]]);mat.set('spec',[body.find('material').get('spec')[0]]);repaired.append(dict(actor=actor,slot=slot,old=old,new=mat.attrib,geometry_UV_skin_unchanged=True))
        P.write_meshfile(str(file),t)
        af=file.with_suffix('.asset');a=clausewitz(af.read_text(encoding='utf-8-sig'))
        for pm in values(a,'pdxmesh'):
            if values(pm,'file')!=[file.name]:continue
            for ms in values(pm,'meshsettings'):
                if int(one(ms,'index'))<2:continue
                for k,v in [('shader','portrait_skin'),('texture_diffuse',neck.name),('texture_normal',body.find('material').get('n')[0]),('texture_specular',body.find('material').get('spec')[0])]:ms[:]=[(kk,v if kk==k else vv)for kk,vv in ms]
        save_asset(af,a)
    # One flat native pattern, neutral by default; four documented editor channels.
    refs={}
    for name,pixel in [('mask',[255,0,0,0]),('normal',[128,128,255,128]),('properties',[255,38,0,180])]:
        f=common/f'uma_0001_tint_{name}.dds';dds(f,np.asarray(pixel,np.uint8)[None,None,:]);refs[name]=f.name
    palette=common/'uma_0001_tint_palette.dds';dds(palette,np.full((1,16,4),255,np.uint8));refs['palette']=palette.name
    vt=[('pattern_textures',[('name','uma_plain_tint'),('colormask',refs['mask']),('normal',refs['normal']),('properties',refs['properties'])]),('pattern_layout',[('name','uma_plain_tint'),('scale',[('min','1.0'),('max','1.0')]),('rotation',[('min','0'),('max','0')]),('offset',[('x',[('min','0'),('max','0')]),('y',[('min','0'),('max','0')])])]),('variation',[('name','uma_plain_tint'),('pattern',[('weight','1')]+[(c,[('textures','uma_plain_tint'),('layout','uma_plain_tint')])for c in ['r','g','b','a']]),('color_palette',[('weight','1'),('texture',refs['palette'])])])]
    vfile=MOD/'gfx/portraits/accessory_variations/uma_clothing_colors.txt';vfile.parent.mkdir(exist_ok=True);vfile.write_text(format_resource_references(script_block(vt)+'\n'),encoding='utf-8-sig')
    attachment_entities=[]
    for f in(MOD/'gfx/models/portraits/uma').rglob('*.asset'):
        t=clausewitz(f.read_text(encoding='utf-8-sig'));supported=set()
        for pm in values(t,'pdxmesh'):
            if any(values(ms,'shader')==['portrait_attachment']for ms in values(pm,'meshsettings')):supported.add(one(pm,'name'))
        changed=False
        for e in values(t,'entity'):
            if values(e,'pdxmesh')and one(e,'pdxmesh')in supported:
                gd=one(e,'game_data')if values(e,'game_data')else[]
                if not values(e,'game_data'):e.append(('game_data',gd))
                ud=one(gd,'portrait_entity_user_data')if values(gd,'portrait_entity_user_data')else[]
                if not values(gd,'portrait_entity_user_data'):gd.append(('portrait_entity_user_data',ud))
                ud[:]=[(k,v)for k,v in ud if k!='portrait_accessory'];ud.append(('portrait_accessory',[('pattern_mask',refs['mask']),('variation','uma_plain_tint')]));attachment_entities.append(one(e,'name'));changed=True
        if changed:save_asset(f,t)
    shader=MOD/'gfx/FX/uma_portrait.shader';s=shader.read_text(encoding='utf-8-sig');start=s.index('Effect portrait_attachment\n');stop=s.index('Effect portrait_attachmentShadow',start);effect=s[start:stop];assert'VARIATIONS_ENABLED'not in effect;effect=effect.replace('"PDX_MESH_BLENDSHAPES"','"PDX_MESH_BLENDSHAPES" "VARIATIONS_ENABLED" "MOE_ACCESSORY_TINT"',1);s=s[:start]+effect+s[stop:]
    # Only selected editor color overrides desaturate the underlying painted dye.
    # This code remains within PS_attachment's Code block; no Effect-tail comment.
    needle='\t\t\t\t\tApplyVariationPatterns( Input, Diffuse, Properties, PatternNormal, SecondColorMask, NormalUVChannel );'
    code='''\t\t\t\t\t#ifdef MOE_ACCESSORY_TINT
\t\t\t\t\t\tfloat4 UmaSourceProperties = Properties;
\t\t\t\t\t\tfloat3 UmaSourceNormal = NormalSample;
\t\t\t\t\t\tint UmaColorBase = GetColorOverrideOffset( Input.InstanceIndex );
\t\t\t\t\t\tbool UmaHasColor = false;
\t\t\t\t\t\tif( UmaColorBase >= 0 )
\t\t\t\t\t\t{
\t\t\t\t\t\t\tUmaHasColor = PatternColorOverrides[UmaColorBase * 4].a > 0.0f;
\t\t\t\t\t\t}
\t\t\t\t\t\tif( UmaHasColor )
\t\t\t\t\t\t{
\t\t\t\t\t\t\tDiffuse.rgb = vec3( dot( Diffuse.rgb, float3( 0.2126f, 0.7152f, 0.0722f ) ) );
\t\t\t\t\t\t}
\t\t\t\t\t#endif
'''+needle+'''
\t\t\t\t\t#ifdef MOE_ACCESSORY_TINT
\t\t\t\t\t\tProperties = UmaSourceProperties;
\t\t\t\t\t\tNormalSample = UmaSourceNormal;
\t\t\t\t\t\tPatternNormal = UmaSourceNormal;
\t\t\t\t\t\tNormalUVChannel = 0.0f;
\t\t\t\t\t#endif'''
    assert s.count(needle)==1;s=s.replace(needle,code);s=s.replace('#ifdef VARIATIONS_ENABLED\n\t\t\t\tApplyClothFresnel','#if defined( VARIATIONS_ENABLED ) && !defined( MOE_ACCESSORY_TINT )\n\t\t\t\tApplyClothFresnel');s=s.replace('#ifdef VARIATIONS_ENABLED\n\t\t\t\t\tfloat3 Color = CommonPixelShaderWithTwoNormal','#if defined( VARIATIONS_ENABLED ) && !defined( MOE_ACCESSORY_TINT )\n\t\t\t\t\tfloat3 Color = CommonPixelShaderWithTwoNormal');shader.write_text(s,encoding='utf8')
    report=dict(neck_shader='portrait_skin',neck_reference_DDS=neck.name,reference_RGBA=reference.tolist(),source_body_neck_ring_vertex_ids=ids,body_diffuse_unchanged=True,head_geometry_and_skin_unchanged=True,neck_materials=repaired,attachment_entities=len(attachment_entities),entity_names=attachment_entities,variation='uma_plain_tint',pattern_resources=refs,default_palette_neutral_white=True,override_policy='Native variation palette/user-data; existing painted RGB retained until a selected override, then luminance preserves shaded detail while allowing a new hue.',original_game_files_modified=False,CK3_shader_compilation_executed=False,barbershop_runtime_verified=False)
    dump(ROOT/'Reports/material-palette-repair.json',report);print('V10_MATERIAL_REPAIRED',reference.tolist(),len(attachment_entities),flush=True)
if __name__=='__main__':main()
