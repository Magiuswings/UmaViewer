"""Independent Blender 4.2 reopen, source comparison and real PDX roundtrip."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from collections import Counter
import bpy
from mathutils import Matrix,Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

def check_source(obj,source,core,category):
    attribute=obj.data.attributes['uma_source_vertex']
    ids=[item.value for item in attribute.data]
    positions=[core.vec(source['vertices'][i]) for i in ids]
    for shape in source.get('shapes',[]):
        for k,i in enumerate(ids):positions[k]-=core.vec(shape['deltas'][i])*shape['weight']
    err=max(((v.co-p).length for v,p in zip(obj.data.vertices,positions)),default=0)
    assert err<1e-6,('Source geometry changed',obj.name,err)
    assert list(obj.matrix_world)==list(Matrix.Identity(4)),('Source transform changed',obj.name)
    def cycle(t):return min(tuple(t[i:]+t[:i]) for i in range(len(t)))
    expected=Counter(cycle(list(reversed(f['triangles'][i:i+3]))) for f in source['faces']
                     if category=='body_base' or f['category']==category for i in range(0,len(f['triangles']),3))
    actual=Counter(cycle([ids[i] for i in poly.vertices]) for poly in obj.data.polygons)
    assert actual==expected,('Source category partition changed',obj.name,category)
    for layer,uv in zip(obj.data.uv_layers,source['uvs']):
        for loop in obj.data.loops:
            expected=uv['values'][ids[loop.vertex_index]]
            assert (layer.data[loop.index].uv-Vector((expected['x'],expected['y']))).length<1e-7
    return err

def main():
    config=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8'))
    assert bpy.app.version[:2]==(4,2)
    out=Path(config['output']);src=Path(config['manifest'])
    sys.path.insert(0,str(Path(config['plugin']).parent))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    io_pdx_mesh.register()
    from blender_pipeline import binary_checks,SHADERS
    core_path=HERE/'uma_blender_import.py'
    if not core_path.exists():core_path=HERE.parents[1]/'Assets/StreamingAssets/Blender/uma_blender_import.py'
    spec=importlib.util.spec_from_file_location('source_core',core_path);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    manifest=json.loads((out/'export-manifest.json').read_text(encoding='utf8'))
    normalized=json.loads(src.read_text(encoding='utf8'))
    original_path=Path(config.get('source_manifest',config['manifest']))
    original=json.loads(original_path.read_text(encoding='utf8'))
    if config.get('character_db'):
        from character_types import read_database,resolve_characters,make_body_type_groups
        resolution=json.loads((out/'character-body-profiles.json').read_text(encoding='utf8'))
        current=read_database(config['character_db'],[str(r['id']) for r in resolution['metadata']['characters']])
        assert current==resolution['metadata'],'Character database parameters changed since export'
        assert resolve_characters(src,current,resolution['base_costume'])==resolution
        if config.get('body_type_morphs'):
            index=json.loads((out/'apparel-index.json').read_text(encoding='utf8'))
            assert make_body_type_groups(src,index,resolution)==json.loads((out/'body-type-validation.json').read_text(encoding='utf8'))
    originals={j['name']:j for j in original['jobs']}
    for job in normalized['jobs']:
        a=json.loads((src.parent/job['snapshot']).read_text(encoding='utf8'))
        b=json.loads((original_path.parent/originals[job['name']]['snapshot']).read_text(encoding='utf8'))
        assert a['bones']==b['bones'] and a['materials']==b['materials']
        assert len(a['meshes'])==len(b['meshes'])
        for x,y in zip(a['meshes'],b['meshes']):
            assert {k:v for k,v in x.items() if k!='faces'}=={k:v for k,v in y.items() if k!='faces'}
            def triangles(mesh):return Counter((tuple(f['triangles'][i:i+3]),f['material']) for f in mesh['faces'] for i in range(0,len(f['triangles']),3))
            assert triangles(x)==triangles(y),'Family partition normalization changed source geometry'
    reports=[];roundtrips=[];morphs=[]
    for item in manifest['components']:
        bpy.ops.wm.open_mainfile(filepath=str(out/item['blend']))
        assert bpy.app.version_file[:2]==(4,2),bpy.app.version_file
        objects=sorted((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:pdx.get_mesh_index(o.data))
        source=json.loads((src.parent/item['source_snapshot']).read_text(encoding='utf8'))
        rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
        mapping=json.loads((out/item['rig_report']).read_text(encoding='utf8'))
        reference_path=config['head_reference'] if item['kind']=='head' else config['body_reference']
        reference=pdx_data.read_meshfile(reference_path).find('object')[0].find('skeleton')
        names=[b.tag for b in reference]
        assert {b.name for b in rig.data.bones}==set(names)
        for bone in reference:
            parent=names[bone.attrib['pa'][0]] if 'pa' in bone.attrib else None
            assert (rig.data.bones[bone.tag].parent.name if rig.data.bones[bone.tag].parent else None)==parent
        max_error=0
        for obj in objects:
            original=next(m for m in source['meshes'] if m['name']==obj['uma_source_renderer'])
            max_error=max(max_error,check_source(obj,original,core,item['category']))
            for mat in obj.data.materials:
                assert mat['shader'] in set(SHADERS.values())
                if item['category']!='body_base':assert mat['shader']==SHADERS[item['category']]
            for vertex in obj.data.vertices:
                influences=[g for g in vertex.groups if g.weight>0]
                assert len(influences)<=4 and abs(sum(g.weight for g in influences)-1)<1e-6
                assert all(obj.vertex_groups[g.group].name in names for g in influences)
            # Independently verify source weight accumulation and bone mapping.
            attr=[i.value for i in obj.data.attributes['uma_source_vertex'].data]
            source_bones={b['id']:b['name'] for b in source['bones']}
            semantic={v['source_name']:v['target'] for v in mapping['source_mapping'].values()}
            source_weights={}
            for weight in original['weights']:
                if weight['weight']>0:
                    target=semantic[source_bones[weight['bone']]]
                    vals=source_weights.setdefault(weight['vertex'],{})
                    vals[target]=vals.get(target,0)+weight['weight']
            for vertex,index in zip(obj.data.vertices,attr):
                expected=sorted(source_weights.get(index,{}).items(),key=lambda v:(-v[1],v[0]))[:4]
                if not expected:expected=[('bn_h_head' if item['kind']=='head' else 'body_root',1)]
                total=sum(w for _,w in expected)
                actual={obj.vertex_groups[g.group].name:g.weight for g in vertex.groups if g.weight>0}
                assert set(actual)=={n for n,w in expected}
                assert all(abs(actual[n]-w/total)<2e-6 for n,w in expected)
            evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
            rest_error=max(((a.co-b.co).length for a,b in zip(obj.data.vertices,evaluated.vertices)),default=0)
            obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
            assert rest_error<1e-5,rest_error
        checks=binary_checks(out/item['mesh'],pdx_data,objects,pdx)
        # Confirm referenced texture files really exist adjacent to exported mesh.
        parsed=pdx_data.read_meshfile(str(out/item['mesh']))
        for node in parsed.find('object'):
            for mesh in node.findall('mesh'):
                material=mesh.find('material')
                if material is not None:
                    for key in ('diff','n','spec'):
                        if key in material.attrib:assert ((out/item['mesh']).parent/material.attrib[key][0]).is_file()
        root=next(b for b in rig.pose.bones if b.parent is None)
        probe_obj=objects[0];before=[v.co.copy() for v in probe_obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices]
        root.location.x=.01;bpy.context.view_layer.update()
        moved=probe_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        displacement=max(((a-b.co).length for a,b in zip(before,moved.data.vertices)),default=0)
        assert displacement>.001,('Bone does not deform mesh',item['name'])
        root.location.x=0;bpy.context.view_layer.update()
        reports.append(dict(name=item['name'],source_coordinate_max_error=max_error,bone_count=len(names),
                            root_deformation_max=displacement,binary=checks,passed=True))
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(out/item['mesh']),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=False)
        imported=[o for o in bpy.data.objects if o.type=='MESH']
        assert sum(len(o.data.polygons) for o in imported)==sum(x['triangles'] for x in checks)
        assert all(o.data.uv_layers for o in imported)
        assert all(any(m.type=='ARMATURE' and m.object for m in o.modifiers) for o in imported)
        assert {m['shader'] for o in imported for m in o.data.materials}=={x['shader'] for x in checks}
        roundtrips.append(dict(name=item['name'],objects=len(imported),triangles=sum(len(o.data.polygons) for o in imported),passed=True))
        print('PDX_VERIFIED '+item['name'],flush=True)
        (out/'verification.json').write_text(json.dumps(dict(passed=False,in_progress=True,blender=bpy.app.version_string,components=reports,roundtrips=roundtrips,morphs=morphs),ensure_ascii=False,indent=2),encoding='utf8')
    for group in manifest.get('morph_groups',[]):
        bpy.ops.wm.open_mainfile(filepath=str(out/group['blend']))
        base=next(o for o in bpy.data.objects if o.type=='MESH')
        assert bpy.app.version_file[:2]==(4,2)
        assert base.data.shape_keys and len(base.data.shape_keys.key_blocks)==len(group['targets'])+1
        basis=base.data.shape_keys.key_blocks[0]
        assert all(tuple(a.co)==tuple(b.co) for a,b in zip(basis.data,base.data.vertices))
        parsed=pdx_data.read_meshfile(str(out/group['base_mesh']))
        base_meshes=parsed.find('object')[0].findall('mesh')
        base_skeleton=parsed.find('object')[0].find('skeleton')
        for target in group['targets']:
            base_item=next(c for c in manifest['components'] if c['job']==group['base_job'] and c['category']==('body_base' if group['category']=='whole_mesh' else group['category']))
            target_item=next(c for c in manifest['components'] if c['blend']==target['source_component'])
            from body_profiles import profiles_compatible
            if group.get('purpose')=='body_type':
                validation=json.loads((out/'body-type-validation.json').read_text(encoding='utf8'))
                check=next(c for c in validation['checks'] if c['base']==group['base_record'] and c['target'].startswith(target_item['job']+'::'))
                assert check['passed'] and check['max_weight_error']<=1e-6 and check['max_bind_matrix_error']<=1e-5
                assert target['key'].startswith('height_') and 'chara' not in target['key'],'Character-specific torso key was created'
            else:assert profiles_compatible(base_item.get('body_profile'),target_item.get('body_profile')),'Cross-bust component morph was exported'
            key=base.data.shape_keys.key_blocks[target['key']]
            assert key.value==0
            binary=pdx_data.read_meshfile(str(out/target['mesh']))
            assert binary.find('object')[0].tag==parsed.find('object')[0].tag
            t=binary.find('object')[0].findall('mesh')
            target_skeleton=binary.find('object')[0].find('skeleton')
            assert [(b.tag,b.attrib) for b in target_skeleton]==[(b.tag,b.attrib) for b in base_skeleton]
            assert len(t)==len(base_meshes)
            source_item=next(c for c in manifest['components'] if c['blend']==target['source_component'])
            source_description=next(o for o in source_item['objects'] if o['renderer']==target['source_renderer'])
            with bpy.data.libraries.load(str(out/target['source_component']),link=False) as (available,loaded):
                loaded.objects=[source_description['name']]
            target_object=loaded.objects[0]
            from morphs import topology_mapping
            correspondence,reason=topology_mapping(base,target_object)
            assert correspondence is not None,reason
            assert all((point.co-target_object.data.vertices[j].co).length<1e-7 for point,j in zip(key.data,correspondence))
            for slot,(a,b) in enumerate(zip(base_meshes,t)):
                assert len(a.attrib['p'])==len(b.attrib['p'])
                assert a.attrib['tri']==b.attrib['tri']
                for layer in ('u0','u1','u2','u3'):assert a.attrib.get(layer)==b.attrib.get(layer)
                info,ids=pdx.get_mesh_info(base,slot,split_criteria=['id','p','uv'],sort_vertices=True)
                expected=[float(v) for i in ids for v in pdx.swap_coord_space(base.matrix_world@key.data[i].co)]
                assert len(expected)==len(b.attrib['p'])
                assert max((abs(a-b) for a,b in zip(expected,b.attrib['p'])),default=0)<1e-6
            max_key_delta=max(((a.co-b.co).length for a,b in zip(basis.data,key.data)),default=0)
            assert abs(max_key_delta-target['max_delta'])<1e-6
        morphs.append(dict(name=group['name'],keys=len(group['targets']),passed=True))
    assert len(reports)==len(manifest['components'])
    if config.get('body_type_morphs'):
        from character_types import verify_bindings
        verify_bindings(out,manifest)
    (out/'verification.json').write_text(json.dumps(dict(passed=True,in_progress=False,blender=bpy.app.version_string,
          components=reports,roundtrips=roundtrips,morphs=morphs,limitations=['CK3 game/animation runtime not tested']),ensure_ascii=False,indent=2),encoding='utf8')
    print('PDX_ALL_VERIFIED components='+str(len(reports))+' morph_groups='+str(len(morphs)),flush=True)

if __name__=='__main__':main()
