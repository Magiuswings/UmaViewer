"""Reopen actual output files and verify geometry, materials, pose and deformation."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion

directory = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
reports = []
for part in ("clothing", "body"):
    bpy.ops.wm.open_mainfile(filepath=str(directory / (part + ".blend")))
    scene = bpy.context.scene
    objects = [o for o in scene.objects if o.type == "MESH"]
    assert len(objects) == 1
    obj = objects[0]
    assert obj["uma_part"] == part
    assert len(obj.data.vertices) == 4, "Excluded or other-part vertices leaked"
    assert len(obj.data.polygons) == 2
    assert len(obj.data.uv_layers) == 2
    assert "UnityColor" in obj.data.color_attributes
    assert obj["uma_unweighted_vertices"] == 0
    assert len(obj.vertex_groups) == 6, "More-than-four bone influences were lost"
    for vertex in obj.data.vertices:
        assert abs(sum(g.weight for g in vertex.groups) - 1) < 1e-6
    rig = obj.modifiers["Uma armature"].object
    assert len(rig.data.bones) == 6
    by_id = {b["uma_bone_id"]: b for b in rig.data.bones}
    assert by_id["b1"].name != by_id["b2"].name
    for i in range(1, 6):
        assert by_id[f"b{i}"].parent == by_id[f"b{i-1}"]
    assert len(obj.data.shape_keys.key_blocks) == 2
    assert abs(obj.data.shape_keys.key_blocks["Smile"].value - 0.3) < 1e-6
    deps = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(deps).to_mesh()
    try:
        before = [v.co.copy() for v in evaluated.vertices]
        assert abs(before[0].x + 0.03) < 1e-6, "Shape influence applied twice"
        assert all(abs(v.y) < 1e-6 for v in before), "Y-up to Z-up conversion failed"
        assert max(v.z for v in before) >= 1
        # Exported normals agree with the geometry after handedness conversion.
        assert all(p.normal.y < -0.99 for p in evaluated.polygons)
    finally:
        obj.evaluated_get(deps).to_mesh_clear()
    root = rig.pose.bones[by_id["b0"].name]
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Quaternion((0, 0, 1), 0.5)
    bpy.context.view_layer.update()
    evaluated_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated = evaluated_obj.to_mesh()
    try:
        assert max((v.co - old).length for v, old in zip(evaluated.vertices, before)) > 0.1, "Armature does not deform"
    finally:
        evaluated_obj.to_mesh_clear()
    mat = obj.data.materials[0]
    assert mat["unity_shader"]
    assert {n.target for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL"} == {"EEVEE", "CYCLES"}
    assert "_MaskColorR1" in mat["unity_material_properties"]
    assert mat.node_tree.nodes["_MainTex"].image.packed_file
    assert mat.node_tree.nodes["_MaskColorTex"].image.packed_file
    assert any(n.label == "R area tint" and n.outputs[0].is_linked for n in mat.node_tree.nodes)
    assert all(i.packed_file for i in bpy.data.images if i.type == "IMAGE")
    report = json.loads((directory / (part + ".report.json")).read_text())
    report["reopen_verified"] = True
    report["armature_deformation_verified"] = True
    reports.append(report)
(directory / "verification.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
print("UMA_BLENDER_REOPEN_VERIFIED " + json.dumps(reports))
