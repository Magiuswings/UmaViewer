"""Conservative source-topology morph matching, with no geometry reconstruction.

Public API (stdlib only; Blender is accepted through duck typing):
  index_manifest(path, family_overrides=None) -> JSON-serializable evidence index.
  topology_mapping(base, target) -> (base-index -> target-index list | None, reason).
  add_shape_key(base, target, name) -> Blender KeyBlock (Basis stays unchanged).
  make_blendshape_object(base, target, name) -> copied Blender object/mesh.

Only identical directed polygon connectivity AND every existing UV layer qualify.
UV values use exact floating-point equality. UV atlas changes cannot be shape keys.
Duplicate UV signatures are accepted only when original vertex indices independently
pass the full face/UV comparison; otherwise the correspondence is ambiguous.
The index never treats a shared costume variant number as proof of shared clothing.
All categories, including incompatible apparel and all body bases, remain indexed.
"""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
try:
    from body_profiles import body_profile, profiles_compatible
except ModuleNotFoundError:
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'HeadlessExporter'))
    from body_profiles import body_profile, profiles_compatible


APPAREL = frozenset(("clothing", "footwear", "headwear"))
ANATOMICAL = frozenset(("eyebrows", "eyes", "face", "face_effects", "tail"))


def _cycle(values):
    values = tuple(values)
    return min(values[i:] + values[:i] for i in range(len(values)))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _xy(value):
    return (float(value["x"]), float(value["y"])) if isinstance(value, dict) else tuple(map(float, value[:2]))


def _mesh_view(obj):
    """Return vertices, faces, and face-corner UV vectors without touching input."""
    if isinstance(obj, dict):
        vertices = obj["vertices"]
        raw = obj.get("faces", ())
        faces = []
        if raw and isinstance(raw[0], dict):
            for section in raw:
                indices = section.get("triangles", ())
                if len(indices) % 3:
                    raise ValueError("Source triangle index array is not divisible by three")
                faces.extend(tuple(indices[i:i + 3]) for i in range(0, len(indices), 3))
        else:
            faces = [tuple(face) for face in raw]
        layers = sorted(obj.get("uvs", ()), key=lambda item: item.get("channel", 0))
        names = [str(layer.get("channel", i)) for i, layer in enumerate(layers)]
        uv = [[tuple(_xy(layer["values"][index]) for layer in layers) for index in face] for face in faces]
        return vertices, faces, uv, names
    data = obj.data if hasattr(obj, "data") else obj
    vertices = data.vertices
    faces = [tuple(p.vertices) for p in data.polygons]
    layers = list(data.uv_layers)
    uv = [[tuple(tuple(float(v) for v in layer.data[index].uv) for layer in layers)
           for index in p.loop_indices] for p in data.polygons]
    return vertices, faces, uv, [layer.name for layer in layers]


def _corner_faces(faces, uv, mapping=None):
    return Counter(_cycle(tuple((mapping[index] if mapping else index, corner)
                               for index, corner in zip(face, corners)))
                   for face, corners in zip(faces, uv))


