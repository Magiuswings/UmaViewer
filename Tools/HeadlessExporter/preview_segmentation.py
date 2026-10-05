"""Render source and broad apparel groups side by side for a supplied character."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("manifest", type=Path)
parser.add_argument("--character", required=True)
parser.add_argument("--variant", required=True)
parser.add_argument("--shared-body", help="Full generic prefab identifier, e.g. bdy0004_00_00_1_0_2")
args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
root = args.manifest.resolve().parent
manifest = json.loads(args.manifest.read_text(encoding="utf8"))
jobs = manifest["jobs"]
body = next(j for j in jobs if j["kind"] == "body" and (
    j["name"].endswith("body_"+args.shared_body) if args.shared_body else
    j["character_id"] == args.character and j["name"].endswith("_"+args.variant)))
head = next((j for j in jobs if j["kind"] == "head" and j["character_id"] == args.character and j["name"].endswith("_"+args.variant)), None)
tails = [j for j in jobs if j["kind"] == "tail" and j["character_id"] == args.character]
sources = [body]+([head] if head else [])
entries = manifest["blender_outputs"]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
for column, category in enumerate(("source_reference", "clothing", "footwear", "headwear", "hair")):
    selected = [e for e in entries if e["category"] == category and any(e["source"] == j["source"] and e["character_id"] == j["character_id"] for j in sources+(tails if category == "source_reference" else []))]
    for entry in selected:
        with bpy.data.libraries.load(str(root/entry["path"]), link=False) as (src, dest):
            dest.objects = [n for n in src.objects if "Preview light" not in n]
        for obj in dest.objects:
            if obj is None: continue
            scene.collection.objects.link(obj)
            if obj.parent is None: obj.location.x += (column-2)*1.2
            if obj.type == "ARMATURE": obj.hide_render = True
    curve = bpy.data.curves.new(category, "FONT")
    curve.body = category if selected else category+" (empty)"
    curve.size = .085
    curve.align_x = "CENTER"
    label = bpy.data.objects.new(category, curve)
    scene.collection.objects.link(label)
    label.location = ((column-2)*1.2, -.15, -.15)
    label.rotation_euler = (1.5708, 0, 0)
engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
scene.world = bpy.data.worlds.new("Preview world")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.18,.18,.18,1)
light = bpy.data.lights.new("Sun", "SUN")
light.energy = 4
sun = bpy.data.objects.new("Sun", light)
scene.collection.objects.link(sun)
sun.rotation_euler = (.5,-.5,-.3)
camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(camera)
camera.location = (0,-8,1.0)
camera.rotation_euler = (Vector((0,0,.75))-camera.location).to_track_quat("-Z","Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 6.2
scene.camera = camera
scene.render.resolution_x = 1800
scene.render.resolution_y = 620
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(root/("segmentation_"+args.character+"_"+(args.shared_body or args.variant)+".png"))
bpy.ops.render.render(write_still=True)
print("UMA_SEGMENTATION_PREVIEW "+scene.render.filepath, flush=True)
