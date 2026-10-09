"""Render front/profile/wire views of the actual selected common face."""
import argparse,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--targets',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);d=np.load(a.targets/'face-targets.npz');C=np.array([[-1,0,0],[0,0,-1],[0,1,0]])
points=d['Basis']@C.T;center=(points.min(0)+points.max(0))*.5;points-=center;faces=d['faces'][:,::-1]
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.world=bpy.data.worlds.new('FaceAudit');scene.world.color=(.12,.12,.12)
mat=bpy.data.materials.new('NeutralFace');mat.use_nodes=True;shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=(.58,.60,.63,1);shader.inputs['Roughness'].default_value=.8
wire=bpy.data.materials.new('NetworkEdges');wire.diffuse_color=(.02,.025,.03,1)
for i,label in enumerate(('Common network / front','Common network / profile',f'{len(points)} vertices / {len(faces)} triangles')):
    mesh=bpy.data.meshes.new(label);mesh.from_pydata(points.tolist(),[],faces.tolist());mesh.update();obj=bpy.data.objects.new(label,mesh);bpy.context.collection.objects.link(obj);obj.location.x=i*.28;mesh.materials.append(mat)
    for poly in mesh.polygons:poly.use_smooth=True
    if i==1:obj.rotation_euler.z=np.pi/2
    if i==2:mesh.materials.append(wire);m=obj.modifiers.new('Vertex network','WIREFRAME');m.thickness=.00035;m.use_replace=False;m.material_offset=1
    c=bpy.data.curves.new(label,'FONT');c.body=label;c.size=.014;c.align_x='CENTER';o=bpy.data.objects.new(label+'text',c);bpy.context.collection.objects.link(o);o.location=(i*.28,-.03,.14);o.rotation_euler=(np.pi/2,0,0)
bpy.ops.object.camera_add(location=(.28,-2,.015));cam=bpy.context.object;cam.rotation_euler=(Vector((.28,0,.015))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.86;scene.camera=cam
for pos,energy,size in [((-.3,-1,.7),65,1),((.8,-1,.3),30,1)]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=energy;o.data.size=size;o.rotation_euler=(Vector((.28,0,0))-o.location).to_track_quat('-Z','Y').to_euler()
scene.render.engine='BLENDER_EEVEE_NEXT';scene.view_settings.view_transform='AgX';scene.render.resolution_x=1500;scene.render.resolution_y=650;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.filepath=str(a.targets/'common-face-network.png');bpy.ops.render.render(write_still=True)
