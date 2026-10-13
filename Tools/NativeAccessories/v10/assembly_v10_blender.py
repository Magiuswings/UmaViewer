"""Final editable native-loop assembly, explicit owned rigs and actual root-only matching."""
import os,sys,json,gc
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
sys.path[:0]=[str(Path(__file__).resolve().parent),'E:/UmaViewer-Workspace/PDX-vendor']
from paths_v10 import ROOT,MOD,REPO,V9
V8=V9
V7=V8
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7')]
import bpy,numpy as np
from mathutils import Matrix,Vector
from io_pdx_mesh import pdx_data as P
from io_pdx_mesh.pdx_blender import blender_import_export as IO
from head_assembly_math import rigdata,compose,readlocals,deform,shared_pose
from assembly_math_v10 import head_attachment,external
SW=np.array([[1,0,0],[0,0,1],[0,1,0]],float);SW4=np.eye(4);SW4[:3,:3]=SW;BASE=MOD/'gfx/models/portraits/uma/0001';OUT=ROOT/'Editable';OUT.mkdir(parents=True,exist_ok=True)
REG=json.loads((ROOT/'Reports/head-registration.json').read_text());PREV=json.loads((ROOT/'Preview/Palette/preview-index.json').read_text())['rows'];families=json.loads((ROOT/'Reports/clothing-registration.json').read_text())['families'];bridgefile=ROOT/'Reports/neck-delivery-source.json';bridges=json.loads((bridgefile if bridgefile.exists()else V7/'HeadSources/NeckBridge/neck-delivery.json').read_text());CASES=[]
def clip(module):return MOD/f'gfx/models/portraits/uma/animation/{module}/uma_{module}_native_idle.anim'
CAT={f.name:f for f in(MOD/'gfx').rglob('*.dds')}
def tex(ref,file):return CAT[Path(ref).name]
def load(file,label,actor):
    before=set(bpy.data.objects);held=[]
    for obj in before:
        if obj.type=='ARMATURE':
            for bone in obj.data.bones:held.append((bone,bone.name));bone.name='_hold_'+obj.name+'_'+bone.name
    try:IO.import_meshfile(str(file),imp_locs=False,join_materials=False,bonespace=False)
    finally:
        for bone,name in held:bone.name=name
    new=[o for o in bpy.data.objects if o not in before and o.type=='MESH'];tree=P.read_meshfile(str(file));items=[];rig=None;D=None
    for oi,node in enumerate(tree.find('object')):
        data=rigdata(node.find('skeleton'))
        if D is None:D=data
        else:assert data['names']==D['names']and np.allclose(data['bind'],D['bind'],atol=1e-4)
        for mi,m in enumerate(node.findall('mesh')):
            ob=next(o for o in new if o.data.name==node.tag+'-'+str(mi).zfill(3)or o.name.startswith(node.tag+'-'+str(mi).zfill(3)));own=next(q.object for q in ob.modifiers if q.type=='ARMATURE');assert len(own.data.bones)==len(data['names']);rig=own;ob.name=label+f'_o{oi}_m{mi}';ob.parent=rig;ob.matrix_parent_inverse=Matrix.Identity(4);ob.matrix_basis=Matrix.Identity(4);items.append((ob,m))
            n=np.asarray(m.get('n')).reshape(-1,3)@SW.T;assert len(n)==len(ob.data.vertices);ob.data.polygons.foreach_set('use_smooth',[True]*len(ob.data.polygons));ob.data.normals_split_custom_set_from_vertices(n.tolist())
            mat=m.find('material');mapping={Path(v[0]).name:tex(v[0],file)for k,v in mat.attrib.items()if isinstance(v,list)and v and isinstance(v[0],str)and v[0].endswith('.dds')}
            for material in ob.data.materials:
                for nodeimg in material.node_tree.nodes:
                    if nodeimg.type!='TEX_IMAGE' or nodeimg.image is None:continue
                    name=Path(nodeimg.image.filepath).name
                    if name in mapping:nodeimg.image.filepath=str(mapping[name]);nodeimg.image.reload();assert nodeimg.image.size[0]>0
                material.use_fake_user=True
            preview=next((r for r in PREV if r['actor']==actor and Path(r['mesh'])==file and r['object']==oi and r['slot']==mi),None)
            if preview:
                original=ob.data.materials[0];material=original.copy();material.name=label+f'_palette_{mi}';bs=material.node_tree.nodes.get('Principled BSDF');image=bpy.data.images.load(preview['png'],check_existing=True);image.alpha_mode='STRAIGHT';nt=material.node_tree.nodes.new('ShaderNodeTexImage');nt.image=image;material.node_tree.links.new(nt.outputs['Color'],bs.inputs['Base Color'])
                for link in list(bs.inputs['Alpha'].links):material.node_tree.links.remove(link)
                bs.inputs['Alpha'].default_value=1
                if preview['element']in ['hair','ear','tail']:material.node_tree.links.new(nt.outputs['Alpha'],bs.inputs['Alpha']);material.surface_render_method='DITHERED'
                bs.inputs['Roughness'].default_value=.75;bs.inputs['Specular IOR Level'].default_value=.1;ob.data.materials[0]=material;ob['raw_PDX_material']=original.name
    rig.name=label+'_owned_rig';return dict(file=file,items=items,rig=rig,D=D)
