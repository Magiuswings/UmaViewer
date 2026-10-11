import os
import bpy,json,numpy as np
from pathlib import Path
from mathutils import Vector
R=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));O=R/'clothing-parts';d=json.loads((R/'parsed/body.json').read_text());m=d['meshes'][0];p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);p=p[:,[0,2,1]];p[:,0]*=-1;p[:,1]*=-1;tri=np.array(m['faces'][0]['triangles']).reshape(-1,3);uv=np.array([[v[k]for k in 'xy']for v in m['uvs'][0]['values']]);bpy.ops.wm.read_factory_settings(use_empty=True);mat=bpy.data.materials.new('source atlas');mat.use_nodes=True;n=mat.node_tree.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(R/'parsed/resources/textures/tex_bdy1001_00_diff__3e2e906bee.png'));mat.node_tree.links.new(n.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
for col in [0,1]:
 pp=p.copy()
 if col:pp=pp[:,[1,0,2]];pp[:,0]*=-1
 pp[:,0]+=col*2;mesh=bpy.data.meshes.new('source');mesh.from_pydata(pp.tolist(),[],tri[:,::-1].tolist());mesh.update();obj=bpy.data.objects.new('source',mesh);bpy.context.collection.objects.link(obj);mesh.materials.append(mat);layer=mesh.uv_layers.new(name='UV0')
 for l in mesh.loops:layer.data[l.index].uv=uv[l.vertex_index]
 for f in mesh.polygons:f.use_smooth=True
bpy.ops.object.camera_add(location=(1,-7,.8));cam=bpy.context.object;cam.rotation_euler=(Vector((1,0,.8))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=3.8;bpy.context.scene.camera=cam
for pos,energy in [((0,-4,4),600),((3,2,3),500)]:
 bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=energy;l.data.size=4;l.rotation_euler=(Vector((1,0,.8))-l.location).to_track_quat('-Z','Y').to_euler()
s=bpy.context.scene;s.world=bpy.data.worlds.new('sourceworld');s.world.color=(.12,.12,.12);s.render.engine='BLENDER_EEVEE_NEXT';s.render.resolution_x=1500;s.render.resolution_y=900;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.filepath=str(O/'clothing-native-source-front-side.png');s.view_settings.view_transform='Standard';bpy.ops.render.render(write_still=True)
