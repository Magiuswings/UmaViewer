"""Independent static material variation review; no formal-mod mutations."""
import re,json,hashlib,collections,sys
from pathlib import Path
from PIL import Image
V=Path(r'E:\UmaViewer-Exports\2026-10-13-UMA-V10');R=V/'UMA-V10';G=Path(r'D:\steam\steamapps\common\Crusader Kings III')
shader_path=R/'gfx/FX/uma_portrait.shader';variation_path=R/'gfx/portraits/accessory_variations/uma_clothing_colors.txt';rules_path=R/'gfx/portraits/customization_rules/uma_portrait_customization.txt';shared=R/'gfx/models/portraits/uma/0001/shared'
native_path=G/'jomini/gfx/FX/jomini/portrait_accessory_variation.fxh';data_path=G/'jomini/gfx/FX/jomini/portrait_user_data.fxh'
def read(p):return p.read_text(encoding='utf-8-sig')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blocks(s):
    s=re.sub(r'#[^\n]*','',s);i=0;out=[]
    while i<len(s):
        m=re.search(r'([\w.@-]+)\s*=\s*\{',s[i:])
        if not m:break
        op=i+m.end()-1;j=op+1;depth=1
        while depth:
            if s[j]=='{':depth+=1
            elif s[j]=='}':depth-=1
            j+=1
        out.append((m[1],s[op+1:j-1]));i=j
    return out
def scalar(s,k):
    m=re.search(r'(?m)^\s*'+re.escape(k)+r'\s*=\s*("[^"]*"|[^\s{}]+)',s);return m[1].strip('"') if m else None
sources=[]
def source(p,needle,note):
    lines=read(p).splitlines();hits=[i+1 for i,l in enumerate(lines) if needle in l];assert hits,needle
    entry=dict(file=str(p),line=hits[0],sha256=sha(p),code=lines[hits[0]-1].strip(),note=note);sources.append(entry);return entry
native=read(native_path);userdata=read(data_path);shader=read(shader_path);variation=read(variation_path);rules=read(rules_path)
source(native_path,'UV /= Desc._Scale','pattern UV divides by descriptor scale')
source(native_path,'MaskIndexOffset * 4 + i','the active pattern/channel determines the override color index')
source(native_path,'Diffuse *= PatternDiffuse','native multiplies source RGB/alpha by variation diffuse')
source(native_path,'Diffuse.rgb *= PatternProperties.rrr','pattern properties R also multiplies source RGB as AO')
source(data_path,'return ColorIndex > 0 ? (ColorIndex - 1) * 4 : -1','color blocks resolve to -1 or 0/4/8/12')
source(data_path,'Desc._UseColorOverrides = ColorOverrideOffset > 0','native raw color block marker enables color overrides')
source(G/'game/gfx/portraits/accessory_variations/example.txt','Color palette textures are 16-wide','documented native palette width')
source(G/'game/gfx/portraits/accessory_variations/example.txt','r,g,b,a here refers','variation pattern channels map to entity pattern mask')
stock_rules=G/'game/gfx/portraits/customization_rules/_customization_rules.info'
source(stock_rules,'accessory_color_override_block_0 (','four editor block fields refer to portrait modifier groups')
source(stock_rules,'All four are required','all four color override blocks are required')
stock_entity=G/'game/gfx/models/portraits/m_legwear/western/war_01/m_legwear_secular_western_war_01.asset'
source(stock_entity,'portrait_entity_user_data =','stock nesting for portrait_accessory is entity/game_data/portrait_entity_user_data')

dds_paths=collections.defaultdict(list)
for p in R.rglob('*.dds'):dds_paths[p.name].append(p)
images={}
for suffix in ('mask','normal','properties','palette'):
    p=shared/f'uma_0001_tint_{suffix}.dds';im=Image.open(p).convert('RGBA');pixels=list(im.getdata());images[suffix]=dict(path=str(p),sha256=sha(p),size=list(im.size),unique_rgba=[list(x) for x in sorted(set(pixels))]);assert len(dds_paths[p.name])==1
