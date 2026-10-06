"""Lock apparel partitions for an exact-topology costume family, without mesh edits."""
import copy
import json
import os
from pathlib import Path
from morphs import topology_mapping
from body_profiles import body_profile, profiles_compatible, select_body_bases

def normalize_manifest(source,output,index):
    source=Path(source);output=Path(output)
    output.mkdir(parents=True,exist_ok=True);(output/'snapshots').mkdir(exist_ok=True)
    manifest=json.loads(source.read_text(encoding='utf8'))
    original=copy.deepcopy(manifest)
    jobs={j['name']:j for j in manifest['jobs']}
    data={j['name']:json.loads((source.parent/j['snapshot']).read_text(encoding='utf8')) for j in manifest['jobs']}
    records={r['id']:r for r in index['records']}
    changes=[];blocked=[]
    for group in index['compatible_groups']:
        base=records[group['base']]
        if base['category']!='whole_mesh':continue
        base_profile=body_profile(jobs[base['job']]['source'],jobs[base['job']]['kind'])
        if not base_profile:continue
        bm=data[base['job']]['meshes'][base['mesh_index']]
        labels={tuple(sorted(f['triangles'][i:i+3])):f['category'] for f in bm['faces'] for i in range(0,len(f['triangles']),3)}
        for tid in group['targets']:
            target=records[tid]
            target_profile=body_profile(jobs[target['job']]['source'],jobs[target['job']]['kind'])
            if not profiles_compatible(base_profile,target_profile):
                blocked.append(dict(base_job=base['job'],target_job=target['job'],base_profile=base_profile,target_profile=target_profile,reason='body_profile_mismatch; keep target original skin/clothing classification'))
                continue
            tm=data[target['job']]['meshes'][target['mesh_index']]
            mapping,reason=topology_mapping(bm,tm)
            if mapping is None:raise ValueError('Indexed family no longer matches: '+reason)
            inverse={v:i for i,v in enumerate(mapping)}
            untouched={k:copy.deepcopy(v) for k,v in tm.items() if k!='faces'}
            sections={}
            for f in tm['faces']:
                for i in range(0,len(f['triangles']),3):
                    tri=f['triangles'][i:i+3]
                    category=labels[tuple(sorted(inverse[v] for v in tri))]
                    if category!=f['category']:
                        changes.append(dict(base_job=base['job'],target_job=target['job'],renderer=tm['name'],
                                            source_triangle=tri,old_category=f['category'],new_category=category,
                                            reason='Same confirmed source costume family, exact UV/connectivity; use base partition for geometry morphs'))
                    key=(f['material'],category)
                    if key not in sections:sections[key]=dict(f,category=category,triangles=[])
                    sections[key]['triangles'].extend(tri)
            tm['faces']=list(sections.values())
            assert {k:v for k,v in tm.items() if k!='faces'}==untouched
    for job in manifest['jobs']:
        d=data[job['name']]
        job['body_profile']=body_profile(job['source'],job['kind'])
        job['categories']=sorted({f['category'] for m in d['meshes'] for f in m['faces'] if f['triangles']})
        job['category_triangles']={c:sum(len(f['triangles'])//3 for m in d['meshes'] for f in m['faces'] if f['category']==c) for c in job['categories']}
        (output/job['snapshot']).write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    for file in (source.parent/manifest['resources']).rglob('*'):
        if file.is_file():
            dst=output/manifest['resources']/file.relative_to(source.parent/manifest['resources'])
            dst.parent.mkdir(parents=True,exist_ok=True)
            if not dst.exists():os.link(file,dst)
    if manifest.get('body_bases'):
        manifest['body_bases']=select_body_bases(manifest['jobs'],lambda job:data[job['name']],manifest['body_bases'][0].get('selection','auto'))
    manifest['partition_policy']='Reuse partitions only within the same complete generic body profile including bust; preserve other bust profiles and all source geometry'
    manifest['source_manifest']=str(source.resolve())
    manifest['partition_changes']=changes
    manifest['blocked_partition_transfers']=blocked
    path=output/'manifest.json';path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    (output.parent/'partition-changes.json').write_text(json.dumps(dict(changed_triangles=len(changes),changes=changes,
                blocked_transfers=blocked,source=str(source.resolve()),policy=manifest['partition_policy'],source_preserved=True),ensure_ascii=False,indent=2),encoding='utf8')
    return path
