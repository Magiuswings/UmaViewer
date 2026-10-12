import sys,json,numpy as np
from pathlib import Path
R=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7');sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeBody'];from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
P=parser_only(Path('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))
def prune(n):
 native=n.removeprefix('uma_src_');return n.startswith('bn_h_ear')or native.startswith('Ear')or native.startswith('Sp_He_Ear')or any(s in native for s in ['Tail','tail'])
for file in [R/'Rigs/body.mesh',R/'Rigs/head_1001.mesh',R/'Rigs/head_1002.mesh',R/'UMA-V7/gfx/models/portraits/uma/0001/uma_0001_head_female.mesh']:
 t=P.read_meshfile(str(file));sk=t.find('object')[0].find('skeleton');names=[n.tag for n in sk];b=inverse_bind(sk);world=np.linalg.inv(b);removed=[n for n in names if prune(n)or n=='uma_head_base'];core=[n for n in names if n.startswith('bn_h_')and not prune(n)];print(file.name,'bones',len(sk),'prune',len(removed),'retained',len(sk)-len(removed),'core',len(core),'commonclav',[n for n in core if'clav'in n],flush=True);print('REMOVE',removed);print('ROOT',world[names.index('head_root')].tolist()if'head_root'in names else None)
reg=json.loads((R/'Reports/head-registration.json').read_text());
for actor in ['1001','1002']:
 rows=[r for r in reg if str(r['actor'])==actor and r.get('shared_pose')=='head'and not r.get('independent_native_pose')];weighted=set()
 for r in rows:
  tree=P.read_meshfile(r['mesh'])
  for obj in tree.find('object'):
   names=[b.tag for b in obj.find('skeleton')]
   for m in obj.findall('mesh'):
    skin=m.find('skin')
    if skin is not None:
     ix=np.array(skin.attrib['ix']);w=np.array(skin.attrib['w']);weighted.update(names[i]for i in set(ix[w>0]))
 print('ACTOR',actor,len(rows),'weighted',len(weighted),'removed_weighted',[n for n in weighted if prune(n)],'renamed_weighted_core',len([n for n in weighted if n.startswith('bn_h_')and not prune(n)and'clav'not in n]))
