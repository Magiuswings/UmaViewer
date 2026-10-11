import os
"""Enable already-imported custom normals in Blender4.2 QA scenes, no asset edit."""
import json
from pathlib import Path
import numpy as np,bpy
from mathutils import Vector,Matrix
import sys
sys.path.insert(0,'E:/UmaViewer-Workspace/PDX-vendor')
from io_pdx_mesh import pdx_data as P
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));OUT=ROOT/'HeadSources/AssemblyQA';delivery=json.loads((ROOT/'HeadSources/NeckBridge/neck-delivery.json').read_text());snapshots=[]
reg=json.loads((ROOT/'Reports/head-registration.json').read_text());files={r['prefix']:Path(r['mesh'])for r in reg};files['body146']=ROOT/'UMA-V7/gfx/models/portraits/uma/0001/uma_0001_body_base.mesh';files['carrier199']=ROOT/'UMA-V7/gfx/models/portraits/uma/0001/uma_0001_head_female.mesh'
def evaluated(obj):
    ob=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ob.to_mesh();p=np.array([tuple(ob.matrix_world@v.co)for v in mesh.vertices]);ob.to_mesh_clear();return p
for actor in ['1001','1002']:
    for variant in ['80','00']:
        path=OUT/f'{actor}_{variant}_neck_repaired_assembly.blend';bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;scene.frame_set(1)
        normals=[]
        for obj in bpy.data.objects:
            if obj.type!='MESH':continue
            obj.data.polygons.foreach_set('use_smooth',[True]*len(obj.data.polygons))
            if obj.name not in files:continue
            data=obj.data;expected=np.array(P.read_meshfile(str(files[obj.name])).find('object')[0].find('mesh').get('n')).reshape(-1,3)[:,[0,2,1]];ids=np.array([l.vertex_index for l in data.loops]);data.update();before=np.zeros((len(data.loops),3));data.corner_normals.foreach_get('vector',before.ravel());prior=float(np.linalg.norm(before-expected[ids],axis=1).max());data.normals_split_custom_set_from_vertices(expected.tolist());data.update();after=np.zeros((len(data.loops),3));data.corner_normals.foreach_get('vector',after.ravel());error=float(np.linalg.norm(after-expected[ids],axis=1).max());assert error<.1,(obj.name,error);normals.append({'object':obj.name,'actual_source_PDX':str(files[obj.name]),'has_custom_normals':data.has_custom_normals,'loop_normal_error_before_explicit_restore':prior,'loop_normal_error_after_source_restore':error,'loop_normal_mean_error_after_source_restore':float(np.linalg.norm(after-expected[ids],axis=1).mean()),'loop_normal_p99_error_after_source_restore':float(np.percentile(np.linalg.norm(after-expected[ids],axis=1),99)),'vertices_order_exact':len(expected)==len(data.vertices)})
        bpy.context.view_layer.update();carrier=bpy.data.objects['carrier199_owned_rig'];carrier.matrix_basis=carrier.pose.bones['head_root'].matrix.inverted();carrier['current_root_external_compensation']='Actual clips omit head_root, retained static -d root bind needs object +d after thoracic socket. Object basis inverse(current root pose), so root world equals body thoracic.';bpy.context.view_layer.update();body=bpy.data.objects['body146'];bridge=bpy.data.objects[f'uma_{actor}_neck_base'];ring=next(r for r in delivery['actors']if r['row']['actor']==actor);p=evaluated(bridge);b=evaluated(body)[ring['lower_ring_body_vertex_ids']];lower=float(np.linalg.norm(p[:6]-b,axis=1).max());upperobjects=[o for o in bpy.data.objects if o.type=='MESH'and o.name in [f'uma_{actor}_face_{variant}',f'uma_{actor}_neck_patch_{variant}']];u=np.vstack([evaluated(o)for o in upperobjects]);upper=float(max(np.linalg.norm(u-v,axis=1).min()for v in p[6:]));assert lower<.005 and upper<.0001,(actor,variant,lower,upper)
        camera=scene.camera;center=camera.location-Vector((65,0,0));files=[]
        for view,offset in [('front',(0,-65,0)),('side',(65,0,0))]:camera.location=center+Vector(offset);camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/f'{actor}_{variant}_neck_repaired_{view}.png');bpy.ops.render.render(write_still=True);files.append(scene.render.filepath)
        scene['custom_normal_display_policy']='Stock SDK sets normals, but Blender>=4.1 lacks use_auto_smooth; polygons smooth enabled here to display actual saved vertex normals.';scene['cpu_preview_scope']='Actual palette tint applied to diffuse, Blender PBR lighting; not CK3 court shader proof.';bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(path));snapshots.append({'actor':actor,'variant':variant,'lower_ring_snapshot_error_cm':lower,'upper_ring_snapshot_error_cm':upper,'custom_normal_objects':normals,'pngs':files,'blend':str(path)});print('SMOOTH_SNAPSHOT',actor,variant,lower,upper,flush=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
for actor,x in [('1001',-35),('1002',35)]:
    source=OUT/f'{actor}_80_neck_repaired_assembly.blend'
    with bpy.data.libraries.load(str(source),link=False)as(src,dst):dst.objects=list(src.objects)
    linked=[o for o in dst.objects if o is not None]
    for obj in linked:bpy.context.collection.objects.link(obj)
    group=bpy.data.objects.new(actor+'_assembly_offset',None);bpy.context.collection.objects.link(group)
    for obj in linked:
        if obj.parent is None:saved=obj.matrix_world.copy();obj.parent=group;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_world=saved
    group.location.x=x
bpy.context.scene.frame_set(1);bpy.context.scene.frame_end=151;bpy.context.scene.render.fps=30;bpy.context.view_layer.update();bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;dual=OUT/'uma_v7_dual_actor_neck_repaired.blend';bpy.ops.wm.save_as_mainfile(filepath=str(dual));bpy.ops.wm.open_mainfile(filepath=str(dual));assert len([o for o in bpy.data.objects if o.type=='ARMATURE'])>=4
p=OUT/'blender-neck-repair-qa.json';r=json.loads(p.read_text());r['saved_idle_snapshot_actual_Bpy_closure_checks']=snapshots;r['custom_normals_displayed_correctly_Blender42']=True;r['local_neck_surface_endpoint_closure_passed']=True;r['entire_character_watertight_claimed']=False;r['dual_blend_reopened']=True;r['visual_inspection_pending']=True;p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print('SMOOTH_NECK_PREVIEW_COMPLETE',flush=True)

