"""Blender4.2 + unmodified IO PDX Mesh: independent actual final rig/motion imports."""
import os,sys,json,gc,hashlib
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
sys.path[:0]=[str(Path(__file__).resolve().parent),'E:/UmaViewer-Workspace/PDX-vendor']
from paths_v9 import ROOT,MOD,REPO
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7')]
import bpy,numpy as np
from io_pdx_mesh import pdx_data as P
from io_pdx_mesh.pdx_blender import blender_import_export as IO
from head_assembly_math import rigdata,compose,readlocals,deform
from mathutils import Matrix
SW=np.array([[1,0,0],[0,0,1],[0,1,0]],float);SW4=np.eye(4);SW4[:3,:3]=SW
out=ROOT/'Reports';checks=[]
CAT={f.name:f for f in(MOD/'gfx').rglob('*.dds')}
def load(file):
    bpy.ops.wm.read_factory_settings(use_empty=True);IO.import_meshfile(str(file),imp_locs=False,join_materials=False,bonespace=False);tree=P.read_meshfile(str(file));obj=tree.find('object')[0];rigdata_=rigdata(obj.find('skeleton'));meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];rig=next(m.object for m in meshes[0].modifiers if m.type=='ARMATURE');
    for meshob in meshes:
        for mat in meshob.data.materials:
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE'and node.image and Path(node.image.filepath).name in CAT:
                    node.image.filepath=str(CAT[Path(node.image.filepath).name]);node.image.reload()
    assert len(rig.data.bones)==len(rigdata_['names']);assert {b.name for b in rig.data.bones}==set(rigdata_['names']);return tree,obj,rigdata_,meshes,rig
def actual(obj):
    ob=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ob.to_mesh();p=np.array([tuple(ob.matrix_world@v.co)for v in mesh.vertices]);ob.to_mesh_clear();return p
modules=[('body',MOD/'gfx/models/portraits/uma/0001/uma_0001_body_base.mesh'),('head',MOD/'gfx/models/portraits/uma/0001/uma_0001_head_female.mesh'),('ear',MOD/'gfx/models/portraits/uma/1001/uma_1001_ear_00.mesh'),('tail',MOD/'gfx/models/portraits/uma/1001/uma_1001_tail_base.mesh'),('ear_1002_00',MOD/'gfx/models/portraits/uma/1002/uma_1002_ear_00.mesh')]
for module,file in modules:
    clip_module='ear'if module=='ear_1002_00'else module
    tree,node,D,objects,rig=load(file);clip=MOD/f'gfx/models/portraits/uma/animation/{clip_module}/uma_{clip_module}_native_idle.anim';info=P.read_meshfile(str(clip)).find('info');assert info.get('j')[0]==len(rig.data.bones);assert [b.tag for b in info]==D['names'];IO.import_animfile(str(clip));count=info.get('sa')[0];samples=[]
    for frame in sorted({0,count//2,count-1}):
        bpy.context.scene.frame_set(frame+1);bpy.context.view_layer.update();world=compose(D,readlocals(P,clip,frame));goal=deform(node.find('mesh'),D,world)@SW.T;got=actual(objects[0]);assert got.shape==goal.shape;error=float(np.linalg.norm(got-goal,axis=1).max());assert error<.005,(module,frame,error);samples.append(dict(frame=frame,max_lbs_error_cm=error))
    checks.append(dict(module=module,mesh=str(file),mesh_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),animation=str(clip),animation_sha256=hashlib.sha256(clip.read_bytes()).hexdigest(),bones=len(rig.data.bones),frames=count,SDK_animation_import_unmodified=True,exact_all_joint_table=True,samples=samples));print('V9_SDK_NATIVE_MODULE',module,len(rig.data.bones),count,samples,flush=True);gc.collect()
# Static shared accessories keep their own inverse binds, while their current pose is owned by the carrier.
registry=json.loads((ROOT/'Reports/head-registration.json').read_text());static=[]
for row in registry:
    if row.get('shared_pose')!='head' or row['variant']not in ['00','80','base']or row['element']not in ['head','eye','brow','hair']:continue
    file=Path(row['mesh']);tree,node,D,objects,rig=load(file);points=np.array([tuple(rig.data.bones[n].matrix_local.translation)for n in D['names']]);error=float(np.linalg.norm(points-D['bind'][:,:3,3]@SW.T,axis=1).max());assert error<.005;(static.append(dict(actor=row['actor'],element=row['element'],variant=row['variant'],bones=len(D['names']),bind_import_max_error_cm=error,mesh=str(file))));gc.collect()
for actor in ['1001','1002']:
    file=MOD/f'gfx/models/portraits/uma/{actor}/uma_{actor}_clothes_00_base.mesh'
    if not file.exists():
        file=next((MOD/f'gfx/models/portraits/uma/{actor}').glob('*clothes*_base.mesh'))
    load(file)
report=dict(passed=True,blender=bpy.app.version_string,modules=checks,static_head_components=static,SDK_modified=False,all_module_counts_exact=True,CK3_game_executed=False)
(out/'blender-sdk-native-validation.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V9_BLENDER_SDK_NATIVE_COMPLETE',flush=True)
