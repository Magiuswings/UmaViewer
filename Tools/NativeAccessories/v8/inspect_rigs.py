import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import json,sys,re
from pathlib import Path
import numpy as np
V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7');REPO=Path('E:/UmaViewer-Workspace/UmaViewer-source');sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import parser_only
P=parser_only(Path('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'));rows=json.loads((V7/'Reports/head-registration.json').read_text());answer=[]
for actor in ['1001','1002']:
    weighted=set();ancestor=set();sample=None
    for row in rows:
        if row['actor']!=actor or row['shared_pose']!='head':continue
        tree=P.read_meshfile(row['mesh'])
        for obj in tree.find('object'):
            sk=obj.find('skeleton');sample=sk
            for mesh in obj.findall('mesh'):
                skin=mesh.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);w=np.array(skin.get('w')).reshape(-1,4)
                for i in set(ix[w>1e-8]):
                    weighted.add(sk[i].tag)
                    while i is not None:
                        ancestor.add(sk[i].tag);pa=sk[i].get('pa');i=pa[0]if pa else None
    answer.append({'actor':actor,'weighted':sorted(weighted),'ancestor':sorted(ancestor),'count':len(weighted),'ancestor_count':len(ancestor)})
print(json.dumps(answer,indent=2));N=json.loads(Path('E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3/native-bone-transforms.json').read_text());print('BODY N',[(k,np.array(N['posed'][k])[:3,3].tolist())for k in ['Hip','Spine','Neck','Head']])