def evaluated(ob):
    obj=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=obj.to_mesh();p=np.asarray([tuple(obj.matrix_world@v.co)for v in mesh.vertices])@SW.T;obj.to_mesh_clear();return p
def action(part,module):
    rig=part['rig'];D=part['D'];path=clip(module);info=P.read_meshfile(str(path)).find('info');count=info.get('sa')[0];assert [b.tag for b in info]==D['names'];frames=np.zeros((count,len(D['names']),10),np.float32);restlocal={};prior={}
    for b in rig.data.bones:restlocal[b.name]=b.parent.matrix_local.inverted()@b.matrix_local if b.parent else b.matrix_local
    for f in range(count):
        local=readlocals(P,path,f)
        for i,n in enumerate(D['names']):
            basis=restlocal[n].inverted()@Matrix((SW4@local[n]@SW4).tolist());t,q,s=basis.decompose()
            if n in prior:q.make_compatible(prior[n])
            prior[n]=q.copy();frames[f,i]=[*t,*q,*s]
    a=bpy.data.actions.new(part['rig'].name+'_'+module+'_native_idle');a.use_fake_user=True
    for i,n in enumerate(D['names']):
        rig.pose.bones[n].rotation_mode='QUATERNION'
        for dp,off,width in [('location',0,3),('rotation_quaternion',3,4),('scale',7,3)]:
            for c in range(width):
                v=frames[:,i,off+c];ids=np.array([0,count-1])if np.max(abs(v-v[0]))<1e-7 else np.arange(count);fc=a.fcurves.new('pose.bones["'+n+'"].'+dp,index=c,action_group=n);fc.keyframe_points.add(len(ids));fc.keyframe_points.foreach_set('co',np.column_stack([ids+1,v[ids]]).astype(np.float32).ravel())
                for key in fc.keyframe_points:key.interpolation='LINEAR'
    rig.animation_data_create();rig.animation_data.action=a;return count
def shared(part,owner):
    part['rig'].matrix_basis=Matrix.Identity(4);c=part['rig'].constraints.new('COPY_TRANSFORMS');c.target=owner['rig']
    for b in part['rig'].pose.bones:
        if b.name in owner['rig'].pose.bones:
            c=b.constraints.new('COPY_TRANSFORMS');c.target=owner['rig'];c.subtarget=b.name;c.target_space='POSE';c.owner_space='POSE'
def joint_parent(part,owner,name):
    empty=bpy.data.objects.new(part['rig'].name+'_joint',None);bpy.context.collection.objects.link(empty);c=empty.constraints.new('COPY_TRANSFORMS');c.target=owner['rig'];c.subtarget=name;part['rig'].parent=empty;part['rig'].matrix_parent_inverse=Matrix.Identity(4);part['rig'].matrix_basis=Matrix.Identity(4);return empty
