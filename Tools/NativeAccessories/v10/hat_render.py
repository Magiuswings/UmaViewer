import os,sys,json
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import bpy,numpy as np
from mathutils import Vector
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,readlocals,compose,shared_pose,deform
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V10');BASE=V/'UMA-V10/gfx/models/portraits/uma';shared=os.environ.get('UMA_HAT_SHARED')=='1';O=V/'HatRepair'/('SharedBody'if shared else'');R=O/'Renders';R.mkdir(parents=True,exist_ok=True);P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');rows=json.loads((V/'Reports/clothing-registration.json').read_text())['families'];rep=json.loads((O/('hat-shared-body.json'if shared else'hat-repair.json')).read_text(encoding='utf-8-sig'))
bodyo=P.read_meshfile(str(BASE/'0001/uma_0001_body_base.mesh')).find('object')[0];B=rigdata(bodyo.find('skeleton'));BW=compose(B,readlocals(P,BASE/'animation/body/uma_body_native_idle.anim',0));headbase=BASE/'0001/uma_0001_head_female.mesh';head=P.read_meshfile(str(headbase)).find('object')[0];H=rigdata(head.find('skeleton'));HW=compose(H,readlocals(P,BASE/'animation/head/uma_head_native_idle.anim',0));ext=BW[B['names'].index('bn_sp_thoracic')]@np.linalg.inv(HW[H['names'].index('head_root')]);missing=[]
def instantiate(file,carrier=None,cw=None,external=None):
 objects=[];file=Path(file)
 for o in P.read_meshfile(str(file)).find('object'):
  sk=o.find('skeleton');rig=rigdata(sk)if sk is not None else None
  for slot,n in enumerate(o.findall('mesh')):
   p=deform(n,rig,shared_pose(rig,carrier,cw))if carrier is not None else np.array(n.get('p')).reshape(-1,3)
   if external is not None:p=p@external[:3,:3].T+external[:3,3]
   tri=np.array(n.get('tri')).reshape(-1,3);mesh=bpy.data.meshes.new(o.tag+str(slot));mesh.from_pydata(p[:,[0,2,1]].tolist(),[],tri[:,::-1].tolist());mesh.update();ob=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(ob);objects.append(ob);uv=np.array(n.get('u0')).reshape(-1,2);layer=mesh.uv_layers.new(name='UV0')
   for poly in mesh.polygons:
    for loop in poly.loop_indices:layer.data[loop].uv=(uv[mesh.loops[loop].vertex_index,0],1-uv[mesh.loops[loop].vertex_index,1])
   material=bpy.data.materials.new(mesh.name);material.use_nodes=True;material.diffuse_color=(.6,.63,.7,1);bs=material.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.7;diff=n.find('material').get('diff')[0];texture=Path(diff);texture=texture if texture.is_absolute()else file.parent/texture
   if not texture.exists():
    for folder in [BASE/'0001',BASE/'0001/shared',BASE/'1001',BASE/'1002']:
     candidate=folder/Path(diff).name
     if candidate.exists():texture=candidate;break
   if texture.exists():
    tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(texture),check_existing=True);material.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
   else:missing.append(str(texture))
   mesh.materials.append(material)
 return objects
scene=bpy.context.scene;bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.device='CPU';scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=850;scene.render.resolution_y=950;scene.render.resolution_percentage=100;scene.world.color=(.35,.35,.35);scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='PNG'
for location,energy,size in [((90,-120,210),1300,160),((-80,50,170),900,120)]:
 data=bpy.data.lights.new('softbox','AREA');data.energy=energy*100;data.shape='DISK';data.size=size;ob=bpy.data.objects.new('softbox',data);scene.collection.objects.link(ob);ob.location=location;ob.rotation_euler=(Vector((0,0,145))-ob.location).to_track_quat('-Z','Y').to_euler()
camera=bpy.data.cameras.new('camera');cam=bpy.data.objects.new('camera',camera);scene.collection.objects.link(cam);scene.camera=cam;camera.type='ORTHO';camera.ortho_scale=70
baseobjs=instantiate(BASE/'1001/uma_1001_head_00.mesh',H,HW,ext)
for result in rep['results']:
 if os.environ.get('UMA_HAT_RENDER_FAMILY')and result['family']!=os.environ['UMA_HAT_RENDER_FAMILY']:continue
 family=result['family'];r=next(r for r in rows if r['family']==family);hat=instantiate(result['candidate_base'],B,BW)if shared else instantiate(result['candidate_base'],H,HW,ext);clothes=instantiate(r['parts']['clothes']['base_mesh'],B,BW);headorigin=(ext@HW[H['names'].index('bn_h_head')])[:3,3];target=Vector((headorigin[0],headorigin[2],headorigin[1]-5))
 for label,delta in [('front',(0,-170,4)),('side',(170,0,4))]:
  cam.location=target+Vector(delta);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(R/f'{family}_{label}.png');bpy.ops.render.render(write_still=True)
 for ob in hat+clothes:bpy.data.objects.remove(ob,do_unlink=True)
print('HAT_RENDER_DONE',missing,flush=True);(R/'render-report.json').write_text(json.dumps({'blender':bpy.app.version_string,'frame':0,'source_native_idle':True,'candidate_static_head_attachment':not shared,'candidate_native_head_semantic_shared_body':shared,'diffuse_only_approximation_not_ck3_shader':True,'body_clothing_unchanged':'real V10 clothes mapped to real body idle','missing_diffuse':missing,'renders':[str(p)for p in R.glob('*.png')]},indent=2)+'\n',encoding='utf-8-sig')
