"""Render both engine-specific material outputs from an actual saved fixture."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

directory = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(directory / "clothing.blend"))
scene = bpy.context.scene
camera_data = bpy.data.cameras.new("Validation camera")
camera = bpy.data.objects.new("Validation camera", camera_data)
scene.collection.objects.link(camera)
camera.location = (-0.5, -4, 0.5)
camera.rotation_euler = (Vector((-0.5, 0, 0.5)) - camera.location).to_track_quat("-Z", "Y").to_euler()
camera_data.type = "ORTHO"
camera_data.ortho_scale = 1.4
scene.camera = camera
scene.render.resolution_x = 128
scene.render.resolution_y = 128
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
reports = []
for engine in (scene.render.engine, "CYCLES"):
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = 2
        scene.cycles.use_denoising = False
    scene.render.filepath = str(directory / ("material_" + engine.lower() + ".png"))
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    pixels = list(image.pixels)
    rgb = [pixels[i] for i in range(len(pixels)) if i % 4 != 3]
    assert max(rgb) - min(rgb) > 0.02, "Rendered image is flat or empty"
    reports.append({"engine": engine, "rendered": True, "width": image.size[0], "height": image.size[1]})
    bpy.data.images.remove(image)
(directory / "material_render_verification.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
print("UMA_MATERIAL_RENDER_OK " + json.dumps(reports))
