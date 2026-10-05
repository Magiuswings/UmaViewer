"""UmaViewer snapshot -> editable, packed Blender scenes. Blender 4.2+.

blender --background --factory-startup --python-exit-code 1 --python
    uma_blender_import.py -- model.uma.json --split
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

# Reflect handedness, then rotate Y-up to Z-up. Reverse face winding too.
C = Matrix(((-1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def vec(value):
    return C.to_3x3() @ Vector((value["x"], value["y"], value["z"]))


def validate(data, directory):
    if data.get("version") != 1:
        raise ValueError("Unsupported UmaViewer snapshot version")
    ids = {b["id"] for b in data["bones"]}
    if len(ids) != len(data["bones"]):
        raise ValueError("Duplicate bone IDs")
    parents = {b["id"]: b.get("parent") for b in data["bones"]}
    for bone in data["bones"]:
        if len(bone["matrix"]) != 16 or not all(math.isfinite(n) for n in bone["matrix"]):
            raise ValueError("Invalid bone matrix")
        visited = set()
        current = bone["id"]
        while current:
            if current not in parents or current in visited:
                raise ValueError("Invalid or cyclic bone hierarchy")
            visited.add(current)
            current = parents[current]
    for material in data["materials"]:
        for prop in material["properties"]:
            if prop.get("texture"):
                path = (directory / prop["texture"]).resolve()
                if not path.is_relative_to(directory.resolve()) or not path.is_file():
                    raise ValueError("Missing or unsafe texture path: " + prop["texture"])
    for mesh in data["meshes"]:
        count = len(mesh["vertices"])
        for field in ("vertices", "normals", "colors"):
            values = mesh.get(field, [])
            if field != "vertices" and len(values) not in (0, count):
                raise ValueError("Mismatched " + field)
            if any(not math.isfinite(v.get(k, 0)) for v in values for k in ("x", "y", "z", "w")):
                raise ValueError("Non-finite mesh values")
        for uv in mesh.get("uvs", []):
            if len(uv["values"]) != count:
                raise ValueError("Mismatched UV count")
        for face in mesh["faces"]:
            indices = face["triangles"]
            if face["part"] not in ("clothing", "body") or len(indices) % 3:
                raise ValueError("Invalid face section")
            if any(i < 0 or i >= count for i in indices):
                raise ValueError("Invalid triangle index")
            if face["material"] < -1 or face["material"] >= len(data["materials"]):
                raise ValueError("Invalid material index")
        for influence in mesh["weights"]:
            if influence["bone"] not in ids or not 0 <= influence["vertex"] < count:
                raise ValueError("Invalid weight binding")
            if not math.isfinite(influence["weight"]) or influence["weight"] < 0:
                raise ValueError("Invalid bone weight")
        for shape in mesh.get("shapes", []):
            if len(shape["deltas"]) != count or not math.isfinite(shape["weight"]):
                raise ValueError("Invalid shape key")


def make_rig(data):
    armature = bpy.data.armatures.new(data["name"] + "_Skeleton")
    rig = bpy.data.objects.new(data["name"] + "_Rig", armature)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    mapping = {}
    for entry in data["bones"]:
        bone = armature.edit_bones.new(entry["name"][:50] or entry["id"])
        m = entry["matrix"]
        matrix = C @ Matrix(tuple(tuple(m[r * 4 + c] for c in range(4)) for r in range(4))) @ C.inverted()
        # Bone scales are already baked into exported vertices; edit bones use orthonormal rotation.
        rotation = matrix.to_quaternion().to_matrix().to_4x4()
        rotation.translation = matrix.translation
        bone.matrix = rotation
        bone.length = 0.04
        mapping[entry["id"]] = bone.name
    for entry in data["bones"]:
        if entry.get("parent"):
            armature.edit_bones[mapping[entry["id"]]].parent = armature.edit_bones[mapping[entry["parent"]]]
    bpy.ops.object.mode_set(mode="OBJECT")
    for entry in data["bones"]:
        armature.bones[mapping[entry["id"]]]["uma_bone_id"] = entry["id"]
        armature.bones[mapping[entry["id"]]]["unity_name"] = entry["name"]
        armature.bones[mapping[entry["id"]]]["unity_snapshot_matrix"] = entry["matrix"]
    rig.show_in_front = True
    rig["uma_pose"] = data.get("pose", "Current pose snapshot")
    rig.select_set(False)
    return rig, mapping


def node(nodes, kind, label, x, y):
    item = nodes.new(kind)
    item.label = label
    item.location = (x, y)
    return item


def make_material(entry, directory):
    mat = bpy.data.materials.new(entry["name"])
    mat.use_nodes = True
    mat["unity_shader"] = entry["shader"]
    mat["unity_keywords"] = json.dumps(entry.get("keywords", []))
    mat["unity_material_properties"] = json.dumps(entry["properties"], ensure_ascii=False)
    mat["unity_render_queue"] = entry["renderQueue"]
    mat["uma_shader_note"] = "Editable toon approximation; source Unity shader parameters are retained."
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    output = node(nodes, "ShaderNodeOutputMaterial", "Surface", 900, 200)
    output.target = "EEVEE"
    cycles_output = node(nodes, "ShaderNodeOutputMaterial", "Cycles surface", 900, -250)
    cycles_output.target = "CYCLES"
    bsdf = node(nodes, "ShaderNodeBsdfPrincipled", "Cycles / PBR fallback", 600, -250)
    bsdf.inputs["Roughness"].default_value = 0.8
    bsdf.inputs["Specular IOR Level"].default_value = 0.15
    links.new(bsdf.outputs["BSDF"], cycles_output.inputs["Surface"])
    props = {p["name"]: p for p in entry["properties"]}
    texture_nodes = {}
    for i, prop in enumerate(entry["properties"]):
        if prop.get("texture"):
            image_node = node(nodes, "ShaderNodeTexImage", prop["name"], -1200, -i * 240)
            # Distinct image datablocks allow one texture to be used as both color and data.
            image_node.image = bpy.data.images.load(str(directory / prop["texture"]), check_existing=False)
            image_node.image.colorspace_settings.name = "sRGB" if prop.get("srgb", True) else "Non-Color"
            image_node.name = prop["name"]
            texture_nodes[prop["name"]] = image_node
            uv = node(nodes, "ShaderNodeUVMap", "UV0", -1700, -i * 240)
            uv.uv_map = "UV0"
            mapping = node(nodes, "ShaderNodeMapping", prop["name"] + " UV transform", -1500, -i * 240)
            scale, offset = prop.get("scale") or [1, 1], prop.get("offset") or [0, 0]
            mapping.inputs["Scale"].default_value = (scale[0], scale[1], 1)
            mapping.inputs["Location"].default_value = (offset[0], offset[1], 0)
            links.new(uv.outputs["UV"], mapping.inputs["Vector"])
            links.new(mapping.outputs["Vector"], image_node.inputs["Vector"])
    base = texture_nodes.get("_MainTex") or texture_nodes.get("_BaseMap")
    tint = props.get("_BaseColor", props.get("_Color", {})).get("value") or [1, 1, 1, 1]
    rgb = node(nodes, "ShaderNodeRGB", "Base tint", -650, 250)
    rgb.outputs[0].default_value = tuple(tint[:4])
    color = rgb.outputs[0]
    if base:
        multiply = node(nodes, "ShaderNodeMixRGB", "Texture x tint", -400, 250)
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1
        links.new(base.outputs["Color"], multiply.inputs[1])
        links.new(color, multiply.inputs[2])
        color = multiply.outputs[0]
        links.new(base.outputs["Alpha"], bsdf.inputs["Alpha"])
    # Area shaders vary between regions. Keep the actual colors and an editable
    # two-band-per-channel preview, rather than losing the active color set.
    palette = {}
    for i, key in enumerate(("R1", "R2", "G1", "G2", "B1", "B2")):
        prop = props.get("_MaskColor" + key)
        if prop and prop.get("value"):
            control = node(nodes, "ShaderNodeRGB", "Color set " + key, -500, -650 - 130 * i)
            control.outputs[0].default_value = tuple(prop["value"])
            palette[key] = control.outputs[0]
    area = texture_nodes.get("_MaskColorTex")
    if area and palette and "USE_MASK_COLOR" in entry.get("keywords", []):
        area.image.colorspace_settings.name = "Non-Color"
        split = node(nodes, "ShaderNodeSeparateColor", "Area mask channels", -900, -700)
        links.new(area.outputs["Color"], split.inputs[0])
        for channel in ("R", "G", "B"):
            first, second = palette.get(channel + "1"), palette.get(channel + "2")
            if not first or not second:
                continue
            pair = node(nodes, "ShaderNodeMixRGB", channel + " palette pair", -100, -650)
            band = node(nodes, "ShaderNodeMath", channel + " area band (editable)", -350, -650)
            band.operation = "GREATER_THAN"
            band.inputs[1].default_value = 0.75
            links.new(split.outputs[{"R": "Red", "G": "Green", "B": "Blue"}[channel]], band.inputs[0])
            links.new(band.outputs[0], pair.inputs[0])
            links.new(second, pair.inputs[1])
            links.new(first, pair.inputs[2])
            gate = node(nodes, "ShaderNodeMath", channel + " area coverage", -100, -850)
            gate.operation = "GREATER_THAN"
            gate.inputs[1].default_value = 0.01
            links.new(split.outputs[{"R": "Red", "G": "Green", "B": "Blue"}[channel]], gate.inputs[0])
            recolor = node(nodes, "ShaderNodeMixRGB", channel + " area tint", 100, -650)
            recolor.blend_type = "MULTIPLY"
            links.new(gate.outputs[0], recolor.inputs[0])
            links.new(color, recolor.inputs[1])
            links.new(pair.outputs[0], recolor.inputs[2])
            color = recolor.outputs[0]
        mat["uma_area_mask_note"] = "Preview assumes channel 1=first color, 0.5=second color. Regional shader encodings can differ; adjust area band nodes."
    links.new(color, bsdf.inputs["Base Color"])
    diffuse = node(nodes, "ShaderNodeBsdfDiffuse", "Toon lighting", -300, 650)
    diffuse.inputs["Color"].default_value = (1, 1, 1, 1)
    light = node(nodes, "ShaderNodeShaderToRGB", "EEVEE lighting", -100, 650)
    links.new(diffuse.outputs[0], light.inputs[0])
    ramp = node(nodes, "ShaderNodeValToRGB", "Toon light / shadow", 100, 650)
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.45, 0.45, 0.5, 1)
    ramp.color_ramp.elements[1].position = 0.5
    links.new(light.outputs[0], ramp.inputs[0])
    mix = node(nodes, "ShaderNodeMixRGB", "Toon shading", 350, 350)
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1
    links.new(color, mix.inputs[1])
    links.new(ramp.outputs["Color"], mix.inputs[2])
    emission = node(nodes, "ShaderNodeEmission", "EEVEE toon surface", 600, 250)
    links.new(mix.outputs[0], emission.inputs[0])
    surface = emission.outputs[0]
    transparent = "alpha" in entry["shader"].lower() or "transparent" in entry["shader"].lower() or "_ALPHATEST_ON" in entry.get("keywords", []) or entry["renderQueue"] >= 2450
    if transparent and base:
        transparent_node = node(nodes, "ShaderNodeBsdfTransparent", "Texture transparency", 500, 50)
        alpha_mix = node(nodes, "ShaderNodeMixShader", "Alpha", 760, 200)
        links.new(base.outputs["Alpha"], alpha_mix.inputs[0])
        links.new(transparent_node.outputs[0], alpha_mix.inputs[1])
        links.new(surface, alpha_mix.inputs[2])
        surface = alpha_mix.outputs[0]
    links.new(surface, output.inputs["Surface"])
    normal = texture_nodes.get("_BumpMap") or texture_nodes.get("_NormalMap")
    if normal:
        normal.image.colorspace_settings.name = "Non-Color"
        normal_map = node(nodes, "ShaderNodeNormalMap", "Normal map", 300, -400)
        links.new(normal.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_mesh(entry, part, collection, rig, bone_names, materials):
    sections = [s for s in entry["faces"] if s["part"] == part and s["triangles"]]
    if not sections:
        return None
    used = sorted({v for s in sections for v in s["triangles"]})
    remap = {old: new for new, old in enumerate(used)}
    faces, material_indices = [], []
    for section in sections:
        indices = section["triangles"]
        for i in range(0, len(indices), 3):
            faces.append(tuple(remap[v] for v in reversed(indices[i:i + 3])))
            material_indices.append(section["material"])
    mesh = bpy.data.meshes.new(entry["name"] + "_" + part)
    # Undo current shape influence: the snapshot has already baked it. Keys restore it once.
    positions = [vec(entry["vertices"][v]) for v in used]
    for shape in entry.get("shapes", []):
        for i, old in enumerate(used):
            positions[i] -= vec(shape["deltas"][old]) * shape["weight"]
    mesh.from_pydata(positions, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(mesh.name, mesh)
    collection.objects.link(obj)
    slots = {}
    for index in sorted(set(material_indices)):
        slots[index] = len(mesh.materials)
        mesh.materials.append(materials[index] if index >= 0 else bpy.data.materials.new("Missing source material"))
    for face, index in zip(mesh.polygons, material_indices):
        face.material_index = slots[index]
        face.use_smooth = True
    for uv in entry.get("uvs", []):
        layer = mesh.uv_layers.new(name="UV" + str(uv["channel"]))
        for loop in mesh.loops:
            value = uv["values"][used[loop.vertex_index]]
            layer.data[loop.index].uv = (value["x"], value["y"])
    if entry.get("colors"):
        colors = mesh.color_attributes.new(name="UnityColor", type="FLOAT_COLOR", domain="POINT")
        for i, old in enumerate(used):
            value = entry["colors"][old]
            colors.data[i].color = (value["x"], value["y"], value["z"], value["w"])
    if entry.get("normals"):
        mesh.normals_split_custom_set_from_vertices([vec(entry["normals"][old]) for old in used])
    totals = {}
    for weight in entry["weights"]:
        if weight["vertex"] in remap:
            totals[weight["vertex"]] = totals.get(weight["vertex"], 0) + weight["weight"]
    groups = {}
    for weight in entry["weights"]:
        old = weight["vertex"]
        if old not in remap or weight["weight"] <= 0:
            continue
        bone = weight["bone"]
        if bone not in groups:
            groups[bone] = obj.vertex_groups.new(name=bone_names[bone])
        groups[bone].add([remap[old]], weight["weight"] / totals[old], "ADD")
    modifier = obj.modifiers.new("Uma armature", "ARMATURE")
    modifier.object = rig
    obj.parent = rig
    obj["uma_part"] = part
    obj["unity_renderer"] = entry["name"]
    obj["uma_unweighted_vertices"] = sum(totals.get(old, 0) == 0 for old in used)
    if entry.get("shapes"):
        obj.shape_key_add(name="Basis")
        for shape in entry["shapes"]:
            key = obj.shape_key_add(name=shape["name"])
            for i, old in enumerate(used):
                key.data[i].co = positions[i] + vec(shape["deltas"][old])
            key.slider_min = min(-1.0, shape["weight"])
            key.slider_max = max(1.0, shape["weight"])
            key.value = shape["weight"]
    return obj


def build(data, directory, parts, output):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    rig, bone_names = make_rig(data)
    used_materials = {s["material"] for m in data["meshes"] for s in m["faces"] if s["part"] in parts and s["triangles"] and s["material"] >= 0}
    materials = {i: make_material(data["materials"][i], directory) for i in used_materials}
    objects = []
    for part in parts:
        collection = bpy.data.collections.new(part.capitalize())
        scene.collection.children.link(collection)
        for mesh in data["meshes"]:
            obj = make_mesh(mesh, part, collection, rig, bone_names, materials)
            if obj:
                objects.append(obj)
    if not objects:
        raise ValueError("No selected geometry for " + ", ".join(parts))
    text = bpy.data.texts.new("UmaViewer source and shader notes")
    text.write(json.dumps({"name": data["name"], "pose": data.get("pose"), "warnings": data.get("warnings", []), "materials": data["materials"]}, ensure_ascii=False, indent=2))
    scene["uma_source"] = data["name"]
    scene["uma_export_parts"] = ",".join(parts)
    scene["uma_shader_fidelity"] = "Approximate EEVEE toon; Unity lighting, area-color masks, outlines and physics require adaptation."
    scene.world = bpy.data.worlds.new("Uma neutral world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.12, 0.12, 0.12, 1)
    sun_data = bpy.data.lights.new("Preview sunlight", "SUN")
    sun_data.energy = 2
    sun = bpy.data.objects.new("Preview sunlight", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (0.4, -0.6, -0.4)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report = {"output": output.name, "parts": list(parts), "meshes": len(objects), "vertices": sum(len(o.data.vertices) for o in objects), "triangles": sum(len(o.data.polygons) for o in objects), "bones": len(rig.data.bones), "materials": len(materials), "packed_images": sum(i.packed_file is not None for i in bpy.data.images), "unweighted_vertices": sum(o["uma_unweighted_vertices"] for o in objects)}
    output.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("UMA_BLENDER_EXPORT " + json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--split", action="store_true", help="Create clothing.blend and body.blend independently")
    parser.add_argument("--part", choices=("all", "clothing", "body"), default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    snapshot = args.snapshot.resolve()
    data = json.loads(snapshot.read_text(encoding="utf-8-sig"))
    validate(data, snapshot.parent)
    if args.split:
        if args.output:
            parser.error("--split writes beside the snapshot; do not combine with --output")
        for part in ("clothing", "body"):
            if any(s["part"] == part and s["triangles"] for m in data["meshes"] for s in m["faces"]):
                build(data, snapshot.parent, (part,), snapshot.parent / (part + ".blend"))
            else:
                print("UMA_BLENDER_SKIP " + part + ": no geometry assigned")
    else:
        parts = ("clothing", "body") if args.part == "all" else (args.part,)
        output = (args.output or snapshot.parent / (args.part + ".blend")).resolve()
        if output.suffix.lower() != ".blend":
            parser.error("--output must end in .blend")
        build(data, snapshot.parent, parts, output)


if __name__ == "__main__":
    main()
