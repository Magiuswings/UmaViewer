import os
import json,sys,numpy as np
from pathlib import Path
from collections import defaultdict
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'));from build_ck3_mod import parser_only
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text())
for fam in ['bdy1001_00','bdy1002_00','bdy0020_00_00']:
 f=next(x for x in reg['families']if x['family']==fam);data=json.loads(Path(f['source_snapshot']).read_text());rows=[]
 for category,part in f['parts'].items():
  tree=pd.read_meshfile(part['base_mesh']);nodes=[m for o in tree.find('object')for m in o.findall('mesh')];groups=defaultdict(list)
  for node,mapping in zip(nodes,part['source_maps']):
   p=np.array(node.attrib['p']).reshape(-1,3);original=data['meshes'][mapping['mesh']]['vertices']
   for i,sourceid in enumerate(mapping['source_vertex_ids']):groups[(mapping['mesh'],tuple(round(original[sourceid][k],5)for k in 'xyz'))].append(p[i])
  errors=[max(np.linalg.norm(np.array(v)-np.array(v).mean(0),axis=1))for v in groups.values()if len(v)>1]
  rows.append((category,max(errors)if errors else 0,sum(e>.1 for e in errors)))
 print('SEAM_PROOF',fam,rows)
