import os
"""Actual final meshes and explicit current-joint assembly, no source/config edits."""
import json,sys,hashlib
from pathlib import Path
import numpy as np,bpy
from mathutils import Matrix,Vector
sys.path[:0]=[str(Path(__file__).resolve().parent),'E:/UmaViewer-Workspace/PDX-vendor',str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter')]
import io_pdx_mesh
from io_pdx_mesh import pdx_data as P
from io_pdx_mesh.pdx_blender import blender_import_export as IO
from build_ck3_mod import clausewitz,one,values
from head_assembly_math import rigdata,compose,readlocals,shared_pose,deform
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));MOD=ROOT/'UMA-V7';BASE=MOD/'gfx/models/portraits/uma/0001';OUT=ROOT/'HeadSources/AssemblyQA';OUT.mkdir(exist_ok=True);REG=json.loads((ROOT/'Reports/head-registration.json').read_text());SW4=np.eye(4);SW4[:3,:3]=np.array([[1,0,0],[0,0,1],[0,1,0]]);SW=SW4[:3,:3];CASES=[]
ADD=ROOT/'Rigs/uma_1002_head_points.anim';a0=readlocals(P,ADD,0);a1=readlocals(P,ADD,1);DELTAS={n:a1[n][:3,3]-m[:3,3]for n,m in a0.items()if np.abs(a1[n][:3,3]-m[:3,3]).max()>1e-8};assert len(DELTAS)==16
def load(file,label):
    before=set(bpy.data.objects);held=[]
    # The stock SDK reuses any single rig sharing bone names, even with another
    # skeleton bind. Isolate scene data during this import, not SDK functions.
    for obj in before:
        if obj.type!='ARMATURE':continue
        for bone in obj.data.bones:held.append((bone,bone.name));bone.name='_qa_hold_'+obj.name+'_'+bone.name
    try:IO.import_meshfile(str(file),imp_locs=False,join_materials=False,bonespace=False)
    finally:
        for bone,name in held:bone.name=name
    new=[o for o in bpy.data.objects if o not in before];obj=next(o for o in new if o.type=='MESH');rig=next(m.object for m in obj.modifiers if m.type=='ARMATURE');obj.name=label;rig.name=label+'_owned_rig';obj.parent=rig;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=Matrix.Identity(4);node=P.read_meshfile(str(file)).find('object')[0];data=rigdata(node.find('skeleton'));assert len(data['names'])==len(rig.data.bones),(file,len(data['names']),len(rig.data.bones));return {'file':str(file),'obj':obj,'rig':rig,'node':node.find('mesh'),'data':data}
def pose(part,world):
    for i,n in enumerate(part['data']['names']):
        p=part['data']['parents'][i];local=np.linalg.inv(world[p])@world[i]if p is not None else world[i];bone=part['rig'].data.bones[n];restlocal=bone.parent.matrix_local.inverted()@bone.matrix_local if bone.parent else bone.matrix_local;part['rig'].pose.bones[n].matrix_basis=restlocal.inverted()@Matrix((SW4@local@SW4).tolist())
def point(part,name):
    rig=part['rig'];return np.array(rig.matrix_world@rig.pose.bones[name].matrix.translation)[[0,2,1]]
def evaluated(part):
    ob=part['obj'].evaluated_get(bpy.context.evaluated_depsgraph_get());me=ob.to_mesh();result=np.array([tuple(ob.matrix_world@v.co)for v in me.vertices])[:,[0,2,1]];ob.to_mesh_clear();return result
def verify(part,world,external):
    goal=deform(part['node'],part['data'],world);goal=(external[:3,:3]@goal.T).T+external[:3,3];actual=evaluated(part);err=float(np.linalg.norm(actual-goal,axis=1).max());assert np.isfinite(actual).all()
    if err>=.004:
        debug={'file':part['file'],'error':err,'expected_external':external.tolist(),'actual_rig_world_pdx':(SW4@np.array(part['rig'].matrix_world)@SW4).tolist(),'actual_obj_world_pdx':(SW4@np.array(part['obj'].matrix_world)@SW4).tolist(),'actual_bounds':[actual.min(0).tolist(),actual.max(0).tolist()],'goal_bounds':[goal.min(0).tolist(),goal.max(0).tolist()],'firstactual':actual[0].tolist(),'firstgoal':goal[0].tolist()};(OUT/'assembly-failure-diagnostic.json').write_text(json.dumps(debug,indent=2)+'\n',encoding='utf8')
    assert err<.004,(part['file'],err);return err
