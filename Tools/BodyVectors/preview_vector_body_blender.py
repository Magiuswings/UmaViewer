"""Render the saved single-variable body endpoints for a compact diagnostic sheet."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

def camera(name,position,target):
    data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
    obj.location=position;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler();data.type='ORTHO';data.ortho_scale=1.66;bpy.context.scene.camera=obj
    return obj

def main():
    p=argparse.ArgumentParser();p.add_argument('--delivery',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);args.output.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(args.delivery/'uma_common_body_vectors.blend'))
    body=next(o for o in bpy.data.objects if o.type=='MESH');keys=body.data.shape_keys.key_blocks
    for o in bpy.data.objects:
        if o.type=='ARMATURE':o.hide_render=True
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.eevee.taa_render_samples=16
    scene.render.resolution_x=600;scene.render.resolution_y=600;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.world=bpy.data.worlds.new('Diagnostic World');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.055,.055,.065,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
    for name,location,power,size in (('Key',(-2,-3,3),400,3),('Fill',(2,-1,1.5),180,3),('Back',(0,2,3),240,2)):
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=location;obj.rotation_euler=(Vector((0,0,.7))-obj.location).to_track_quat('-Z','Y').to_euler()
    cam=camera('Front',(0,-4,.75),(0,0,.75));scene.view_settings.view_transform='AgX'
    records=[]
    for name in ('height_0','height_1','height_2','shape_0','shape_1','shape_2','bust_0','bust_1','bust_2','bust_3','bust_4'):
        for k in keys:k.value=0
        keys[name].value=1;bpy.context.view_layer.update();scene.render.filepath=str(args.output/(name+'.png'));bpy.ops.render.render(write_still=True)
        records.append(dict(key=name,image=name+'.png',view='front',default_other_parameters=dict(height=1,shape=0,bust=2)))
    for k in keys:k.value=0
    cam.location=(0,4,.75);cam.rotation_euler=(Vector((0,0,.75))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(args.output/'basis_back.png');bpy.ops.render.render(write_still=True)
    records.append(dict(key='Basis',image='basis_back.png',view='back'))
    (args.output/'preview-manifest.json').write_text(json.dumps(dict(records=records,source_blend=str(args.delivery/'uma_common_body_vectors.blend'),source_blend_not_saved_or_changed=True,material='Actual packed source-completed diffuse via Blender Principled preview, not CK3 runtime lighting'),ensure_ascii=False,indent=2),encoding='utf8')
    print('VECTOR_PREVIEW_COMPLETE',len(records),flush=True)

if __name__=='__main__':main()
