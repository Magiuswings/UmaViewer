"""Stage the supplied v5 and explicit 1001 material policy, without modifying inputs."""
import argparse, copy, json, re, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image

def write_json(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);a=p.parse_args()
    r=a.root;src=r/'v5';mod=r/'UMA-V6-1001';assert src.is_dir();mod.mkdir(exist_ok=True)
    # Keep the user-provided script layout and body definitions. Old face assets
    # are deliberately excluded rather than left as duplicate gfx definitions.
    for f in src.rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(src)
        if rel.parts[:4]==('gfx','models','portraits','uma'):
            if rel.parts[4]=='1001':continue
            if rel.parts[4]=='0001' and not f.name.startswith('uma_0001_body'):continue
        dst=mod/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
    shared=mod/'gfx/models/portraits/uma/0001';char=mod/'gfx/models/portraits/uma/1001';char.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src/'gfx/models/portraits/uma/0001/uma_0001_head_empty.asset',shared/'uma_0001_head_empty.asset')
    raw=json.loads((r/'parsed/head.json').read_text());head=next(b for b in raw['bones']if b['name']=='Head');origin=np.array(head['matrix']).reshape(4,4)[:3,3]
    policy={'source_head_world':origin.tolist(),'engine_transform':np.diag([-97.6403989,97.6403989,-97.6403989]).tolist(),'engine_head_anchor':[0,26.87430954,4.59109068],'head_geometry_policy':'original renderer world vertices, subtract original Head world, then scale/reflection and add carrier Head anchor','source':str(r/'parsed/head.json')}
    write_json(r/'head-policy.json',policy)
    materials=[]
    def dds(file,array):Image.fromarray(np.asarray(array,dtype=np.uint8),'RGBA').save(file,pixel_format='DXT5')
    def flat(prefix,normal=(0,128,0,128),ssao=96):
        for k,color in [('normal',normal),('properties',(0,38,0,180)),('ssao',(255,255,255,ssao))]:dds(char/(prefix+'_'+k+'.dds'),np.tile(color,(32,32,1)))
    resources=r/'parsed/resources'
    mats={m['name']:m for m in raw['materials']}
    def main_tex(mat):return next(p for p in mats[mat]['properties']if p['name']=='_MainTex')
    records=[('face','mtl_chr1001_80_face','portrait_skin_face'),('face_parts','mtl_chr1001_80_face','portrait_skin_face'),('eye','mtl_chr1001_80_eye','portrait_eye'),('brow','mtl_chr1001_80_face','portrait_hair_brow_overlay'),('hair','mtl_chr1001_80_hair','portrait_hair'),('ear','mtl_chr1001_80_hair','portrait_hair')]
    # Material names are parsed from the actual source; eye can carry eye0 suffix.
    for element,mat,shader in records:
        if mat not in mats:
            mat=next(n for n in mats if ('eye' if element=='eye'else element)in n)
        tex=main_tex(mat);pixels=np.array(Image.open(resources/tex['texture']).convert('RGBA'));prefix='uma_1001_'+element+'_base'
        source_pixels=pixels.copy();mask=None
        if element=='eye':
            scale=tex.get('scale',[1,1]);offset=tex.get('offset',[0,0]);w,h=Image.fromarray(pixels).size
            pixels=pixels[int((1-offset[1]-scale[1])*h):int((1-offset[1])*h),int(offset[0]*w):int((offset[0]+scale[0])*w)].copy()
        if element in ['face','face_parts','brow']:pixels[:,:,3]=255
        if element in ['hair','ear']:
            ctrl=next(x for x in mats[mat]['properties']if x['name']=='_OptionMaskMap');control=np.array(Image.open(resources/ctrl['texture']).convert('RGBA'))
            rgb=pixels[:,:,:3].astype(float)/255.;white=(rgb.min(2)>.7)&((rgb.max(2)-rgb.min(2))<.2)
            mask=(control[:,:,2]>127)&~white
            lum=rgb@np.array([.2126,.7152,.0722]);valid=lum[mask& (pixels[:,:,3]>10)];ref=float(np.percentile(valid,85))if len(valid)else .5
            neutral=np.clip(lum/max(ref,1e-8)*.82,0,1);pixels[:,:,:3]=np.where(mask[:,:,None],np.rint(neutral[:,:,None]*255),pixels[:,:,:3])
        if element=='brow':
            lum=pixels[:,:,:3].astype(float)@np.array([.2126,.7152,.0722]);pixels[:,:,:3]=np.rint(lum[:,:,None]);mask=np.ones(pixels.shape[:2],bool)
        dds(char/(prefix+'_diffuse.dds'),pixels)
        flat(prefix,normal=(0,128,255 if element=='eye'else 0,128))
        if mask is not None:
            normals=np.tile([0,128,0,128],(*mask.shape,1)).astype(np.uint8);normals[:,:,2]=mask.astype(np.uint8)*255;dds(char/(prefix+'_normal.dds'),normals)
        materials.append(dict(element=element,shader=shader,prefix=prefix,source_material=mat,source_texture=tex['texture'],diffuse_size=list(pixels.shape[:2]),palette_mask='normal B'if element in ['hair','ear','brow']else'diffuse alpha',masked_pixels=int(mask.sum())if mask is not None else pixels.shape[0]*pixels.shape[1],white_hair_marking_preserved=element in ['hair','ear']))
    # Head and torso use the same skin response and SSAO policy. Both formerly
    # used neutral normal maps: their difference was shader/SSAO, not detail.
    for file in shared.glob('uma_0001_body*_ssao.dds'):dds(file,np.tile([255,255,255,96],(32,32,1)))
    for file in shared.glob('uma_0001_body*_properties.dds'):dds(file,np.tile([0,38,0,180],(32,32,1)))
    shader=(src/'gfx/FX/uma_portrait.shader').read_text(encoding='utf-8-sig')
    skin_defines='"SKIN_SCATTERING" "TRANSLUCENCY" "PDX_MESH_BLENDSHAPES" "MOE_SKIN_RESPONSE" "DOUBLE_SIDED_ENABLED" "MOE_FACE_FILL"'
    for effect in ['portrait_skin','portrait_skin_face']:
        pattern=r'(Effect\s+'+effect+r'\s*\{)(.*?)(\n\})';match=re.search(pattern,shader,re.S);assert match
        body=re.sub(r'Defines\s*=\s*\{[^}]*\}','Defines = { '+skin_defines+' }',match[2])
        if 'RasterizerState'not in body:body+='\n\tRasterizerState = "rasterizer_no_culling"'
        shader=shader[:match.start()]+match[1]+body+match[3]+shader[match.end():]
    shader+='''\n// Eyebrows are a late alpha pass, preserving source mesh coordinates.\nDepthStencilState uma_brow_overlay\n{\n\tDepthEnable = no\n\tDepthWriteEnable = no\n}\n\nEffect portrait_hair_brow_overlay\n{\n\tVertexShader = "VS_standard"\n\tPixelShader = "PS_hair"\n\tBlendState = "hair_alpha_blend"\n\tDepthStencilState = "uma_brow_overlay"\n\tRasterizerState = "rasterizer_back_culling"\n\tDefines = { "PDX_MESH_BLENDSHAPES" "MOE_FACE_FILL" }\n}\n'''
    (mod/'gfx/FX/uma_portrait.shader').write_text(shader,encoding='utf8')
    for ending,color in [('diffuse',[255,255,255,0]),('normal',[0,128,0,128]),('properties',[0,38,0,180]),('ssao',[255,255,255,0])]:
        dds(shared/('uma_0001_head_empty_'+ending+'.dds'),np.tile(color,(32,32,1)))
    write_json(r/'head-materials.json',materials)
    write_json(r/'material-policy.json',{'skin_effect_defines':skin_defines,'head_and_body_same_lighting':True,'body_flat_toon_removed':True,'real_time_surface_lighting_enabled':True,'skin_ssao_alpha':96,'hair_palette_channel':'packed normal blue; diffuse alpha remains opacity','brow_depth_test':False,'brow_mesh_moved':False,'no_original_texture_override':True,'runtime_verified':False})
    print('PREPARED_V6_MATERIALS',len(materials),flush=True)
if __name__=='__main__':main()
