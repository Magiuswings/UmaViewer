"""Render delivered PDX heads and the two real swim morph endpoints; no source save."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

def frame(objects,output):
    scene=bpy.context.scene
    points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center=(lo+hi)/2
    camera=bpy.data.objects.new('Validation camera',bpy.data.cameras.new('Validation camera'))
    scene.collection.objects.link(camera);scene.camera=camera
    camera.location=center+Vector((0,-4,.1))
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=max(hi.z-lo.z,(hi.x-lo.x)*1.5)*1.15
    for pos,energy in (((3,-4,4),500),((-3,-2,2),250)):
        data=bpy.data.lights.new('Validation light','AREA');data.energy=energy;data.size=4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light)
        light.location=center+Vector(pos);light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('Validation world');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.16,.16,1)
    scene.render.engine='BLENDER_EEVEE_NEXT'
    scene.render.resolution_x=512;scene.render.resolution_y=768;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
    scene.render.filepath=str(output);bpy.ops.render.render(write_still=True)

def main():
    config=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8'))
    assert bpy.app.version[:2]==(4,2)
    out=Path(config['output']);dest=out/'previews';dest.mkdir(exist_ok=True)
    manifest=json.loads((out/'export-manifest.json').read_text(encoding='utf8'))
    for cid,variant in (('1001','30'),('1003','80')):
        bpy.ops.wm.read_factory_settings(use_empty=True);objects=[]
        for item in manifest['components']:
            if item['character_id']!=cid or item['kind']!='head' or item['variant']!=variant or item['category'] not in ('face','eyes','eyebrows','hair','headwear'):continue
            with bpy.data.libraries.load(str(out/item['blend']),link=False) as (source,loaded):
                loaded.objects=[o['name'] for o in item['objects']]
            for obj in loaded.objects:
                bpy.context.scene.collection.objects.link(obj);objects.append(obj)
                rig=next(m.object for m in obj.modifiers if m.type=='ARMATURE')
                if rig.name not in bpy.context.scene.objects:bpy.context.scene.collection.objects.link(rig)
        frame(objects,dest/('chara'+cid+'_head.png'))
    bases=json.loads((out/'body-bases.json').read_text(encoding='utf8'))['bases']
    for base in bases:
        if not base.get('body_profile') or base['body_profile']['costume_id']!='0004':continue
        bpy.ops.wm.open_mainfile(filepath=str(out/base['blend']))
        obj=next(o for o in bpy.data.objects if o.type=='MESH')
        frame([obj],dest/('swim_bust_'+base['bust']+'.png'))
    if (out/'character-body-bindings.json').is_file():
        actors=json.loads((out/'character-body-bindings.json').read_text(encoding='utf8'))['characters']
        for actor in actors:
            if not actor.get('body_type_blend'):continue
            bpy.ops.wm.open_mainfile(filepath=str(out/actor['body_type_blend']))
            obj=next(o for o in bpy.data.objects if o.type=='MESH')
            for key in obj.data.shape_keys.key_blocks:key.value=0
            if actor['body_type_key']!='Basis':obj.data.shape_keys.key_blocks[actor['body_type_key']].value=actor['body_type_key_value']
            for mat in obj.data.materials:
                original=json.loads(mat['uma_original_material'])
                override=next((o for o in actor['diffuse_overrides'] if o['source_material']==original['name']),None)
                if override:
                    bsdf=mat.node_tree.nodes.get('Principled BSDF')
                    bsdf.inputs['Base Color'].links[0].from_node.image=bpy.data.images.load(str(out/override['diffuse']),check_existing=True)
            bpy.context.view_layer.update()
            frame([obj],dest/('body_type_'+actor['body_type']+'.png'))
    print('PDX_PREVIEWS_COMPLETE',flush=True)

if __name__=='__main__':main()
