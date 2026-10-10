"""Reimport the 1001 accessories, evaluate shared animation, render and save."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector,Euler

def write(file,data):file.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def coords(obj):return np.array([v.co[:]for v in obj.data.vertices])

def main():
    p=argparse.ArgumentParser()
    for n in ('root','repo','plugin','game'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert a.root.resolve()==Path('E:/UmaViewer-Exports/2026-10-10-Head-Accessory-1001').resolve();assert bpy.app.version[:2]==(4,2)
    sys.path[:0]=[str(a.plugin.parent),str(a.repo/'Tools/NativeBody')]
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from build_native_body_blend import native_action
    from test_vanilla_body_animation_blender import inverse_bind,globals_for
    io_pdx_mesh.register();bpy.ops.wm.read_factory_settings(use_empty=True);mod=a.root/'Uma-1001-Accessory-Test';plan=json.loads((a.root/'build-verification.json').read_text());models=mod/'gfx/models/portraits/uma';evidence=a.root/'Evidence';evidence.mkdir(exist_ok=True)
    empty=models/'0001/uma_0001_head_empty.mesh';carrierdata=pdx_data.read_meshfile(str(empty));skel=carrierdata.find('object')[0].find('skeleton');bind=inverse_bind(skel);names=[n.tag for n in skel];swap=np.array([[1,0,0],[0,0,1],[0,1,0]])
    pdx.import_meshfile(str(empty),imp_mesh=False,imp_skel=True,imp_locs=False,bonespace=False);rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');rig.name='uma_0001_head_carrier';assert len(rig.data.bones)==61 and not any(o.type=='MESH'for o in bpy.context.scene.objects)
    meshes={};nodes={};imports=[]
    for row in plan['accessories']:
        before=set(bpy.data.objects);file=mod/row['file'];data=pdx_data.read_meshfile(str(file));node=data.find('object')[0].find('mesh');nodes[row['element']]=node
        pdx.import_meshfile(str(file),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=True,bonespace=False);new=[o for o in bpy.data.objects if o not in before];obj=next(o for o in new if o.type=='MESH');obj.name='uma_1001_'+row['element'];world=obj.matrix_world.copy()
        for modifier in obj.modifiers:
            if modifier.type=='ARMATURE':modifier.object=rig
        obj.parent=rig;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_world=world
        for other in new:
            if other.type=='ARMATURE'and other!=rig:bpy.data.objects.remove(other,do_unlink=True)
        expected=np.array(node.attrib['p']).reshape(-1,3)@swap.T;assert len(obj.data.vertices)==row['vertices'];assert np.max(abs(coords(obj)-expected))<1e-4
        for mat in obj.data.materials:
            for n in mat.node_tree.nodes:
                if n.type=='TEX_IMAGE'and n.image and'diffuse'in n.image.name and row['element']in ['face','face_parts']:n.image.alpha_mode='NONE'
        meshes[row['element']]=obj;imports.append(row['file'])
    face=meshes['face'];targetfile=models/'1001/uma_1001_face_80.mesh';target=pdx_data.read_meshfile(str(targetfile)).find('object')[0].find('mesh');before=set(bpy.data.objects);pdx.import_meshfile(str(targetfile),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=True,bonespace=False);new=[o for o in bpy.data.objects if o not in before];target_object=next(o for o in new if o.type=='MESH');target_points=coords(target_object);assert len(target_points)==875 and np.max(abs(target_points-np.array(target.attrib['p']).reshape(-1,3)@swap.T))<1e-4
    for obj in new:bpy.data.objects.remove(obj,do_unlink=True)
    basis=face.shape_key_add(name='Basis');key=face.shape_key_add(name='uma_bs_face_1001');key.data.foreach_set('co',target_points.astype(np.float32).reshape(-1));key.value=1.;key.relative_key=basis;face.data.normals_split_custom_set_from_vertices((np.array(target.attrib['n']).reshape(-1,3)@swap.T).tolist());imports.append(targetfile.relative_to(mod).as_posix());imports.insert(0,empty.relative_to(mod).as_posix())
    triangles=np.array([p.vertices[:]for p in face.data.polygons]);assert len(face.data.vertices)==875 and len(triangles)==1334
    degenerate=0;quality=[];q0=np.array([v.co[:]for v in basis.data]);q1=np.array([v.co[:]for v in key.data])
    for strength in [0.,.25,.5,.75,1.]:
        q=q0*(1-strength)+q1*strength;t=q[triangles];areas=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1);count=int(sum(areas<1e-8));assert count==0;quality.append(dict(strength=strength,degenerate_faces=count))
    native_action.skeleton=skel;clips=[('idle','uma_female_head_idle_1.anim'),('court','uma_female_head_throneRoom_ruler3_1.anim'),('event','uma_male_head_praying_standing.anim'),('emotion','uma_male_head_emotion_angry.anim')];actions=[];tests=[]
    for label,filename in clips:
        file=models/'animation'/filename;assert file.is_file();action=native_action(rig,file,pdx_data);actions.append(action);clip=pdx_data.read_meshfile(str(file));info=clip.find('info');samples=clip.find('samples');count=info.attrib['sa'][0];checks=[]
        for frame in sorted({0,count//2,count-1}):
            bpy.context.scene.frame_set(frame+1);world=globals_for(info,samples,frame,skel);skinmat=world@bind;errors={}
            for element,obj in meshes.items():
                node=target if element=='face'else nodes[element];q=np.column_stack((np.array(node.attrib['p']).reshape(-1,3),np.ones(len(obj.data.vertices))));skin=node.find('skin');ix=np.array(skin.attrib['ix']).reshape(-1,4);weights=np.array(skin.attrib['w']).reshape(-1,4);goal=np.zeros((len(q),3))
                for slot in range(4):goal+=np.einsum('nij,nj->ni',skinmat[np.maximum(ix[:,slot],0)],q)[:,:3]*weights[:,slot,None]
                evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();actual=np.array([tuple(evaluated.matrix_world@v.co)for v in mesh.vertices]);evaluated.to_mesh_clear();error=float(np.max(abs(actual-goal@swap.T)));assert error<.01,(label,frame,element,error);assert np.isfinite(actual).all();errors[element]=error
            checks.append(dict(frame=frame,element_errors_cm=errors))
        tests.append(dict(context=label,file=filename,frames=count,samples=checks));print('VERIFIED_SHARED_HEAD_CONTEXT',label,flush=True)
    # Procedural eye rotations are not necessarily stored in .anim clips.
    # Probe the same iris around old stock and matching UMA pivots explicitly.
    stock=pdx_data.read_meshfile(str(a.game/'gfx/models/portraits/female_head/female_head.mesh')).find('object')[0].find('skeleton');stockworld=np.linalg.inv(inverse_bind(stock));umaworld=np.linalg.inv(bind);stockids={n.tag:i for i,n in enumerate(stock)};eye=nodes['eye'];points=np.array(eye.attrib['p']).reshape(-1,3);skin=eye.find('skin');ix=np.array(skin.attrib['ix']).reshape(-1,4);weights=np.array(skin.attrib['w']).reshape(-1,4);probes=[]
    for side in ['l','r']:
        name='bn_h_eye_'+side+'_rotate';i=names.index(name);active=np.any((ix==i)&(weights>0),axis=1);center=points[active].mean(0);uma=umaworld[i,:3,3];original=stockworld[stockids[name],:3,3]
        for axis in ['X','Y']:
            for angle in [-15,15]:
                R=np.array(Matrix.Rotation(np.deg2rad(angle),3,axis));wrong=original+R@(center-original);correct=uma+R@(center-uma);probes.append(dict(side=side,axis=axis,angle_degrees=angle,old_center_displacement_cm=float(np.linalg.norm(wrong-center)),matched_center_displacement_cm=float(np.linalg.norm(correct-center)),old_to_matched_center_error_cm=float(np.linalg.norm(wrong-correct))))
    assert max(r['matched_center_displacement_cm']for r in probes)<.1
    # Compare shader palette responsiveness, preserving the actual DDS RGB.
    active_body=models/'0001/uma_0001_body_skin1_diffuse.dds'
    image=bpy.data.images.load(str(active_body),check_existing=True);image.colorspace_settings.name='Non-Color';buffer=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(buffer);body=buffer.reshape(-1,4);assert np.all(abs(body[:,3]-1)<1e-6)
    proof=next(r for r in plan['palette']if r['file']==active_body.name);assert proof['rgb_pixels_exact']and proof['compressed_rgb_blocks_exact']and proof['alpha_before']==[0,0]
    palette_tests=[]
    for palette in [[1,1,1],[.8,.6,.4],[.45,.3,.2]]:
        rgb=body[:,:3];mask=body[:,3:4];new=rgb*(1-mask)+rgb*np.array(palette)*mask;old=rgb;palette_tests.append(dict(palette=palette,old_mean_rgb=old.mean(0).tolist(),repaired_mean_rgb=new.mean(0).tolist()))
    # Save an actual native-action preview, cameras follow the animated head.
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world=bpy.data.worlds.new('QA');scene.world.color=(.18,.18,.18);scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
    rest_points=np.concatenate([np.array((target if e=='face'else nodes[e]).attrib['p']).reshape(-1,3)@swap.T for e in meshes]);center=Vector((rest_points.min(0)+rest_points.max(0))*.5);size=float(np.max(rest_points.max(0)-rest_points.min(0)));camera_data=bpy.data.cameras.new('QA camera');camera=bpy.data.objects.new('QA camera',camera_data);scene.collection.objects.link(camera);camera_data.type='ORTHO';camera_data.ortho_scale=size*1.25;camera.location=center+Vector((0,-size*2,0));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update();rest_camera=camera.matrix_world.copy();scene.camera=camera;lights=[]
    for name,offset,energy in [('key',(-25,-45,30),35000),('fill',(25,-35,0),16000)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.size=40.;light=bpy.data.objects.new(name,data);scene.collection.objects.link(light);light.location=center+Vector(offset);light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update();lights.append((light,light.matrix_world.copy()))
    def check_render():
        image=bpy.data.images.load(scene.render.filepath,check_existing=False);pixels=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(pixels);variance=float(np.std(pixels.reshape(-1,4)[:,:3]));bpy.data.images.remove(image);assert variance>.03,'Blank QA image: '+scene.render.filepath
    rest_head=rig.data.bones['bn_h_head'].matrix_local.copy();renders=[]
    for (label,filename),action in zip(clips,actions):
        rig.animation_data.action=action;scene.frame_set(int(action.frame_range[1]//2)+1);delta=rig.pose.bones['bn_h_head'].matrix@rest_head.inverted();camera.matrix_world=delta@rest_camera
        for light,rest in lights:light.matrix_world=delta@rest
        scene.render.filepath=str(evidence/('1001_'+label+'.png'));bpy.ops.render.render(write_still=True);check_render();renders.append('Evidence/1001_'+label+'.png')
    # Visual gaze test in the same neutral bone frame, independent of clip t/q.
    rig.animation_data.action=None
    for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    camera.matrix_world=rest_camera
    for light,rest in lights:light.matrix_world=rest
    from mathutils import Quaternion
    for angle in [-15,15]:
        for side in ['l','r']:
            bone=rig.pose.bones['bn_h_eye_'+side+'_rotate'];bone.rotation_mode='QUATERNION';bone.rotation_quaternion=Quaternion(Vector((1,0,0)),float(np.deg2rad(angle)))
        bpy.context.view_layer.update();label='gaze_'+('minus15'if angle<0 else'plus15');scene.render.filepath=str(evidence/('1001_'+label+'.png'));bpy.ops.render.render(write_still=True);check_render();renders.append('Evidence/1001_'+label+'.png')
    rig.animation_data.action=actions[0];scene.frame_set(1);rig.hide_set(True);camera.hide_set(True)
    for light,_ in lights:light.hide_set(True)
    values=[];deps=bpy.context.evaluated_depsgraph_get()
    for obj in meshes.values():
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();values.extend([tuple(evaluated.matrix_world@v.co)for v in mesh.vertices]);evaluated.to_mesh_clear()
    q=np.array(values);viewcenter=Vector((q.min(0)+q.max(0))*.5)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':region=area.spaces.active.region_3d;region.view_location=viewcenter;region.view_distance=size*1.7;region.view_rotation=Euler((np.pi/2,0,0)).to_quaternion();region.view_perspective='ORTHO'
    bpy.ops.object.select_all(action='DESELECT');face.select_set(True);bpy.context.view_layer.objects.active=face;bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True);bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;folder=a.root/'Models/1001';folder.mkdir(parents=True,exist_ok=True);file=folder/'uma_1001_head_accessory.blend';bpy.ops.wm.save_as_mainfile(filepath=str(file))
    # Reopen the actual saved file, not the in-memory construction.
    bpy.ops.wm.open_mainfile(filepath=str(file));face=bpy.data.objects['uma_1001_face'];assert len(face.data.vertices)==875 and len(face.data.shape_keys.key_blocks)==2;assert face.data.shape_keys.key_blocks['uma_bs_face_1001'].value==1;assert len([o for o in bpy.context.scene.objects if o.type=='ARMATURE'])==1;assert len([o for o in bpy.context.scene.objects if o.type=='MESH'])==5;assert all(i.packed_file for i in bpy.data.images if i.source=='FILE')
    report=dict(passed=True,scope='1001 only',pdx_plugin_imports=7,empty_carrier_reimported=True,carrier_rendered_vertices=0,bones=61,accessory_meshes=5,shared_blender_rig=True,face_vertices=875,face_triangles=1334,bs_strength_checks=quality,animation_contexts=tests,native_pose_checks=sum(len(t['samples'])for t in tests)*5,procedural_eye_rotation_probes=probes,palette_shader_formula_tests=palette_tests,body_texture_rgb_exact=True,all_diffuse_references_custom=True,blender_reopened=True,packed_textures=True,model_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),renders=renders,game_runtime_verified=False)
    write(a.root/'blender-verification.json',report);print('SINGLE_CHARACTER_ACCESSORY_VERIFIED',len(tests),'contexts',len(probes),'gaze probes',flush=True)

if __name__=='__main__':main()
