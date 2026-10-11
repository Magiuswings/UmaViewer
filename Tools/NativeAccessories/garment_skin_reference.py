import json,sys,copy,hashlib,os,tempfile
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));OUT=ROOT/'clothing-parts';CAN=Path(os.environ.get("UMA_V6_CANONICAL", "E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3"));REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"));OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
import build_ck3_mod as b
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pdx=b.parser_only(Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh")))
d=json.loads((ROOT/'parsed/body.json').read_text());m=d['meshes'][0];bones={x['id']:x for x in d['bones']};byname={x['name']:x for x in d['bones']};p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);uv=np.array([[v[k]for k in 'xy']for v in m['uvs'][0]['values']]);tri=np.array(m['faces'][0]['triangles']).reshape(-1,3)
tex=Image.open(ROOT/'parsed/resources/textures/tex_bdy1001_00_diff__3e2e906bee.png').convert('RGBA');pixels=np.asarray(tex);palette=np.array([252,228,204]);samples=np.concatenate([uv[tri],(uv[tri[:,0]]+uv[tri[:,1]])[:,None]/2,(uv[tri[:,1]]+uv[tri[:,2]])[:,None]/2,(uv[tri[:,2]]+uv[tri[:,0]])[:,None]/2,uv[tri].mean(1)[:,None]],axis=1);samples%=1
colors=pixels[np.minimum((1-samples[:,:,1])*tex.height,tex.height-1).astype(int),np.minimum(samples[:,:,0]*tex.width,tex.width-1).astype(int),:3].astype(float);votes=(np.linalg.norm(colors-palette,axis=-1)<=42).sum(1);skin=votes>=5
# Use source garment chains as affirmative cloth evidence even if a gold trim resembles skin.
sourceweights=defaultdict(list)
for w in m['weights']:sourceweights[w['vertex']].append((bones[w['bone']]['name'],w['weight']))
aux=np.array([sum(w for n,w in sourceweights[i]if n.startswith('Sp_'))for i in range(len(p))]);skin&=aux[tri].mean(1)<.15
# Head/neck tiny anatomical stub does not belong in accessory.
headmass=np.array([sum(w for n,w in sourceweights[i]if n=='Head')for i in range(len(p))]);skin|=(headmass[tri].mean(1)>.5)&(p[tri][:,:,1].mean(1)>1.30)
skin &= p[tri][:,:,1].mean(1)>.65
keep=~skin;faces=tri[keep];used=np.unique(faces);remap=np.full(len(p),-1,int);remap[used]=np.arange(len(used));faces=remap[faces]
C=np.array([[-1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]],float);N=json.loads((CAN/'native-bone-transforms.json').read_text());B={n:C@np.array(x['matrix']).reshape(4,4)@np.linalg.inv(C)for n,x in byname.items()};T={}
def transport(n):
 if n in T:return T[n]
 if n in N['posed']:T[n]=np.array(N['posed'][n])@np.linalg.inv(np.array(N['bind'][n]))
 else:
  pa=bones.get(byname[n]['parent']);T[n]=transport(pa['name'])if pa else np.diag([.991494545]*3+[1])
 return T[n]
for n in B:transport(n)
h=np.column_stack([p@C[:3,:3].T,np.ones(len(p))]);fit=np.zeros((len(p),3))
for i,ws in sourceweights.items():
 for n,w in ws:fit[i]+=(T[n]@h[i])[:3]*w
# Native fitted soles share source-body foot shear; apply same affine coefficients.
fitreport=json.loads((CAN/'rest-pose-fitting.json').read_text())
for corr in fitreport['foot_corrections']:
 side=corr['side'];ids=np.array([sum(w for n,w in sourceweights[i]if n.startswith(('Ankle','Toe'))and n.endswith(side))for i in range(len(p))]);slope=corr['heel_pitch_slope'];body=np.load(CAN/'fitted-body-profiles.npz')['h1_s0_b2'];source=np.load(CAN/'source-skin-profiles.npz')['h1_s0_b2'];# source actual fitted shifts only millimeters; keep source shoes ground minimum separately
 foot=ids>.95
 if foot.any():fit[foot,2]-=fit[foot,2].min()
np.savez_compressed(OUT/'source-native-skin-reference.npz',p=fit,tri=tri[skin]);print('SOURCE_EXPOSED_SKIN_REFERENCE',int(skin.sum()),flush=True)
