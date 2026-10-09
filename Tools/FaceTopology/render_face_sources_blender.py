"""Compare raw skin shells to one common-network trial with matched cameras."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--targets',type=Path,required=True);p.add_argument('--source-npz',type=Path);p.add_argument('--target-npz',type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
original=np.load(a.source_npz or a.root/'preview-sources.npz');target=np.load(a.target_npz or a.targets/'face-targets.npz');C=np.array([[-1,0,0],[0,0,-1],[0,1,0]])
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.world=bpy.data.worlds.new('AuditWorld');scene.world.color=(.12,.12,.12)
mat=bpy.data.materials.new('DiagnosticClay');mat.use_nodes=True;bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.6,.62,.65,1);bsdf.inputs['Roughness'].default_value=.8
prefix='original_'if 'original_1001_p'in original.files else''
ids=[id for id in ['1001','1003','1071','1105','2008','9003','9007','npc_000','npc_009']if id in target.files and prefix+id+'_p'in original.files]
for row,id in enumerate(ids):
    for col in range(2):
        points=original[prefix+id+'_p']if col==0 else target[id];faces=original[prefix+id+'_faces']if col==0 else target['faces'];points=points@C.T
        center=(points.min(0)+points.max(0))/2;points-=center
        mesh=bpy.data.meshes.new(id+str(col));mesh.from_pydata(points.tolist(),[],faces[:,::-1].tolist());mesh.update();o=bpy.data.objects.new(id+str(col),mesh);bpy.context.collection.objects.link(o);o.location=(col*.4,0,-row*.35);mesh.materials.append(mat)
        for f in mesh.polygons:f.use_smooth=True
        curve=bpy.data.curves.new(id,'FONT');curve.body=id+(' / source'if col==0 else' / common');curve.size=.02;curve.align_x='CENTER';text=bpy.data.objects.new(id+'label',curve);bpy.context.collection.objects.link(text);text.location=(col*.4,-.1,-row*.35+.17);text.rotation_euler=(np.pi/2,0,0)
bpy.ops.object.camera_add(location=(.2,-5,-1.4));camera=bpy.context.object;camera.rotation_euler=(Vector((.2,0,-1.4))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=3.45;scene.camera=camera
for pos,power,size in [((-.4,-1,1),180,2),((.8,-1,0),100,2),((0,1,1),130,2)]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(Vector((.2,0,-1.4))-o.location).to_track_quat('-Z','Y').to_euler()
scene.render.engine='BLENDER_EEVEE_NEXT';scene.view_settings.view_transform='AgX';scene.render.resolution_x=800;scene.render.resolution_y=2200;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.filepath=str(a.targets/'source-common-front.png');bpy.ops.render.render(write_still=True)
