import os
"""Whole native connected components versus naked-head 80; no topology edits."""
import json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'HeadSources'));index=json.loads((ROOT/'head-parts-index.json').read_text(encoding='utf8'));report=[]
def components(data,mesh):
    pos=np.array([[v[k]for k in 'xyz']for v in mesh['vertices']]);head=np.array(next(b for b in data['bones']if b['name']=='Head')['matrix']).reshape(4,4)[:3,3];pos-=head
    tri=np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in mesh['faces']]);uf=list(range(len(pos)))
    def find(i):
        while uf[i]!=i:uf[i]=uf[uf[i]];i=uf[i]
        return i
    for row in tri:
        for v in row[1:]:uf[find(int(v))]=find(int(row[0]))
    grouped={}
    for i,row in enumerate(tri):grouped.setdefault(find(int(row[0])),[]).append(i)
    bonebyid={b['id']:b for b in data['bones']};byv={i:[]for i in range(len(pos))}
    for w in mesh['weights']:byv[w['vertex']].append((bonebyid[w['bone']]['name'],w['weight']))
    uv=np.array([[v['x'],v['y']]for v in mesh['uvs'][0]['values']])
    mats=[]
    for f in mesh['faces']:mats.extend([data['materials'][f['material']]['name']]*(len(f['triangles'])//3))
    result=[]
    for n,(root,ids)in enumerate(grouped.items()):
        vi=np.unique(tri[ids]);p=pos[vi];geometry=sorted(tuple(tuple(v)for v in sorted(np.round(pos[row],6).tolist()))for row in tri[ids]);fingerprint=hashlib.sha256(repr(geometry).encode()).hexdigest();boneweights={n for i in vi for n,w in byv[int(i)]};ear=any('Ear'in n for n in boneweights)
        result.append({'component_id':n,'vertices':len(vi),'triangles':len(ids),'source_vertex_ids':vi.tolist(),'source_triangle_ids':ids,'native_weight_bones':sorted(boneweights),'materials':sorted({mats[i]for i in ids}),'bounds_head_relative_min':p.min(0).tolist(),'bounds_head_relative_max':p.max(0).tolist(),'uv_min':uv[vi].min(0).tolist(),'uv_max':uv[vi].max(0).tolist(),'geometry_fingerprint':fingerprint,'native_ear_weighted':ear})
    return result
for char in ['1001','1002']:
    baseline=next(r for r in index['records']if r['kind']=='head'and r['character_id']==char and r['variant']=='80');base=json.loads(Path(baseline['parsed_json']).read_text(encoding='utf8'));bm=next(m for m in base['meshes']if m['name']=='M_Hair');bc=components(base,bm);fingerprints={c['geometry_fingerprint']:c for c in bc}
    for row in index['records']:
        if row['kind']!='head'or row['character_id']!=char:continue
        data=json.loads(Path(row['parsed_json']).read_text(encoding='utf8'));mesh=next(m for m in data['meshes']if m['name']=='M_Hair');cs=components(data,mesh);present=set();new=[];hair=[];ear=[]
        for c in cs:
            matched=fingerprints.get(c['geometry_fingerprint']);c['baseline_80_component']=matched['component_id']if matched else None
            if matched:present.add(matched['component_id']);c['classification']='unchanged_baseline_ear'if c['native_ear_weighted']else'unchanged_baseline_hair';(ear if c['native_ear_weighted']else hair).extend(c['source_triangle_ids'])
            else:c['classification']='variant_changed_or_added_ear_component'if c['native_ear_weighted']else'variant_added_or_modified_headwear_or_hair_component';(ear if c['native_ear_weighted']else new).extend(c['source_triangle_ids'])
        rec={'character_id':char,'variant':row['variant'],'source_json':row['parsed_json'],'source_mesh':'M_Hair','components':cs,'unmodified_baseline_hair_triangle_ids':hair,'ear_triangle_ids':ear,'headwear_or_modified_hair_triangle_ids':new,'baseline_80_components_absent':[c['component_id']for c in bc if c['component_id']not in present],'component_partition_complete':len(hair)+len(ear)+len(new)==sum(c['triangles']for c in cs),'geometry_only_matching_precision_m':1e-6,'export_strategy':'For newly changed/added components keep original native weights/material/whole component. If baseline hair components are absent, switch that variant complete hair instead of stacking headwear over missing/changed base. Ear components are identified by native Ear weights; keep their Head-weighted base as one component.'}
        report.append(rec);print('HEADGEAR_PARTITION',char,row['variant'],'components',len(cs),'basehairtri',len(hair),'eartri',len(ear),'newtri',len(new),'absentbase',len(rec['baseline_80_components_absent']),flush=True)
(ROOT/'headwear-partitions.json').write_text(json.dumps({'partitions':report,'no_triangles_discarded':True,'semantics_limit':'Variant geometry additions are headwear candidates; original source names/bones/materials are authoritative. Changes in hairstyle are not falsely labelled wearable objects.'},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
index['headwear_partition_json']=str(ROOT/'headwear-partitions.json');index['full_native_rig_contract']='Keep all source bones plus unweighted transforms; map supported semantic nodes to stock carrier only if source subtrees remain exact relative to that mapped node. All unmatched chains must retain source local bind transform and original name or namespaced source ID, not be collapsed to Head. Head/neck offset applies at uma_head_base only; no face mesh rebake needed.'
(ROOT/'head-parts-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
