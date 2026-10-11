import os
import json,numpy as np
from pathlib import Path
from PIL import Image
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'));d=json.loads((R/'parsed/bdy1002_00/bdy1002_00.json').read_text());m=d['meshes'][0];mat=d['materials'][0];prop=next(p for p in mat['properties']if p['name']=='_MainTex');print('TEX_PUBLIC',prop);p=np.array([[v[a]for a in 'xyz']for v in m['vertices']]);uv=np.array([[v[a]for a in 'xy']for v in m['uvs'][0]['values']]);tex=np.array(Image.open(R/'parsed/bdy1002_00/resources'/prop['texture']).convert('RGB'));rgb=tex[np.minimum(((1-uv[:,1])*tex.shape[0]).astype(int),tex.shape[0]-1),np.minimum((uv[:,0]*tex.shape[1]).astype(int),tex.shape[1]-1)];region=(abs(p[:,0])>.3)&(p[:,1]>1.0);print('ARM_RGB',np.quantile(rgb[region],[0,.1,.5,.9,1],axis=0));bones={b['id']:b['name']for b in d['bones']};from collections import Counter;c=Counter()
for w in m['weights']:
 if region[w['vertex']]:c[bones[w['bone']]]+=w['weight']
print('ARM_WEIGHT_NAMES',c.most_common(15));print('COLORS',m.get('colors',[])[:2])