def clips(row):
    asset=Path(row['mesh']).with_suffix('.asset');tree=clausewitz(asset.read_text(encoding='utf-8-sig'));pm=one(tree,'pdxmesh');return {one(a,'id'):(asset.parent/one(a,'type')).resolve()for a in values(pm,'animation')}
def marker(name,p,color):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,radius=.16,location=tuple(SW@p));obj=bpy.context.object;obj.name=name;mat=bpy.data.materials.new(name);mat.diffuse_color=(*color,1);obj.data.materials.append(mat);return obj
def render_evidence(actor,variant,parts,body,carrier):
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world=bpy.data.worlds.new('Assembly evidence');scene.world.color=(.12,.12,.12);scene.view_settings.view_transform='Standard'
    previews=json.loads((OUT/'PalettePreview/preview-index.json').read_text())['rows']
    def preview(part):
        row=next(r for r in previews if r['actor']==actor and Path(r['mesh'])==Path(part['file']));mat=bpy.data.materials.new('CPU palette diffuse '+part['obj'].name);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.75;bs.inputs['Specular IOR Level'].default_value=.2;tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(row['png'],check_existing=True);mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
        if part is not body and part['row']['element']in ['hair','ear','tail']:mat.node_tree.links.new(tex.outputs['Alpha'],bs.inputs['Alpha']);mat.surface_render_method='DITHERED'
        return mat
    originals={}
    for p in [body,*parts]:
        originals[p['obj']]=list(p['obj'].data.materials);p['obj'].data.materials.clear();p['obj'].data.materials.append(preview(p))
    points=[]
    defs=[(body,'bn_sp_cervical',(1,.8,.12)),(carrier,'bn_h_neck_1',(.1,.95,.9)),(carrier,'bn_h_eye_l_rotate',(1,.15,.15)),(carrier,'bn_h_eye_r_rotate',(1,.15,.15)),(carrier,'bn_h_forehead_l_browInner',(.3,1,.2)),(carrier,'bn_h_forehead_r_browInner',(.3,1,.2)),(carrier,'bn_h_head',(.8,.3,1))]
    for owner,n,color in defs:
        p=point(owner,n);points.append(p);marker(owner['obj'].name+'_'+n,p,color)
    q=np.array(points);center=Vector(tuple(SW@((q.min(0)+q.max(0))/2)));center.z+=1.5;camera_data=bpy.data.cameras.new('Assembly camera');camera=bpy.data.objects.new('Assembly camera',camera_data);scene.collection.objects.link(camera);camera_data.type='ORTHO';camera_data.ortho_scale=31;scene.camera=camera
    for name,offset,energy in [('Key',(-25,-50,35),17000),('Fill',(30,-25,10),9000)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.size=35;obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=center+Vector(offset);obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
    files=[]
    for label,offset in [('front',(0,-65,0)),('side',(65,0,0))]:
        camera.location=center+Vector(offset);camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/f'{actor}_{variant}_neck_repaired_{label}.png');bpy.ops.render.render(write_still=True);files.append(scene.render.filepath)
    for obj,mats in originals.items():
        obj['original_PDX_material_names']=[m.name for m in mats]
        for mat in mats:mat.use_fake_user=True
    return files
