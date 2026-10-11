import os
"""Verify undressing is identity and retained auxiliary joints do not alter animation."""
import hashlib,json,re,sys
from pathlib import Path
import numpy as np
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));GAME=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game'))));OLD=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'UMA-V6-1001'));MOD=R/'UMA-V7';sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only,clausewitz,one,values
from test_vanilla_body_animation_blender import mesh_info,globals_for,inverse_bind
pdx=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));path=Path('gfx/models/portraits/uma/0001/uma_0001_body_base.mesh');old=pdx.read_meshfile(str(OLD/path));new=pdx.read_meshfile(str(MOD/path));os,op,ob=mesh_info(old);ns,np_,nb=mesh_info(new)
assert all(np.array_equal(a,b)for pa,pb in zip(op,np_)for a,b in zip(pa,pb));assert np.array_equal(ob,nb[:len(os)])
for p,ix,w,e in np_:assert not np.any(ix[w>0]>=134)
none=pdx.read_meshfile(str((MOD/path).with_name('uma_0001_body_none.mesh'))).find('object')[0].find('mesh');base=new.find('object')[0].find('mesh');assert none.attrib==base.attrib and none.find('skin').attrib==base.find('skin').attrib
shape={}
for tag in ['b0','b1','b3','b4','s1','s2']:
    mesh=pdx.read_meshfile(str((MOD/path).with_name('uma_0001_body_'+tag+'.mesh'))).find('object')[0].find('mesh');assert mesh.attrib['tri']==base.attrib['tri']and len(mesh.attrib['p'])==len(base.attrib['p']);assert mesh.find('skin').attrib==base.find('skin').attrib;shape[tag]=np.array(mesh.attrib['p']).reshape(-1,3)
body1001=np.array(base.attrib['p']).reshape(-1,3);body1002=body1001+(shape['s1']-body1001)+(shape['b0']-body1001);assert np.isfinite(body1002).all()
asset=one(clausewitz((MOD/path.with_suffix('.asset')).read_text(encoding='utf-8-sig')),'pdxmesh');clips=values(asset,'animation');selected=[x for x in clips if re.search('idle|sit|court|throne',one(x,'id'),re.I)];selected=selected[:32];checks=[]
for clip in selected:
    file=((MOD/path).parent/one(clip,'type')).resolve()
    if not file.is_file():file=GAME/file.relative_to(MOD)
    tree=pdx.read_meshfile(str(file));info=tree.find('info');samples=tree.find('samples');frames=info.attrib['sa'][0];tests=[]
    for frame in sorted({0,frames//2,frames-1}):
        ow=globals_for(info,samples,frame,os);nw=globals_for(info,samples,frame,ns);error=float(np.max(abs(ow@ob-nw[:134]@nb[:134])));assert error<1e-9
        out=[]
        p,ix,w,e=np_[0]
        for actor,points in [('1001',body1001),('1002',body1002)]:
            mats=nw@nb;pos=np.c_[points,np.ones(len(points))];q=np.zeros_like(points)
            for slot in range(4):q+=np.einsum('nij,nj->ni',mats[np.maximum(ix[:,slot],0)],pos)[:,:3]*w[:,slot,None]
            assert np.isfinite(q).all();out.append({'actor':actor,'bounds_min_cm':q.min(0).tolist(),'bounds_max_cm':q.max(0).tolist()})
        tests.append({'frame':frame,'old_vs_new_core_skin_matrix_error':error,'naked_body':out})
    checks.append({'id':one(clip,'id'),'source_file':str(file),'source_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'tests':tests})
report={'passed':True,'body_vertices':len(body1001),'body_triangles':len(base.attrib['tri'])//3,'body_bones':len(ns),'old_core_bones_exact':len(os),'no_runtime_weight_uses_auxiliary_joints':True,'clothed_and_none_targets_exact_basis':True,'retained_auxiliary_joints_cannot_change_existing_skinning':True,'body1002_profile':'h1_s1_b0 = Basis + gaunt_1 + breast_shape_1','body1002_bounds_cm':[body1002.min(0).tolist(),body1002.max(0).tolist()],'tested_stock_clips':len(checks),'clips':checks,'game_runtime_verified':False};(R/'Reports/body-undress-animation.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('BODY_UNDRESS_AND_ANIMATION_PASSED',len(checks),'stock clips',len(body1001),'vertices',flush=True)
