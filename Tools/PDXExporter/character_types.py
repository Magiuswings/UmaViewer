"""Read actual character parameters and validate reusable generic body types."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
from morphs import topology_mapping
from body_profiles import body_profile

def read_database(path,character_ids):
    path=Path(path).resolve()
    if not path.is_file():raise FileNotFoundError(path)
    connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        columns={r['name'] for r in connection.execute('PRAGMA table_info(chara_data)')}
        required={'id','bust','skin','height','shape'}
        if not required<=columns:raise ValueError('Missing chara_data fields: '+str(sorted(required-columns)))
        fields=[f for f in ('id','bust','skin','height','shape','scale','socks','sex') if f in columns]
        all_rows=[dict(r) for r in connection.execute('SELECT '+','.join(fields)+' FROM chara_data ORDER BY id')]
        wanted={int(i) for i in character_ids if str(i).isdigit()}
        rows=[r for r in all_rows if r['id'] in wanted]
        missing=wanted-{r['id'] for r in rows}
        if missing:raise ValueError('Characters absent from database: '+str(sorted(missing)))
        distribution=Counter((r['height'],r['shape'],r['bust']) for r in all_rows)
    finally:connection.close()
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return dict(database=str(path),database_sha256=digest.hexdigest(),table='chara_data',
                characters=rows,total_characters=len(all_rows),
                profile_distribution=[dict(height=k[0],shape=k[1],bust=k[2],characters=n) for k,n in sorted(distribution.items())])

def type_id(profile):
    return 'height_'+str(profile['height'])+'__shape_'+str(profile['shape'])+'__bust_'+str(profile['bust'])

def resolve_characters(manifest_path,metadata,costume='0004_00_00'):
    path=Path(manifest_path);manifest=json.loads(path.read_text(encoding='utf8'))
    fields=costume.split('_')
    if len(fields)!=3 or not all(f.isdigit() for f in fields):raise ValueError('Base costume must be costume_subtype_setting, e.g. 0004_00_00')
    bodies=[j for j in manifest['jobs'] if j['kind']=='body' and body_profile(j['source'])]
    result=[]
    for row in metadata['characters']:
        expected=dict(costume_id=fields[0],body_type_sub=fields[1],body_setting=fields[2],
                      height=str(row['height']),shape=str(row['shape']),bust=str(row['bust']))
        candidates=[j for j in bodies if all(body_profile(j['source'])[k]==v for k,v in expected.items())]
        record=dict(character_id=str(row['id']),parameters=row,expected_profile=expected,body_type=type_id(expected),
                    runtime_root_scale=row.get('scale')/160.7529 if row.get('scale') is not None else None,
                    runtime_scale_applied=False)
        if not candidates:
            record['status']='missing_template';result.append(record);continue
        job=sorted(candidates,key=lambda j:j['name'])[0]
        data=json.loads((path.parent/job['snapshot']).read_text(encoding='utf8'))
        expected_diffuse='tex_bdy'+costume+'_'+str(row['skin'])+'_'+str(row['bust'])+'_diff'
        main=[Path(p['texture']).stem.split('__')[0] for m in data['materials'] for p in m['properties'] if p['name']=='_MainTex' and p.get('texture')]
        record.update(selected_job=job['name'],selected_prefab=job['source'],selected_profile=body_profile(job['source']),
                      expected_diffuse=expected_diffuse,selected_diffuse=main,
                      skin_texture_matches=expected_diffuse in main,
                      status='matched' if expected_diffuse in main else 'skin_texture_mismatch')
        result.append(record)
    return dict(metadata=metadata,base_costume=costume,characters=result,
                all_requested_parameters_matched=all(r['status']=='matched' for r in result),
                scope='Character table selects a generic body template; does not assert dedicated costume meshes are identical')

def _skeleton(data):
    names={b['id']:('__asset_root' if b['name'].startswith('pfb_') else b['name']) for b in data['bones']}
    bones={names[b['id']]:dict(parent=names.get(b['parent']),matrix=b['matrix']) for b in data['bones']}
    return names,bones

def make_body_type_groups(manifest_path,index,resolution):
    if not resolution['all_requested_parameters_matched']:raise ValueError('Body type morphs require matching table parameters AND skin texture selection')
    path=Path(manifest_path);manifest=json.loads(path.read_text(encoding='utf8'))
    jobs={j['name']:j for j in manifest['jobs']}
    selected={r['selected_job'] for r in resolution['characters']}
    records=[r for r in index['records'] if r['job'] in selected and r['category']=='whole_mesh']
    sources={name:json.loads((path.parent/jobs[name]['snapshot']).read_text(encoding='utf8')) for name in selected}
    buckets=defaultdict(list)
    for record in records:
        p=record['body_profile']
        buckets[(p['costume_id'],p['body_type_sub'],p['body_setting'],record['mesh_name'])].append(record)
    groups=[];checks=[]
    for bucket in buckets.values():
        base=sorted(bucket,key=lambda r:r['body_profile']['geometry_key'])[0];targets=[]
        for target in sorted(bucket,key=lambda r:r['body_profile']['geometry_key']):
            if target['id']==base['id']:continue
            a,b=sources[base['job']],sources[target['job']]
            am,bm=a['meshes'][base['mesh_index']],b['meshes'][target['mesh_index']]
            mapping,reason=topology_mapping(am,bm)
            an,ab=_skeleton(a);bn,bb=_skeleton(b)
            hierarchy=set(ab)==set(bb) and all(ab[n]['parent']==bb[n]['parent'] for n in ab)
            bind_error=max((abs(x-y) for n in set(ab)&set(bb) for x,y in zip(ab[n]['matrix'],bb[n]['matrix'])),default=0)
            def weights(mesh,names):
                result=defaultdict(dict)
                for w in mesh['weights']:
                    if w['weight']>0:
                        values=result[w['vertex']];name=names[w['bone']]
                        values[name]=values.get(name,0)+w['weight']
                return result
            aw,bw=weights(am,an),weights(bm,bn)
            weight_error=None
            if mapping is not None:
                weight_error=max((abs(aw[i].get(n,0)-bw[j].get(n,0)) for i,j in enumerate(mapping) for n in set(aw[i])|set(bw[j])),default=0)
            passed=mapping is not None and hierarchy and bind_error<=1e-5 and weight_error is not None and weight_error<=1e-6
            checks.append(dict(base=base['id'],target=target['id'],topology_reason=reason,hierarchy_equal=hierarchy,
                               max_bind_matrix_error=bind_error,max_weight_error=weight_error,passed=passed,
                               tolerance=dict(bind_matrix=1e-5,weight=1e-6,uv=0)))
            if passed:targets.append(target['id'])
        if targets:groups.append(dict(base=base['id'],targets=targets,body_type_mode=True))
    return dict(groups=groups,checks=checks,
                policy='Only verified table-selected whole generic body types; never copy skin/clothing partitions across profiles; no per-character torso keys')

def verify_bindings(output,export_manifest):
    out=Path(output)
    bindings=json.loads((out/'character-body-bindings.json').read_text(encoding='utf8'))['characters']
    resolution=json.loads((out/'character-body-profiles.json').read_text(encoding='utf8'))
    for actor in bindings:
        expected=next(r for r in resolution['characters'] if r['character_id']==actor['character_id'])
        assert actor['parameters']==expected['parameters'] and actor['selected_job']==expected['selected_job']
        assert actor['per_character_torso_key'] is False and actor['runtime_scale_applied'] is False
        group=next(g for g in export_manifest['morph_groups'] if g['blend']==actor['body_type_blend'])
        assert group['purpose']=='body_type'
        if actor['body_type_key']=='Basis':assert actor['selected_job']==group['base_job'] and actor['body_type_key_value']==0
        else:assert any(t['key']==actor['body_type_key'] and t['source_job']==actor['selected_job'] for t in group['targets']) and actor['body_type_key_value']==1
        for override in actor['diffuse_overrides']:
            path=out/override['diffuse'];assert path.is_file()
            assert path.stem.split('__')[0]==actor['expected_diffuse']
    return dict(passed=True,characters=len(bindings),per_character_torso_keys=0)
