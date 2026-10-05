"""Reopen EVERY real output and compare it to its decoded source snapshot."""
import collections
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

path=Path(sys.argv[sys.argv.index("--")+1]).resolve()
manifest=json.loads(path.read_text(encoding="utf8"))
root=path.parent
snapshots={(j["source"],j["character_id"]):json.loads((root/j["snapshot"]).read_text(encoding="utf8")) for j in manifest["jobs"]}
reports=[]
assert len({e["path"] for e in manifest["blender_outputs"]}) == len(manifest["blender_outputs"]), "Output filename collision"
if manifest.get("segmentation") == "broad_apparel_v2":
    forbidden = {"accessories", "skirt", "cape", "upper_clothing", "gloves", "shoes", "socks_or_legwear"}
    for job in manifest["jobs"]:
        data = snapshots[job["source"],job["character_id"]]
        assert not forbidden.intersection(job["categories"]), "Legacy fine clothing split remains"
        assert not set(job["empty_apparel"]).intersection(job["categories"]), "Empty category contains geometry"
        for category in job["empty_apparel"]:
            assert not any(e["category"] == category and e["source"] == job["source"] and e["character_id"] == job["character_id"] for e in manifest["blender_outputs"]), "Empty group exported"
        if job["kind"] == "head" and data["variant"] == "80":
            assert "headwear" in job["empty_apparel"], "Bare supplied head acquired fictitious headwear"
for entry in manifest["blender_outputs"]:
    data=snapshots[entry["source"],entry["character_id"]]
    category=entry["category"]
    filename=root/entry["path"]
    bpy.ops.wm.open_mainfile(filepath=str(filename))
    rig=next(o for o in bpy.context.scene.objects if o.type=="ARMATURE")
    mapping={b["uma_bone_id"]:b.name for b in rig.data.bones}
    assert len(mapping)==len(data["bones"])
    for bone in data["bones"]:
        exported=rig.data.bones[mapping[bone["id"]]]
        assert (exported.parent.name if exported.parent else None)==(mapping[bone["parent"]] if bone.get("parent") else None)
    count=0
    for obj in [o for o in bpy.context.scene.objects if o.type=="MESH"]:
        mesh=next(m for m in data["meshes"] if m["name"]==obj["unity_renderer"])
        faces=[f for f in mesh["faces"] if category in ("source_reference","body_base") or f["category"]==category]
        expected=[tuple(reversed(f["triangles"][i:i+3])) for f in faces for i in range(0,len(f["triangles"]),3)]
        used=sorted({v for triangle in expected for v in triangle})
        indices=[v.value for v in obj.data.attributes["uma_source_vertex"].data]
        assert indices==used,filename.name+": source vertex mapping differs"
        actual=[tuple(indices[v] for v in polygon.vertices) for polygon in obj.data.polygons]
        assert actual==expected,filename.name+": source triangles differ"
        assert obj["uma_unweighted_vertices"]==0
        expected_weights=collections.defaultdict(lambda:collections.Counter())
        for weight in mesh["weights"]:
            expected_weights[weight["vertex"]][mapping[weight["bone"]]]+=weight["weight"]
        deps=bpy.context.evaluated_depsgraph_get()
        evaluated_obj=obj.evaluated_get(deps)
        evaluated=evaluated_obj.to_mesh()
        try:
            original_positions=[]
            for vertex,old in zip(evaluated.vertices,used):
                v=mesh["vertices"][old]
                point=Vector((-v["x"],-v["z"],v["y"]))
                assert (vertex.co-point).length<1e-5,filename.name+": neutral rig deforms original geometry"
                original_positions.append(vertex.co.copy())
            for vertex,old in zip(obj.data.vertices,used):
                total=sum(expected_weights[old].values())
                actual_weights={obj.vertex_groups[g.group].name:g.weight for g in vertex.groups}
                assert set(actual_weights)==set(expected_weights[old])
                assert all(abs(actual_weights[name]-weight/total)<2e-6 for name,weight in expected_weights[old].items())
            for uv in mesh["uvs"]:
                layer=obj.data.uv_layers["UV"+str(uv["channel"])]
                for loop in obj.data.loops:
                    value=uv["values"][indices[loop.vertex_index]]
                    assert abs(layer.data[loop.index].uv.x-value["x"])<1e-6
                    assert abs(layer.data[loop.index].uv.y-value["y"])<1e-6
        finally: evaluated_obj.to_mesh_clear()
        root_bone=next(b for b in rig.pose.bones if b.parent is None)
        root_bone.location=(.01,.02,.03)
        bpy.context.view_layer.update()
        evaluated_obj=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        evaluated=evaluated_obj.to_mesh()
        try:
            assert max((v.co-before).length for v,before in zip(evaluated.vertices,original_positions))>.001
        finally: evaluated_obj.to_mesh_clear()
        root_bone.location=(0,0,0)
        bpy.context.view_layer.update()
        count+=len(expected)
    assert all(image.packed_file for image in bpy.data.images if image.type=="IMAGE")
    reports.append(dict(file=entry["path"],triangles=count,topology=True,coordinates=True,weights=True,uv=True,bone_hierarchy=True,packed_textures=True,deformation=True))
    print("VERIFIED "+filename.name,flush=True)
for job in manifest["jobs"]:
    data=json.loads((root/job["snapshot"]).read_text(encoding="utf8"))
    actual=sum(entry["triangles"] for entry in manifest["blender_outputs"] if entry["source"]==job["source"] and entry["category"] not in ("source_reference","body_base") and entry["character_id"]==job["character_id"])
    expected=sum(len(face["triangles"])//3 for mesh in data["meshes"] for face in mesh["faces"])
    assert actual==expected,"Part partition lost or duplicated source triangles"
result=dict(files=len(reports),passed=True,reports=reports,input_sha256=manifest["input_sha256"],
            segmentation=manifest.get("segmentation"),empty_groups=True,unique_filenames=True,
            note="Checks geometry preservation, not semantic accuracy of skin/clothing heuristics or exact Unity shader appearance")
(root/"verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
print("UMA_REAL_EXPORTS_VERIFIED files="+str(len(reports)),flush=True)
