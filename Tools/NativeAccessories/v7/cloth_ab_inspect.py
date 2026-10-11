import os
import json,numpy as np
from pathlib import Path
from collections import defaultdict
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))))
d=json.loads((R/'ClothingSources/parsed/bdy1002_00/bdy1002_00.json').read_text()); a=np.load(R/'ClothingSources/partitions/bdy1002_00/source-parts.npz'); b={x['id']:x for x in d['bones']}
for bid,x in b.items():
 if 'skirt' in x['name'].lower(): print('BONE',x['name'],np.round(np.array(x['matrix']).reshape(4,4)[:3,3],4).tolist())
for mi,m in enumerate(d['meshes']):
 p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]); t=a[f'm{mi}_tri']; part=a[f'm{mi}_part']; selected=t[part==1]; e=np.concatenate([selected[:,[0,1]],selected[:,[1,2]],selected[:,[2,0]]]); n,l=connected_components(coo_matrix((np.ones(len(e)*2),(np.r_[e[:,0],e[:,1]],np.r_[e[:,1],e[:,0]])),shape=(len(p),len(p))).tocsr(),directed=False)
 mass=defaultdict(list)
 for w in m['weights']:
  if 'skirt' in b[w['bone']]['name'].lower(): mass[b[w['bone']]['name']].append((w['vertex'],w['weight']))
 print('MESH',mi,m['name'])
 for name,rows in mass.items():
  ids=np.array([i for i,w in rows]); ws=np.array([w for i,w in rows]); print('INFLUENCE',name,len(ids),'bounds',np.round(p[ids].min(0),3).tolist(),np.round(p[ids].max(0),3).tolist(),'center',np.round(np.average(p[ids],axis=0,weights=ws),3).tolist(),'components',np.unique(l[ids]).tolist())
 for c in np.unique(l[selected[:,0]]):
  ids=np.unique(selected[l[selected[:,0]]==c]);
  if p[ids,1].min()<.85: print('COMPONENT',int(c),len(ids),'tri',int(sum(l[selected[:,0]]==c)),np.round(p[ids].min(0),3).tolist(),np.round(p[ids].max(0),3).tolist())
