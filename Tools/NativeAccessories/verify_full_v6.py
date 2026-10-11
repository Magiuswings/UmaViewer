"""Join the final independently imported parts exactly at their CK3 attachment bones."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector

def main():
    p=argparse.ArgumentParser()
    for name in ['root','repo','plugin','game']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);r=a.root;mod=r/'UMA-V6-1001';models=mod/'gfx/models/portraits/uma';sys.path[:0]=[str(a.plugin.parent),str(a.repo/'Tools/NativeBody')]
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from build_native_body_blend import native_action
    from test_vanilla_body_animation_blender import inverse_bind,globals_for
    io_pdx_mesh.register();bpy.ops.wm.open_mainfile(filepath=str(r/'Models/1001/uma_1001_accessories.blend'));headrig=bpy.data.objects['uma_head_carrier'];plan=json.loads((r/'integration.json').read_text());swap=np.array([[1,0,0],[0,0,1],[0,1,0]])
    def imported(file):
        before=set(bpy.data.objects);pdx.import_meshfile(str(file),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=True,bonespace=False);new=[o for o in bpy.data.objects if o not in before];obj=next(o for o in new if o.type=='MESH');rig=next(m.object for m in obj.modifiers if m.type=='ARMATURE');return obj,rig,new
    body,bodyrig,_=imported(models/'0001/uma_0001_body_base.mesh');body.name='uma_0001_body';bodyrig.name='uma_0001_body_rig';body.parent=bodyrig;body.matrix_parent_inverse=Matrix.Identity(4);body.matrix_basis=Matrix.Identity(4);bodydata=pdx_data.read_meshfile(str(models/'0001/uma_0001_body_base.mesh'));skel=bodydata.find('object')[0].find('skeleton');bind=inverse_bind(skel);assert len(skel)==134;nodes={'body':bodydata.find('object')[0].find('mesh')};objects={'body':body};shapechecks=[]
    body.shape_key_add(name='Basis')
    for key,suffix in [('bs_body_clothed','clothed'),('bs_body_breast_shape_1','b0'),('bs_body_breast_shape_2','b1'),('bs_body_breast_shape_3','b3'),('bs_body_breast_shape_4','b4'),('bs_body_gaunt_1','s1'),('bs_body_fat_1','s2')]:
        target=pdx_data.read_meshfile(str(models/'0001'/('uma_0001_body_'+suffix+'.mesh'))).find('object')[0].find('mesh');assert target.attrib['tri']==nodes['body'].attrib['tri'];block=body.shape_key_add(name=key);block.data.foreach_set('co',(np.array(target.attrib['p']).reshape(-1,3)@swap.T).astype(np.float32).reshape(-1));block.value=1. if key=='bs_body_clothed'else 0.;shapechecks.append(dict(element='body',key=key,vertices=len(block.data)))
        if key=='bs_body_clothed':nodes['body']=target
    for row in plan['parts']:
        if row['element']not in ['clothing','footwear']:continue
        obj,rig,new=imported(mod/row['file']);obj.name='uma_1001_'+row['element'];obj.parent=bodyrig;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=Matrix.Identity(4)
        for m in obj.modifiers:
            if m.type=='ARMATURE':m.object=bodyrig
        for other in new:
            if other.type=='ARMATURE'and other!=bodyrig:bpy.data.objects.remove(other,do_unlink=True)
        node=pdx_data.read_meshfile(str(mod/row['file'])).find('object')[0].find('mesh');objects[row['element']]=obj;nodes[row['element']]=node;obj.shape_key_add(name='Basis')
        for key,suffix in [('bs_body_breast_shape_1','b0'),('bs_body_breast_shape_2','b1'),('bs_body_breast_shape_3','b3'),('bs_body_breast_shape_4','b4'),('bs_body_gaunt_1','s1'),('bs_body_fat_1','s2')]:
            file=(mod/row['file']).with_name(row['prefix']+'_'+suffix+'.mesh');target=pdx_data.read_meshfile(str(file)).find('object')[0].find('mesh');assert target.attrib['tri']==node.attrib['tri']and target.attrib['u0']==node.attrib['u0'];block=obj.shape_key_add(name=key);block.data.foreach_set('co',(np.array(target.attrib['p']).reshape(-1,3)@swap.T).astype(np.float32).reshape(-1));shapechecks.append(dict(element=row['element'],key=key,vertices=len(block.data)))
    def attachment(name,target,bone):
        obj=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(obj);c=obj.constraints.new('COPY_TRANSFORMS');c.target=target;c.subtarget=bone;return obj
    # CK3 joint_attachment replaces each child joint's world pose. Head clips
    # already carry the full body-height root translation (~105cm), so parenting
    # the entire armature to thoracic would incorrectly apply it a second time.
    headrig.parent=None;headrig.matrix_world=Matrix.Identity(4)
    for child,parent in [('head_root','bn_sp_thoracic'),('bn_h_l_clavicle','bn_l_clavicle'),('bn_h_r_clavicle','bn_r_clavicle')]:
        c=headrig.pose.bones[child].constraints.new('COPY_TRANSFORMS');c.name='CK3 joint_attachment';c.target=bodyrig;c.subtarget=parent;c.owner_space='WORLD';c.target_space='WORLD'
    tail=bpy.data.objects['uma_1001_tail'];tailrig=next(m.object for m in tail.modifiers if m.type=='ARMATURE');tailrig.parent=attachment('tail_to_torso',bodyrig,'body_root');tailrig.matrix_parent_inverse=Matrix.Identity(4);tailrig.matrix_basis=Matrix.Identity(4);tail.parent=tailrig;tail.matrix_parent_inverse=Matrix.Identity(4);tail.matrix_basis=Matrix.Identity(4);tail.hide_render=False
    scene=bpy.context.scene;scene.render.resolution_x=720;scene.render.resolution_y=960;proof=r/'Evidence';camera=scene.camera;lights=[o for o in scene.objects if o.type=='LIGHT'];allmesh=[o for o in scene.objects if o.type=='MESH'and not o.hide_render];checks=[];actions=[];renders=[]
    def evaluated(obj):
        e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh();q=np.array([tuple(e.matrix_world@v.co)for v in mesh.vertices]);e.to_mesh_clear();return q
    def render(name,side=False):
        q=np.concatenate([evaluated(obj)for obj in allmesh]);center=Vector((q.min(0)+q.max(0))*.5);size=max(float(q[:,2].max()-q[:,2].min()),float(q[:,0 if not side else 1].max()-q[:,0 if not side else 1].min())*960/720)*1.13;camera.data.ortho_scale=size;camera.location=center+Vector((size*2,0,0)if side else(0,-size*2,0));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        for light,offset,energy in zip(lights,[(-60,-130,110),(70,-110,20)],[120000,50000]):light.location=center+Vector(offset);light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler();light.data.energy=energy;light.data.size=110
        bpy.context.view_layer.update();scene.render.filepath=str(proof/(name+'.png'));bpy.ops.render.render(write_still=True);im=bpy.data.images.load(scene.render.filepath,check_existing=False);pixels=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(pixels);std=float(np.std(pixels.reshape(-1,4)[:,:3]));bpy.data.images.remove(im);assert std>.02;renders.append(dict(file='Evidence/'+name+'.png',rgb_standard_deviation=std))
    # Test skinning of the final split meshes against a CPU PDX reconstruction,
    # rather than treating finite bounding boxes as animation correctness.
    for label,name in [('idle','female_body_idle_1.anim'),('court','female_body_throneRoom_ruler1_1.anim')]:
        file=a.game/'gfx/models/portraits/female_body'/name;native_action.skeleton=skel;action=native_action(bodyrig,file,pdx_data);actions.append(action);clip=pdx_data.read_meshfile(str(file));info=clip.find('info');samples=clip.find('samples');count=info.attrib['sa'][0]
        for frame in sorted({0,count//2,count-1}):
            scene.frame_set(frame+1);bpy.context.view_layer.update();G=globals_for(info,samples,frame,skel);M=G@bind;errors={}
            attachment_errors={}
            for child,parent in [('head_root','bn_sp_thoracic'),('bn_h_l_clavicle','bn_l_clavicle'),('bn_h_r_clavicle','bn_r_clavicle')]:
                aa=np.array(headrig.matrix_world@headrig.pose.bones[child].matrix);bb=np.array(bodyrig.matrix_world@bodyrig.pose.bones[parent].matrix);err=float(np.max(abs(aa-bb)));assert err<.01;attachment_errors[child]=err
            for element,obj in objects.items():
                node=nodes[element];q=np.column_stack((np.array(node.attrib['p']).reshape(-1,3),np.ones(len(obj.data.vertices))));skin=node.find('skin');ix=np.array(skin.attrib['ix']).reshape(-1,4);w=np.array(skin.attrib['w']).reshape(-1,4);expected=np.zeros((len(q),3))
                for slot in range(4):expected+=np.einsum('nij,nj->ni',M[np.maximum(ix[:,slot],0)],q)[:,:3]*w[:,slot,None]
                actual=evaluated(obj);error=float(np.max(abs(actual-expected@swap.T)));assert error<.01,(element,label,frame,error);errors[element]=error
            for obj in allmesh:assert np.isfinite(evaluated(obj)).all()
            checks.append(dict(context=label,frame=frame,skin_errors_cm=errors,joint_attachment_matrix_errors=attachment_errors,attachments_finite=True))
        scene.frame_set(count//2+1);render('1001_full_'+label+'_front');render('1001_full_'+label+'_side',True)
    bodyrig.animation_data.action=None
    for bone in bodyrig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    headrig.animation_data.action=None
    for bone in headrig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    # Neutral ear/tail are explicit bind poses; their real animations are retained
    # as editable actions, and the default saved scene selects those real idles.
    for rig in [next(m.object for m in bpy.data.objects['uma_1001_ear'].modifiers if m.type=='ARMATURE'),tailrig]:
        rig.animation_data.action=None
        for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    scene.frame_set(1);render('1001_full_neutral_front');render('1001_full_neutral_side',True)
    bodyrig.animation_data.action=actions[0]
    # Restore head and native ear/tail idle actions by their source filename.
    native_action.skeleton=pdx_data.read_meshfile(str(models/'0001/uma_0001_head_empty.mesh')).find('object')[0].find('skeleton');headrig.animation_data.action=native_action(headrig,models/'animation/uma_female_head_idle_1.anim',pdx_data)
    for kind in ['ear','tail']:
        obj=bpy.data.objects['uma_1001_'+kind];rig=next(m.object for m in obj.modifiers if m.type=='ARMATURE');native_action.skeleton=pdx_data.read_meshfile(str(models/'1001'/('uma_1001_'+kind+'_base.mesh'))).find('object')[0].find('skeleton');rig.animation_data.action=native_action(rig,models/'animation'/kind/('uma_1001_'+kind+'_idle.anim'),pdx_data)
        for curve in rig.animation_data.action.fcurves:curve.modifiers.new('CYCLES')
    scene.frame_set(1);bpy.context.view_layer.update();bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;file=r/'Models/1001/uma_1001_full_chain.blend';bpy.ops.wm.save_as_mainfile(filepath=str(file));bpy.ops.wm.open_mainfile(filepath=str(file));assert len(bpy.data.objects['uma_1001_clothing'].data.vertices)==6397 and len(bpy.data.objects['uma_1001_footwear'].data.vertices)==1929;assert len(bpy.data.objects['uma_0001_body'].data.shape_keys.key_blocks)==8;assert len(bpy.data.objects['uma_1001_clothing'].data.shape_keys.key_blocks)==7;assert all(im.packed_file for im in bpy.data.images if im.source=='FILE')
    report=dict(passed=True,final_pdx_components_reimported=True,head_torso_attachment='Three world joint constraints exactly mirror portrait_types joint_attachment, replacing animated head root rather than adding it twice',ear_attachment='bn_h_head',tail_attachment='body_root',native_motion_rigs_separate=True,body_and_clothing_shape_keys=shapechecks,body_animation_samples=checks,renders=renders,model=str(file),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),packed_textures=True,reopened=True,collision_free=False,game_runtime_verified=False)
    (r/'full-chain-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('V6_FULL_CHAIN_REIMPORT_POSE_REOPEN_VERIFIED',flush=True)
if __name__=='__main__':main()
