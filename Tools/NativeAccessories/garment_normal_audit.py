import os
import sys,numpy as np
from pathlib import Path
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter');import build_ck3_mod as b
R=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));pd=b.parser_only(Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh")))
for f in [next((R/'v5').rglob('uma_0001_body_base.mesh')),R/'clothing-parts/uma_0001_body_clothed.mesh']:
 m=pd.read_meshfile(str(f)).find('object')[0].find('mesh');p=np.array(m.attrib['p']).reshape(-1,3);t=np.array(m.attrib['tri']).reshape(-1,3);n=np.array(m.attrib['n']).reshape(-1,3);cross=np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]);cross/=np.maximum(np.linalg.norm(cross,axis=1)[:,None],1e-12);dot=np.sum(cross*n[t].mean(1),axis=1);print(f.name,'normalsorientation',np.quantile(dot,[0,.01,.5,.99,1]),'negative',sum(dot<0))
