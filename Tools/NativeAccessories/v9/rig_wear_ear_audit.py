import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter')
from build_ck3_mod import parser_only
R=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/HeadSources');OUT=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9/RigRepair');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');registry=json.loads((R/'Reports/head-registration.json').read_text());result=[]
def components(tri):
 parent={int(v):int(v)for v in np.unique(tri)}
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for a,b,c in tri:parent[find(int(b))]=find(int(a));parent[find(int(c))]=find(int(a))
 groups={}
 for i,t in enumerate(tri):groups.setdefault(find(int(t[0])),[]).append(i)
 return list(groups.values())
for row in registry:
 if row['element']!='headwear':continue
 actor=row['actor'];variant=row['variant'];o=P.read_meshfile(row['mesh']).find('object')[0];names=[n.tag for n in sorted(o.find('skeleton'),key=lambda n:n.get('ix')[0])];m=o.find('mesh');p=np.array(m.get('p')).reshape(-1,3);tri=np.array(m.get('tri')).reshape(-1,3);ix=np.array(m.find('skin').get('ix')).reshape(-1,4);w=np.array(m.find('skin').get('w')).reshape(-1,4);earbones=[i for i,n in enumerate(names)if'Ear'in n.split('__')[-1]];earweight=np.sum(w*np.isin(ix,earbones),axis=1);cs=[]
 for ci,ids in enumerate(components(tri)):
  vertices=np.unique(tri[ids]);positive=earweight[vertices]>1e-8;bones=sorted({names[j]for v in vertices for j,a in zip(ix[v],w[v])if a>1e-8});cs.append({'component':ci,'triangle_ids':ids,'vertex_ids':vertices.tolist(),'vertices':len(vertices),'triangles':len(ids),'bounds_attachment_local_cm':[p[vertices].min(0).tolist(),p[vertices].max(0).tolist()],'positive_ear_vertex_count':int(positive.sum()),'maximum_ear_weight':float(earweight[vertices].max()),'positive_weight_bones':bones})
 source=json.loads((V7/f'parsed/chr{actor}_{variant}/head.json').read_text());rawnames={b['id']:b['name']for b in source['bones']};meshstats=[]
 for mesh in source['meshes']:
  ew=[a for a in mesh['weights']if a['weight']>1e-8 and'Ear'in rawnames[a['bone']]];meshstats.append({'source_mesh':mesh['name'],'vertices':len(mesh['vertices']),'positive_ear_weights':len(ew),'ear_weighted_vertices':sorted({a['vertex']for a in ew})})
 delivery=json.loads((V7/f'Export/chr{actor}_{variant}/head-component-delivery.json').read_text());original=next(r for r in delivery['components']if r['element']=='headwear');out={'actor':actor,'variant':variant,'source_mesh':row['mesh'],'source_vertex_mapping':original['source_vertex_mapping'],'total_vertices':len(p),'total_triangles':len(tri),'ear_positive_vertices':int((earweight>1e-8).sum()),'components':cs,'all_original_renderer_ear_weight_stats':meshstats};result.append(out);print('WEAR_EAR_AUDIT',actor,variant,len(p),int((earweight>1e-8).sum()),[(c['vertices'],c['positive_ear_vertex_count'],c['bounds_attachment_local_cm'])for c in cs],flush=True)
(OUT/'headwear-ear-original-positive-weight-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
