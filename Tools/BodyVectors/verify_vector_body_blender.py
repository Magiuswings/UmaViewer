"""Independent reopen, source-coordinate checks, all-combination evaluation and PDX import."""
from collections import defaultdict
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Matrix,Vector

def main():
    config=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8'))
    assert bpy.app.version[:2]==(4,2)
    repo=Path(config['repo']);out=Path(config['output']);src=Path(config['manifest'])
    assert hashlib.sha256(src.read_bytes()).hexdigest()==config['source_manifest_sha256']
    assert hashlib.sha256(Path(config['analysis']).read_bytes()).hexdigest()==config['analysis_sha256']
    sys.path.insert(0,str(repo/'Tools/PDXExporter'));sys.path.insert(0,str(repo/'Tools/HeadlessExporter'));sys.path.insert(0,str(Path(config['plugin']).parent))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    io_pdx_mesh.register()
    from blender_pipeline import write
    spec=importlib.util.spec_from_file_location('vector_check_core',repo/'Assets/StreamingAssets/Blender/uma_blender_import.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    analysis=json.loads(Path(config['analysis']).read_text(encoding='utf8'))
    export=json.loads((out/'export-manifest.json').read_text(encoding='utf8'))
    manifest=json.loads(src.read_text(encoding='utf8'));jobs={j['name']:j for j in manifest['jobs']}
    rig_report=json.loads((out/'rig.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=str(out/export['blend']))
    assert bpy.app.version_file[:2]==(4,2)
    base=next(o for o in bpy.data.objects if o.type=='MESH');rig=next(m.object for m in base.modifiers if m.type=='ARMATURE')
    assert len(base.data.vertices)==3510 and len(base.data.polygons)==5472
    assert len(base.data.materials)==1 and base.data.materials[0]['shader']=='portrait_skin'
    assert len(rig.data.bones)==134
    assert list(base.matrix_world)==list(Matrix.Identity(4))
    source=json.loads((src.parent/jobs[analysis['basis_job']]['snapshot']).read_text(encoding='utf8'))
    sm=source['meshes'][0];ids=[p.value for p in base.data.attributes['uma_source_vertex'].data]
    basis=base.data.shape_keys.key_blocks['Basis'];keys=base.data.shape_keys.key_blocks
    assert len(keys)==12
    basis_error=max((v.co-core.vec(sm['vertices'][i])).length for v,i in zip(basis.data,ids));assert basis_error<1e-7
    assert all(tuple(a.co)==tuple(b.co) for a,b in zip(base.data.vertices,basis.data))
    for layer in base.data.uv_layers:
        channel=int(layer.name[2:]);original=next(l for l in sm['uvs'] if l['channel']==channel)['values']
        for loop in base.data.loops:
            uv=original[ids[loop.vertex_index]];assert (layer.data[loop.index].uv-Vector((uv['x'],uv['y']))).length<1e-7
    semantic={v['source_name']:v['target'] for v in rig_report['source_mapping'].values()};names={b['id']:b['name'] for b in source['bones']}
    expected_weights=defaultdict(lambda:defaultdict(float))
    for w in sm['weights']:expected_weights[w['vertex']][semantic[names[w['bone']]]]+=w['weight']
    weight_error=0.
    for v,i in zip(base.data.vertices,ids):
        expected=sorted(expected_weights[i].items(),key=lambda v:(-v[1],v[0]))[:4];total=sum(w for _,w in expected)
        actual={base.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>0}
        assert set(actual)=={n for n,w in expected}
        weight_error=max(weight_error,max(abs(actual[n]-w/total) for n,w in expected))
    assert weight_error<2e-6
    endpoint=[]
    for definition in export['keys']:
        key=keys[definition['key']];assert key.value==0 and key.relative_key==basis
        data=json.loads((src.parent/jobs[definition['source_job']]['snapshot']).read_text(encoding='utf8'))
        mapping=next(c for c in analysis['correspondence'] if c['job']==definition['source_job'])['mapping'];mesh=data['meshes'][0]
        error=max((v.co-core.vec(mesh['vertices'][mapping[i]])).length for v,i in zip(key.data,ids));assert error<1e-7
        endpoint.append(dict(key=definition['key'],source_coordinate_max_error_m=error,identity=definition['identity']))
    combinations=[]
    for record in analysis['combinations']:
        for key in keys:key.value=0
        for name,value in record['weights'].items():keys[name].value=value
        bpy.context.view_layer.update()
        evaluated=base.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        data=json.loads((src.parent/jobs[record['job']]['snapshot']).read_text(encoding='utf8'));source_mesh=data['meshes'][0]
        mapping=next(c for c in analysis['correspondence'] if c['job']==record['job'])['mapping']
        error=max((v.co-core.vec(source_mesh['vertices'][mapping[i]])).length for v,i in zip(mesh.vertices,ids));evaluated.to_mesh_clear()
        assert error<2e-6,(record['job'],error)
        # UV0 is independently checked for every raw endpoint, including formerly rejected extra UV channels.
        bu=next(l for l in sm['uvs'] if l['channel']==0)['values'];tu=next(l for l in source_mesh['uvs'] if l['channel']==0)['values']
        assert all(bu[i]==tu[j] for i,j in enumerate(mapping))
        combinations.append(dict(profile=record['profile'],max_evaluated_error_m=error,source_uv0_exact=True,passed=True))
    for key in keys:key.value=0
    bpy.context.view_layer.update()
    root=next(b for b in rig.pose.bones if b.parent is None);root.location.x=.01;bpy.context.view_layer.update()
    evaluated=base.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();deformation=max((v.co-b.co).length for v,b in zip(mesh.vertices,base.data.vertices));evaluated.to_mesh_clear()
    assert deformation>.001;root.location.x=0;bpy.context.view_layer.update()
    parsed=pdx_data.read_meshfile(str(out/export['base_mesh']));base_object=parsed.find('object')[0];base_mesh=base_object.find('mesh')
    info,order=pdx.get_mesh_info(base,0,split_criteria=['id','p','uv'],sort_vertices=True)
    file_checks=[]
    binaries={}
    for relative in sorted({export['base_mesh']}|{k['mesh'] for k in export['keys']}):
        binary=pdx_data.read_meshfile(str(out/relative));obj=binary.find('object')[0];mesh=obj.find('mesh')
        binaries[relative]=mesh.attrib['p']
        assert obj.tag==base_object.tag and len(obj.findall('mesh'))==1
        assert mesh.attrib['tri']==base_mesh.attrib['tri']
        for uv in ('u0','u1','u2','u3'):assert mesh.attrib.get(uv)==base_mesh.attrib.get(uv)
        assert [(b.tag,b.attrib) for b in obj.find('skeleton')]==[(b.tag,b.attrib) for b in base_object.find('skeleton')]
        assert mesh.find('skin').attrib==base_mesh.find('skin').attrib
        name=Path(relative).stem;block=basis if name=='base' else keys[name]
        expected=[float(v) for i in order for v in pdx.swap_coord_space(base.matrix_world@block.data[i].co)]
        error=max(abs(a-b) for a,b in zip(expected,mesh.attrib['p']));assert error<1e-6
        assert mesh.find('material').attrib['shader']==['portrait_skin']
        for label in ('diff','n','spec'):assert (out/relative).with_name(mesh.find('material').attrib[label][0]).is_file()
        file_checks.append(dict(file=relative,binary_coordinate_max_error_m=error,vertices=len(mesh.attrib['p'])//3,triangles=len(mesh.attrib['tri'])//3,passed=True))
    binary_combinations=[]
    bp=binaries[export['base_mesh']];definitions={k['key']:k for k in export['keys']}
    for record in analysis['combinations']:
        actual=list(bp)
        for name,value in record['weights'].items():
            target=binaries[definitions[name]['mesh']]
            actual=[p+(t-b)*value for p,t,b in zip(actual,target,bp)]
        data=json.loads((src.parent/jobs[record['job']]['snapshot']).read_text(encoding='utf8'));mesh=data['meshes'][0]
        mapping=next(c for c in analysis['correspondence'] if c['job']==record['job'])['mapping']
        expected=[float(v) for i in order for v in pdx.swap_coord_space(core.vec(mesh['vertices'][mapping[ids[i]]]))]
        error=max(abs(a-b) for a,b in zip(actual,expected));assert error<1e-6
        binary_combinations.append(dict(profile=record['profile'],maximum_coordinate_error_m=error,passed=True))
    roundtrips=[]
    for record in file_checks:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(out/record['file']),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=False)
        meshes=[o for o in bpy.data.objects if o.type=='MESH']
        assert sum(len(o.data.polygons) for o in meshes)==5472
        assert all(o.data.uv_layers and any(m.type=='ARMATURE' and m.object for m in o.modifiers) for o in meshes)
        assert {m['shader'] for o in meshes for m in o.data.materials}=={'portrait_skin'}
        roundtrips.append(dict(file=record['file'],passed=True));print('PDX_VECTOR_ROUNDTRIP',record['file'],flush=True)
    bindings=json.loads((out/'character-body-bindings.json').read_text(encoding='utf8'))['characters']
    inventory=json.loads(Path(config['inventory']).read_text(encoding='utf8'))
    assert len(bindings)==len(inventory['characters'])==173
    for b,row in zip(bindings,inventory['characters']):
        assert b['parameters']==row and not b['per_character_body_key']
        assert set(b['keys'])=={f+'_'+str(row[f]) for f in ('height','shape','bust')}
        assert any(all(c['profile'][f]==row[f] for f in ('height','shape','bust')) for c in combinations)
    write(out/'verification.json',dict(passed=True,blender=bpy.app.version_string,basis_error_m=basis_error,semantic_weight_max_error=weight_error,root_deformation_m=deformation,
                keys=endpoint,combinations=combinations,binary_combinations=binary_combinations,files=file_checks,roundtrips=roundtrips,character_bindings=len(bindings),
                max_combination_evaluated_error_m=max(c['max_evaluated_error_m'] for c in combinations),
                limitations=['Extra target UV channels use Basis values; source UV0 is exact in every profile',
                             'One common Basis armature is reused; source bind points differ across profiles by up to '+str(max(c['maximum_bind_matrix_difference'] for c in analysis['correspondence']))+' source units',
                             'Fat setting03 cannot be an exact key on this topology', '17 unavailable parameter combinations are not source validated', 'CK3 runtime not tested']))
    print('VECTOR_BODY_ALL_VERIFIED',len(combinations),'combinations',len(roundtrips),'PDX roundtrips',flush=True)

if __name__=='__main__':main()
