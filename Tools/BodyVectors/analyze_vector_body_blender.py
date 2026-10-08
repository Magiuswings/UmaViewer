"""Validate source correspondence and independent height/shape/bust displacement vectors."""
import argparse
from collections import defaultdict,Counter
import json
from pathlib import Path
import sys
import numpy as np

FIELDS=('height','shape','bust')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def points(mesh):return np.asarray([[v[k] for k in 'xyz'] for v in mesh['vertices']],dtype=np.float64)
def skeleton(data):
    names={b['id']:('__root' if b['name'].startswith('pfb_') else b['name']) for b in data['bones']}
    return names,{names[b['id']]:dict(parent=names.get(b['parent']),matrix=b['matrix']) for b in data['bones']}
def weights(mesh,names):
    result=defaultdict(lambda:defaultdict(float))
    for w in mesh['weights']:result[w['vertex']][names[w['bone']]]+=w['weight']
    return result
def directed_triangles(mesh):
    values=[]
    for f in mesh['faces']:
        for i in range(0,len(f['triangles']),3):
            t=f['triangles'][i:i+3]
            values.append(min(tuple(t[j:]+t[:j]) for j in range(3)))
    return Counter(values)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--probe-manifest',type=Path,help='Optional selected fat/ordinary common-body snapshots, separate from completed skin')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    sys.path.insert(0,str(args.repo/'Tools/HeadlessExporter'))
    sys.path.insert(0,str(args.repo/'Tools/PDXExporter'))
    from body_profiles import body_profile
    from morphs import topology_mapping
    manifest=json.loads(args.manifest.read_text(encoding='utf8'))
    entries={}
    for job in manifest['jobs']:
        profile=body_profile(job['source'])
        if profile and (profile['costume_id'],profile['body_type_sub'],profile['body_setting'])==('0004','00','00'):
            data=json.loads((args.manifest.parent/job['snapshot']).read_text(encoding='utf8'))
            if len(data['meshes'])!=1:raise ValueError('Canonical body has multiple renderers')
            entries[tuple(int(profile[f]) for f in FIELDS)]=(job,data,data['meshes'][0])
    base_profile=(1,0,2)
    base_job,base_data,base_mesh=entries[base_profile]
    basis=points(base_mesh);an,ab=skeleton(base_data);aw=weights(base_mesh,an)
    sources={};correspondence=[]
    for profile,(job,data,mesh) in sorted(entries.items()):
        mapping,reason=topology_mapping(base_mesh,mesh)
        uv_exact=mapping is not None
        if mapping is None and len(base_mesh['vertices'])==len(mesh['vertices']) and directed_triangles(base_mesh)==directed_triangles(mesh):
            mapping=list(range(len(base_mesh['vertices'])))
            reason='Verified original-index directed topology; target UV differs, common Basis UV retained explicitly'
        if mapping is None:raise ValueError(str(profile)+': '+reason)
        sources[profile]=points(mesh)[mapping]
        bn,bb=skeleton(data);bw=weights(mesh,bn)
        hierarchy=set(ab)==set(bb) and all(ab[n]['parent']==bb[n]['parent'] for n in ab)
        bind_error=max(abs(x-y) for n in ab for x,y in zip(ab[n]['matrix'],bb[n]['matrix'])) if set(ab)==set(bb) else None
        weight_error=max(abs(aw[i].get(n,0)-bw[j].get(n,0)) for i,j in enumerate(mapping) for n in set(aw[i])|set(bw[j]))
        uv_error=max(abs(base_mesh['uvs'][li]['values'][i][k]-layer['values'][j][k]) for li,layer in enumerate(mesh['uvs']) for i,j in enumerate(mapping) for k in ('x','y'))
        bu=next(l for l in base_mesh['uvs'] if l['channel']==0)['values'];tu=next(l for l in mesh['uvs'] if l['channel']==0)['values']
        uv0_equal=all(bu[i]==tu[j] for i,j in enumerate(mapping))
        if not uv0_equal or not hierarchy or weight_error>1e-6:raise ValueError('Common Basis contract failed for '+str(profile))
        correspondence.append(dict(profile=list(profile),job=job['name'],vertices=len(mesh['vertices']),triangles=sum(len(f['triangles'])//3 for f in mesh['faces']),mapping_reason=reason,mapping=mapping,
                                   source_uv_exact=uv_exact,source_uv0_exact=uv0_equal,maximum_uv_difference=uv_error,hierarchy_equal=hierarchy,maximum_bind_matrix_difference=bind_error,maximum_semantic_weight_difference=weight_error))
    keys=[];vectors={}
    for axis,field in enumerate(FIELDS):
        for value in sorted({p[axis] for p in entries}):
            anchor=list(base_profile);anchor[axis]=value;anchor=tuple(anchor)
            if anchor not in sources:raise ValueError('No pure single-variable anchor '+str(anchor))
            name=field+'_'+str(value)
            delta=sources[anchor]-basis;vectors[(axis,value)]=delta
            keys.append(dict(key=name,variable=field,value=value,baseline_value=base_profile[axis],source_profile=list(anchor),source_job=entries[anchor][0]['name'],identity=bool(np.max(np.abs(delta))==0),max_delta_m=float(np.linalg.norm(delta,axis=1).max())))
    database=json.loads(args.inventory.read_text(encoding='utf8'))
    records=[]
    for profile,actual in sorted(sources.items()):
        predicted=basis+sum((vectors[(axis,value)] for axis,value in enumerate(profile)),np.zeros_like(basis))
        error=np.linalg.norm(actual-predicted,axis=1)
        records.append(dict(profile=dict(zip(FIELDS,profile)),job=entries[profile][0]['name'],max_error_m=float(error.max()),rms_error_m=float(np.sqrt(np.mean(error**2))),mean_error_m=float(error.mean()),vertices_above_0_01mm=int(np.count_nonzero(error>1e-5)),vertices_above_0_1mm=int(np.count_nonzero(error>1e-4)),vertices_above_1mm=int(np.count_nonzero(error>.001)),exact_within_0_01mm=bool(error.max()<=1e-5),weights={FIELDS[axis]+'_'+str(value):1 for axis,value in enumerate(profile)}))
    design=np.zeros((len(entries),8));labels=[k for k in keys if not k['identity']]
    actual_delta=[]
    for row,(profile,actual) in enumerate(sorted(sources.items())):
        for col,key in enumerate(labels):design[row,col]=int(profile[FIELDS.index(key['variable'])]==key['value'])
        actual_delta.append((actual-basis).reshape(-1))
    fit,_,rank,_=np.linalg.lstsq(design,np.asarray(actual_delta),rcond=None)
    residual=np.asarray(actual_delta)-design@fit
    norms=np.linalg.norm(residual.reshape(len(entries),-1,3),axis=2)
    fat=[]
    probe_path=args.probe_manifest or args.manifest
    probes=json.loads(probe_path.read_text(encoding='utf8'))
    for job in probes['jobs']:
        profile=body_profile(job['source'])
        if profile and profile['costume_id']=='0002' and profile['body_setting']=='03':
            data=json.loads((probe_path.parent/job['snapshot']).read_text(encoding='utf8'))
            mesh=data['meshes'][0]
            mapping,reason=topology_mapping(base_mesh,mesh)
            normal=next((j for j in probes['jobs'] if j['source']==job['source'].replace('_00_03_','_00_00_')),None)
            fat.append(dict(profile=profile,job=job['name'],vertices=len(mesh['vertices']),triangles=sum(len(f['triangles'])//3 for f in mesh['faces']),canonical_mapping_reason=reason,canonical_correspondence=mapping is not None,ordinary_reference_job=normal['name'] if normal else None))
    result=dict(basis_profile=dict(zip(FIELDS,base_profile)),basis_job=base_job['name'],scope='Canonical competitive swimsuit bdy0004_00_00 only; bdy0009 is skin-coverage donor, four bdy0002 bodies are fat comparison probes',
                source_manifest=str(args.manifest),keys=keys,correspondence=correspondence,combinations=records,
                source_profiles=len(entries),character_count=database['total_characters'],
                database_profiles_available=all(tuple(r[f] for f in FIELDS) in entries for r in database['characters']),
                all_combinations_exact_within_0_01mm=all(r['exact_within_0_01mm'] for r in records),
                maximum_composition_error_m=max(r['max_error_m'] for r in records),
                constrained_additive_least_squares=dict(rank=int(rank),keys=len(labels),max_error_m=float(norms.max()),rms_error_m=float(np.sqrt(np.mean(norms**2))),note='Diagnostic only; never silently replace real pure-variable endpoints with fitted coordinates'),
                fat_variants=fat,private_keys_serialized=False,source_models_unchanged=True)
    write(args.output/'vector-analysis.json',result)
    print(json.dumps({k:result[k] for k in ('basis_profile','source_profiles','database_profiles_available','all_combinations_exact_within_0_01mm','maximum_composition_error_m','constrained_additive_least_squares','fat_variants')},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
