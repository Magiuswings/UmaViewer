"""Create a native-bind editable Blender 4.2 file using PDX IO import/export."""
import argparse,copy,json,os,sys
from pathlib import Path
import numpy as np
import bpy
from mathutils import Matrix,Quaternion

def native_action(rig,file,pdx_data):
    """Write real stock local transforms as batch fcurves, without slow frame_set/keyframe_insert loops."""
    from test_vanilla_body_animation_blender import globals_for,inverse_bind
    data=pdx_data.read_meshfile(str(file));info=data.find('info');samples=data.find('samples');duration=info.attrib['sa'][0]
    # The importer uses the exact native bone names. Reuse its stored reference
    # skeleton from the original file, independent of active animation state.
    skeleton=native_action.skeleton;names=[n.tag for n in skeleton];lookup={n:i for i,n in enumerate(names)}
    rest={bone.name:bone.matrix_local.copy()for bone in rig.data.bones};frames=np.zeros((duration,len(names),10),dtype=np.float32)
    swap=Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)));previous={}
    for frame in range(duration):
        world=globals_for(info,samples,frame,skeleton)
        for i,name in enumerate(names):
            bone=rig.data.bones[name];parent=lookup[bone.parent.name]if bone.parent else None
            local=np.linalg.inv(world[parent])@world[i]if parent is not None else world[i]
            restlocal=rest[bone.parent.name].inverted()@rest[name]if bone.parent else rest[name]
            basis=restlocal.inverted()@(swap@Matrix(local.tolist())@swap);t,q,s=basis.decompose()
            if name in previous:q.make_compatible(previous[name])
            previous[name]=q.copy();frames[frame,i]=[*t,*q,*s]
    action=bpy.data.actions.new(file.stem);action.use_fake_user=True
    for i,name in enumerate(names):
        for data_path,offset,size in [('location',0,3),('rotation_quaternion',3,4),('scale',7,3)]:
            for component in range(size):
                values=frames[:,i,offset+component];constant=np.max(np.abs(values-values[0]))<1e-7
                ids=np.array([0,duration-1])if constant else np.arange(duration);curve=action.fcurves.new(f'pose.bones["{name}"].{data_path}',index=component,action_group=name);curve.keyframe_points.add(len(ids));curve.keyframe_points.foreach_set('co',np.column_stack((ids+1,values[ids])).astype(np.float32).reshape(-1))
                for key in curve.keyframe_points:key.interpolation='LINEAR'
                curve.update()
    rig.animation_data_create();rig.animation_data.action=action;return action

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--mod',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--character-id',default='1001');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert bpy.app.version[:2]==(4,2)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True);sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(a.plugin.parent));sys.path.insert(0,str(a.repo/'Tools/BodyVectors'));sys.path.insert(0,str(a.repo/'Tools/PDXExporter'))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from build_vector_body_blender import accelerate_pdx_lookup
    io_pdx_mesh.register();accelerate_pdx_lookup(pdx)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    prefix=a.character_id+'_body_';folder=a.mod/'gfx/models/portraits/uma'/a.character_id;file=folder/(prefix+'base.mesh');pdx.import_meshfile(str(file),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=True,bonespace=False)
    body=next(o for o in bpy.context.scene.objects if o.type=='MESH');rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');rig.name=a.character_id+'_body_vanilla_rig';body.name=a.character_id+'_body';body['coordinate_policy']='Preserved source geometry in centimeters; corrected inverse-bind direction frames; original UMA source preserved';body['height_runtime']='gene_height -> stock body_height additive; HeightSource references are not registered as additional live BS'
    before=pdx_data.read_meshfile(str(file));node=before.find('object')[0].find('mesh');base=np.asarray(node.attrib['p']).reshape(-1,3)
    assert len(body.data.vertices)==len(base)==14787 and len(rig.data.bones)==134
    # PDX IO's very short display tails lose orientation precision when added to
    # heads ~100 cm from the origin. Restore the exact reference frame with
    # longer display tails; heads, parents and skinning semantics stay fixed.
    from test_vanilla_body_animation_blender import inverse_bind
    native_skeleton=before.find('object')[0].find('skeleton');world=np.linalg.inv(inverse_bind(native_skeleton))
    bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
    for i,node_bone in enumerate(native_skeleton):
        bone=rig.data.edit_bones[node_bone.tag];bone.length=3.;bone.matrix=pdx.swap_coord_space(Matrix(world[i].tolist()))
    bpy.ops.object.mode_set(mode='OBJECT');bpy.context.view_layer.update()
    basis=body.shape_key_add(name='Basis');endpointkeys={'b0':'bs_body_breast_shape_1','b1':'bs_body_breast_shape_2','b3':'bs_body_breast_shape_3','b4':'bs_body_breast_shape_4','s1':'bs_body_gaunt_1','s2':'bs_body_fat_1','h0':'HeightSource_0','h2':'HeightSource_2'}
    for variant,keyname in endpointkeys.items():
        target=pdx_data.read_meshfile(str(folder/(prefix+variant+'.mesh'))).find('object')[0].find('mesh');q=np.asarray(target.attrib['p']).reshape(-1,3);assert target.attrib['tri']==node.attrib['tri'];key=body.shape_key_add(name=keyname)
        key.data.foreach_set('co',q[:,[0,2,1]].astype(np.float32).reshape(-1));key.value=0;key.relative_key=basis
    # A useful editor opens in the real vanilla idle pose; bind matrices remain
    # exact native references. Other actual clips are stored as independent Actions.
    actions=[];stock=a.game/'gfx/models/portraits/female_body'
    # Keep XML outside bpy ID properties (which cannot store Element objects).
    native_action.skeleton=before.find('object')[0].find('skeleton')
    for clip in ['female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim','female_body_jockey_walk.anim']:
        action=native_action(rig,stock/clip,pdx_data);actions.append(action);print('NATIVE_ACTION_IMPORTED',clip,flush=True)
    rig.animation_data.action=actions[0];bpy.context.scene.frame_set(1)
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    roundtrip=a.output/'roundtrip'/a.character_id;roundtrip.mkdir(parents=True);rig.data.pose_position='REST';bpy.ops.object.select_all(action='DESELECT');body.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=body
    # PDX IO changes the export object name to the mesh datablock's name.
    body.data.name=before.find('object')[0].tag;pdx.set_mesh_index(body.data,0)
    records=[]
    for variant in ['base',*endpointkeys]:
        # PDX IO intentionally exports Mesh.data, not the evaluated shape-key
        # mix. Materialize one endpoint in a temporary plain mesh.
        clone=body.copy();clone.data=body.data.copy();bpy.context.scene.collection.objects.link(clone);clone.shape_key_clear()
        source=pdx_data.read_meshfile(str(folder/(prefix+variant+'.mesh')));source_node=source.find('object')[0].find('mesh');endpoint=np.asarray(source_node.attrib['p']).reshape(-1,3);clone.data.vertices.foreach_set('co',endpoint[:,[0,2,1]].astype(np.float32).reshape(-1));clone.data.normals_split_custom_set_from_vertices(np.asarray(source_node.attrib['n']).reshape(-1,3)[:,[0,2,1]].tolist())
        saved_name=body.data.name;body.data.name=saved_name+'__editing';clone.data.name=saved_name;bpy.ops.object.select_all(action='DESELECT');clone.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=clone
        target=roundtrip/(prefix+variant+'.mesh');pdx.export_meshfile(str(target),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
        data=clone.data;bpy.data.objects.remove(clone,do_unlink=True);bpy.data.meshes.remove(data);body.data.name=saved_name
        parsed=pdx_data.read_meshfile(str(target));source=pdx_data.read_meshfile(str(folder/target.name));ps=parsed.find('object')[0].find('skeleton');ss=source.find('object')[0].find('skeleton')
        assert [n.tag for n in ps]==[n.tag for n in ss]
        binderror=max(abs(x-y)for n,r in zip(ps,ss)for x,y in zip(n.attrib['tx'],r.attrib['tx']));q=np.asarray(parsed.find('object')[0].find('mesh').attrib['p']).reshape(-1,3);expected=np.asarray(source.find('object')[0].find('mesh').attrib['p']).reshape(-1,3)
        # Exporter may split/deduplicate equivalent vertex normals. Compare a
        # position multiset rather than assuming its vertex numbering stays fixed.
        qs=np.round(q,4);es=np.round(expected,4);q=q[np.lexsort((qs[:,2],qs[:,1],qs[:,0]))];expected=expected[np.lexsort((es[:,2],es[:,1],es[:,0]))]
        assert q.shape==expected.shape
        error=float(np.linalg.norm(q-expected,axis=1).max());assert error<.0003 and binderror<.003,(variant,error,binderror)
        # Keep the binary engine contract byte-for-value exact after Blender's
        # edit-bone orthonormalization. The PDX-exported geometry/skin stays intact.
        obj=parsed.find('object')[0];at=list(obj).index(ps);obj.remove(ps);obj.insert(at,copy.deepcopy(ss));pdx_data.write_meshfile(str(target),parsed)
        records.append(dict(variant=variant,vertices=len(q),position_max_error_cm=error,blender_bind_max_coefficient_error=binderror,engine_bind_canonicalized_exact=True))
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True);rig.data.pose_position='POSE';bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body;bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
    blend=a.output/(prefix+'native.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(passed=True,blender_version=bpy.app.version_string,vertices=len(body.data.vertices),triangles=len(body.data.polygons),bones=len(rig.data.bones),keys=endpointkeys,actual_vanilla_actions=[x.name for x in actions],unit_scale_length=.01,roundtrips=records)
    (a.output/'blender-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('NATIVE_BODY_BLEND_COMPLETE',flush=True)

if __name__=='__main__':main()