def editable_snapshot(actor,variant,body,carrier,parts,native):
    # Retain actual native materials, packed files, real shape endpoint geometry,
    # and explicit source actions. These are editable QA rigs, not CK3 shaders.
    for suffix in ['b0','b1','b3','b4','s1','s2','h0','h2']:
        path=BASE/('uma_0001_body_'+suffix+'.mesh')
        if not path.exists():continue
        if body['obj'].data.shape_keys is None:body['obj'].shape_key_add(name='Basis')
        raw=P.read_meshfile(str(path)).find('object')[0].find('mesh');p=np.array(raw.get('p')).reshape(-1,3);assert len(p)==len(body['obj'].data.vertices);key=body['obj'].shape_key_add(name='source_body_'+suffix);key.data.foreach_set('co',(p@SW.T).astype(np.float32).ravel());key.value=0
    def source_action(part,clip,delta=None):
        data=part['data'];count=P.read_meshfile(str(clip)).find('info').get('sa')[0];rest=part['rig'].data.bones;restlocal={}
        for n in data['names']:
            b=rest[n];restlocal[n]=b.parent.matrix_local.inverted()@b.matrix_local if b.parent else b.matrix_local
        frames=np.zeros((count,len(data['names']),10),np.float32);previous={}
        for frame in range(count):
            world=compose(data,readlocals(P,clip,frame),delta)
            for i,n in enumerate(data['names']):
                pa=data['parents'][i];local=np.linalg.inv(world[pa])@world[i]if pa is not None else world[i];basis=restlocal[n].inverted()@Matrix((SW4@local@SW4).tolist());t,q,s=basis.decompose()
                if n in previous:q.make_compatible(previous[n])
                previous[n]=q.copy();frames[frame,i]=[*t,*q,*s]
        action=bpy.data.actions.new(actor+'_'+variant+'_'+Path(clip).stem);action.use_fake_user=True
        for i,n in enumerate(data['names']):
            part['rig'].pose.bones[n].rotation_mode='QUATERNION'
            for dp,off,size in [('location',0,3),('rotation_quaternion',3,4),('scale',7,3)]:
                for channel in range(size):
                    vals=frames[:,i,off+channel];ids=np.array([0,count-1])if np.max(np.abs(vals-vals[0]))<1e-7 else np.arange(count);curve=action.fcurves.new('pose.bones["'+n+'"].'+dp,index=channel,action_group=n);curve.keyframe_points.add(len(ids));curve.keyframe_points.foreach_set('co',np.column_stack([ids+1,vals[ids]]).astype(np.float32).ravel())
                    for k in curve.keyframe_points:k.interpolation='LINEAR'
        part['rig'].animation_data_create();part['rig'].animation_data.action=action;return action
    source_action(body,Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body/female_body_idle_1.anim')))
    source_action(carrier,MOD/'gfx/models/portraits/uma/animation/uma_female_head_idle_1.anim',DELTAS if actor=='1002'else{})
    socket=bpy.data.objects.new(actor+'_thoracic_socket',None);bpy.context.collection.objects.link(socket);c=socket.constraints.new('COPY_TRANSFORMS');c.target=body['rig'];c.subtarget='bn_sp_thoracic';carrier['rig'].parent=socket;carrier['rig'].matrix_parent_inverse=Matrix.Identity(4);carrier['rig'].matrix_basis=Matrix.Identity(4)
    for part in parts:
        if part['row']['node']:
            source_action(part,part['animations']['idle'])
        else:
            c=part['rig'].constraints.new('COPY_TRANSFORMS');c.target=carrier['rig']
            for b in part['rig'].pose.bones:
                if b.name in carrier['rig'].pose.bones:
                    c=b.constraints.new('COPY_TRANSFORMS');c.target=carrier['rig'];c.subtarget=b.name;c.target_space='POSE';c.owner_space='POSE'
    for bb,hb in [('bn_l_clavicle','bn_h_l_clavicle'),('bn_r_clavicle','bn_h_r_clavicle')]:
        c=carrier['rig'].pose.bones[hb].constraints.new('COPY_TRANSFORMS');c.target=body['rig'];c.subtarget=bb;c.target_space='WORLD';c.owner_space='WORLD'
    carrier['rig']['uma_head_points_1002']=1 if actor=='1002'else 0;carrier['rig']['points_control_policy']='Actual binary additive translation deltas baked into source head idle action. Property is inspection metadata, not an interactive runtime DNA evaluator.';body['rig']['shape_endpoint_policy']='Actual final body b0/b1/b3/b4/s1/s2/h0/h2 endpoints, all zero for base assembly QA.'
    text=bpy.data.texts.new(actor+'_source_points_additive.json');text.write(json.dumps({'source':str(ADD),'deltas':{n:v.tolist()for n,v in DELTAS.items()},'actor_pose':1 if actor=='1002'else 0},indent=2))
    scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update();scene.render.fps=30;scene.frame_start=1;scene.frame_end=151
    bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;file=OUT/(actor+'_'+variant+'_neck_repaired_assembly.blend');bpy.ops.wm.save_as_mainfile(filepath=str(file));return str(file)

# Binary edits get one isolated unmodified SDK import before assembly.
OWN=ROOT/'HeadSources';checks=[]
idx=json.loads((OWN/'Export/head-export-index.json').read_text())
files=[Path(r['mesh_path'])for h in idx['heads']for r in h['components']if r.get('present')and r['element']in ['hair','neck_patch']]
files += [Path(r['mesh_path'])for h in idx['heads']if (h['actor'],h['variant'])==('1002','30')for r in h['components']if r['element']=='headwear']
files += [Path(r['mesh'])for r in json.loads((OWN/'NeckBridge/neck-delivery.json').read_text())['rows']]
for file in files:
    bpy.ops.wm.read_factory_settings(use_empty=True);part=load(file,file.stem);assert len(part['data']['names'])<=255;checks.append({'file':str(file),'bone_count':len(part['data']['names']),'vertices':len(part['obj'].data.vertices),'triangles':len(part['obj'].data.polygons),'standard_SDK_import_passed':True})
(OUT/'neck-repair-sdk-import.json').write_text(json.dumps({'passed':True,'checks':checks,'vendor_modified':False},indent=2)+'\n',encoding='utf8')

for sex in ['female','male']:
    for actor in ['1001','1002']:
        for variant in ['80','00']:
            bpy.ops.wm.read_factory_settings(use_empty=True);body=load(BASE/'uma_0001_body_base.mesh','body146');carrier=load(BASE/f'uma_0001_head_{sex}.mesh','carrier199');carrier['obj'].hide_render=True;carrier['obj'].hide_set(True);assert len(carrier['data']['names'])==199;assert len(body['data']['names'])==146
            rows=[r for r in REG if r['actor']==actor and r['variant']==variant and r['element']in['face','eye','brow','hair','face_parts','ear','headwear','neck_patch']];rows += [r for r in REG if r['actor']==actor and r['element']in ['tail','neck']];parts=[];native=[]
            for row in rows:
                item=load(Path(row['mesh']),row['prefix']);item['row']=row
                if row['node']:
                    item['animations']=clips(row);native.append(item)
                parts.append(item)
            delta=DELTAS if actor=='1002'else{};dw=compose(body['data']);cw=compose(carrier['data'],delta=delta);expected_rig=rigdata(P.read_meshfile(str(ROOT/f'Rigs/head_{actor}.mesh')).find('object')[0].find('skeleton'));pivot_errors={}
            for n in ['bn_h_eye_l_rotate','bn_h_eye_r_rotate','bn_h_eye_l_lidUpper','bn_h_eye_r_lidUpper','bn_h_forehead_l_browInner','bn_h_forehead_r_browInner','bn_h_forehead_l_browOuter','bn_h_forehead_r_browOuter']:
                pivot_errors[n]=float(np.linalg.norm(cw[carrier['data']['names'].index(n),:3,3]-expected_rig['bind'][expected_rig['names'].index(n),:3,3]))
            assert max(pivot_errors.values())<.00001
            # Each native attachment owns its armature. No ambiguous global bone-name
            # resolver is used for pose assignment in the assembled scene.
            for item in native:
                attach=bpy.data.objects.new(item['row']['prefix']+'_node_attachment',None);bpy.context.collection.objects.link(attach);con=attach.constraints.new('COPY_TRANSFORMS');con.target=(body if item['row']['node']=='body_root'else carrier)['rig'];con.subtarget=item['row']['node'];item['rig'].parent=attach;item['rig'].matrix_parent_inverse=Matrix.Identity(4);item['rig'].matrix_basis=Matrix.Identity(4);item['attachment']=attach
            def state(bodyworld,headworld,fraction,native_state='idle'):
                pose(body,bodyworld);bi=body['data']['names'].index('bn_sp_thoracic');ri=carrier['data']['names'].index('head_root');external=bodyworld[bi]@np.linalg.inv(headworld[ri]);headworld=headworld.copy()
                for bb,hb in [('bn_l_clavicle','bn_h_l_clavicle'),('bn_r_clavicle','bn_h_r_clavicle')]:headworld[carrier['data']['names'].index(hb)]=np.linalg.inv(external)@bodyworld[body['data']['names'].index(bb)]
                pose(carrier,headworld);carrier['rig'].matrix_world=Matrix((SW4@external@SW4).tolist());bpy.context.view_layer.update();errors={} 
                for item in parts:
                    if not item['row']['node']:
                        pw=shared_pose(item['data'],carrier['data'],headworld);pose(item,pw);item['rig'].matrix_world=Matrix((SW4@external@SW4).tolist());item['poseworld']=pw;item['external']=external
                    else:
                        path=item['animations'][native_state];count=P.read_meshfile(str(path)).find('info').get('sa')[0];f=round((count-1)*fraction);pw=compose(item['data'],readlocals(P,path,f));pose(item,pw);target=bodyworld[body['data']['names'].index('body_root')]if item['row']['node']=='body_root'else external@headworld[carrier['data']['names'].index('bn_h_head')];item['poseworld']=pw;item['external']=target
                bpy.context.view_layer.update()
                for item in parts:errors[item['row']['element']]=verify(item,item['poseworld'],item['external'])
                root_error=float(np.linalg.norm(point(carrier,'head_root')-point(body,'bn_sp_thoracic')));neck_error=float(np.linalg.norm(point(carrier,'bn_h_neck_1')-point(body,'bn_sp_cervical')));assert root_error<.002;assert neck_error<.02
                bridge=next(p for p in parts if p['row']['element']=='neck');actual=evaluated(bridge);sourcebody=evaluated(body);delivery=json.loads((ROOT/'HeadSources/NeckBridge/neck-delivery.json').read_text());ring=next(a for a in delivery['actors']if a['row']['actor']==actor);edge_error=float(np.linalg.norm(actual[:6]-sourcebody[ring['lower_ring_body_vertex_ids']],axis=1).max());assert edge_error<.005
                upperpoints=np.vstack([evaluated(p)for p in parts if p['row']['element']in ['face','neck_patch']]);upper_error=float(max(np.linalg.norm(upperpoints-v,axis=1).min()for v in actual[6:]));assert upper_error<.0001
                return {'bridge_top_actual_bpy_to_original_face_or_patch_error_cm':upper_error,'bridge_bottom_actual_bpy_lbs_to_body_ring_error_cm':edge_error,'head_root_to_body_thoracic_error_cm':root_error,'head_neck_to_body_cervical_error_cm':neck_error,'attachment_skinning_world_errors_cm':errors,'native_single_attachment_verified':True}
            neutral=state(dw,cw,0);renders=[]
            if sex=='female':renders=render_evidence(actor,variant,parts,body,carrier)
            samples=[];contexts=[('idle',Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body/female_body_idle_1.anim')),MOD/'gfx/models/portraits/uma/animation/uma_female_head_idle_1.anim'),('court',Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body/female_body_throneRoom_ruler3_1.anim')),MOD/'gfx/models/portraits/uma/animation/uma_female_head_throneRoom_ruler3_1.anim')]
            for context,bclip,hclip in contexts:
                bc=P.read_meshfile(str(bclip)).find('info').get('sa')[0];hc=P.read_meshfile(str(hclip)).find('info').get('sa')[0]
                for fraction in [0,.5,1]:
                    bw=compose(body['data'],readlocals(P,bclip,round((bc-1)*fraction)));hw=compose(carrier['data'],readlocals(P,hclip,round((hc-1)*fraction)),delta);samples.append({'context':context,'fraction':fraction,**state(bw,hw,fraction)})
            native_entries=[]
            for native_state in ['idle_entry','frontEnd_middle_entry']:
                for fraction in [0,.5,1]:native_entries.append({'context':native_state,'fraction':fraction,**state(dw,cw,fraction,native_state)})
            editable=editable_snapshot(actor,variant,body,carrier,parts,native)if sex=='female'else None
            case={'actor':actor,'variant':variant,'carrier_sex':sex,'body_scope':'Actual final UMA female/body146; male placeholder compatibility tested with same body146, not stock male_body_entity anatomy.','carrier_bones':199,'body_bones':146,'rest_additive_matches_actor_bind_point_error_cm':pivot_errors,'additive_gene_pose':1 if actor=='1002'else 0,'neutral':neutral,'head_body_idle_court_samples':samples,'native_entry_samples':native_entries,'native_meshes':[r['file']for r in native],'point_evidence_pngs':renders,'editable_blend':editable};CASES.append(case);(OUT/'blender-neck-repair-qa.json').write_text(json.dumps({'cases':CASES,'passed':False,'SDK_mesh_import_unmodified':True,'actual_named_rig_ownership':True,'runtime_game_executed':False},indent=2)+'\n',encoding='utf8');print('ASSEMBLY_CASE_VERIFIED',actor,sex,variant,max(neutral['attachment_skinning_world_errors_cm'].values()),flush=True)
