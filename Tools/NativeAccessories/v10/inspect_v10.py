import sys,json
import numpy as np
from PIL import Image
from paths_v10 import ROOT,MOD,V9,REPO,PLUGIN
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7')]
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,compose,readlocals,deform
P=parser_only(PLUGIN);CAT={f.name:f for f in MOD.rglob('*.dds')}
def main():
    rows=[]
    for actor in ['1001','1002']:
        for file in [MOD/f'gfx/models/portraits/uma/{actor}/uma_{actor}_head_00.mesh',MOD/'gfx/models/portraits/uma/0001/uma_0001_body_base.mesh']:
            for obj in P.read_meshfile(str(file)).find('object'):
                for mi,m in enumerate(obj.findall('mesh')):
                    mat=m.find('material');rgba=np.array(Image.open(CAT[mat.get('diff')[0]]).convert('RGBA'));uv=np.array(m.get('u0')).reshape(-1,2);x=np.clip(np.rint((rgba.shape[1]-1)*uv[:,0]).astype(int),0,rgba.shape[1]-1);y=np.clip(np.rint((rgba.shape[0]-1)*(1-uv[:,1])).astype(int),0,rgba.shape[0]-1);pixels=rgba[y,x];row=dict(actor=actor,file=file.name,slot=mi,material=mat.attrib,texture_size=list(rgba.shape[:2]),sample_RGBA_mean=pixels.mean(axis=0).tolist(),alpha_range=[int(pixels[:,3].min()),int(pixels[:,3].max())]);rows.append(row);print('SKIN',row,flush=True)
    for variant in ['08','09']:
        file=MOD/f'gfx/models/portraits/uma/0001/uma_0001_headwear_0008_{variant}_00_base.mesh';o=P.read_meshfile(str(file)).find('object')[0];D=rigdata(o.find('skeleton'));pts=np.vstack([np.array(m.get('p')).reshape(-1,3)for m in o.findall('mesh')]);BW=compose(D,readlocals(P,MOD/'gfx/models/portraits/uma/animation/body/uma_body_native_idle.anim',0));sample=deform(o.find('mesh'),D,BW);used=np.unique(np.array(o.find('mesh').find('skin').get('ix')));used=[int(i)for i in used if i>=0];r=dict(file=file.name,vertices=len(pts),bounds=[pts.min(axis=0).tolist(),pts.max(axis=0).tolist()],animated_bounds=[sample.min(axis=0).tolist(),sample.max(axis=0).tolist()],bones=len(D['names']),skin_indices=used,skin_names=[D['names'][i]for i in used],bind_points={D['names'][i]:D['bind'][i,:3,3].tolist()for i in used});rows.append(r);print('HAT',r,flush=True)
    (ROOT/'Reports/input-material-hat-audit.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
if __name__=='__main__':main()
