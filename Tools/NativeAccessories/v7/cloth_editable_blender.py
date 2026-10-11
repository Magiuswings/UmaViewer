import os
"""One editable project per family from actual final PDX: source points, all parts, six BS, exact-bind references."""
import sys,json,os,gc
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));sys.path[:0]=[str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'),str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/NativeBody')];from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());D=np.array([[1,0,0,0],[0,0,1,0],[0,1,0,0],[0,0,0,1]],float);E=np.diag([-1,1,-1,1]);outputs=[]
def build_rig(sk,name,collection):
 arm=bpy.data.armatures.new(name);rig=bpy.data.objects.new(name,arm);collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);world=np.linalg.inv(inverse_bind(sk));bpy.ops.object.mode_set(mode='EDIT');names=[b.tag for b in sk]
 for i,n in enumerate(names):
  bone=arm.edit_bones.new(n);matrix=D@world[i]@D;frame=Matrix(matrix.tolist());rot=frame.to_quaternion().to_matrix().to_4x4();rot.translation=frame.translation;bone.matrix=rot;bone.length=1
 for i,node in enumerate(sk):
  if node.attrib.get('pa'):arm.edit_bones[node.tag].parent=arm.edit_bones[names[node.attrib['pa'][0]]]
 bpy.ops.object.mode_set(mode='OBJECT');rig['pdx_exact_skeleton']=json.dumps([dict(name=b.tag,attributes=b.attrib)for b in sk]);rig['point_policy']='Exact source-point translations preserved; edit-bone quaternion frame cannot carry shear, original full affine inverse-bind is retained above';rig.show_in_front=True;return rig,names

for fi,family in enumerate(reg['families']):
 bpy.ops.wm.read_factory_settings(use_empty=True);main=bpy.context.scene.collection;first=next(iter(family['parts'].values()));tree=pd.read_meshfile(first['base_mesh']);sk=tree.find('object')[0].find('skeleton');rig,names=build_rig(sk,family['family']+'_fittedBodyRig',main);allobjects=[]
 for category,part in family['parts'].items():
  base=pd.read_meshfile(part['base_mesh']);targets={key:pd.read_meshfile(file)for key,file in part['shape_targets'].items()}
  for oi,obj in enumerate(base.find('object')):
   for mi,node in enumerate(obj.findall('mesh')):
    p=np.array(node.attrib['p']).reshape(-1,3)[:,[0,2,1]];tri=np.array(node.attrib['tri']).reshape(-1,3)[:,::-1];mesh=bpy.data.meshes.new(obj.tag+f'_slot{mi}');mesh.from_pydata(p.tolist(),[],tri.tolist());mesh.update();object=bpy.data.objects.new(mesh.name,mesh);main.objects.link(object);allobjects.append(object);object['wardrobe_group']=category;object['source_pdx']=part['base_mesh'];object['source_vertex_map']=json.dumps(part['source_maps'][sum(len(o.findall('mesh'))for o in list(base.find('object'))[:oi])+mi]);uv=np.array(node.attrib['u0']).reshape(-1,2);layer=mesh.uv_layers.new(name='UV0')
    for loop in mesh.loops:layer.data[loop.index].uv=(uv[loop.vertex_index,0],1-uv[loop.vertex_index,1])
    for face in mesh.polygons:face.use_smooth=True
    normals=np.array(node.attrib['n']).reshape(-1,3)[:,[0,2,1]];mesh.normals_split_custom_set_from_vertices(normals.tolist());ix=np.array(node.find('skin').attrib['ix']).reshape(-1,4);w=np.array(node.find('skin').attrib['w']).reshape(-1,4)
    for boneid in np.unique(ix[w>0]):
     group=object.vertex_groups.new(name=names[int(boneid)]);ids,slots=np.where((ix==boneid)&(w>0));bins={}
     for i,j in zip(ids,slots):bins.setdefault(round(float(w[i,j]),3),[]).append(int(i))
     for weight,vertices in bins.items():group.add(vertices,weight,'REPLACE')
    bpy.context.view_layer.objects.active=object;bpy.ops.object.select_all(action='DESELECT');object.select_set(True);bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL',lock_active=False);mod=object.modifiers.new('Body shared pose','ARMATURE');mod.object=rig;object.parent=rig;basis=object.shape_key_add(name='Basis')
    for key,t in targets.items():
     point=np.array(t.find('object')[oi].findall('mesh')[mi].attrib['p']).reshape(-1,3)[:,[0,2,1]];shape=object.shape_key_add(name=key);shape.data.foreach_set('co',point.astype(np.float32).ravel());shape.relative_key=basis;shape.value=0
    material=node.find('material');texpath=str(Path(part['base_mesh']).parent/material.attrib['diff'][0]);mat=bpy.data.materials.get(Path(texpath).stem)
    if mat is None:
     mat=bpy.data.materials.new(Path(texpath).stem);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.8;tx=mat.node_tree.nodes.new('ShaderNodeTexImage');tx.image=bpy.data.images.load(texpath,check_existing=True);mat.node_tree.links.new(tx.outputs['Color'],bs.inputs['Base Color']);mat.node_tree.links.new(tx.outputs['Alpha'],bs.inputs['Alpha']);mat['shader']=material.attrib['shader'][0]
    mesh.materials.append(mat)
 # Full original source hierarchy is an editable hidden T-pose reference, not another runtime rig.
 refs=bpy.data.collections.new('NATIVE_SOURCE_REFERENCE_DO_NOT_EXPORT');main.children.link(refs);source=json.loads(Path(family['source_snapshot']).read_text());arm=bpy.data.armatures.new('OriginalNativeSource');native=bpy.data.objects.new('OriginalNativeSource',arm);refs.objects.link(native);bpy.context.view_layer.objects.active=native;bpy.ops.object.select_all(action='DESELECT');native.select_set(True);bpy.ops.object.mode_set(mode='EDIT');byid={};used=set()
 for b in source['bones']:
  name=b['name'];suffix=1
  while name in used:name=b['name']+'_'+str(suffix);suffix+=1
  used.add(name);byid[b['id']]=name;bone=arm.edit_bones.new(name);m=E@np.array(b['matrix']).reshape(4,4)@E;m[:3,3]*=100;frame=Matrix(m.tolist());rotation=frame.to_quaternion().to_matrix().to_4x4();rotation.translation=frame.translation;bone.matrix=rotation;bone.length=1
 for b in source['bones']:
  if b.get('parent'):arm.edit_bones[byid[b['id']]].parent=arm.edit_bones[byid[b['parent']]]
 bpy.ops.object.mode_set(mode='OBJECT');native['source_snapshot']=family['source_snapshot'];native['original_skin_weights']=family['source_points'];refs.hide_viewport=True;refs.hide_render=True;rig['source_points']=family['source_points'];rig['body_clothed_fixed']=False;rig.data.pose_position='REST';bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01;bpy.context.preferences.filepaths.save_version=0;bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;dest=Path(family['directory'])/Path(family['asset_path']).with_suffix('.blend').name;bpy.ops.wm.save_as_mainfile(filepath=str(dest));outputs.append(dict(family=family['family'],file=str(dest),fitted_bones=len(sk),source_reference_bones=len(source['bones']),objects=len(allobjects),shape_keys_per_object=7,exact_bind_reference=True,body_clothed_fixed=False));print('WARDROBE_EDITABLE',fi+1,'/',len(reg['families']),family['family'],flush=True);gc.collect()
(R/'Reports/clothing-editable-projects.json').write_text(json.dumps(outputs,indent=2),encoding='utf8');print('EDITABLE_ALL_COMPLETE',len(outputs),flush=True)