def topology_mapping(base_object, target_object):
    """Return a verified bijection in base order, or a specific rejection reason.

    Translation/scale/warping is never used to determine vertex correspondence.
    Face order and cyclic corner order may vary; winding and all UVs may not.
    """
    try:
        bv, bf, bu, bl = _mesh_view(base_object)
        tv, tf, tu, tl = _mesh_view(target_object)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        return None, "invalid_mesh: " + str(exc)
    if len(bv) != len(tv):
        return None, "vertex_count_mismatch:%d!=%d" % (len(bv), len(tv))
    if len(bf) != len(tf):
        return None, "face_count_mismatch:%d!=%d" % (len(bf), len(tf))
    if not bf:
        return None, "empty_mesh"
    if not bl or not tl:
        return None, "missing_uv_evidence"
    if bl != tl:
        return None, "uv_layer_mismatch:" + repr((bl, tl))
    identity = list(range(len(bv)))
    target_faces = _corner_faces(tf, tu)
    if _corner_faces(bf, bu) == target_faces:
        return identity, "verified_original_indices_connectivity_and_all_uv_layers"
    # Unused vertices have no UV/topology correspondence and cannot be guessed.
    def signatures(vertex_count, faces, uv):
        values = [[] for _ in range(vertex_count)]
        for face, corners in zip(faces, uv):
            for index, corner in zip(face, corners):
                values[index].append(corner)
        return [tuple(sorted(values)) for values in values]
    bs = signatures(len(bv), bf, bu)
    ts = signatures(len(tv), tf, tu)
    if Counter(bs) != Counter(ts):
        return None, "uv_vertex_signature_mismatch"
    if any(not signature for signature in bs):
        return None, "unused_vertex_correspondence_ambiguous"
    if len(set(bs)) != len(bs):
        return None, "ambiguous_duplicate_uvs_original_indices_not_verified"
    lookup = {signature: index for index, signature in enumerate(ts)}
    mapping = [lookup[signature] for signature in bs]
    if _corner_faces(bf, bu, mapping) != target_faces:
        return None, "directed_face_connectivity_mismatch"
    return mapping, "verified_unique_uv_bijection_and_directed_connectivity"


def _category_mesh(mesh, category):
    sections = [s for s in mesh["faces"] if s.get("category") == category and s.get("triangles")]
    used = sorted({v for section in sections for v in section["triangles"]})
    remap = {old: new for new, old in enumerate(used)}
    return {"vertices": [mesh["vertices"][v] for v in used],
            "faces": [{"triangles": [remap[v] for v in section["triangles"]]} for section in sections],
            "uvs": [{"channel": layer["channel"], "values": [layer["values"][v] for v in used]}
                    for layer in mesh.get("uvs", ())]}, used


