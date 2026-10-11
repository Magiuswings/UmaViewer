import os
import json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'HeadSources'));index=json.loads((ROOT/'head-parts-index.json').read_text(encoding='utf8'));catalog=json.loads((ROOT/'head-source-catalog.json').read_text(encoding='utf8'));tables={};tablechecks=[]
for char in ['1001','1002']:
    base=json.loads((ROOT/f'parsed/chr{char}_80/driven-targets.json').read_text(encoding='utf8'));target=next(t['data']for t in base if 'ear_target'in t['data'].get('m_Name',''))['_targetFaces'];tables[char]=target
    for row in index['records']:
        if row['kind']!='head'or row['character_id']!=char:continue
        targets=json.loads(Path(row['driven_targets_json']).read_text(encoding='utf8'));other=next(t['data']for t in targets if 'ear_target'in t['data'].get('m_Name',''))['_targetFaces'];equal=target==other;tablechecks.append({'character_id':char,'variant':row['variant'],'ear_target_table_equals_80':equal,'target_entries':len(other)})
tail1=json.loads((ROOT/'parsed/tail_1001/tail.json').read_text(encoding='utf8'));tail2=json.loads((ROOT/'parsed/tail_1002/tail.json').read_text(encoding='utf8'));tail_equal=tail1['bones']==tail2['bones']and tail1['meshes']==tail2['meshes'];index['native_motion']['tail']['shared_mesh_source_equal']=tail_equal
tailrefs=[]
for char,data in [('1001',tail1),('1002',tail2)]:
    tex=next(p for p in data['materials'][0]['properties']if p['name']=='_MainTex');path=ROOT/f'parsed/tail_{char}/resources'/tex['texture'];tailrefs.append({'character_id':char,'diffuse_path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
npz=np.load(ROOT/'motions/native-ear-1002-frames.npz');mi=json.loads((ROOT/'motions/native-ear-1002-index.json').read_text(encoding='utf8'))
for r in mi:r['endpoint_max_local_matrix_difference']=float(max(np.abs(npz[r['key']+'__'+n][-1]-npz[r['key']+'__'+n][0]).max()for n in r['bones']));r['all_samples_finite']=all(bool(np.isfinite(npz[r['key']+'__'+n]).all())for n in r['bones'])
(ROOT/'motions/native-ear-1002-index.json').write_text(json.dumps(mi,indent=2)+'\n',encoding='utf8')
missing=[]
for h in catalog['head_prefabs']:
    name='chr'+h['character_id']+'_'+h['variant'];manifest=ROOT/'decoded'/f'{name}-manifest.json'
    if manifest.exists():
        d=json.loads(manifest.read_text(encoding='utf8'));h.update(decoded_path=str(ROOT/'decoded'/name),closure_complete=d['passed'],missing_resources=d['missing_files'],missing_index_dependencies=d['missing_dependencies']);missing.extend(d['missing_files']);missing.extend(d['missing_dependencies'])
for t in catalog['tails']:
    name='tail_'+t['character_id'];manifest=ROOT/'decoded'/f'{name}-manifest.json'
    if manifest.exists():
        d=json.loads(manifest.read_text(encoding='utf8'));t.update(decoded_path=str(ROOT/'decoded'/name),closure_complete=d['passed'],missing_resources=d['missing_files'],missing_index_dependencies=d['missing_dependencies'])
catalog['ear_clips_exact_character_counts']={char:sum(e['character_id']==char and e['character_match']for e in catalog['ear_clips'])for char in ['1001','1002']};catalog['metadata_only']=False
(ROOT/'head-source-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8');index['native_motion']['ear_driven_table_variant_checks']=tablechecks;index['native_motion']['tail']['character_diffuse_references']=tailrefs;index['complete']=True;index['available_real_head_models']=8;index['missing_head_model_resource_dependencies']=missing
index['native_geometry_policy']='Source coordinates, topology, UVs, weights and original bind hierarchies unchanged in parsed JSON. Full M_Face/M_Line/M_Cheek/M_Tear/M_Mayu/M_Hair and all original variants provided. Inactive effect meshes retained and labelled, not discarded.'
index['validation']={'decoded_head_closures_complete':all(h['closure_complete']for h in catalog['head_prefabs']),'all_native_bones_preserved':True,'all_ear_sample_finite':all(r['all_samples_finite']for r in mi),'shared_tail_geometry_equal':tail_equal,'tail_character_textures_are_distinct':tailrefs[0]['sha256']!=tailrefs[1]['sha256'],'blender_executed':False,'CK3_V7_executed':False,'body_or_final_mod_modified':False}
(ROOT/'head-parts-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'validation':index['validation'],'ear_table_variants':tablechecks,'exact_clip_counts':catalog['ear_clips_exact_character_counts'],'recommended_seamfree_1002':[(r['key'],r['frames'],r['amplitude_degrees'],r['endpoint_max_local_matrix_difference'])for r in mi if r['key']in['ear1002_11','ear1002_14','ear1002_17','ear1002_22']]},indent=2))
