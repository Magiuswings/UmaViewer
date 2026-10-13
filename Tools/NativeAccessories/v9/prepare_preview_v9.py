"""CPU palette evidence from final DDS; preview is Blender PBR, not CK3 shader validation."""
import sys,json
from pathlib import Path
import numpy as np
from PIL import Image
from paths_v9 import ROOT,MOD,REPO,PLUGIN
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import parser_only
P=parser_only(PLUGIN);out=ROOT/'Preview/Palette';out.mkdir(parents=True,exist_ok=True)
palette={r['actor']:r['colors']for r in json.loads((ROOT/'Reports/palette-presets.json').read_text())};registry=json.loads((ROOT/'Reports/head-registration.json').read_text());records=[]
def linear(v):return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
def srgb(v):return np.where(v<=.0031308,v*12.92,1.055*v**(1/2.4)-.055)
CAT={f.name:f for f in(MOD/'gfx').rglob('*.dds')}
def tex(ref,mesh):return CAT[Path(ref).name]
for actor in ['1001','1002']:
    rows=[(MOD/'gfx/models/portraits/uma/0001/uma_0001_body_base.mesh','body')]+[(Path(r['mesh']),r['element'])for r in registry if r['actor']==actor and r['variant']in ['80','00','base']and r['element']not in ['cheek','tear']]
    for mesh,element in rows:
        for oi,obj in enumerate(P.read_meshfile(str(mesh)).find('object')):
            for mi,part in enumerate(obj.findall('mesh')):
                mat=part.find('material');rgba=np.array(Image.open(tex(mat.get('diff')[0],mesh)).convert('RGBA'));rgb=linear(rgba[:,:,:3]/255);shader=mat.get('shader')[0];alpha=np.ones(rgba.shape[:2]);mask=np.zeros(rgba.shape[:2]);color=None
                if 'skin'in shader:color='skin';mask=rgba[:,:,3]/255
                elif 'eye'in shader:color='eye';mask=rgba[:,:,3]/255
                elif 'hair'in shader:
                    color='hair';normal=np.array(Image.open(tex(mat.get('n')[0],mesh)).convert('RGBA').resize((rgba.shape[1],rgba.shape[0]),Image.Resampling.NEAREST));mask=normal[:,:,2]/255;alpha=rgba[:,:,3]/255
                if color:rgb*=1-mask[:,:,None]+mask[:,:,None]*linear(np.array(palette[actor][color]['palette_rgb_255'])/255)
                rgba[:,:,:3]=np.rint(np.clip(srgb(rgb),0,1)*255);rgba[:,:,3]=np.rint(alpha*255);path=out/f'{actor}_{mesh.stem}_{oi}_{mi}.png';Image.fromarray(rgba,'RGBA').save(path);records.append(dict(actor=actor,mesh=str(mesh),object=oi,slot=mi,element=element,shader=shader,png=str(path),palette_color=color,source_material_diffuse=mat.get('diff')[0]))
(out/'preview-index.json').write_text(json.dumps(dict(actual_CK3_shader_lighting_verified=False,cpu_rule='sRGB decoded to linear, diffuse multiplied by original palette selected RGB with actual alpha/B mask. PBR preview only.',rows=records),indent=2),encoding='utf8');print('V9_PREVIEW_TEXTURES',len(records),flush=True)
