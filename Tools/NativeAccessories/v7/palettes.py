import os
"""Nearest fixed-palette points from source material UVs; palettes remain read-only."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));GAME=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game'))));index=json.loads((R/'HeadSources/head-parts-index.json').read_text());results=[]
skin_source=Path(str(Path(os.environ.get('UMA_V7_SKIN_COLORS','E:/UmaViewer-Exports/2026-10-08-Skin-Envelope/vector-delivery/skin-colors.json'))));skin_table=json.loads(skin_source.read_text());skin1=next(x for x in skin_table['palettes']if x['skin']==1)
def lab(rgb):
    a=np.asarray(rgb,float)/255.;a=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4);xyz=a@np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])/np.array([.95047,1,1.08883]);v=np.where(xyz>.008856,np.cbrt(xyz),7.787*xyz+16/116);return np.stack([116*v[...,1]-16,500*(v[...,0]-v[...,1]),200*(v[...,1]-v[...,2])],axis=-1)
def art_color(record,element):
    raw=json.loads(Path(record['parsed_json']).read_text());mesh=next(m for m in raw['meshes']if m['name']==('M_Hair'if element=='hair'else'M_Face'));faces=[f for f in mesh['faces']if f['category']==('eyes'if element=='eye'else'hair')];faces=faces or mesh['faces'];f=faces[0];mat=raw['materials'][f['material']];main=next(p for p in mat['properties']if p['name']=='_MainTex'and p.get('texture'));pix=np.array(Image.open(Path(record['texture_root'])/main['texture']).convert('RGBA'));tri=np.array([n for f in faces for n in f['triangles']]).reshape(-1,3);uv=np.array([[u['x'],u['y']]for u in mesh['uvs'][0]['values']]);center=uv[tri].mean(1)*np.array(main.get('scale',[1,1]))+np.array(main.get('offset',[0,0]));x=np.minimum((center[:,0]%1*pix.shape[1]).astype(int),pix.shape[1]-1);y=np.minimum(((1-center[:,1]%1)*pix.shape[0]).astype(int),pix.shape[0]-1);colors=pix[y,x,:3].astype(float);p=np.array([[v[k]for k in 'xyz']for v in mesh['vertices']]);area=np.linalg.norm(np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]]),axis=1)*.5;valid=(colors.max(1)>35)&(colors.max(1)<240)&((colors.max(1)-colors.min(1))>12)&(pix[y,x,3]>20);bins=(colors//8).astype(int);unique,ids=np.unique(bins[valid],axis=0,return_inverse=True);masses=np.bincount(ids,weights=area[valid]);choose=ids==masses.argmax();return np.average(colors[valid][choose],axis=0,weights=area[valid][choose]).tolist()
palettes={}
for category in ['skin','hair','eye']:
    file=GAME/'gfx/portraits'/(category+'_palette.dds');pix=np.array(Image.open(file).convert('RGB'));assert pix.shape[0]==pix.shape[1];palettes[category]=(file,pix,lab(pix));
for actor in ['1001','1002']:
    source=next(x for x in index['records']if x['kind']=='head'and x['character_id']==actor and x['variant']=='80');targets={'skin':skin1['statistics']['rgb_srgb_255'],'hair':art_color(source,'hair'),'eye':art_color(source,'eye')};coords={}
    for category,target in targets.items():
        file,pix,colors=palettes[category];error=np.linalg.norm(colors-lab(target),axis=-1);y,x=np.unravel_index(error.argmin(),error.shape);xy=[(float(x)+.5)/pix.shape[1],(float(y)+.5)/pix.shape[0]];coords[category]={'target_rgb_255':target,'palette_rgb_255':pix[y,x].tolist(),'xy':xy,'rectangle':[xy[0],xy[1],xy[0],xy[1]],'delta_e76':float(error[y,x]),'palette':file.relative_to(GAME).as_posix(),'palette_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'palette_size':list(pix.shape[:2]),'source':'database skin index1 default diffuse'if category=='skin'else'area-weighted dominant source material UV color','pixel':[int(x),int(y)]}
    coords['skin']['source']='chara_data skin=1 -> original default diffuse area-weighted skin statistics';coords['skin']['source_statistics_file']=str(skin_source);coords['skin']['source_texture']=skin1['source_texture'];coords['skin']['source_texture_sha256']=skin1['source_sha256'];coords['skin']['sampling_method']=skin1['statistics']['method']
    results.append({'actor':actor,'database_skin_index':1,'colors':coords,'one_rectangle_per_color':True,'palettes_changed':False})
(R/'Reports/source-skin-color-table.json').write_text(json.dumps(skin_table,indent=2),encoding='utf8')
(R/'Reports/palette-presets.json').write_text(json.dumps(results,indent=2),encoding='utf8');print('FIXED_PALETTE_PRESETS',json.dumps(results),flush=True)
