"""Create source-reference and per-part Blender files from real decoded Unity bundles."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import bpy

HERE = Path(__file__).resolve().parent
core_path = HERE / "uma_blender_import.py"
if not core_path.exists(): core_path = HERE.parents[1] / "Assets/StreamingAssets/Blender/uma_blender_import.py"
spec = importlib.util.spec_from_file_location("uma_blender_core",core_path)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

def build(data, resources, output, category, job):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.unit_settings.system = "METRIC"
    rig, names = core.make_rig(data)
    selected = []
    for original in data["meshes"]:
        mesh = dict(original)
        faces = [dict(f,part="body") for f in original["faces"] if (category in (None,"body_base") or f["category"] == category) and f["triangles"]]
        if not faces: continue
        mesh["faces"] = faces
        selected.append(mesh)
    indices = {f["material"] for m in selected for f in m["faces"] if f["material"] >= 0}
    materials = {i:core.make_material(data["materials"][i],resources) for i in indices}
    collection = bpy.data.collections.new(category or "SourceReference")
    scene.collection.children.link(collection)
    objects = []
    for mesh in selected:
        obj = core.make_mesh(mesh,"body",collection,rig,names,materials)
        if obj is None: continue
        obj["uma_category"] = category or "source_reference"
        obj["uma_source_asset"] = data["source"]
        obj["uma_character_id"] = data["character_id"]
        obj["uma_character_name"] = data.get("character_name","")
        obj["uma_variant"] = data["variant"]
        obj["uma_mesh_path_id"] = str(mesh["unity_mesh_id"])
        obj["uma_source_renderer_active"] = mesh["active"]
        used = sorted({v for f in mesh["faces"] for v in f["triangles"]})
        source_indices = obj.data.attributes.new("uma_source_vertex",type="INT",domain="POINT")
        for item,index in zip(source_indices.data,used): item.value=index
        obj.hide_render = not mesh["active"]
        objects.append(obj)
    if not objects: return None
    scene["uma_source"] = data["source"]
    scene["uma_character_id"] = data["character_id"]
    scene["uma_category"] = category or "source_reference"
    scene["uma_classification"] = job["classification"]
    scene["uma_empty_apparel"] = json.dumps(job.get("empty_apparel",[]))
    if data.get("segmentation"):
        scene["uma_segmentation"] = json.dumps(data["segmentation"],ensure_ascii=False)
    if data.get("attachment"):
        scene["uma_attachment"] = json.dumps(data["attachment"])
    scene["uma_shader_fidelity"] = "Editable approximation; original textures and material parameters retained"
    text = bpy.data.texts.new("Uma source provenance")
    text.write(json.dumps({k:data[k] for k in ("source","character_id","character_name","variant","pose","warnings","audits","materials")},ensure_ascii=False,indent=2))
    scene.world = bpy.data.worlds.new("Preview world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value=(.15,.15,.15,1)
    sun_data=bpy.data.lights.new("Preview light","SUN")
    sun_data.energy=3
    sun=bpy.data.objects.new("Preview light",sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler=(.5,-.7,-.4)
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    result=dict(file=output.name,category=category or "source_reference",character_id=data["character_id"],source=data["source"],
                objects=len(objects),vertices=sum(len(o.data.vertices) for o in objects),triangles=sum(len(o.data.polygons) for o in objects),
                bones=len(rig.data.bones),packed_images=sum(i.packed_file is not None for i in bpy.data.images),
                unweighted_vertices=sum(o["uma_unweighted_vertices"] for o in objects))
    print("UMA_REAL_ASSET_EXPORTED " + json.dumps(result),flush=True)
    return result

def main():
    path=Path(sys.argv[sys.argv.index("--")+1]).resolve()
    manifest=json.loads(path.read_text(encoding="utf8"))
    output=path.parent
    resources=output/manifest["resources"]
    results=[]
    for job in manifest["jobs"]:
        data=json.loads((output/job["snapshot"]).read_text(encoding="utf8"))
        core.validate(data,resources)
        directory=output/"blends"/("chara"+job["character_id"])
        result=build(data,resources,directory/(job["name"]+"__source_reference.blend"),None,job)
        if result: results.append(dict(result,path=(directory/result["file"]).relative_to(output).as_posix()))
        for category in job["categories"]:
            result=build(data,resources,directory/(job["name"]+"__"+category+".blend"),category,job)
            if result: results.append(dict(result,path=(directory/result["file"]).relative_to(output).as_posix()))
        if any(base["name"]==job["name"] for base in manifest.get("body_bases",[])):
            result=build(data,resources,directory/(job["name"]+"__body_base.blend"),"body_base",job)
            if result: results.append(dict(result,path=(directory/result["file"]).relative_to(output).as_posix()))
    manifest["blender_outputs"]=results
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
    print("UMA_HEADLESS_COMPLETE files="+str(len(results)),flush=True)

if __name__=="__main__": main()