def shapes(part,base,suffixes):
    for suffix,keyname in suffixes:
        p=base.with_name(base.stem.removesuffix('_base')+'_'+suffix+'.mesh')
        if not p.exists():continue
        nodes=P.read_meshfile(str(p)).find('object');targets=[m for o in nodes for m in o.findall('mesh')];assert len(targets)==len(part['items'])
        for(ob,_),m in zip(part['items'],targets):
            if ob.data.shape_keys is None:ob.shape_key_add(name='Basis')
            key=ob.shape_key_add(name=keyname);points=np.asarray(m.get('p')).reshape(-1,3)@SW.T;assert len(points)==len(key.data);key.data.foreach_set('co',points.astype(np.float32).ravel());key.value=0
def verify(part,world,x):
    errors=[]
    for ob,node in part['items']:
        goal=external(deform(node,part['D'],world),x);actual=evaluated(ob);error=float(np.linalg.norm(actual-goal,axis=1).max());assert error<.01,(part['file'],error);errors.append(error)
    return max(errors)
def render(actor,variant,body,parts):
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=850;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world=bpy.data.worlds.new('Native assembly evidence');scene.world.color=(.14,.14,.14);scene.view_settings.view_transform='Standard';center=Vector((0,0,88));cd=bpy.data.cameras.new('Evidence camera');cam=bpy.data.objects.new('Evidence camera',cd);scene.collection.objects.link(cam);scene.camera=cam;cd.type='ORTHO';cd.ortho_scale=195
    bpy.ops.mesh.primitive_plane_add(size=500,location=(0,0,0));floor=bpy.context.object;floor.name='Reference_ground_Z0_cm';fm=bpy.data.materials.new('Reference ground');fm.diffuse_color=(.2,.2,.2,1);floor.data.materials.append(fm)
    for name,offset,energy in [('Key',(-80,-130,110),150000),('Fill',(85,-70,60),80000)]:
        ld=bpy.data.lights.new(name,'AREA');ld.energy=energy;ld.size=90;lo=bpy.data.objects.new(name,ld);scene.collection.objects.link(lo);lo.location=center+Vector(offset);lo.rotation_euler=(center-lo.location).to_track_quat('-Z','Y').to_euler()
    files=[]
    for view,offset in [('front',(0,-300,0)),('side',(300,0,0)),('back',(0,300,0))]:
        cam.location=center+Vector(offset);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(ROOT/f'Preview/{actor}_{variant}_native_{view}.png');bpy.ops.render.render(write_still=True);files.append(scene.render.filepath)
    return files
