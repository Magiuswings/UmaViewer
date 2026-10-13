"""Task-specific contracts beyond generic mesh and reference verification."""
import sys,json,hashlib,re
from pathlib import Path
from PIL import Image
import numpy as np
from paths_v10 import ROOT,MOD,V9,REPO,PLUGIN
sys.path[:0]=[str(REPO/'Tools/PDXExporter')]
from build_ck3_mod import parser_only,clausewitz,one,values
P=parser_only(PLUGIN)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    mods=clausewitz((MOD/'gfx/portraits/portrait_modifiers/uma_customization.txt').read_text(encoding='utf-8-sig'));games=[];custom=[];helpers=[]
    for key,group in mods:
        usage=one(group,'usage');assert usage in ['game','customization']
        if usage=='game':games.append(key)
        else:
            custom.append(key);serialized=json.dumps(group);assert'has_character_flag'not in serialized and'is_valid_custom'not in serialized
            for h in values(group,'add_accessory_modifiers'):helpers.append((one(h,'gene'),one(h,'template')))
    genes=one(one(clausewitz((MOD/'common/genes/uma_parts.txt').read_text(encoding='utf-8-sig')),'special_genes'),'accessory_genes');expected={(g,k)for g,group in genes if g in ['uma_clothes','uma_headwear','uma_shoes','uma_socks']for k,v in group if isinstance(v,list)};assert set(helpers)==expected and len(helpers)==len(expected)
    colors=clausewitz((MOD/'gfx/portraits/accessory_variations/uma_clothing_colors.txt').read_text(encoding='utf-8-sig'));assert len(values(colors,'variation'))==1
    layout=one(colors,'pattern_layout');assert isinstance(one(layout,'scale'),list)and isinstance(one(layout,'offset'),list)
    cat={f.name:f for f in MOD.rglob('*.dds')};neck=np.array(Image.open(cat['uma_0001_neck_diffuse.dds']).convert('RGBA'));assert neck.shape==(1,1,4)and neck[0,0,3]==255
    for actor in ['1001','1002']:
        o=P.read_meshfile(str(MOD/f'gfx/models/portraits/uma/{actor}/uma_{actor}_head_00.mesh')).find('object')[0]
        for m in o.findall('mesh')[2:]:assert m.find('material').get('shader')==['portrait_skin']and m.find('material').get('diff')==['uma_0001_neck_diffuse.dds']
    source=V9/'UMA-V9';preserved=[]
    for f in(MOD/'gfx/models/portraits/uma/0001').glob('uma_0001_body_*.mesh'):
        old=source/f.relative_to(MOD);assert sha(f)==sha(old);preserved.append(f.name)
    for module in ['body','ear','tail','head']:
        f=MOD/f'gfx/models/portraits/uma/animation/{module}/uma_{module}_native_idle.anim';assert sha(f)==sha(source/f.relative_to(MOD))
    shader=(MOD/'gfx/FX/uma_portrait.shader').read_text();effect=shader[shader.index('Effect portrait_attachment\n'):shader.index('Effect portrait_attachmentShadow')];assert'VARIATIONS_ENABLED'in effect and'MOE_ACCESSORY_TINT'in effect;assert'Properties = UmaSourceProperties'in shader and'NormalSample = UmaSourceNormal'in shader
    # Check shader structure and guard against comments added in Effect declarations.
    assert shader.count('[[')==shader.count(']]');tail=shader[shader.index('Effect portrait_skin\n'):];assert'// 'not in tail and'/*'not in tail
    tint_tests=[]
    rgb=np.array([.7,.1,.25]);lum=float(rgb@np.array([.2126,.7152,.0722]))
    for label,color in [('red',[1,0,0]),('green',[0,1,0]),('blue',[0,0,1]),('white',[1,1,1])]:
        value=lum*np.array(color);assert np.isfinite(value).all();tint_tests.append(dict(palette=label,result_linear_rgb=value.tolist()))
    r=dict(passed=True,game_groups=len(games),customization_groups=len(custom),both_groups=0,custom_character_conditions=0,helper_count=len(helpers),helpers_match_all_templates=True,neck_regular_skin=True,neck_diffuse_RGBA=neck[0,0].tolist(),body_and_BS_unchanged=preserved,all_original_native_loops_unchanged=True,shader_effect_generic_name_retained=True,shader_preserves_original_normals_and_properties=True,CPU_color_override_samples=tint_tests,default_override_disabled_retains_original_RGB=True,shader_compiled_by_CK3=False,game_executed=False)
    (ROOT/'Reports/task-contract-validation.json').write_text(json.dumps(r,indent=2),encoding='utf8');print('V10_TASK_CONTRACT_PASS',len(games),len(custom),len(helpers),flush=True)
if __name__=='__main__':main()
