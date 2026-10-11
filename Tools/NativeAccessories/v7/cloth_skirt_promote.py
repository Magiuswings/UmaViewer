import os
"""Adopt inspected 1002 D/Dlocal candidate only; preserve baseline mesh/blend; verify seven endpoints."""
import json,sys,shutil,hashlib
from pathlib import Path
import numpy as np
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));A=R/'ClothingParts/AB-bdy1002_00';case=sys.argv[1]if len(sys.argv)>1 else 'Dlocal';regfile=R/'ClothingParts/clothing-registration.json';reg=json.loads(regfile.read_text());fam=next(f for f in reg['families']if f['family']=='bdy1002_00');part=fam['parts']['clothes'];ab=json.loads((A/'ab-candidates.json').read_text());selected=next(c for c in ab['candidates']if c['case']==case);sys.path[:0]=[str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'),str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/NativeBody')];from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));files={'base':part['base_mesh'],**{Path(f).stem.rsplit('_',1)[-1]:f for f in part['shape_targets'].values()}};blend=Path(fam['directory'])/Path(fam['asset_path']).with_suffix('.blend').name;backup=A/'baseline'/blend.name
if blend.exists()and not backup.exists():shutil.copy2(blend,backup)
checks=[];baseweights=None;delta=None
for tag,target in files.items():
 candidate=Path(selected['files'][tag]);tree=pd.read_meshfile(str(candidate));baseline=pd.read_meshfile(ab['candidates'][0]['files'][tag]);nodes=[n for o in tree.find('object')for n in o.findall('mesh')];oldnodes=[n for o in baseline.find('object')for n in o.findall('mesh')];ws=[];ds=[]
 assert np.array_equal(inverse_bind(tree.find('object')[0].find('skeleton')),inverse_bind(baseline.find('object')[0].find('skeleton')))
 for n,b in zip(nodes,oldnodes):
  assert n.attrib['tri']==b.attrib['tri']and n.attrib['u0']==b.attrib['u0'];ws.append((n.find('skin').attrib['ix'],n.find('skin').attrib['w']));ds.append(np.array(n.attrib['p'])-np.array(b.attrib['p']));assert abs(np.array(n.find('skin').attrib['w']).reshape(-1,4).sum(1)-1).max()<2e-7
 if baseweights is None:baseweights=ws;delta=ds
 else:
  assert ws==baseweights
  for d0,d1 in zip(delta,ds):assert np.max(abs(d0-d1))<1e-5
 shutil.copy2(candidate,target);pd.read_meshfile(str(target));checks.append(dict(tag=tag,path=target,pdx_readback=True,topology_uv_bind_exact=True,same_weights=True,same_bs_delta=True,sha256=hashlib.sha256(Path(target).read_bytes()).hexdigest()))
fam['skirt_pose_refinement']=dict(case=case,native_source_region='MSkirt front/side-front and rear directional weights; waist preserved',candidate_manifest=str(A/'ab-candidates.json'),source_mask=selected['classification'],local_clearance=selected.get('correction_report'),pose_report=str(A/('ab-'+case+'-collision.json')),image=str(A/('ab-'+case+'-neutral-idle-throne.png')),body_modified=False,all_seven_endpoints_same_weights=True,all_seven_endpoints_same_delta=True,baseline_blend=str(backup),visual_game_verified=False);regfile.write_text(json.dumps(reg,indent=2),encoding='utf8');(A/'selected-delivery.json').write_text(json.dumps(dict(selected=case,production_written=True,editable_pending=True,baseline_blend=str(backup),checks=checks,refinement=fam['skirt_pose_refinement']),indent=2),encoding='utf8');print('SKIRT_PROMOTED',case,len(checks),str(blend),flush=True)