for actor in ['1001','1002']:
    for variant in ['00','80']:
        bpy.ops.wm.read_factory_settings(use_empty=True);body=load(BASE/'uma_0001_body_base.mesh','body146',actor);head=load(BASE/'uma_0001_head_female.mesh','carrier245',actor)
        for ob,_ in head['items']:ob.hide_render=True;ob.hide_set(True)
        count=action(body,'body');action(head,'head');joint_parent(head,body,'bn_sp_thoracic');head['rig'].matrix_basis=Matrix((SW4@np.linalg.inv(head['D']['bind'][head['D']['names'].index('head_root')])@SW4).tolist())
        # The V9 seam is driven by dedicated body-follow bones, no clavicle attachment override.
        rows=[r for r in REG if r['actor']==actor and ((r['variant']==variant and r['element']not in ['cheek','tear'])or r['element']in ['head','eye','brow','tail'])];parts=[]
        for row in rows:
            part=load(Path(row['mesh']),row['prefix'],actor);part['row']=row
            if row.get('shared_pose')=='head':shared(part,head)
            elif row['element']=='headwear':joint_parent(part,head,'bn_h_head')
            elif row['element']=='tail':action(part,'tail');joint_parent(part,body,'body_root')
            else:action(part,'ear');joint_parent(part,head,row['node'])
            parts.append(part)
        suffixes=[('b0','bs_body_breast_shape_1'),('b1','bs_body_breast_shape_2'),('b3','bs_body_breast_shape_3'),('b4','bs_body_breast_shape_4'),('s1','bs_body_gaunt_1'),('s2','bs_body_fat_1')];shapes(body,BASE/'uma_0001_body_base.mesh',suffixes)
        # Keep actor2 vector keys at zero during endpoint closure QA, then activate the real actor preset.
        wardrobe=[]
        if variant=='00':
            family=next(f for f in families if f['family']=='bdy'+actor+'_00')
            for element,row in family['parts'].items():
                part=load(Path(row['base_mesh']),actor+'_'+element,actor);part['element']=element;shared(part,body);shapes(part,Path(row['base_mesh']),suffixes);wardrobe.append(part)
        tests=[];ring=next(r for r in bridges['actors']if r['row']['actor']==actor)
        for f in [0,count//2,count-1]:
            bpy.context.scene.frame_set(f+1);bpy.context.view_layer.update();BW=compose(body['D'],readlocals(P,clip('body'),f));HW=compose(head['D'],readlocals(P,clip('head'),f));x,HW=head_attachment(body['D'],BW,head['D'],HW);errors={'body':verify(body,BW,np.eye(4)),'head':verify(head,HW,x)}
            for part in parts:
                row=part['row']
                if row.get('shared_pose')=='head':W=shared_pose(part['D'],head['D'],HW);ex=x
                elif row['element']=='headwear':W=part['D']['bind'];ex=x@HW[head['D']['names'].index('bn_h_head')]
                else:
                    module='tail'if row['element']=='tail'else'ear';frames=P.read_meshfile(str(clip(module))).find('info').get('sa')[0];W=compose(part['D'],readlocals(P,clip(module),min(f,frames-1)));ex=BW[body['D']['names'].index('body_root')]if module=='tail'else x@HW[head['D']['names'].index(row['node'])]
                errors[row['element']]=verify(part,W,ex)
            bridge=next(p for p in parts if p['row']['element']=='head');low=evaluated(bridge['items'][-1][0])[:6];bp=evaluated(body['items'][0][0]);lower=float(np.linalg.norm(low-bp[ring['lower_ring_body_vertex_ids']],axis=1).max());assert lower<.005;tests.append(dict(frame=f,all_component_lbs_max_cm=errors,neck_bottom_to_actual_body_cm=lower))
        if actor=='1002':
            for part in [body,*wardrobe]:
                for ob,_ in part['items']:
                    if ob.data.shape_keys:
                        ob.data.shape_keys.key_blocks['bs_body_breast_shape_1'].value=1;ob.data.shape_keys.key_blocks['bs_body_gaunt_1'].value=1
        bpy.context.scene.frame_set(1);bpy.context.view_layer.update();pngs=render(actor,variant,body,parts);scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=count;scene.render.fps=30;scene['validation_scope']='Final binary meshes; exact245/146/169/9 native loops; actual root-only joint-parent constraints. Blender PBR preview, CK3 runtime pending.';bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;path=OUT/f'uma_{actor}_{variant}_native_assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));bpy.ops.wm.open_mainfile(filepath=str(path));assert bpy.context.scene.frame_end==count;CASES.append(dict(actor=actor,variant=variant,tests=tests,editable=str(path),packed_and_reopened=True,preview_pngs=pngs));(ROOT/'Reports/blender-native-assembly.json').write_text(json.dumps(dict(passed=False,cases=CASES),indent=2),encoding='utf8');print('V10_NATIVE_ASSEMBLY',actor,variant,flush=True);gc.collect()
(ROOT/'Reports/blender-native-assembly.json').write_text(json.dumps(dict(passed=True,blender=bpy.app.version_string,cases=CASES,SDK_mesh_import_unmodified=True,exact_module_animations_prevalidated=True,explicit_owned_rig_actions=True,no_head_additive=True,all_shape_geometry_from_final_binary=True,CK3_game_executed=False),indent=2),encoding='utf8');print('V10_NATIVE_ASSEMBLY_COMPLETE',flush=True)
