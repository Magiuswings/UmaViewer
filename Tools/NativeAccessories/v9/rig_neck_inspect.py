import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter')
from build_ck3_mod import parser_only
R=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')
H=json.loads((R/'Rigs/headcarrier.json').read_text());HW=np.array(H['world'])
for n in ['head_root','bn_h_head','uma_1002_bn_h_head','bn_h_neck_1','uma_1002_bn_h_neck_1','bn_h_l_clavicle','bn_h_eye_l_rotate','uma_1002_bn_h_eye_l_rotate']:
 print('POINT',n,HW[H['index_by_name'][n],:3,3].tolist())
for actor in ['1001','1002']:
 f=R/f'UMA-V8/gfx/models/portraits/uma/{actor}/uma_{actor}_neck_base.mesh';o=P.read_meshfile(str(f)).find('object')[0];sk=sorted(o.find('skeleton'),key=lambda n:n.get('ix')[0]);names=[n.tag for n in sk];m=o.find('mesh');p=np.array(m.get('p')).reshape(-1,3);ix=np.array(m.find('skin').get('ix')).reshape(-1,4);w=np.array(m.find('skin').get('w')).reshape(-1,4)
 inv=[]
 for b in sk:
  x=np.eye(4);x[:3]=np.array(b.get('tx')).reshape(4,3).T;inv.append(x)
 inv=np.array(inv)
 for n in ['head_root','bn_h_l_clavicle','bn_h_r_clavicle']:
  old=np.linalg.inv(inv[names.index(n)]);new=HW[H['index_by_name'][n]];print('BRIDGE_BIND',actor,n,old[:3,3].tolist(),new[:3,3].tolist(),'delta',float(abs(old-new).max()))
 for i in range(6):print('LOWER',actor,i,p[i].tolist(),[(names[j],float(a))for j,a in zip(ix[i],w[i])if a>0])
for kind in ['female_head','male_head']:
 f=Path('D:/steam/steamapps/common/Crusader Kings III/game/gfx/models/portraits')/kind/(kind+'.mesh');o=P.read_meshfile(str(f)).find('object')[0];sk=o.find('skeleton');print('VANILLA',kind,len(sk),[n.tag for n in sk if n.tag in ['head_root','bn_h_head','bn_h_l_clavicle','bn_h_r_clavicle']])
