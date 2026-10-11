import os
import sys,json,numpy as np,copy
from pathlib import Path
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter');import build_ck3_mod as b
R=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001")) / 'clothing-parts';pd=b.parser_only(Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh")));template=pd.read_meshfile(str(R/'uma_1001_clothing_00.mesh'));a=np.load(R/'garment-prepared.npz');order=np.array(list(dict.fromkeys(np.sort(a['faces'],axis=1).ravel().tolist())));m=template.find('object')[0].find('mesh');uv=np.column_stack([a['uv'][order,0],1-a['uv'][order,1]]);inv=np.empty(len(order),int);inv[order]=np.arange(len(order));tri=np.roll(inv[a['faces']],1,axis=1);m.attrib['u0']=uv.ravel().tolist();m.attrib['tri']=tri.ravel().tolist()
for tag in ['base','b0','b1','b3','b4','s1','s2']:
 tree=copy.deepcopy(template);m=tree.find('object')[0].find('mesh');p=a['p'if tag=='base'else tag][order][:,[0,2,1]]*100;n=np.zeros_like(p);fn=np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]])
 for slot in range(3):np.add.at(n,tri[:,slot],fn)
 n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12);t=np.zeros_like(p);uvd1=uv[tri[:,1]]-uv[tri[:,0]];uvd2=uv[tri[:,2]]-uv[tri[:,0]];den=uvd1[:,0]*uvd2[:,1]-uvd2[:,0]*uvd1[:,1];den=np.where(abs(den)<1e-12,1,den);tf=((p[tri[:,1]]-p[tri[:,0]])*uvd2[:,1,None]-(p[tri[:,2]]-p[tri[:,0]])*uvd1[:,1,None])/den[:,None]
 for slot in range(3):np.add.at(t,tri[:,slot],tf)
 t-=n*np.sum(t*n,axis=1)[:,None];t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-12);m.attrib['p']=p.ravel().tolist();m.attrib['n']=n.ravel().tolist();m.attrib['ta']=np.column_stack([t,np.ones(len(p))]).ravel().tolist();sk=m.find('skin');sk.attrib['ix']=a['ix'][order].ravel().tolist();sk.attrib['w']=a['w'][order].ravel().tolist();m.find('aabb').attrib.update(min=p.min(0).tolist(),max=p.max(0).tolist());center=(p.min(0)+p.max(0))/2;m.attrib['boundingsphere']=center.tolist()+[float(np.linalg.norm(p-center,axis=1).max())];file=R/('uma_1001_clothing_00'+(''if tag=='base'else '_'+tag)+'.mesh');pd.write_meshfile(str(file),tree);pd.read_meshfile(str(file));print('UPDATED_PDX',tag,flush=True)
(R/'clothing-pdx-vertex-order.json').write_text(json.dumps(dict(export_to_prepared=order.tolist(),method='Recovered PDX exporter source index insertion order verified by exact UV0 match'),indent=2))
