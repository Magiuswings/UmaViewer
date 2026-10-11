import os
"""Offline diffuse*selected palette preview, without claiming CK3 shader lighting."""
import json,sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));OUT=ROOT/'HeadSources/AssemblyQA/PalettePreview';OUT.mkdir(exist_ok=True);P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))));palette={r['actor']:r['colors']for r in json.loads((ROOT/'Reports/palette-presets.json').read_text())};reg=json.loads((ROOT/'Reports/head-registration.json').read_text());rows=[]
for actor in ['1001','1002']:
    rows+=[(actor,ROOT/'UMA-V7/gfx/models/portraits/uma/0001/uma_0001_body_base.mesh','body')]
for row in reg:
    if row['variant']in ['80','00','base']and row['element']not in ['cheek','tear']:rows.append((row['actor'],Path(row['mesh']),row['element']))
def linear(v):return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
def srgb(v):return np.where(v<=.0031308,v*12.92,1.055*v**(1/2.4)-.055)
records=[]
for actor,path,element in rows:
    m=P.read_meshfile(str(path)).find('object')[0].find('mesh').find('material');rgba=np.array(Image.open(path.parent/m.get('diff')[0]).convert('RGBA'));rgb=linear(rgba[:,:,:3]/255.);shader=m.get('shader')[0];alpha=np.ones(rgba.shape[:2]);mask=np.zeros(rgba.shape[:2]);color=None
    if 'skin'in shader:color='skin';mask=rgba[:,:,3]/255.
    elif 'eye'in shader:color='eye';mask=rgba[:,:,3]/255.
    elif 'hair'in shader:
        color='hair';normal=np.array(Image.open(path.parent/m.get('n')[0]).convert('RGBA').resize((rgba.shape[1],rgba.shape[0]),Image.Resampling.NEAREST));mask=normal[:,:,2]/255.;alpha=rgba[:,:,3]/255.
    if color:rgb*=1-mask[:,:,None]+mask[:,:,None]*linear(np.array(palette[actor][color]['palette_rgb_255'])/255.)
    rgba[:,:,:3]=np.rint(np.clip(srgb(rgb),0,1)*255);rgba[:,:,3]=np.rint(alpha*255);name=actor+'_'+path.stem+'.png';Image.fromarray(rgba,'RGBA').save(OUT/name);records.append({'actor':actor,'mesh':str(path),'element':element,'shader':shader,'png':str(OUT/name),'palette_color':color,'source_material_diffuse':m.get('diff')[0]})
(OUT/'preview-index.json').write_text(json.dumps({'actual_CK3_shader_lighting_verified':False,'cpu_rule':'sRGB texture decoded to linear, Diffuse*selected original Palette with actual alpha/B mask, encoded sRGB; PBR preview lighting only','rows':records},indent=2)+'\n',encoding='utf8');print('PREVIEW_TEXTURES',len(records))
