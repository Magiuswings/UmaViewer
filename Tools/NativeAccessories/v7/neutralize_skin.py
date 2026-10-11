import os
"""Remove baked skin base hue before the unchanged shader multiplies palette color."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));MOD=R/'UMA-V7';manifest=json.loads((R/'Reports/head-registration.json').read_text());backup=R/'SkinMaterialSources';backup.mkdir(exist_ok=True);records=[]
table=json.loads((R/'Reports/source-skin-color-table.json').read_text());ref=next(x for x in table['palettes']if x['skin']==1)['statistics']['rgb_srgb_255']
def linear(rgb):
    rgb=np.asarray(rgb,float)/255.;return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
def srgb(rgb):return np.where(rgb<=.0031308,rgb*12.92,1.055*np.power(np.maximum(rgb,0),1/2.4)-.055)*255
skin=linear(ref);files=set()
for row in manifest:
    if row['element']in ['face','face_parts']:files.add(Path(row['mesh']).with_name(row['prefix']+'_diffuse.dds'))
files.add(MOD/'gfx/models/portraits/uma/0001/uma_0001_body_skin1_diffuse.dds')
for file in sorted(files):
    assert file.is_file(),file;source=backup/file.name
    # A registration re-run restores original derived textures. Read those;
    # standalone re-runs use the saved original to avoid dividing twice.
    original=file.read_bytes()
    previous=R/'Reports/skin-neutralization.json'
    old=json.loads(previous.read_text())if previous.exists()else{}
    completed=next((x for x in old.get('textures',[])if x['file']==file.relative_to(MOD).as_posix()),None)
    if not(completed and hashlib.sha256(original).hexdigest()==completed['output_sha256']):source.write_bytes(original)
    rgba=np.array(Image.open(source).convert('RGBA'));mask=rgba[:,:,3:4]/255.;factor=(1-mask)+mask*skin;rgb=linear(rgba[:,:,:3]);neutral=np.clip(rgb/factor,0,1);out=rgba.copy();out[:,:,:3]=np.clip(np.rint(srgb(neutral)),0,255).astype(np.uint8);Image.fromarray(out).save(file,pixel_format='DXT5')
    # Preserve original BC3 alpha blocks exactly; RGB recompression must not
    # change the shader's palette or transparency mask at antialiased edges.
    oldbytes=source.read_bytes();newbytes=bytearray(file.read_bytes());assert oldbytes[84:88]==newbytes[84:88]==b'DXT5'and len(oldbytes)==len(newbytes),file
    for offset in range(128,len(newbytes),16):newbytes[offset:offset+8]=oldbytes[offset:offset+8]
    file.write_bytes(newbytes);actual=np.array(Image.open(file).convert('RGBA'));assert np.array_equal(actual[:,:,3],rgba[:,:,3]),file
    rebuilt=srgb(linear(actual[:,:,:3])*factor);active=mask[:,:,0]>.5;error=np.abs(rebuilt-rgba[:,:,:3]);records.append({'file':file.relative_to(MOD).as_posix(),'original_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'alpha_mask_preserved':True,'source_base_reference_srgb255':ref,'mean_reference_reconstruction_error_srgb255':float(error[active].mean())if active.any()else 0,'max_reference_reconstruction_error_srgb255':float(error[active].max())if active.any()else 0})
report={'unchanged_shader_operation':'lerp(Diffuse, Diffuse*Palette, DiffuseAlpha)','normalization_space':'linear RGB, encoded back to sRGB DXT5','source_base_reference_srgb255':ref,'original_body_face_geometry_unchanged':True,'shader_unchanged':True,'palettes_unchanged':True,'textures':records};(R/'Reports/skin-neutralization.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('SKIN_PALETTE_BASE_NEUTRALIZED',len(records),flush=True)