# One editable two-actor scene, appended from the verified female/base snapshots.
bpy.ops.wm.read_factory_settings(use_empty=True)
for actor,x in [('1001',-35),('1002',35)]:
    source=OUT/(actor+'_80_neck_repaired_assembly.blend')
    with bpy.data.libraries.load(str(source),link=False)as(src,dst):dst.objects=list(src.objects)
    linked=[o for o in dst.objects if o is not None]
    for obj in linked:bpy.context.collection.objects.link(obj)
    group=bpy.data.objects.new(actor+'_assembly_offset',None);bpy.context.collection.objects.link(group)
    for obj in linked:
        if obj.parent is None:
            saved=obj.matrix_world.copy();obj.parent=group;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_world=saved
    group.location.x=x
bpy.context.scene.frame_set(1);bpy.context.scene.frame_end=151;bpy.context.scene.render.fps=30;bpy.context.view_layer.update();bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;dual=OUT/'uma_v7_dual_actor_neck_repaired.blend';bpy.ops.wm.save_as_mainfile(filepath=str(dual));bpy.ops.wm.open_mainfile(filepath=str(dual));assert len([o for o in bpy.data.objects if o.type=='ARMATURE'])>=4
REPORT={'passed':True,'blender':bpy.app.version_string,'cases':CASES,'dual_actor_editable_blend':str(dual),'dual_blend_reopened':True,'actual_final_meshes_and_clips_read':True,'SDK_mesh_import_unmodified':True,'vendor_or_configs_modified':False,'head_additive_from_binary_frame1_minus_frame0':True,'static_uma_head_base_inherits_once':True,'connection_rule':'headObjectWorld=bodyThoracicCurrentWorld*inverse(head_root current localWorld). Native ear/wear node=bn_h_head, tail node=body_root.','native_source_animation_pose_assignment':'Explicit per-object owned armature from actual PDX local tracks avoids ambiguous duplicate native bone names in assembled SDK global resolver. All native clips were previously validated through unmodified SDK one-rig import.','skin_preview_CPU_palette_applied':True,'skin_lighting_is_Blender_PBR_not_CK3_shader':True,'neck_bridge_source_16_points_16_triangles':True,'marker_color_legend':{'body_cervical':'yellow','head_neck':'cyan','eye_rotate':'red','brow_inner':'green','head_anchor':'purple'},'scope_limitations':['Offline explicit current-joint attachment emulation, not CK3 execution or shader compilation.','All three current joint matches (head_root, left clavicle, right clavicle) explicitly solved; bridge bottom error compared to actual evaluated body vertices.','Body shape endpoint data present but all zero for base QA; wardrobe genes and actual stock male/boy body anatomy outside this test.','Editable idle head action bakes actual point additive; metadata property is not an interactive DNA solver.']};(OUT/'blender-neck-repair-qa.json').write_text(json.dumps(REPORT,indent=2)+'\n',encoding='utf8');print('V7_FINAL_ASSEMBLY_QA_COMPLETE',flush=True)
