import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
import numpy as np
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,readlocals,compose,shared_pose,deform
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9');M=V/'UMA-V9/gfx/models/portraits/uma';P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')
report=json.loads((V/'Reports/clothing-registration.json').read_text())
print('top',report.keys())
for r in report['families']:
 if r['family'].startswith('bdy1001_00'):
  print('family',r['family'],r.keys())
  for k,v in r['parts'].items(): print(k, v.get('base_mesh'),v.get('vertices'))
  print('sourcekeys',[(k,str(v)[:300])for k,v in r.items()if 'source'in k])
body=P.read_meshfile(str(M/'0001/uma_0001_body_base.mesh')).find('object')[0];B=rigdata(body.find('skeleton'));a=M/'animation/body/uma_body_native_idle.anim';W=compose(B,readlocals(P,a,0))
print('body frame',P.read_meshfile(str(a)).find('info').attrib)
for n in B['names']:
 if any(s in n for s in ('hip','knee','ankle','ft','offset','root')):print(n,B['parents'][B['names'].index(n)],W[B['names'].index(n),:3,3].round(5).tolist())
for r in report['families']:
 if r['family'].startswith('bdy1001_00'):
  o=P.read_meshfile(r['parts']['shoes']['base_mesh']).find('object')[0];S=rigdata(o.find('skeleton'));v=np.vstack([deform(n,S,shared_pose(S,B,W))for n in o.findall('mesh')]);print('shoe aabb',v.min(0).tolist(),v.max(0).tolist()); print('low',v[np.argsort(v[:,1])[:12]].round(4).tolist())
  side=v[v[:,0]<0];z=side[:,2]; print('sagittal_bins',[(round(float(a),2),round(float(b),2),int(sum((z>=a)&(z<b))),round(float(side[(z>=a)&(z<b),1].min()),5) if sum((z>=a)&(z<b))else None)for a,b in zip(np.linspace(z.min(),z.max()+.01,16)[:-1],np.linspace(z.min(),z.max()+.01,16)[1:])]);print('bind_aabb',np.vstack([np.array(n.get('p')).reshape(-1,3)for n in o.findall('mesh')]).min(0).tolist());print('sourcepoints',Path(r['source_points']).read_text()[:900]);print('snapshot',Path(r['source_snapshot']).read_text()[:900])
