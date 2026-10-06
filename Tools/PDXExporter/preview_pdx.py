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
    swim=next(g for g in manifest['morph_groups'] if g['category']=='whole_mesh' and 'bdy0004' in g['base_job'])
    for value in (0,1):
        bpy.ops.wm.open_mainfile(filepath=str(out/swim['blend']))
        obj=next(o for o in bpy.data.objects if o.type=='MESH')
        obj.data.shape_keys.key_blocks[swim['targets'][0]['key']].value=value
        bpy.context.view_layer.update()
        frame([obj],dest/('swim_morph_'+str(value)+'.png'))
    print('PDX_PREVIEWS_COMPLETE',flush=True)

if __name__=='__main__':main()
