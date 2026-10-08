"""Build the actual editable vector keys and export each nonzero endpoint using PDX IO."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def accelerate_pdx_lookup(pdx):
    import inspect
    source=inspect.getsource(pdx.get_mesh_info)
    assert 'export_verts.index(new_vert)' in source
    source=source.replace('unique_verts = set()', 'unique_verts = set()\n    unique_indices = {}')
    source=source.replace('i = export_verts.index(new_vert)', 'i = unique_indices[new_vert]')
    source=source.replace('export_verts.append(new_vert)', 'unique_indices[new_vert] = len(export_verts)\n                export_verts.append(new_vert)')
    exec(compile(source, '<verified-pdx-index-cache>', 'exec'),pdx.__dict__)

def main():
    config=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8'))
    assert bpy.app.version[:2]==(4,2)
    repo=Path(config['repo']);out=Path(config['output']);src=Path(config['manifest'])
    sys.path.insert(0,str(repo/'Tools/PDXExporter'));sys.path.insert(0,str(repo/'Tools/HeadlessExporter'));sys.path.insert(0,str(Path(config['plugin']).parent))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    io_pdx_mesh.register()
    accelerate_pdx_lookup(pdx)
    from blender_pipeline import build,geometry_signature,select_export,write
    from rigging import adapt_rig
    core_path=repo/'Assets/StreamingAssets/Blender/uma_blender_import.py'
    spec=importlib.util.spec_from_file_location('vector_body_core',core_path);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    analysis=json.loads(Path(config['analysis']).read_text(encoding='utf8'));manifest=json.loads(src.read_text(encoding='utf8'))
    jobs={j['name']:j for j in manifest['jobs']}
    base_data=json.loads((src.parent/jobs[analysis['basis_job']]['snapshot']).read_text(encoding='utf8'))
    # Reuse the established material/rig builder, with a local texture-folder alias.
    (out/'textures').mkdir()
    for file in (out/'meshes').glob('*.dds'):os.link(file,out/'textures'/file.name)
    rig,objects=build(base_data,'body_base',config,core)
    assert len(objects)==1
    base=objects[0];signature=geometry_signature(base)
    rig_report=adapt_rig(rig,objects,config['body_reference'],pdx,pdx_data,'body')
    rig=bpy.data.objects[rig_report['rig_name']]
    assert geometry_signature(base)==signature,'Rig adaptation moved the mesh'
    write(out/'rig.json',rig_report)
    base.name='UMA_Common_Body';base.data.name='M_Body_body'
    ids=[v.value for v in base.data.attributes['uma_source_vertex'].data]
    base.shape_key_add(name='Basis')
    names=[]
    for definition in analysis['keys']:
        data=json.loads((src.parent/jobs[definition['source_job']]['snapshot']).read_text(encoding='utf8'))
        mesh=data['meshes'][0]
        correspondence=next(c for c in analysis['correspondence'] if c['job']==definition['source_job'])['mapping']
        key=base.shape_key_add(name=definition['key'],from_mix=False);key.slider_min=0;key.slider_max=1;key.value=0
        for target,source_id in zip(key.data,ids):target.co=core.vec(mesh['vertices'][correspondence[source_id]])
        key.relative_key=base.data.shape_keys.key_blocks['Basis'];names.append(key.name)
    base['uma_body_vector_policy']=config['policy'];base['uma_basis_parameters']=json.dumps(analysis['basis_profile'])
    base['uma_original_mesh_position_unchanged']=True
    pdx.set_mesh_index(base.data,0)
    select_export([base],rig)
    base_file=out/'meshes/base.mesh'
    pdx.export_meshfile(str(base_file),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
    parsed=pdx_data.read_meshfile(str(base_file));base_node=parsed.find('object')[0].find('mesh')
    results=[]
    for definition in analysis['keys']:
        key=base.data.shape_keys.key_blocks[definition['key']]
        if definition['identity']:
            results.append(dict(definition,mesh='meshes/base.mesh'));continue
        # Export a complete endpoint explicitly. Never apply the modifier or move Basis.
        clone=base.copy();clone.data=base.data.copy();bpy.context.scene.collection.objects.link(clone)
        clone.shape_key_clear()
        for vertex,target in zip(clone.data.vertices,key.data):vertex.co=target.co
        data=json.loads((src.parent/jobs[definition['source_job']]['snapshot']).read_text(encoding='utf8'))
        mesh=data['meshes'][0];mapping=next(c for c in analysis['correspondence'] if c['job']==definition['source_job'])['mapping']
        clone.data.normals_split_custom_set_from_vertices([core.vec(mesh['normals'][mapping[i]]) for i in ids])
        original_name=base.data.name;base.data.name=original_name+'__editing';clone.data.name=original_name
        select_export([clone],rig);file=out/'meshes'/(definition['key']+'.mesh')
        pdx.export_meshfile(str(file),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
        target=pdx_data.read_meshfile(str(file)).find('object')[0].find('mesh')
        assert target.attrib['tri']==base_node.attrib['tri']
        for uv in ('u0','u1','u2','u3'):assert target.attrib.get(uv)==base_node.attrib.get(uv)
        assert len(target.attrib['p'])==len(base_node.attrib['p'])
        clone_data=clone.data;bpy.data.objects.remove(clone,do_unlink=True);bpy.data.meshes.remove(clone_data);base.data.name=original_name
        results.append(dict(definition,mesh='meshes/'+file.name))
        print('EXPORTED_VECTOR',definition['key'],flush=True)
    # Mesh.copy() duplicates its Key datablock. Clearing/removing an endpoint leaves
    # that unused Key with a NULL owner in Blender4.2; saving would report an error.
    # The scene contains only this task's data, so purge zero-user temporary blocks.
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True)
    select_export([base],rig);bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'uma_common_body_vectors.blend'))
    write(out/'export-manifest.json',dict(blend='uma_common_body_vectors.blend',base_mesh='meshes/base.mesh',basis_profile=analysis['basis_profile'],basis_job=analysis['basis_job'],keys=results,
                                        editable_keys=len(results),nonzero_keys=sum(not k['identity'] for k in results),mesh_vertices=len(base.data.vertices),triangles=len(base.data.polygons),skeleton_bones=len(rig.data.bones),
                                        material_shader='portrait_skin',material_slots=len(base.data.materials),skin_completion=True,source_mesh_not_translated=True,per_character_body_keys=0))
    print('VECTOR_BODY_BUILT',len(results),'keys',flush=True)

if __name__=='__main__':main()
