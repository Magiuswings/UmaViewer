"""Render the actual supplied character's body/head/tail source-reference exports."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

path=Path(sys.argv[sys.argv.index("--")+1]).resolve()
root=path.parent
manifest=json.loads(path.read_text(encoding="utf8"))
character=manifest["characters"][0]
entries=[o for o in manifest["blender_outputs"] if o["category"]=="source_reference" and o["character_id"]==character]
bodies=[o for o in entries if "__body_" in o["file"]]
heads=[o for o in entries if "__head_" in o["file"]]
tails=[o for o in entries if "__tail_" in o["file"]]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
for i,body in enumerate(bodies):
    variant=body["file"].split("bdy"+character+"_")[1].split("__")[0]
    head=next((o for o in heads if "chr"+character+"_"+variant+"__" in o["file"]),heads[0] if heads else None)
    for entry in [body]+([head] if head else [])+tails[:1]:
        with bpy.data.libraries.load(str(root/entry["path"]),link=False) as (src,dest):
            dest.objects=[name for name in src.objects if "Preview light" not in name]
        for obj in dest.objects:
            if obj is None: continue
            scene.collection.objects.link(obj)
            if obj.parent is None: obj.location.x+=(i-(len(bodies)-1)/2)*1.6
            if obj.type=="ARMATURE": obj.hide_render=True
    text=bpy.data.curves.new("Costume label","FONT")
    text.body="costume "+variant
    text.align_x="CENTER"
    text.size=.10
    label=bpy.data.objects.new("Costume label",text)
    scene.collection.objects.link(label)
    label.location=((i-(len(bodies)-1)/2)*1.6,-.05,-.15)
    label.rotation_euler=(1.5708,0,0)
engines=scene.render.bl_rna.properties["engine"].enum_items.keys()
scene.render.engine="BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
scene.world=bpy.data.worlds.new("Preview world")
scene.world.use_nodes=True
scene.world.node_tree.nodes["Background"].inputs[0].default_value=(.12,.12,.12,1)
sun_data=bpy.data.lights.new("Sun","SUN");sun_data.energy=4
sun=bpy.data.objects.new("Sun",sun_data);scene.collection.objects.link(sun)
sun.rotation_euler=(.5,-.5,-.3)
camera_data=bpy.data.cameras.new("Camera")
camera=bpy.data.objects.new("Camera",camera_data);scene.collection.objects.link(camera)
camera.location=(0,-8,1.0)
camera.rotation_euler=(Vector((0,0,.75))-camera.location).to_track_quat("-Z","Y").to_euler()
camera_data.type="ORTHO";camera_data.ortho_scale=max(2,len(bodies)*1.6)
scene.camera=camera
scene.render.resolution_x=1600;scene.render.resolution_y=650;scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.render.filepath=str(root/"preview.png")
bpy.ops.render.render(write_still=True)
print("UMA_REAL_PREVIEW "+scene.render.filepath)
