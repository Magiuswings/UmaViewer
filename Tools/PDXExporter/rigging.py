"""Adapt a CK3 bind skeleton to UMA joints without changing mesh geometry.

Run inside Blender 4.2. ``adapt_rig`` returns a JSON-serializable audit;
the replacement armature is available as ``bpy.data.objects[report['rig_name']]``.
The old armature object is removed after verification. No modifiers are applied.
Animations require separate retargeting; this module does not copy animation.
"""
from array import array
from collections import Counter, defaultdict
from itertools import combinations
import math
from pathlib import Path
import re
from statistics import median

import bpy
from mathutils import Matrix, Vector


def _semantic_map(kind):
    if kind == "head":
        mapping = {
            "Position": "head_root", "Neck": "bn_h_neck_1", "Head": "bn_h_head",
            "Mouth_Root": "bn_h_face_lower", "Chin": "bn_h_jaw_low",
            "Nose": "bn_h_nose_main", "Mouth_up_01_C": "bn_h_mouth_upperLip",
            "Mouth_bottom_01_C": "bn_h_mouth_lowerLip",
        }
        for side in ("L", "R"):
            s = side.lower()
            mapping.update({
                f"Cheek_{side}": f"bn_h_cheek_{s}_main",
                f"Eye_locator_{side}": f"bn_h_eye_{s}_main",
                f"Eye_{side}": f"bn_h_eye_{s}_rotate",
                f"Eye_up_02_{side}": f"bn_h_eye_{s}_lidUpper",
                f"Eye_bottom_02_{side}": f"bn_h_eye_{s}_lidLower",
                f"Eyebrow_01_{side}": f"bn_h_forehead_{s}_browInner",
                f"Eyebrow_02_{side}": f"bn_h_forehead_{s}_browOuter",
                f"Mouth_middle_{side}": f"bn_h_mouth_{s}_corner",
                f"Mouth_up_02_{side}": f"bn_h_mouth_{s}_upperLip",
                f"Mouth_bottom_02_{side}": f"bn_h_mouth_{s}_lowerLip",
                f"Ear_01_{side}": f"bn_h_ear_{s}_main",
                f"Shoulder_{side}": f"bn_h_{s}_clavicle",
            })
        return mapping
    mapping = {
        "Position": "ground_joint", "Hip": "body_root", "Waist": "bn_sp_lumbar",
        "Spine": "bn_sp_thoracic", "Neck": "bn_sp_cervical",
    }
    for side in ("L", "R"):
        s = side.lower()
        for old, new in (
            ("Shoulder", "clavicle"), ("Arm", "shoulder"), ("Elbow", "elbow"),
            ("ArmRoll", "forearm"), ("Wrist", "wrist"), ("ShoulderRoll", "deltoid"),
            ("Hand_Attach", "prop"), ("Thigh", "hip"), ("Knee", "knee"),
            ("Ankle", "ankle"), ("Toe", "ftBall"),
        ):
            mapping[f"{old}_{side}"] = f"bn_{s}_{new}"
        for old, new in (("Thumb", "thumb"), ("Index", "index"), ("Middle", "mid"),
                         ("Ring", "ring"), ("Pinky", "pinky")):
            for n in range(1, 4):
                mapping[f"{old}_{n:02}_{side}"] = f"bn_{s}_fi_{new}{n}"
    return mapping


