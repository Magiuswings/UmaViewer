import os
import sys,json,numpy as np
from pathlib import Path
from collections import defaultdict
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'))
for f in ['bdy1001_00','bdy0001_00_01','bdy0003_00_01','bdy0004_00_00']:
 files=list((R/'parsed'/f).glob('bdy*.json'));d=json.loads(files[-1].read_text());m=d['meshes'][0];p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);tri=np.array([t for face in m['faces']for t in np.array(face['triangles']).reshape(-1,3)]);edge=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]);n,l=connected_components(coo_matrix((np.ones(len(edge)*2),(np.r_[edge[:,0],edge[:,1]],np.r_[edge[:,1],edge[:,0]])),shape=(len(p),len(p))).tocsr(),directed=False);sizes=[]
 for k in range(n):
  ids=np.flatnonzero(l==k);count=int(sum(l[tri[:,0]]==k))
  if count and p[ids,1].max()<.73:sizes.append((k,count,len(ids),round(p[ids,1].min(),3),round(p[ids,1].max(),3),round(p[ids,1].mean(),3)))
 print(f,'rawcomponents',n,'lower_groups',sizes[:60],flush=True)
