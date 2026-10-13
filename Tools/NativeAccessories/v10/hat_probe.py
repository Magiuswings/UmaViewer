import os,sys,json
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only
from head_assembly_math import rigdata
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V10');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');rows=json.loads((V/'Reports/clothing-registration.json').read_text())['families']
for family in ['bdy0008_08_00','bdy0008_09_00']:
 r=next(r for r in rows if r['family']==family);print('\nFAMILY',family);print('source paths',[(k,v)for k,v in r.items()if k in ['source_snapshot','source_points','source_partition','headwear_source']]);h=r['parts']['headwear'];print('hat source map sizes',[(len(x['source_vertex_ids']),len(x['source_triangle_indices']))for x in h['source_maps']]);s=json.loads(Path(r['source_snapshot']).read_text());print('bones',[(b['name'],b.get('matrix'))for b in s['bones']if b['name']in ['Head','Neck']or 'Hat'in b['name']]);print('mesh source',s['meshes'][0]['source']);o=P.read_meshfile(h['base_mesh']).find('object')[0];D=rigdata(o.find('skeleton'));print('bounds',[(np.array(m.get('p')).reshape(-1,3).min(0).tolist(),np.array(m.get('p')).reshape(-1,3).max(0).tolist())for m in o.findall('mesh')]);print('weighted',[(D['names'][i],round(float(np.array(m.find('skin').get('w')).reshape(-1,4)[np.array(m.find('skin').get('ix')).reshape(-1,4)==i].sum()),3))for m in o.findall('mesh')for i in np.unique(np.array(m.find('skin').get('ix')))if i>=0]);z=np.load(r['headwear_source']);print('npzkeys',z.files);print('partition',Path(r['source_partition']).read_text()[:2200]);print('weights sample',s['meshes'][0]['weights'][h['source_maps'][0]['source_vertex_ids'][0]])