neck=shared/'uma_0001_neck_diffuse.dds';im=Image.open(neck).convert('RGBA');neck_info=dict(path=str(neck),sha256=sha(neck),size=list(im.size),rgba=list(im.getpixel((0,0))))
assert images['mask']['unique_rgba']==[[255,0,0,0]]
assert images['palette']['size']==[16,1] and images['palette']['unique_rgba']==[[255,255,255,255]]
assert images['properties']['unique_rgba'][0][0]==255 and images['normal']['unique_rgba'][0][2]==255
assert neck_info['size']==[1,1] and neck_info['rgba']==[255,235,222,255]
variation_blocks=dict(blocks(variation));assert set(variation_blocks)=={'pattern_textures','pattern_layout','variation'}
for kind,b in variation_blocks.items():assert scalar(b,'name')=='uma_plain_tint'
pt=variation_blocks['pattern_textures'];resource_refs={key:scalar(pt,key) for key in ('colormask','normal','properties')};resource_refs['palette']=scalar(dict(blocks(variation_blocks['variation']))['color_palette'],'texture')
assert all('/' not in name and '\\' not in name and len(dds_paths[name])==1 for name in resource_refs.values())
layout=dict(blocks(variation_blocks['pattern_layout']));assert scalar(layout['scale'],'min')==scalar(layout['scale'],'max')=='1.0'
pattern=dict(blocks(variation_blocks['variation']))['pattern'];pattern_channels=dict(blocks(pattern));assert set(pattern_channels)==set('rgba')
assert all(scalar(b,'textures')==scalar(b,'layout')=='uma_plain_tint' for b in pattern_channels.values())

meshes={};entities=[];missing=[];texture_refs=[];neck_slots=[]
for p in (R/'gfx/models').rglob('*.asset'):
    top=blocks(read(p))
    for kind,b in top:
        if kind=='pdxmesh':
            key=scalar(b,'name');slots=[leaf for k,leaf in blocks(b) if k=='meshsettings'];meshes[key]=dict(file=str(p),attachment=any(scalar(s,'shader')=='portrait_attachment' for s in slots),slots=slots)
            for s in slots:
                for k in ('texture_diffuse','texture_normal','texture_specular'):
                    val=scalar(s,k)
                    if val:texture_refs.append(dict(asset=str(p),slot=scalar(s,'index'),field=k,value=val,basename_only='/' not in val and '\\' not in val,unique_basename=len(dds_paths[val])==1))
            if p.name in ('uma_1001_head_00.asset','uma_1002_head_00.asset') and scalar(b,'file')==p.with_suffix('.mesh').name:
                for s in slots:
                    if scalar(s,'index') in ('2','3'):
                        assert scalar(s,'shader')=='portrait_skin' and scalar(s,'texture_diffuse')==neck.name
                        neck_slots.append(dict(asset=str(p),slot=scalar(s,'index'),shader=scalar(s,'shader'),diffuse=scalar(s,'texture_diffuse'),normal=scalar(s,'texture_normal'),properties=scalar(s,'texture_specular')))
        elif kind=='entity':entities.append((str(p),b))
attachments=[]
for file,e in entities:
    mesh=scalar(e,'pdxmesh')
    if mesh not in meshes or not meshes[mesh]['attachment']:continue
    name=scalar(e,'name');gd=dict(blocks(e)).get('game_data','');ud=dict(blocks(gd)).get('portrait_entity_user_data','');pa=dict(blocks(ud)).get('portrait_accessory','')
    if scalar(pa,'pattern_mask')!='gfx/models/portraits/uma/0001/shared/uma_0001_tint_mask.dds' or scalar(pa,'variation')!='uma_plain_tint':missing.append(name)
    attachments.append(dict(entity=name,file=file,mesh=mesh))
assert len(attachments)==196 and not missing and len(neck_slots)==4
assert all(x['basename_only'] and x['unique_basename'] for x in texture_refs)
rule=dict(blocks(dict(blocks(rules))['uma']));modifiers=read(R/'gfx/portraits/portrait_modifiers/uma_customization.txt');groups=dict(blocks(modifiers));expected=['uma_custom_clothes','uma_custom_headwear','uma_custom_shoes','uma_custom_socks']
editor_blocks={}
for i,g in enumerate(expected):
    value=scalar(rules,'accessory_color_override_block_'+str(i));assert value==g and scalar(groups[g],'usage')=='customization';editor_blocks[str(i)]=value
assert scalar(rule['color_genes'],'hair')=='uma_custom_character'
assert 'color_scope' not in modifiers+rules+read(R/'gfx/portraits/accessories/uma_parts.txt')

