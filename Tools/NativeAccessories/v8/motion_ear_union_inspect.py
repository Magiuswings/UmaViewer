import json,sys,re
from pathlib import Path
import numpy as np
sys.path[:0]=['C:/Users/33775/Desktop/网页制作/UmaV7Scripts','E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter']
from build_ck3_mod import parser_only
ROOT=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/HeadSources/Export');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');idx=json.loads((ROOT/'head-export-index.json').read_text());counts=[]
for header in idx['heads']:
    need=set();weighted=set();sk=None
    for row in header['components']:
        if row['element']not in ['ear','headwear']or not row['present']:continue
        obj=P.read_meshfile(row['mesh_path']).find('object')[0];sk=obj.find('skeleton');names=[b.tag for b in sk];skin=obj.find('mesh').find('skin');ix=np.array(skin.get('ix'));w=np.array(skin.get('w'));active=set(ix[w>1e-8]);weighted|={names[i]for i in active};need|=active
    assert sk is not None
    need|={i for i,b in enumerate(sk)if re.search(r'(^|_)(ear)(_|$|[0-9])',b.tag,re.I)};stack=list(need)
    while stack:
        i=stack.pop();pa=sk[i].get('pa')
        if pa and pa[0]not in need:need.add(pa[0]);stack.append(pa[0])
    counts.append({'actor':header['actor'],'variant':header['variant'],'useful_kept_bones':len(need),'positive_bone_names':sorted(weighted),'kept_names':[sk[i].tag for i in sorted(need)]})
print(json.dumps(counts,indent=2));print('FULL_NAMESPACED_UNION_COUNT',sum(r['useful_kept_bones']for r in counts)+1)
