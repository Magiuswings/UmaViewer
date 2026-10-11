import os
import json,sys
from pathlib import Path
import numpy as np
from collections import Counter
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))));OLD=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001'))));OUT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'HeadSources'));report=json.loads((OUT/'head-neck-interface.json').read_text(encoding='utf8'));body=P.read_meshfile(str(OLD/'UMA-V6-1001/gfx/models/portraits/uma/0001/uma_0001_body_base.mesh')).find('object')[0].find('mesh');bp=np.array(body.get('p')).reshape(-1,3);top=bp[(bp[:,1]>bp[:,1].max()-.5)&(np.abs(bp[:,0])<8)];raw=json.loads((OLD/'parsed/head.json').read_text(encoding='utf8'));mf=next(m for m in raw['meshes']if m['name']=='M_Face');v=np.array([[x[k]for k in 'xyz']for x in mf['vertices']]);hsrc=np.array(next(b for b in raw['bones']if b['name']=='Head')['matrix']).reshape(4,4)[:3,3];anchor=np.array([0.,26.87430954,4.59109068]);C=np.diag([-97.6403989,97.6403989,-97.6403989]);engine=(v-hsrc)@C.T+anchor;T=np.array(report['body_thoracic_bind']);root=np.eye(4);root[:3,3]=report['recommended_new_head_root_bind_position_cm'];attach=T@np.linalg.inv(root);points=(attach[:3,:3]@engine.T).T+attach[:3,3];bottom=points[np.array(report['face_bottom_interface']['bottom_source_vertex_ids'])];checks={'v6_body_top_neck_vertices':len(top),'v6_body_top_neck_aabb_min':top.min(0).tolist(),'v6_body_top_neck_aabb_max':top.max(0).tolist(),'new_face_min_y_minus_body_max_y_cm':float(points[:,1].min()-bp[:,1].max()),'nearest_face_bottom_to_body_top_vertex_cm':float(np.linalg.norm(bottom[:,None,:]-top[None,:,:],axis=2).min()),'interface_note':'Scalar bounds and nearest vertices are not matching seam rings. Joint correction fixes neck anchor; it does not imply watertight surfaces. Current V6 body-neck topology is compared, not the forthcoming reconstructed V7 body.'};report['face_bottom_interface'].update(checks)
# Actual welded MFace skin boundary, excluding separate iris faces. The lowest
# point of MFace is chin, so it must not be presented as a neck seam.
tri=np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in mf['faces']if f['category']=='face']);lookup={};weld=[];rep=[]
for i,p in enumerate(v):
    key=tuple(np.round(p,6))
    if key not in lookup:lookup[key]=len(rep);rep.append(i)
    weld.append(lookup[key])
weld=np.array(weld);wt=weld[tri];edges=Counter(tuple(sorted((int(row[a]),int(row[b]))))for row in wt for a,b in [(0,1),(1,2),(2,0)]);boundary=[e for e,n in edges.items()if n==1];uf=list(range(len(rep)))
def find(i):
    while uf[i]!=i:uf[i]=uf[uf[i]];i=uf[i]
    return i
for a,b in boundary:uf[find(b)]=find(a)
groups={}
for a,b in boundary:groups.setdefault(find(a),set()).update([a,b])
rings=[]
for ids in groups.values():
    src=np.array([rep[i]for i in sorted(ids)]);world=points[src];rings.append({'source_vertex_ids':src.tolist(),'points':len(src),'world_center':world.mean(0).tolist(),'world_bounds_min':world.min(0).tolist(),'world_bounds_max':world.max(0).tolist(),'nearest_to_body_top_vertex_cm':float(np.linalg.norm(world[:,None]-top[None],axis=2).min())})
rings.sort(key=lambda r:r['world_center'][1]);report['face_topological_boundary']={'weld_rounding_m':1e-6,'boundary_edges':len(boundary),'groups_sorted_by_mean_y':rings,'lowest_scalar_point_is_chin_not_interface':True,'mesh_minimum_bounds_are_not_seam_position':True}
(OUT/'head-neck-interface.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'bounds':checks,'actual_face_boundaries':[{k:v for k,v in r.items()if k!='source_vertex_ids'}for r in rings]},indent=2))
