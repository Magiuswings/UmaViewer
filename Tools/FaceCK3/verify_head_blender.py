"""Independently reopen the saved head and import each packaged PDX endpoint."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector

def main():
    p=argparse.ArgumentParser()
    for n in ('repo','plugin','root','targets'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path[:0]=[str(a.plugin.parent),str(a.repo/'Tools/NativeBody')]
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from test_vanilla_body_animation_blender import inverse_bind,globals_for
    io_pdx_mesh.register();assert bpy.app.version[:2]==(4,2)
    prep=json.loads((a.root/'prepared.json').read_text());z=np.load(a.targets/'face-targets.npz');T=np.array(prep['engine_transform']);origin=np.array(prep['engine_origin']);swap=np.array([[1,0,0],[0,0,1],[0,1,0]]);file=a.root/'Models/0001/uma_0001_head_base.blend';bpy.ops.wm.open_mainfile(filepath=str(file));face=bpy.data.objects['uma_0001_face'];rig=bpy.data.objects['uma_0001_head_rig'];keys=face.data.shape_keys.key_blocks;assert len(keys)==183 and len(face.data.vertices)==875 and len(face.data.polygons)==1334
    assert np.array_equal(np.array([list(p.vertices)for p in face.data.polygons]),z['faces'][:,::-1]);expected=(z['Basis']@T.T+origin)@swap.T;assert np.max(abs(np.array([v.co[:]for v in keys['Basis'].data])-expected))<1e-4
    degenerate=0;checks=0;max_error=0.
    for row in prep['records']:
        actual=np.array([v.co[:]for v in keys[row['attribute']].data]);goal=(z[row['id']]@T.T+origin)@swap.T;error=np.max(abs(actual-goal));assert error<1e-4;max_error=max(max_error,float(error))
        for strength in (.25,.5,.75,1.):
            q=expected*(1-strength)+actual*strength;tri=q[z['faces']];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1);degenerate+=int(sum(area<1e-8));checks+=1
    assert degenerate==0;assert len(rig.data.bones)==61;assert all(i.packed_file for i in bpy.data.images if i.source=='FILE')
    # Real reused idle is present in the editable file. Verify Blender's skinning
    # against exact saved engine matrices for both distinct neutral identities.
    mod=a.root/'Uma-Face-Morphs';base=pdx_data.read_meshfile(str(mod/'gfx/models/portraits/uma/0001/uma_0001_head_base.mesh'));sk=base.find('object')[0].find('skeleton');bind=inverse_bind(sk);names=[b.tag for b in sk];groups={g.index:g.name for g in face.vertex_groups};ws=[]
    for v in face.data.vertices:ws.append([(names.index(groups[g.group]),g.weight)for g in v.groups if g.weight>0])
    posed_checks=0;posed_max_error=0.
    action=rig.animation_data.action;clip=pdx_data.read_meshfile(str(mod/'gfx/models/portraits/uma/animation'/(action.name+'.anim')));info=clip.find('info');samples=clip.find('samples');frames=info.attrib['sa'][0]
    for ident in ['1001','1003','npc_000']:
        for key in keys:key.value=0
        keys['uma_bs_face_'+ident].value=1.
        for frame in sorted({0,frames//2,frames-1}):
            bpy.context.scene.frame_set(frame+1);q=np.column_stack((z[ident]@T.T+origin,np.ones(875)));mat=globals_for(info,samples,frame,sk)@bind;goal=np.array([sum((mat[j]@q[i])[:3]*w for j,w in influences)for i,influences in enumerate(ws)])@swap.T;evaluated=face.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh();actual=np.array([v.co[:]for v in evaluated.vertices]);face.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear();error=float(np.max(abs(actual-goal)));assert error<.01,(ident,frame,error);posed_max_error=max(posed_max_error,error);posed_checks+=1
    # Render the saved default head in the same idle, without saving QA cameras.
    for key in keys:key.value=0
    keys['uma_bs_face_1001'].value=1.;bpy.context.scene.frame_set(1);scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world=bpy.data.worlds.new('QA world');scene.world.color=(.2,.2,.2)
    points=[];deps=bpy.context.evaluated_depsgraph_get()
    for obj in scene.objects:
        if obj.type!='MESH':continue
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();points.extend([tuple(evaluated.matrix_world@v.co)for v in mesh.vertices]);evaluated.to_mesh_clear()
    q=np.array(points);center=Vector((q.min(0)+q.max(0))*.5);size=float(np.max(q.max(0)-q.min(0)));camera_data=bpy.data.cameras.new('QA');camera=bpy.data.objects.new('QA',camera_data);scene.collection.objects.link(camera);camera_data.type='ORTHO';camera_data.ortho_scale=size*1.2;camera.location=center+Vector((0,-size*2,0));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
    for label,position,power in [('key',(-25,-45,65),35000),('fill',(25,-35,35),20000)]:
        light_data=bpy.data.lights.new(label,'AREA');light_data.energy=power;light_data.shape='DISK';light_data.size=40.;light=bpy.data.objects.new(label,light_data);scene.collection.objects.link(light);light.location=center+Vector(position)-Vector((0,0,35));light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    evidence=a.root/'Evidence';evidence.mkdir(exist_ok=True);scene.render.filepath=str(evidence/'uma_1001_head_idle.png');bpy.ops.render.render(write_still=True)
    # Use the plugin itself to read every mesh from the finished mod, including
    # materials resolved relative to each target's actual folder.
    imports=[]
    for row in [dict(id='Basis',mesh='meshes/0001/uma_0001_head_base.mesh'),*prep['records']]:
        bpy.ops.wm.read_factory_settings(use_empty=True);target=mod/'gfx/models/portraits/uma'/row['mesh'].removeprefix('meshes/');pdx.import_meshfile(str(target),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=True,bonespace=False);objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];skin=next(o for o in objects if o.data.name.startswith('uma_0001_faceShape'));assert len(skin.data.vertices)==875 and len(skin.data.polygons)==1334;assert len(objects)==5
        for obj in objects:
            assert len(obj.data.vertices)>0 and len(obj.vertex_groups)==61
            assert np.isfinite(np.array([v.co[:]for v in obj.data.vertices])).all()
        imports.append(row['id'])
        if len(imports)%20==0:print('PDX_HEADS_REIMPORTED',len(imports),flush=True)
    report=dict(passed=True,blender=bpy.app.version_string,blend_reopened=True,face_vertices=875,face_triangles=1334,identity_keys=182,endpoint_and_intermediate_checks=checks,degenerate_faces=degenerate,shape_coordinate_error_cm=max_error,packed_textures=True,pdx_plugin_imports=len(imports),imported_identities=imports,idle_pose_samples=posed_checks,idle_matrix_max_error_cm=posed_max_error,render='Evidence/uma_1001_head_idle.png',game_runtime_verified=False)
    (a.root/'blender-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('CK3_HEAD_REOPEN_VERIFICATION_COMPLETE',len(imports),flush=True)

if __name__=='__main__':main()
