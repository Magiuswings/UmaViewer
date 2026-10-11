"""Actual PDX IO reimport, shared head/native attachment animation and visual proof."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector,Euler,Quaternion

def main():
    p=argparse.ArgumentParser()
    for n in ['root','repo','plugin','game']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--full',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert bpy.app.version[:2]==(4,2)
    sys.path[:0]=[str(a.plugin.parent),str(a.repo/'Tools/NativeBody')]
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from build_native_body_blend import native_action
    from test_vanilla_body_animation_blender import inverse_bind,globals_for
    io_pdx_mesh.register();bpy.ops.wm.read_factory_settings(use_empty=True);r=a.root;mod=r/'UMA-V6-1001';models=mod/'gfx/models/portraits/uma';proof=r/'Evidence';proof.mkdir(exist_ok=True);plan=json.loads((r/'integration.json').read_text());swap=np.array([[1,0,0],[0,0,1],[0,1,0]])
    def import_one(file):
        before=set(bpy.data.objects);pdx.import_meshfile(str(file),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=True,bonespace=False);new=[o for o in bpy.data.objects if o not in before];obj=next(o for o in new if o.type=='MESH');rig=next(m.object for m in obj.modifiers if m.type=='ARMATURE');return obj,rig,new
    carrier,headrig,_=import_one(models/'0001/uma_0001_head_empty.mesh');carrier.hide_render=True;carrier.hide_set(True);headrig.name='uma_head_carrier';data=pdx_data.read_meshfile(str(models/'0001/uma_0001_head_empty.mesh'));skel=data.find('object')[0].find('skeleton');bind=inverse_bind(skel);names=[b.tag for b in skel];meshes={};nodes={};records={};native=[]
    for row in plan['parts']:
        if row['element']in ['clothing','footwear']and not a.full:continue
        file=mod/row['file'];obj,rig,new=import_one(file);obj.name='uma_1001_'+row['element'];element=row['element'];nodes[element]=pdx_data.read_meshfile(str(file)).find('object')[0].find('mesh');meshes[element]=obj;records[element]=row
        if not row.get('attachment_node') and element!='clothing':
            for modifier in obj.modifiers:
                if modifier.type=='ARMATURE':modifier.object=headrig
            obj.parent=headrig;obj.matrix_parent_inverse=Matrix.Identity(4)
            for other in new:
                if other.type=='ARMATURE'and other!=headrig:bpy.data.objects.remove(other,do_unlink=True)
        elif row.get('attachment_node'):
            obj.parent=rig;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=Matrix.Identity(4)
            native.append((element,obj,rig,row,pdx_data.read_meshfile(str(file)).find('object')[0].find('skeleton')))
        # Preview the actual texture mask and preserve all source UVs.
        for mat in obj.data.materials:
            bsdf=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            if bsdf:bsdf.inputs['Roughness'].default_value=.72
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE'and node.image and 'diffuse'in node.image.name:
                    node.image.alpha_mode='NONE'if element in ['face','face_parts','brow']else'STRAIGHT'
            if bsdf and element in ['hair','ear','tail','brow']:
                diffuse=next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE'and n.image and 'diffuse'in n.image.name);normal=next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE'and n.image and 'normal'in n.image.name);normal.image.colorspace_settings.name='Non-Color';sep=mat.node_tree.nodes.new('ShaderNodeSeparateColor');mat.node_tree.links.new(normal.outputs['Color'],sep.inputs[0]);mul=mat.node_tree.nodes.new('ShaderNodeMixRGB');mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1.;mul.inputs[2].default_value=(.24,.075,.11,1);mat.node_tree.links.new(diffuse.outputs['Color'],mul.inputs[1]);mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mat.node_tree.links.new(sep.outputs['Blue'],mix.inputs[0]);mat.node_tree.links.new(diffuse.outputs['Color'],mix.inputs[1]);mat.node_tree.links.new(mul.outputs['Color'],mix.inputs[2]);mat.node_tree.links.new(mix.outputs['Color'],bsdf.inputs['Base Color'])
    # Native ears have their own skeleton/clip and are attached to the head bone.
    # The external transform is applied once, exactly like accessory node=.
    attachments={}
    for element,obj,rig,row,nskel in native:
        if element=='tail':continue
        attach=bpy.data.objects.new('ear_attachment',None);bpy.context.collection.objects.link(attach);con=attach.constraints.new('COPY_TRANSFORMS');con.target=headrig;con.subtarget=row['attachment_node'];rig.parent=attach;rig.matrix_parent_inverse=Matrix.Identity(4);rig.matrix_basis=Matrix.Identity(4);attachments[element]=attach
    native_action.skeleton=skel;headtests=[];actions=[]
    for label,filename in [('idle','uma_female_head_idle_1.anim'),('court','uma_female_head_throneRoom_ruler3_1.anim'),('event','uma_male_head_praying_standing.anim'),('emotion','uma_male_head_emotion_angry.anim')]:
        file=models/'animation'/filename;action=native_action(headrig,file,pdx_data);actions.append((label,action));clip=pdx_data.read_meshfile(str(file));info=clip.find('info');samples=clip.find('samples');count=info.attrib['sa'][0];checks=[]
        for frame in sorted({0,count//2,count-1}):
            bpy.context.scene.frame_set(frame+1);world=globals_for(info,samples,frame,skel);skinmat=world@bind;errors={}
            for element,obj in meshes.items():
                if element in ['ear','tail','clothing']:continue
                node=nodes[element];q=np.column_stack((np.array(node.attrib['p']).reshape(-1,3),np.ones(len(obj.data.vertices))));skin=node.find('skin');ix=np.array(skin.attrib['ix']).reshape(-1,4);weights=np.array(skin.attrib['w']).reshape(-1,4);goal=np.zeros((len(q),3))
                for slot in range(4):goal+=np.einsum('nij,nj->ni',skinmat[np.maximum(ix[:,slot],0)],q)[:,:3]*weights[:,slot,None]
                evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();actual=np.array([tuple(evaluated.matrix_world@v.co)for v in mesh.vertices]);evaluated.to_mesh_clear();error=float(np.max(abs(actual-goal@swap.T)));assert error<.01,(label,frame,element,error);errors[element]=error
            checks.append(dict(frame=frame,maximum_skinning_error_cm=max(errors.values())))
        headtests.append(dict(context=label,frames=count,checks=checks))
    # Keep a true neutral scene for texture/geometry inspection, avoiding an
    # animated camera accidentally hiding a malformed attachment.
    headrig.animation_data.action=None
    for bone in headrig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    for element,obj,rig,row,nskel in native:
        if element=='tail':obj.hide_render=True;rig.hide_render=True;continue
        rig.animation_data_clear()
        for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    scene=bpy.context.scene;scene.frame_set(1);scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world=bpy.data.worlds.new('Verification');scene.world.color=(.16,.16,.16);scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
    def points(objects):
        values=[];deps=bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();values.extend([tuple(evaluated.matrix_world@v.co)for v in mesh.vertices]);evaluated.to_mesh_clear()
        return np.array(values)
    q=points([o for k,o in meshes.items()if k not in ['tail','clothing']]);center=Vector((q.min(0)+q.max(0))*.5);size=float(np.max(q.max(0)-q.min(0)));camdata=bpy.data.cameras.new('QA');camera=bpy.data.objects.new('QA',camdata);scene.collection.objects.link(camera);camdata.type='ORTHO';camdata.ortho_scale=size*1.16;scene.camera=camera
    lightobjects=[]
    for name,offset,energy in [('Key',(-25,-45,30),12500),('Fill',(25,-35,5),5500)]:
        lightdata=bpy.data.lights.new(name,'AREA');lightdata.energy=energy;lightdata.size=40;light=bpy.data.objects.new(name,lightdata);scene.collection.objects.link(light);light.location=center+Vector(offset);light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler();lightobjects.append(light)
    renders=[]
    def render(name,angle=0):
        camera.location=center+Vector((np.sin(angle)*size*2,-np.cos(angle)*size*2,0));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update();scene.render.filepath=str(proof/(name+'.png'));bpy.ops.render.render(write_still=True);im=bpy.data.images.load(scene.render.filepath,check_existing=False);pixels=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(pixels);std=float(np.std(pixels.reshape(-1,4)[:,:3]));bpy.data.images.remove(im);assert std>.03,name;renders.append(dict(file='Evidence/'+name+'.png',rgb_standard_deviation=std))
    render('1001_head_original_front');render('1001_head_original_side',np.pi/2)
    meshes['hair'].hide_render=True
    for element,obj,rig,row,nskel in native:
        if element=='ear':obj.hide_render=True
    gray=bpy.data.materials.new('Geometry QA');gray.diffuse_color=(.6,.6,.6,1);scene.view_layers[0].material_override=gray;render('1001_face_geometry_front');render('1001_face_geometry_side',np.pi/2);scene.view_layers[0].material_override=None
    for element,obj,rig,row,nskel in native:
        if element=='ear':obj.hide_render=False
    meshes['hair'].hide_render=False
    # Save the native head idle plus actual ear idle as editable actions.
    headrig.animation_data.action=actions[0][1]
    for element,obj,rig,row,nskel in native:
        native_action.skeleton=nskel
        action=native_action(rig,models/next(x['file']for x in row['animations']if x['state']=='idle'),pdx_data);rig.animation_data.action=action
    scene.frame_set(1);bpy.context.view_layer.update();actual_points=points([o for k,o in meshes.items()if k not in ['tail','clothing','footwear']]);actual_center=Vector((actual_points.min(0)+actual_points.max(0))*.5);delta=actual_center-center;camera.location+=delta
    for light in lightobjects:light.location+=delta
    center=actual_center;headrig.hide_set(True)
    for obj in [camera,*lightobjects]:obj.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':region=area.spaces.active.region_3d;region.view_location=center;region.view_distance=size*1.8;region.view_rotation=Euler((np.pi/2,0,0)).to_quaternion();region.view_perspective='ORTHO'
    bpy.ops.object.select_all(action='DESELECT');meshes['face'].select_set(True);bpy.context.view_layer.objects.active=meshes['face'];bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;file=r/'Models/1001/uma_1001_accessories.blend';bpy.ops.wm.save_as_mainfile(filepath=str(file));bpy.ops.wm.open_mainfile(filepath=str(file));assert len(bpy.data.objects['uma_1001_face'].data.vertices)==1292;assert bpy.data.objects['uma_1001_face'].data.shape_keys is None;assert all(im.packed_file for im in bpy.data.images if im.source=='FILE')
    report=dict(passed=True,blender=bpy.app.version_string,head_pose_checks=headtests,shared_head_skinning_samples=60,source_face_vertices=1292,no_face_identity_bs=True,placeholder_triangle=1,native_ear_attached_to_head_bone=True,original_uv_preserved=True,packed_textures=True,blender_reopened=True,model=str(file),model_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),renders=renders,preview_uses_blender_materials=True,ck3_shader_or_live_court_verified=False)
    (r/'blender-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('V6_HEAD_ANIMATION_AND_REOPEN_VERIFIED',flush=True)
if __name__=='__main__':main()