def _read_reference(path, pdx, pdx_data, kind):
    data = pdx_data.read_meshfile(str(path))
    skeletons = [obj.find("skeleton") for obj in data.find("object")]
    skeleton = next((s for s in skeletons if s is not None and len(s)), None)
    if skeleton is None:
        raise ValueError(f"Reference has no skeleton: {path}")
    names = [b.tag for b in skeleton]
    expected = 61 if kind == "head" else 134
    if len(names) != expected or len(set(names)) != len(names):
        raise ValueError(f"Expected {expected} unique CK3 {kind} bones; found {len(names)}")
    result = {}
    for node in skeleton:
        t = node.attrib["tx"]
        if len(t) != 12 or not all(math.isfinite(v) for v in t):
            raise ValueError(f"Invalid reference inverse bind: {node.tag}")
        inv = Matrix(((t[0], t[3], t[6], t[9]), (t[1], t[4], t[7], t[10]),
                      (t[2], t[5], t[8], t[11]), (0, 0, 0, 1)))
        matrix = pdx.swap_coord_space(inv.inverted())
        # Blender edit bones have orthonormal frames, not shear or scale.
        rotation = matrix.to_quaternion().to_matrix().to_4x4()
        rotation.translation = matrix.translation
        parent = node.attrib.get("pa")
        result[node.tag] = {"matrix": rotation, "parent": names[parent[0]] if parent else None}
    # Resolve arbitrary input ordering and reject cycles before editing the scene.
    order, visiting = [], set()
    def visit(name):
        if name in visiting:
            raise ValueError("Cyclic reference skeleton")
        if name in order:
            return
        visiting.add(name)
        parent = result[name]["parent"]
        if parent:
            visit(parent)
        visiting.remove(name)
        order.append(name)
    for name in names:
        visit(name)
    return names, order, result


def _coords(collection):
    values = array("f", [0.0]) * (3 * len(collection))
    collection.foreach_get("co", values)
    return values


def _world_coords(values, matrix):
    return [tuple(matrix @ Vector(values[i:i + 3])) for i in range(0, len(values), 3)]


def _matrix_error(a, b):
    return max(abs(a[r][c] - b[r][c]) for r in range(4) for c in range(4))