def _virtual_skirts(mesh, data):
    """Inspect skirt-bone influence and connected apparel, never split objects."""
    skirt_bones = {b["id"] for b in data.get("bones", ()) if "skirt" in b["name"].lower()}
    influence = defaultdict(float)
    for weight in mesh.get("weights", ()):
        if weight["bone"] in skirt_bones:
            influence[weight["vertex"]] += weight["weight"]
    seeds = {v for v, value in influence.items() if value > .5}
    triangles = []
    for section_index, section in enumerate(mesh.get("faces", ())):
        if section.get("category") != "clothing":
            continue
        indices = section.get("triangles", ())
        triangles.extend((section_index, offset // 3, tuple(indices[offset:offset + 3]))
                         for offset in range(0, len(indices), 3))
    parent = {}
    def find(v):
        parent.setdefault(v, v)
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    for _, _, triangle in triangles:
        a = find(triangle[0])
        for v in triangle[1:]:
            parent[find(v)] = a
    seeded_components = {find(v) for v in seeds if v in parent}
    modes = [("skirt_dominant_virtual", None), ("skirt_connected_virtual", None)]
    modes.extend(("skirt_component_virtual", root) for root in sorted(seeded_components))
    for mode, component_root in modes:
        selected = [(s, f, tri) for s, f, tri in triangles
                    if (all(v in seeds for v in tri) if mode == "skirt_dominant_virtual"
                        else (find(tri[0]) == component_root if component_root is not None
                              else find(tri[0]) in seeded_components))]
        if not selected:
            continue
        used = sorted({v for _, _, tri in selected for v in tri})
        remap = {v: i for i, v in enumerate(used)}
        view = {"vertices": [mesh["vertices"][v] for v in used],
                "faces": [tuple(remap[v] for v in tri) for _, _, tri in selected],
                "uvs": [{"channel": layer["channel"], "values": [layer["values"][v] for v in used]}
                        for layer in mesh.get("uvs", ())]}
        yield mode, view, used, [[s, f] for s, f, _ in selected], sorted(skirt_bones)


def _evidence(mesh):
    vertices, faces, uv, layers = _mesh_view(mesh)
    # UV-labeled face fingerprint is invariant to vertex/face ordering; this is a
    # candidate filter only. topology_mapping is still the acceptance gate.
    uv_faces = sorted(_cycle(tuple(corner for corner in corners)) for corners in uv)
    return {"vertices": len(vertices), "faces": len(faces), "uv_layers": layers,
            "index_connectivity_sha256": _digest(sorted(_cycle(face) for face in faces)),
            "uv_face_sha256": _digest(uv_faces),
            "index_uv_connectivity_sha256": _digest(sorted(_corner_faces(faces, uv).items()))}


def index_manifest(manifest_path, family_overrides=None):
    """Index every character/outfit/category and strict morph compatibility.

    family_overrides optionally maps exact job name/source to a confirmed family.
    Such declarations only affect semantics; they never bypass topology checks.
    Default families are exact source assets, NOT numeric variant suffixes. A
    cross-character 90 outfit is labeled a school-uniform investigation candidate,
    but gets no shared-family claim from that number alone.
    """
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    overrides = family_overrides or {}
    result = {"version": 1, "manifest": str(path.resolve()), "policy": {
        "mapping": "exact directed connectivity plus all UV layers",
        "geometry": "source coordinates; no translation, warp, retopology or broad-clothing resplit",
        "family": "exact source identity or explicit supplied family declaration",
        "variant_number_alone_is_family_evidence": False},
        "characters": manifest.get("characters", []), "jobs": [], "records": [],
        "body_base_candidates": [], "topology_pairs": [], "compatible_groups": [],
        "skirt_component_rejections_summary": {}}
    views = {}
    for job in manifest.get("jobs", ()):
        snapshot_path = path.parent / job["snapshot"]
        data = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
        source = job.get("source", data.get("source", ""))
        family = overrides.get(job["name"], overrides.get(source, source))
        explicit = job["name"] in overrides or source in overrides
        profile=body_profile(source,job.get('kind',data.get('source_kind')))
        entry = {"name": job["name"], "character_id": job.get("character_id"),
                 "source": source, "snapshot": str(snapshot_path.resolve()), "kind": job.get("kind"),
                 "variant": data.get("variant"), "family": family,"body_profile":profile,
                 "family_evidence": "explicit_declaration" if explicit else "exact_source_asset",
                 "categories": job.get("categories", []), "empty_apparel": job.get("empty_apparel", []),
                 "records": []}
        if job.get("kind") == "body" and str(data.get("variant")) == "90":
            entry["investigation_candidate"] = "school_uniform; unconfirmed cross-character garment family"
        result["jobs"].append(entry)
        for mesh_index, mesh in enumerate(data.get("meshes", ())):
            categories = sorted({section.get("category", "unknown") for section in mesh.get("faces", ())
                                 if section.get("triangles")})
            views_to_index = []
            for category in ["whole_mesh"] + categories:
                view, used = (mesh, list(range(len(mesh["vertices"])))) if category == "whole_mesh" else _category_mesh(mesh, category)
                views_to_index.append((category, view, used, None, None))
            if job.get("kind") == "body":
                views_to_index.extend(_virtual_skirts(mesh, data))
            for category, view, used, face_ids, skirt_bones in views_to_index:
                record_id = job["name"] + "::" + str(mesh_index) + "::" + category
                if category == "skirt_component_virtual":
                    record_id += "::component_" + _digest(face_ids)[:12]
                record_family = family
                family_evidence = entry["family_evidence"]
                # Anatomical role is explicit semantic identity; costume suffix is
                # never used for garments. Matching still demands all exact UVs.
                if category in ANATOMICAL and not explicit:
                    record_family = "anatomical:" + category
                    family_evidence = "source_anatomical_category"
                if profile and not explicit:
                    record_family = "generic_body_profile:" + profile['geometry_key']
                    family_evidence = "exact_generic_costume_and_body_dimensions_including_bust"
                record = {"id": record_id, "job": job["name"], "mesh_index": mesh_index,
                          "mesh_name": mesh.get("name"), "category": category,
                          "character_id": job.get("character_id"), "family": record_family,"body_profile":profile,
                          "family_evidence": family_evidence,
                          "active": mesh.get("active", True), "source": source,
                          "is_apparel": category in APPAREL,
                          "source_vertex_indices_sha256": _digest(used), **_evidence(view)}
                if face_ids is not None:
                    record.update(virtual_subset=True, source_vertex_indices=used,
                                  source_face_ids=face_ids, skirt_bone_ids=skirt_bones)
                result["records"].append(record)
                entry["records"].append(record_id)
                views[record_id] = view
                if job.get("kind") == "body" and category == "whole_mesh":
                    result["body_base_candidates"].append(record_id)
    # Every same-category pair is assessed: cardinality rejection is evidence too.
    buckets = defaultdict(list)
    for record in result["records"]:
        buckets[record["category"]].append(record)
    parent = {record["id"]: record["id"] for record in result["records"]}
    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value
    for category, records in buckets.items():
        for i, base in enumerate(records):
            for target in records[i + 1:]:
                # Different disconnected regions of one outfit are NOT morph
                # variants. UV-identical tiny decorations cannot become keys.
                if base["job"] == target["job"]:
                    continue
                mapping = None
                if base["vertices"] != target["vertices"]:
                    reason = "vertex_count_mismatch:%d!=%d" % (base["vertices"], target["vertices"])
                elif base["faces"] != target["faces"]:
                    reason = "face_count_mismatch:%d!=%d" % (base["faces"], target["faces"])
                elif base["uv_layers"] != target["uv_layers"]:
                    reason = "uv_layer_mismatch"
                elif base["uv_face_sha256"] != target["uv_face_sha256"]:
                    reason = "uv_face_fingerprint_mismatch"
                else:
                    mapping, reason = topology_mapping(views[base["id"]], views[target["id"]])
                if category == "skirt_component_virtual" and mapping is None:
                    counts = result["skirt_component_rejections_summary"]
                    reason_class = reason.split(":", 1)[0]
                    counts[reason_class] = counts.get(reason_class, 0) + 1
                    continue
                compatible = mapping is not None
                same_family = base["family"] == target["family"]
                same_profile=profiles_compatible(base['body_profile'],target['body_profile'])
                pair = {"base": base["id"], "target": target["id"], "category": category,
                        "topology_compatible": compatible, "reason": reason,
                        "same_confirmed_family": same_family,
                        "shape_key_eligible": compatible and same_family and same_profile,
                        "same_body_profile":same_profile,
                        "base_bust":base['body_profile']['bust'] if base['body_profile'] else None,
                        "target_bust":target['body_profile']['bust'] if target['body_profile'] else None,
                        "eligibility_rejection":'body_profile_mismatch' if not same_profile else None,
                        "cross_character": base["character_id"] != target["character_id"]}
                if compatible:
                    pair["mapping_sha256"] = _digest(mapping)
                    pair["mapping_identity"] = mapping == list(range(len(mapping)))
                    base_positions = views[base["id"]]["vertices"]
                    target_positions = views[target["id"]]["vertices"]
                    def xyz(value):
                        return [value[axis] for axis in ("x", "y", "z")] if isinstance(value, dict) else value[:3]
                    pair["max_source_coordinate_delta"] = max(
                        sum((a - b) ** 2 for a, b in zip(xyz(base_positions[i]), xyz(target_positions[j]))) ** .5
                        for i, j in enumerate(mapping))
                    pair["uv_tolerance"] = 0.0
                    if base.get("virtual_subset"):
                        pair["base_to_target_mapping"] = mapping
                    if same_family and same_profile:
                        parent[find(target["id"])] = find(base["id"])
                result["topology_pairs"].append(pair)
    groups = defaultdict(list)
    for record in result["records"]:
        groups[find(record["id"])].append(record["id"])
    result["compatible_groups"] = [{"base": values[0], "targets": values[1:]}
                                     for values in groups.values() if len(values) > 1]
    result["summary"] = {"jobs": len(result["jobs"]), "records": len(result["records"]),
        "body_base_candidates": len(result["body_base_candidates"]),
        "topology_compatible_pairs": sum(p["topology_compatible"] for p in result["topology_pairs"]),
        "eligible_pairs": sum(p["shape_key_eligible"] for p in result["topology_pairs"]),
        "cross_character_apparel_compatible_pairs": sum(p["cross_character"] and p["category"] in APPAREL and p["topology_compatible"] for p in result["topology_pairs"])}
    return result


def _safe_mapping(base, target):
    if tuple(tuple(float(v) for v in row) for row in base.matrix_world) != tuple(tuple(float(v) for v in row) for row in target.matrix_world):
        raise ValueError("Object transforms differ; no translation/warping is permitted")
    mapping, reason = topology_mapping(base, target)
    if mapping is None:
        raise ValueError(reason)
    return mapping


def add_shape_key(base, target, name):
    """Add source target coordinates to a key, retaining Basis, mesh and UVs."""
    mapping = _safe_mapping(base, target)
    if base.data.shape_keys is None:
        base.shape_key_add(name="Basis", from_mix=False)
    if name in base.data.shape_keys.key_blocks:
        raise ValueError("Shape key already exists: " + name)
    key = base.shape_key_add(name=name, from_mix=False)
    key.value = 0.0
    for i, target_index in enumerate(mapping):
        key.data[i].co = target.data.vertices[target_index].co
    # Blender 4.2 KeyBlocks do not support ID properties; the Key datablock does.
    metadata=json.loads(base.data.shape_keys.get('uma_morph_sources','{}'))
    metadata[key.name]={'source_target':target.name,'mapping_sha256':_digest(mapping)}
    base.data.shape_keys['uma_morph_sources']=json.dumps(metadata,sort_keys=True)
    return key


def make_blendshape_object(base, target, name):
    """Return an unlinked copy with base faces/UVs and target original coordinates.

    Caller links and exports with io_pdx_mesh's actual as_blendshape option. No
    artificial transform or coordinate displacement is introduced by this helper.
    """
    mapping = _safe_mapping(base, target)
    obj = base.copy()
    import bpy
    mesh=bpy.data.meshes.new(base.data.name+'_morph_export')
    mesh.from_pydata([target.data.vertices[j].co.copy() for j in mapping],[],
                     [tuple(p.vertices) for p in base.data.polygons])
    mesh.update()
    for mat in base.data.materials:mesh.materials.append(mat)
    for a,b in zip(mesh.polygons,base.data.polygons):
        a.material_index=b.material_index;a.use_smooth=b.use_smooth
    for layer in base.data.uv_layers:
        new=mesh.uv_layers.new(name=layer.name)
        for a,b in zip(new.data,layer.data):a.uv=b.uv
    obj.data=mesh
    obj.name = name
    for group in base.vertex_groups:obj.vertex_groups.new(name=group.name)
    # Do not copy then clear Blender Key datablocks: Blender 4.2 can leave
    # an orphan Key with a NULL 'from' pointer which prevents saving .blend.
    # Copy the base skin weights explicitly onto this temporary export mesh.
    for i,vertex in enumerate(base.data.vertices):
        for influence in vertex.groups:
            obj.vertex_groups[influence.group].add([i],influence.weight,'REPLACE')
    obj["uma_is_blendshape"] = True
    obj["uma_source_target"] = target.name
    obj["uma_mapping_sha256"] = _digest(mapping)
    obj.data.update()
    return obj