effect=shader[shader.index('Effect portrait_attachment\n'):shader.index('Effect portrait_attachmentShadow')]
assert '"VARIATIONS_ENABLED"' in effect and '"MOE_ACCESSORY_TINT"' in effect and 'PS_attachment' in effect
fixed='PatternColorOverrides[UmaColorBase * 4].a > 0.0f' in shader and 'for( int UmaChannel' not in shader
assert fixed
for restoration in ('Properties = UmaSourceProperties;','NormalSample = UmaSourceNormal;','PatternNormal = UmaSourceNormal;','NormalUVChannel = 0.0f;'):assert restoration in shader
assert '#if defined( VARIATIONS_ENABLED ) && !defined( MOE_ACCESSORY_TINT )' in shader
source(shader_path,'PatternColorOverrides[UmaColorBase * 4].a','corrected override detection only checks the active flat-R pattern/color slot')
source(shader_path,'Properties = UmaSourceProperties','original response maps are restored after native variation multiplication')
source(shader_path,'float3x3 TBN2 = BuildTangentFrame','two-normal helper computes a UV1 tangent frame before the final lerp')
source(G/'jomini/gfx/FX/jomini/shader_utility.fxh','normalize( cross( float3( 0.0f, 1.0f, 0.0f ), WorldNormal ) )','native tiny-UV fallback normalizes a cross product before checking its length; parallel-Y normal can produce a zero vector')
branch_start=shader.index('Properties.r = 1.0;')
normal_branch=shader[branch_start:branch_start+1200]
single_normal_for_tint='#if defined( VARIATIONS_ENABLED ) && !defined( MOE_ACCESSORY_TINT )' in normal_branch

# CPU branch model is derived from the native local shader and decoded texture constants.
# It does not execute the CK3 GPU compiler, sampler state, shader transfer functions or UI.
def tint(rgb,block,slots):
    active=block>=0 and slots[block*4][3]>0
    base=[sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722)))]*3 if active else list(rgb)
    # PatternMask.R=1 => MaskIndex 0; pattern ColorMask.R=1 => color channel i=0.
    picked=slots[block*4][:3] if block>=0 and slots[block*4][3]>0 else [1,1,1]
    return [a*b*1 for a,b in zip(base,picked)]
src=[.2,.4,.8];none=[[0,0,0,0] for _ in range(64)];samples=[]
for block in (-1,0,4,8,12):
    zero=tint(src,block,none);assert zero==src
    samples.append(dict(case='no_active_override',block=block,source_rgb=src,result=zero,source_preserved=True))
for block in (0,4,8,12):
    active=[list(x) for x in none];active[block*4]=[1,.25,.5,1];result=tint(src,block,active);lum=sum(a*b for a,b in zip(src,(.2126,.7152,.0722)));expected_rgb=[lum,lum*.25,lum*.5];assert result==expected_rgb
    samples.append(dict(case='first_slot_active',block=block,source_rgb=src,result=result,expected=expected_rgb,uses_selected_hue=True))
    for unused in (1,2,3):
        active=[list(x) for x in none];active[block*4+unused]=[.1,.3,.5,1];result=tint(src,block,active);assert result==src
        samples.append(dict(case='unused_G_B_A_slot_only',block=block,unused_offset=unused,result=result,source_preserved=True))
findings=[]
if not single_normal_for_tint:
    findings.append(dict(id='N1',severity='conditional_static_normal_risk',description='Tint restores NormalUVChannel=0, but still calls CommonPixelShaderWithTwoNormal, which constructs and normalizes a UV1 derivative tangent frame before lerp(Base,Layered,0). A degenerate UV1/tangent frame can produce an invalid LayeredNormal; zero lerp weight does not guarantee removal of NaN. No actual failing mesh/runtime result was asserted.',candidate_fix='In PS_attachment color branch use #if defined( VARIATIONS_ENABLED ) && !defined( MOE_ACCESSORY_TINT ) for CommonPixelShaderWithTwoNormal, and original CommonPixelShader for the else path. This restores the old single-normal computation for tint while retaining native pattern normal behavior for other effects.'))
