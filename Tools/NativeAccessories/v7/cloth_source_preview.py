import os
"""CPU UV-textured source geometry previews; no Blender or destination rig."""
import json,sys,gc,argparse
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'))
def preview(snapshot,out):
 d=json.loads(Path(snapshot).read_text(encoding='utf8'));resources=Path(snapshot).parent/'resources';textures={}
 for i,m in enumerate(d['materials']):
  p=next((p for p in m['properties']if p['name']=='_MainTex'and p.get('texture')),None)
  if p:
   try:textures[i]=(np.asarray(Image.open(resources/p['texture']).convert('RGBA')),p.get('scale',[1,1]),p.get('offset',[0,0]))
   except FileNotFoundError:pass
 geom=[]
 for m in d['meshes']:
  if not m.get('active',True):continue
  p=np.array([[v[a]for a in 'xyz']for v in m['vertices']],float);uvl=next((u for u in m['uvs']if u['channel']==0),None);uv=np.array([[v[a]for a in 'xy']for v in uvl['values']])if uvl else np.zeros((len(p),2))
  for f in m['faces']:geom.append((p,np.array(f['triangles']).reshape(-1,3),uv,f['material']))
 if not geom:return
 W,H=640,880;canvas=np.empty((H,2*W,3),np.uint8);canvas[:]=[52,55,63];allp=np.concatenate([p for p,t,u,mat in geom]);lo=allp.min(0);hi=allp.max(0)
 for view in [0,1]:
  xa=0 if view==0 else 2;depthaxis=2 if view==0 else 0;scale=min((W-48)/max(hi[xa]-lo[xa],.1),(H-76)/max(hi[1]-lo[1],.1));center=(lo[xa]+hi[xa])/2;zbuf=np.full((H,W),-np.inf);panel=canvas[:,view*W:(view+1)*W]
  for p,tri,uv,mat in geom:
   proj=np.column_stack([(p[:,xa]-center)*scale+W/2,(hi[1]-p[:,1])*scale+46]);atlas,ts,to=textures.get(mat,(None,[1,1],[0,0]))
   for t in tri:
    q=proj[t];xmin=max(0,int(np.floor(q[:,0].min())));xmax=min(W-1,int(np.ceil(q[:,0].max())));ymin=max(0,int(np.floor(q[:,1].min())));ymax=min(H-1,int(np.ceil(q[:,1].max())))
    if xmax<xmin or ymax<ymin:continue
    e1=q[1]-q[0];e2=q[2]-q[0];den=e1[0]*e2[1]-e2[0]*e1[1]
    if abs(den)<1e-8:continue
    x,y=np.meshgrid(np.arange(xmin,xmax+1)+.5,np.arange(ymin,ymax+1)+.5);dx=x-q[0,0];dy=y-q[0,1];b=(dx*e2[1]-dy*e2[0])/den;c=(dy*e1[0]-dx*e1[1])/den;a=1-b-c;inside=(a>=-1e-6)&(b>=-1e-6)&(c>=-1e-6);depth=a*p[t[0],depthaxis]+b*p[t[1],depthaxis]+c*p[t[2],depthaxis];old=zbuf[ymin:ymax+1,xmin:xmax+1];inside&=depth>old
    if not inside.any():continue
    if atlas is not None:
     u=(a*uv[t[0],0]+b*uv[t[1],0]+c*uv[t[2],0])*ts[0]+to[0];v=(a*uv[t[0],1]+b*uv[t[1],1]+c*uv[t[2],1])*ts[1]+to[1];tx=np.minimum(((u%1)*atlas.shape[1]).astype(int),atlas.shape[1]-1);ty=np.minimum(((1-v%1)*atlas.shape[0]).astype(int),atlas.shape[0]-1);rgba=atlas[ty,tx];inside&=rgba[:,:,3]>100;rgb=rgba[:,:,:3].astype(float)
    else:rgb=np.full((*a.shape,3),180.)
    normal=np.cross(p[t[1]]-p[t[0]],p[t[2]]-p[t[0]]);normal/=max(np.linalg.norm(normal),1e-9);shade=.68+.32*abs(normal[depthaxis]);rgb=np.clip(rgb*shade,0,255).astype(np.uint8);target=panel[ymin:ymax+1,xmin:xmax+1];target[inside]=rgb[inside];old[inside]=depth[inside]
 img=Image.fromarray(canvas);draw=ImageDraw.Draw(img);draw.text((12,9),d.get('family_key','')+' | native geometry / UV textured CPU probe',fill=(240,240,240));draw.text((W+12,28),'Side',fill=(220,220,220));out.parent.mkdir(parents=True,exist_ok=True);img.save(out);out.with_suffix('.json').write_text(json.dumps(dict(source=snapshot,method='Original source bind geometry; UV0 per-pixel texture raster; simple diagnostic lighting; not a Unity/CK3 renderer',views=['front','side']),indent=2),encoding='utf8')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--family',action='append');a=ap.parse_args();idx=json.loads((ROOT/'cloth-source-index.json').read_text(encoding='utf8'))
 for record in idx['records']:
  if a.family and record['family']not in a.family:continue
  if record['status']!='parsed':continue
  source=next(x for x in record['selected_prefabs']if x['prefab']==record['basis_prefab']);path=ROOT/'source-previews'/(record['family']+'.png');preview(source['parsed_path'],path);print('SOURCE_PREVIEW',record['family'],flush=True);gc.collect()
if __name__=='__main__':main()