def _evaluated_coords(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return _world_coords(_coords(mesh.vertices), obj.matrix_world)
    finally:
        evaluated.to_mesh_clear()


def _capture(obj):
    keys = obj.data.shape_keys
    return {
        "data": obj.data, "coords": _coords(obj.data.vertices),
        "world": obj.matrix_world.copy(), "basis": obj.matrix_basis.copy(),
        "shapes": {k.name: {"coords": _coords(k.data), "value": k.value,
                              "mute": k.mute, "min": k.slider_min, "max": k.slider_max,
                              "relative": k.relative_key.name, "vertex_group": k.vertex_group}
                   for k in keys.key_blocks} if keys else {},
        "shape_datablock": keys, "evaluated": _evaluated_coords(obj),
        "polygons": [tuple(p.vertices) for p in obj.data.polygons],
    }


def _check_unchanged(obj, before):
    after = _capture(obj)
    local_exact = before["coords"].tobytes() == after["coords"].tobytes()
    shape_exact = before["shape_datablock"] == after["shape_datablock"] and before["shapes"] == after["shapes"]
    world_error = _matrix_error(before["world"], after["world"])
    basis_error = _matrix_error(before["basis"], after["basis"])
    world_before = _world_coords(before["coords"], before["world"])
    world_after = _world_coords(after["coords"], after["world"])
    coordinate_error = max(((Vector(a) - Vector(b)).length for a, b in zip(world_before, world_after)), default=0.0)
    if len(before["evaluated"]) != len(after["evaluated"]):
        raise AssertionError(f"Evaluated topology changed: {obj.name}")
    evaluated_error = max(((Vector(a) - Vector(b)).length for a, b in zip(before["evaluated"], after["evaluated"])), default=0.0)
    assert obj.data == before["data"] and local_exact, f"Mesh datablock or basis coordinates changed: {obj.name}"
    assert before["polygons"] == after["polygons"], f"Topology changed: {obj.name}"
    assert shape_exact, f"Shape keys changed: {obj.name}"
    assert world_error <= 1e-6 and basis_error <= 1e-6, f"Object transform changed: {obj.name}"
    assert coordinate_error <= 1e-6, f"World coordinates changed: {obj.name}"
    assert evaluated_error <= 1e-5, f"Evaluated geometry changed in rest pose: {obj.name}, {evaluated_error}"
    return {"vertices": len(obj.data.vertices), "shape_keys": len(after["shapes"]),
            "local_coordinates_exact": local_exact, "shape_keys_exact": shape_exact,
            "world_matrix_max_error": world_error, "basis_matrix_max_error": basis_error,
            "world_coordinates_max_error": coordinate_error, "evaluated_coordinates_max_error": evaluated_error}


def _scaled_heads(order, reference, direct, scale):
    heads = {}
    for name in order:
        ref = reference[name]
        parent = ref["parent"]
        if name in direct:
            heads[name] = direct[name].copy()
        elif parent:
            local = reference[parent]["matrix"].inverted() @ ref["matrix"]
            heads[name] = heads[parent] + reference[parent]["matrix"].to_3x3() @ (local.translation * scale)
        else:
            heads[name] = ref["matrix"].translation * scale
    return heads


def _garment_category(name):
    if "Handle" in name or not name.startswith("Sp_"):
        return None
    if "Skirt" in name:
        return "skirt"
    if "Jacket" in name or "Mantle" in name or "Cloak" in name:
        return "cloak"
    if "Sleeve" in name:
        return "sleeve"
    return None


def _garment_mapping(source, reference, heads):
    """Choose nearest compatible target chains, retaining ordered segments.

    Positional search is limited to CK3 garment bones. Unknown anatomy never
    uses a nearest bone search. Multiple source chains may merge into the same
    target chain; the resulting collisions are disclosed in the audit.
    """
    targets = defaultdict(list)
    for name in reference:
        match = re.fullmatch(r"(.*_(skirt|cloak|sleeve))(\d+)", name)
        if match:
            targets[match.group(1)].append((int(match.group(3)), name))
    for prefix in targets:
        targets[prefix] = [n for _, n in sorted(targets[prefix])]
    chains = defaultdict(list)
    for name, entry in source.items():
        category = _garment_category(entry["semantic"])
        if not category:
            continue
        root = name
        while source[root]["parent"] and _garment_category(source[source[root]["parent"]]["semantic"]) == category:
            root = source[root]["parent"]
        chains[(category, root)].append(name)
    mappings, audit = {}, []
    for (category, root), nodes in sorted(chains.items()):
        def depth(name):
            d = 0
            while name != root:
                name = source[name]["parent"]
                d += 1
            return d
        # Ordinary UMA garment chains are linear. Branches get a separate
        # audit and use monotonic depth assignments rather than cross anatomy.
        nodes.sort(key=lambda n: (depth(n), source[n]["semantic"], n))
        candidates = [v for k, v in targets.items() if f"_{category}" in k]
        if not candidates:
            continue
        best = None
        for chain in candidates:
            count = len(nodes)
            if count <= len(chain):
                assignments = combinations(range(len(chain)), count)
            else:
                # More source segments than CK3 segments: monotonic grouping;
                # explicitly recorded rather than pretending every joint survived.
                assignments = [tuple(round(i * (len(chain) - 1) / max(1, count - 1)) for i in range(count))]
            for indices in assignments:
                cost = sum((source[n]["head"] - heads[chain[i]]).length_squared for n, i in zip(nodes, indices))
                item = (cost, tuple(chain[i] for i in indices))
                if best is None or item < best:
                    best = item
        assigned = best[1]
        for name, target in zip(nodes, assigned):
            mappings[name] = target
        audit.append({"source_root": root, "category": category, "source_chain": nodes,
                      "target_chain": list(assigned), "distinct_target_segments": len(set(assigned)),
                      "source_segments": len(nodes), "position_cost": best[0],
                      "segmentation_preserved": len(set(assigned)) == len(nodes)})
    return mappings, audit


def _face_region(name, targets):
    side = "l" if re.search(r"_L(?:_|$)", name) else "r" if re.search(r"_R(?:_|$)", name) else None
    result = None
    if name == "Mouth_In" or name.startswith(("Mouth_bottom_", "Tooth_bottom", "Tongue")):
        result = "bn_h_jaw"
    elif name == "M_Line00":
        result = "bn_h_neck_1"
    elif name.startswith(("Mouth_up_", "Tooth_up")):
        result = "bn_h_mouth_upperLip"
    elif side:
        if name.startswith(("Eye_up_", "Eyelashes_")):
            result = f"bn_h_eye_{side}_lidUpper"
        elif name.startswith("Eye_bottom_"):
            result = f"bn_h_eye_{side}_lidLower"
        elif name.startswith("Eyebrow_"):
            result = f"bn_h_forehead_{side}_browOuter"
        elif name.startswith("Mouth_sub_"):
            result = f"bn_h_cheek_{side}_side"
    return result if result in targets else None


def adapt_rig(rig, objects, reference_path, pdx, pdx_data, kind):
    """Replace UMA rig with a complete CK3 skeleton and accumulated max4 skin.

    ``kind`` is ``body``, ``head`` or ``tail``; tail uses the body reference.
    ``objects`` contains the meshes owned by this export. Meshes sharing the old
    rig but omitted from this list are rejected to prevent destructive rebinding.
    Every source bone and weighted group has a reported mapping or fallback.
    """
    if kind not in ("body", "head", "tail"):
        raise ValueError(f"Unsupported rig kind: {kind}")
    if rig.type != "ARMATURE":
        raise TypeError("Source rig must be an armature")
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    objects = list(dict.fromkeys(o for o in objects if o.type == "MESH"))
    if not objects:
        raise ValueError("No mesh objects to adapt")
    for obj in bpy.data.objects:
        uses_old_rig = obj.parent == rig or any(m.type == "ARMATURE" and m.object == rig for m in obj.modifiers)
        if obj.type == "MESH" and uses_old_rig and obj not in objects:
            raise ValueError(f"Mesh using source rig omitted from export: {obj.name}")
    names, order, reference = _read_reference(reference_path, pdx, pdx_data, kind)
    source = {
        b.name: {"semantic": str(b.get("unity_name", b.name)),
                 "head": rig.matrix_world @ b.head_local,
                 "parent": b.parent.name if b.parent else None}
        for b in rig.data.bones
    }
    for entry in source.values():
        if not all(math.isfinite(v) for v in entry["head"]):
            raise ValueError("Non-finite source joint position")
    by_semantic = defaultdict(list)
    for name, entry in source.items():
        by_semantic[entry["semantic"]].append(name)
    semantic = {s: t for s, t in _semantic_map(kind).items() if s in by_semantic}
    missing_targets = sorted(set(semantic.values()) - set(reference))
    if missing_targets:
        raise ValueError(f"Reference lacks available semantic joint counterparts: {missing_targets}")
    primary = {s: min(by_semantic[s], key=lambda n: (n != s, len(n), n)) for s in semantic}
    direct = {target: source[primary[s]]["head"].copy() for s, target in semantic.items()}
    # Infer units from anatomical distances, excluding Position and attachment
    # nodes. Median resists differences in facial/body proportions.
    measures = []
    anatomy = [s for s in semantic if s not in ("Position", "Hand_Attach_L", "Hand_Attach_R")]
    for a, b in combinations(anatomy, 2):
        source_distance = (source[primary[a]]["head"] - source[primary[b]]["head"]).length
        reference_distance = (reference[semantic[a]]["matrix"].translation - reference[semantic[b]]["matrix"].translation).length
        if source_distance > 1e-5 and reference_distance > 0.1:
            measures.append(source_distance / reference_distance)
    scale = median(measures) if measures else 0.01
    assert 0.000001 < scale < 100.0, f"Implausible helper scale: {scale}"
    initial_heads = _scaled_heads(order, reference, direct, scale)
    garments, garment_audit = _garment_mapping(source, reference, initial_heads) if kind != "head" else ({}, [])
    # When multiple source garment chains use the same CK3 target, retain the
    # most spatially compatible source bind point and disclose all merges.
    garment_drivers = {}
    for name, target in garments.items():
        candidate = ((source[name]["head"] - initial_heads[target]).length_squared, name)
        if target not in garment_drivers or candidate < garment_drivers[target]:
            garment_drivers[target] = candidate
    for target, (_, name) in garment_drivers.items():
        direct[target] = source[name]["head"].copy()
    heads = _scaled_heads(order, reference, direct, scale)
    matrices = {}
    for name in names:
        matrices[name] = reference[name]["matrix"].copy()
        matrices[name].translation = heads[name]
    source_mapping = {}
    for name, entry in source.items():
        if entry["semantic"] in semantic:
            target, method, ancestor = semantic[entry["semantic"]], "semantic_joint", name
        elif name in garments:
            target, method, ancestor = garments[name], "garment_chain_position", name
        else:
            face = _face_region(entry["semantic"], reference) if kind == "head" else None
            if face:
                target, method, ancestor = face, "facial_semantic_region", None
            else:
                current, chain = name, []
                target, ancestor = None, None
                while current:
                    chain.append(current)
                    s = source[current]["semantic"]
                    # Head/Chest have no separate torso counterpart; collapsing
                    # their weights does not override Neck/Spine bind positions.
                    if kind != "head" and s in ("Head", "Chest"):
                        target = "bn_sp_cervical" if s == "Head" else "bn_sp_thoracic"
                        ancestor = current
                        break
                    if s in semantic and s != "Position":
                        target, ancestor = semantic[s], current
                        break
                    if current in garments:
                        target, ancestor = garments[current], current
                        break
                    current = source[current]["parent"]
                if target is None:
                    target = "bn_h_head" if kind == "head" and "Head" in semantic else "bn_h_neck_1" if kind == "head" else "body_root"
                    method = "unresolved_hierarchy_default"
                else:
                    method = "semantic_ancestor_collapse"
        source_mapping[name] = {"source_name": entry["semantic"], "target": target,
                                "method": method, "ancestor": ancestor,
                                "source_head_world": list(entry["head"])}
    before = {obj.name: _capture(obj) for obj in objects}
    weights = {}
    unknown_groups = {}
    for obj in objects:
        group_names = {g.index: g.name for g in obj.vertex_groups}
        weights[obj.name] = [{group_names[g.group]: g.weight for g in v.groups
                              if g.weight > 0 and group_names[g.group] in source_mapping}
                             for v in obj.data.vertices]
        unknown_groups[obj.name] = [g.name for g in obj.vertex_groups if g.name not in source_mapping]
    new_data = bpy.data.armatures.new(f"CK3_{kind}_Skeleton")
    new_rig = bpy.data.objects.new(f"CK3_{kind}_Rig", new_data)
    (rig.users_collection[0] if rig.users_collection else bpy.context.collection).objects.link(new_rig)
    new_rig.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.objects.active = new_rig
    new_rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name in names:
        bone = new_data.edit_bones.new(name)
        bone.head = (0, 0, 0)
        bone.tail = (0, 0.01, 0)
        bone.matrix = matrices[name]
        children = [n for n in names if reference[n]["parent"] == name]
        positive_lengths = [(heads[n] - heads[name]).dot(matrices[name].to_3x3() @ Vector((0, 1, 0))) for n in children]
        positive_lengths = [v for v in positive_lengths if v > 1e-5]
        ref_distances = [(reference[n]["matrix"].translation - reference[name]["matrix"].translation).length * scale for n in children]
        # A submillimetre displayed tail at metre-size world coordinates loses
        # substantial angular precision in Blender's float edit-bone storage.
        # Display length does not affect either bind point or inverse bind.
        bone.length = max(0.01, min(0.25, min(positive_lengths) if positive_lengths else min(ref_distances) if ref_distances else 0.01))
        # matrix assignment decomposes the reference frame into head/tail/roll.
        # Blender's decomposition loses roll precision when the bone Y axis
        # lies near negative world Y (notably the reference right shoulder).
        # Re-align the stored roll to the reference Z axis after final length;
        # this retains the same bind head and direction, without relaxing QA.
        bone.align_roll(matrices[name].to_3x3() @ Vector((0, 0, 1)))
        bone.use_connect = False
        bone.use_deform = True
        bone["ck3_reference_joint"] = name
        bone["uma_bind_method"] = "source_joint" if name in direct else "scaled_reference_parent_local_offset"
        bone["uma_source_joint"] = next((primary[s] for s, t in semantic.items() if t == name), garment_drivers.get(name, (None, ""))[1])
    for name in names:
        parent = reference[name]["parent"]
        new_data.edit_bones[name].parent = new_data.edit_bones[parent] if parent else None
    bpy.ops.object.mode_set(mode="OBJECT")
    new_rig.show_in_front = True
    new_data.pose_position = "POSE"
    report_weights = {}
    for obj in objects:
        for group in list(obj.vertex_groups):
            if group.name in source_mapping or group.name in reference:
                obj.vertex_groups.remove(group)
        groups = {name: obj.vertex_groups.new(name=name) for name in names}
        audit = {"vertices": len(obj.data.vertices), "trimmed_vertices": 0, "unweighted_vertices_assigned": 0,
                 "discarded_weight_mass": 0.0, "input_weight_mass": 0.0, "max_influences_before_trim": 0,
                 "max_influences_after_trim": 0, "maximum_normalization_error": 0.0,
                 "source_weight_mass": {}, "discarded_source_weight_mass": {},
                 "non_skeletal_groups_preserved": unknown_groups[obj.name]}
        for vertex, ws in enumerate(weights[obj.name]):
            accumulated = defaultdict(float)
            for name, weight in ws.items():
                accumulated[source_mapping[name]["target"]] += weight
                audit["source_weight_mass"][name] = audit["source_weight_mass"].get(name, 0.0) + weight
            audit["input_weight_mass"] += sum(ws.values())
            influences = sorted(accumulated.items(), key=lambda x: (-x[1], x[0]))
            audit["max_influences_before_trim"] = max(audit["max_influences_before_trim"], len(influences))
            if len(influences) > 4:
                audit["trimmed_vertices"] += 1
                audit["discarded_weight_mass"] += sum(w for _, w in influences[4:])
                discarded_targets = {n for n, _ in influences[4:]}
                for name, weight in ws.items():
                    if source_mapping[name]["target"] in discarded_targets:
                        audit["discarded_source_weight_mass"][name] = audit["discarded_source_weight_mass"].get(name, 0.0) + weight
            influences = influences[:4]
            if not influences:
                target = "bn_h_head" if kind == "head" else "body_root"
                influences = [(target, 1.0)]
                audit["unweighted_vertices_assigned"] += 1
            total = sum(w for _, w in influences)
            for name, weight in influences:
                groups[name].add([vertex], weight / total, "REPLACE")
            audit["max_influences_after_trim"] = max(audit["max_influences_after_trim"], len(influences))
        found = False
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == rig:
                modifier.object = new_rig
                # Rest pose linear skinning has identity deformation regardless
                # of the new bone frame. Existing modifier options are retained.
                found = True
        if not found:
            modifier = obj.modifiers.new("CK3 skin", "ARMATURE")
            modifier.object = new_rig
        if obj.parent == rig:
            obj.parent = new_rig
            obj.parent_type = "OBJECT"
            obj.parent_bone = ""
            obj.matrix_parent_inverse = new_rig.matrix_world.inverted() @ before[obj.name]["world"] @ before[obj.name]["basis"].inverted()
            obj.matrix_basis = before[obj.name]["basis"]
        report_weights[obj.name] = audit
    for child in list(rig.children):
        if child not in objects:
            world, basis = child.matrix_world.copy(), child.matrix_basis.copy()
            child.parent = new_rig
            child.parent_type = "OBJECT"
            child.matrix_parent_inverse = new_rig.matrix_world.inverted() @ world @ basis.inverted()
            child.matrix_basis = basis
    bpy.context.view_layer.update()
    invariants = {obj.name: _check_unchanged(obj, before[obj.name]) for obj in objects}
    parent_errors, max_head_error, max_orientation_error = [], 0.0, 0.0
    for name in names:
        bone = new_data.bones[name]
        if (bone.parent.name if bone.parent else None) != reference[name]["parent"]:
            parent_errors.append(name)
        max_head_error = max(max_head_error, (bone.head_local - heads[name]).length)
        max_orientation_error = max(max_orientation_error, _matrix_error(bone.matrix_local.to_3x3().to_4x4(), reference[name]["matrix"].to_3x3().to_4x4()))
    assert not parent_errors and len(new_data.bones) == len(names), "CK3 skeleton parent/name contract failed"
    assert max_head_error < 1e-6, "Adapted joint positions changed during armature construction"
    assert max_orientation_error < 5e-5, f"CK3 reference orientations changed: {max_orientation_error}"
    assert all((new_data.bones[t].head_local - source[primary[s]]["head"]).length < 1e-6 for s, t in semantic.items()), "Semantic landmark mismatch"
    for obj in objects:
        targets = {g.index for g in obj.vertex_groups if g.name in reference}
        for vertex in obj.data.vertices:
            influences = [g.weight for g in vertex.groups if g.group in targets and g.weight > 0]
            error = abs(sum(influences) - 1.0)
            assert len(influences) <= 4 and error < 1e-6, "Invalid target weights"
            report_weights[obj.name]["maximum_normalization_error"] = max(report_weights[obj.name]["maximum_normalization_error"], error)
    old_name = rig.name
    bpy.data.objects.remove(rig, do_unlink=True)
    target_usage = Counter(m["target"] for m in source_mapping.values() if m["method"] == "garment_chain_position")
    return {
        "kind": kind, "rig_name": new_rig.name, "removed_rig_name": old_name,
        "reference_path": str(Path(reference_path).resolve()), "reference_bones": len(names),
        "source_bones": len(source), "semantic_mapping": semantic,
        "semantic_points_expected_from_available_source": len(semantic), "semantic_points_verified": len(semantic),
        "helper_offset_scale": scale, "helper_scale_measurements": len(measures),
        "helper_scale_method": "median anatomical source/reference distances" if measures else "fallback 0.01; insufficient semantic distances",
        "source_mapping": source_mapping, "mapping_methods": dict(Counter(v["method"] for v in source_mapping.values())),
        "garment_chains": garment_audit, "garment_target_merges": {n: count for n, count in target_usage.items() if count > 1},
        "generated_helper_bones": [n for n in names if n not in direct],
        "target_bones": {n: {"parent": reference[n]["parent"], "head_world": list(heads[n]),
                             "reference_bind_matrix": [list(row) for row in reference[n]["matrix"]],
                             "adapted_bind_matrix": [list(row) for row in matrices[n]],
                             "method": "source_joint" if n in direct else "scaled_reference_parent_local_offset"} for n in names},
        "weights": report_weights, "invariants": invariants,
        "parent_contract_verified": True, "maximum_joint_error": max_head_error,
        "maximum_orientation_error": max_orientation_error,
        "limitations": ["CK3 animation retargeting and in-game deformation are untested.",
                        "Generated helper alignment uses scaled CK3 parent-local offsets, not artist-authored UMA landmarks.",
                        "Hair, tail and unsupported accessory chains collapse to semantic ancestors; their independent motion is lost."],
    }