boundaries=[dict(id='R1',severity='unverified_engine_binding',detail='Basename-only references are unique and all resolve to actual local DDS by basename. Native stock variation examples use full VFS paths; this static review does not prove CK3 resolves standalone variation texture/mask basenames from the shared asset directory. Preserve the user basename instruction and verify engine import/logs instead of silently replacing paths.'),dict(id='R2',severity='unverified_compile_runtime',detail='No CK3 shader compile or GPU execution. Structural defaults and CPU branch algebra do not prove shader compilation, actual user-data/texture-array upload, color-space sampling, barbershop persistence or GPU normal response.'),dict(id='R3',severity='documented_current_scope',detail='Flat mask R1 and flat color mask R1 provide one effective dye color per wardrobe block. Other palette slots do not alter the picture and now do not desaturate it. Four wardrobe editor blocks are correctly separate from the sixteen possible native palette colors.')]
result=dict(review='independent_static_material_variation_review',status='static_structure_and_CPU_cases_passed' if not findings else 'CPU_color_cases_passed_with_conditional_normal_risk',formal_mod_modified=False,confirmed_findings=findings,tint_uses_original_single_normal_path=single_normal_for_tint,corrected_issue=dict(description='Old any-of-four color check could gray source on unused G/B/A-only override; final formal shader checks only active first slot.',fixed_in_reviewed_shader=True),attachment_entities=len(attachments),attachment_missing_variation=missing,neck_slots=neck_slots,neck_DDS=neck_info,helper_DDS=images,variation_schema_matches_stock=True,variation_all_four_patterns_defined=True,layout_scale_min_max=[1,1],empty_pattern_name_count=0,zero_scale_defined_count=0,basename_texture_reference_count=len(texture_refs),all_basename_refs_unique_and_present=True,variation_basename_resources=resource_refs,shader_effect_generic_name='portrait_attachment',shader_variation_defines_present=True,normal_and_properties_restored=True,cloth_fresnel_disabled_for_tint=True,default_algebra='White pattern/palette gives Diffuse*white; pattern properties R=1 gives no extra AO; normal blue=1 preserves opacity even when enabled. Original source Properties/Normal/PatternNormal/NormalUVChannel restored.',editor_override_blocks=editor_blocks,color_genes_hair='uma_custom_character',invented_color_scope_field_count=0,CPU_cases=samples,CPU_model_boundary='Local native algorithm plus decoded flat texture constants; no GPU shader/color-space/UI execution.',engine_boundaries=boundaries,sources=sources,input_hashes={str(p):sha(p) for p in [shader_path,variation_path,rules_path,native_path,data_path]},shader_compilation_executed=False,CK3_executed=False,barbershop_save_roundtrip_executed=False)
jsonfile=V/'Reports/independent-material-review.json';jsonfile.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
lines=['V10 材质 variation 独立静态审查','结论：静态结构与21项CPU分支样本通过；未运行CK3 shader编译或游戏。','本审查不修改正式Mod。','已复读修正：UmaHasColor仅检查PatternColorOverrides[UmaColorBase*4].a，其他未参与flatR染色的G/B/A槽不再触发去色。',f'196个portrait_attachment entity均正确嵌套portrait_accessory；4个颈部slots2/3均portrait_skin，1px颈环实际RGBA={neck_info["rgba"]}。','variation三个真实schema与原版一致，四pattern引用闭合；scale固定1，flatMask R1，16x1palette全白，properties R1，normal蓝1。默认无override按原ApplyVariationPatterns乘白色与AO1，保留原diffuse；source响应贴图和normal复原，cloth fresnel在tint定义下禁用。','CPU样本覆盖无override（含四有效blockmarker）、首槽实际override、只有其他无效槽override。参考RGBA归一化RGB=(0.2,0.4,0.8)，首槽染色=(1,0.25,0.5)结果=(0.38636,0.09659,0.19318)，无override或仅其他槽均=(0.2,0.4,0.8)。','四editor字段accessory_color_override_block_0/1/2/3分别正确引用clothes/headwear/shoes/socks的customization组。未添加虚构color_scope字段；hair色picker仍映射actor group。','basename贴图引用全部唯一且对应本地实际DDS，符合用户指令；原版variation示例采用完整VFS路径，因此引擎对独立variation配置basename的实际装载不能由文件名闭包证明，仍应通过实机import/log验收；本次不改路径。','GPU编译、user_data与texture array上载、实际sRGB采样、Barber提交存档重载未验证；静态/CPU通过不代表实机通过。','来源证据：']
lines.extend(f'{s["file"]}:{s["line"]} | {s["note"]}' for s in sources)
if findings:
    lines.extend(['条件性normal风险：恢复NormalUVChannel=0仍计算UV1双normal路径，退化导数的无效LayeredNormal不保证被lerp零权重消除。未声称已找到实机坏mesh。','最小候选：PS_attachment的双normal调用条件改成VARIATIONS_ENABLED且非MOE_ACCESSORY_TINT；tint走原CommonPixelShader，其他pattern shader保留双normal。'])
else:lines.append('已复读确认tint走原CommonPixelShader单normal路径，避免无关UV1 tangent frame计算。')
(V/'Reports/independent-material-review.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
print(json.dumps(dict(report=str(jsonfile),static_passed=True,attachments=len(attachments),neck_slots=len(neck_slots),CPU_cases=len(samples),fixed_first_slot=fixed,findings=len(findings),engine_boundaries=len(boundaries)),ensure_ascii=False,indent=2))
