"""Broad apparel groups; keep connected attachments intact instead of naming garments."""
from collections import Counter, defaultdict

APPAREL = ("clothing", "headwear", "footwear")


def components(mesh, records):
    """Weld coincident UV-seam vertices for classification only. Never alter source geometry."""
    parent = {}
    def find(v):
        parent.setdefault(v, v)
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    positions = {}
    for _, triangle in records:
        for v in triangle:
            point = tuple(round(mesh["vertices"][v][axis], 5) for axis in "xyz")
            if point in positions: parent[find(v)] = find(positions[point])
            else: positions[point] = v
        for v in triangle[1:]: parent[find(v)] = find(triangle[0])
    groups = defaultdict(list)
    for record in records: groups[find(record[1][0])].append(record)
    return list(groups.values())


def sample_colors(data, mesh, vertices, resources):
    from PIL import Image
    if not resources or not mesh["uvs"]: return []
    uv = next((u["values"] for u in mesh["uvs"] if u["channel"] == 0), None)
    if uv is None: return []
    colors = []
    for material in {f["material"] for f in mesh["faces"] if f["material"] >= 0}:
        main = next((p for p in data["materials"][material]["properties"] if p["name"] == "_MainTex" and p.get("texture")), None)
        if not main: continue
        with Image.open(resources/main["texture"]) as raw:
            image = raw.convert("RGB")
            for v in vertices:
                u = (uv[v]["x"]*main["scale"][0]+main["offset"][0]) % 1
                t = (uv[v]["y"]*main["scale"][1]+main["offset"][1]) % 1
                colors.append(image.getpixel((min(image.width-1,int(u*image.width)), min(image.height-1,int((1-t)*image.height)))))
    return colors


def hair_reference(data, resources=None):
    """Use the existing undecorated head variant 80 when supplied, without synthesizing hair."""
    neck = next((b["matrix"][7] for b in data["bones"] if b["name"] == "Neck"), 0.)
    points, colors = set(), Counter()
    for mesh in data["meshes"]:
        records = [(f,tuple(f["triangles"][i:i+3])) for f in mesh["faces"] if f["category"] == "hair" for i in range(0,len(f["triangles"]),3)]
        for group in components(mesh,records):
            vertices = {v for _,triangle in group for v in triangle}
            points.update(tuple(round(mesh["vertices"][v][a] - (neck if a == "y" else 0), 4) for a in "xyz") for v in vertices)
            # The largest hair shell supplies colors; ear and ornament swatches are excluded.
            if len(vertices) >= 500:
                colors.update(tuple(round(c/8)*8 for c in rgb) for rgb in sample_colors(data,mesh,vertices,resources))
    return dict(points=points, colors=[c for c,_ in colors.most_common(48)])


def classify(data, reference=None, resources=None):
    bones = {b["id"]: b for b in data["bones"]}
    neck = next((b["matrix"][7] for b in bones.values() if b["name"] == "Neck"), None)
    ancestry = {}
    for ident, bone in bones.items():
        chain, current = [], ident
        while current:
            chain.append(bones[current]["name"].lower())
            current = bones[current].get("parent")
        ancestry[ident] = chain
    garment_hair_bones = set()
    if data["source_kind"] == "head" and reference and reference["colors"] and resources:
        for mesh in data["meshes"]:
            vertices = {v for face in mesh["faces"] if face["category"] in ("hair", "headwear", "clothing") for v in face["triangles"]}
            if len(vertices) < 100: continue
            colors = sample_colors(data,mesh,vertices,resources)
            match = sum(any(sum((a-b)**2 for a,b in zip(rgb,c)) <= 40**2 for c in reference["colors"]) for rgb in colors)/max(len(colors),1)
            if not colors or match >= .5: continue
            for weight in mesh["weights"]:
                if weight["vertex"] not in vertices or weight["weight"] < .05: continue
                current = weight["bone"]
                while current and "hair" in bones[current]["name"].lower():
                    garment_hair_bones.add(current)
                    current = bones[current].get("parent")
    audit = []
    for mesh in data["meshes"]:
        for face in mesh["faces"]:
            if face["category"] in APPAREL:
                face["category"] = "hair" if data["source_kind"] == "head" else "clothing"
        weights = defaultdict(list)
        for w in mesh["weights"]: weights[w["vertex"]].append((w["bone"], w["weight"]))
        records = [(face, tuple(face["triangles"][i:i+3])) for face in mesh["faces"]
                   for i in range(0, len(face["triangles"]), 3)]
        lower_leg_triangles = Counter()
        for face, triangle in records:
            influence = sum(w / 3 for v in triangle for ident, w in weights[v]
                            if any(n.startswith(("knee_", "ankle_", "toe_")) for n in ancestry[ident]))
            if influence > .5: lower_leg_triangles[face["category"]] += 1
        bare_leg = lower_leg_triangles["body_skin"] / max(sum(lower_leg_triangles.values()), 1) > .95
        skin_positions = {tuple(round(mesh["vertices"][v][a], 5) for a in "xyz")
                          for face, triangle in records if face["category"] == "body_skin" for v in triangle}
        candidates = [r for r in records if r[0]["category"] in ("clothing", "hair")]
        assignments = {}
        for group in components(mesh, candidates):
            vertices = {v for _, triangle in group for v in triangle}
            score = Counter()
            for v in vertices:
                total = sum(w for _, w in weights[v]) or 1.
                for ident, w in weights[v]: score[ident] += w / total / len(vertices)
            hair = sum(w for ident, w in score.items() if "hair" in bones[ident]["name"].lower())
            ear = sum(w for ident, w in score.items() if bones[ident]["name"].lower().startswith("ear_"))
            accessory = sum(w for ident, w in score.items() if any(t in bones[ident]["name"].lower() for t in ("acc", "ribbon", "hat", "cap", "ornament")))
            leg = sum(w for ident, w in score.items() if any(n.startswith(("knee_", "ankle_", "toe_", "thigh_")) for n in ancestry[ident]))
            # Skirt chains descend from Hip, while sock ribbons descend from Knee/Ankle.
            lower_leg = sum(w for ident, w in score.items() if any(n.startswith(("knee_", "ankle_", "toe_")) for n in ancestry[ident]))
            head_attachment = sum(w for ident, w in score.items() if "head" in ancestry[ident])
            core_match = 0.
            if reference and neck is not None:
                core_match = sum(tuple(round(mesh["vertices"][v][a] - (neck if a == "y" else 0), 4) for a in "xyz") in reference["points"] for v in vertices) / len(vertices)
            is_hair = group[0][0]["category"] == "hair"
            # Flexible hair / ear geometry and supplied bare-head geometry stay with the base.
            decoration = is_hair and core_match < .85 and hair < .001 and ear < .6 and (accessory > .015 or len(vertices) < 500)
            hair_color_match = None
            colored_hair_match = None
            if is_hair and reference and reference["colors"] and resources:
                colors = sample_colors(data,mesh,vertices,resources)
                if colors:
                    hair_color_match = sum(any(sum((a-b)**2 for a,b in zip(rgb,c)) <= 40**2 for c in reference["colors"]) for rgb in colors)/len(colors)
                    chromatic = [c for c in reference["colors"] if max(c)-min(c) >= 30 and max(c) < 230]
                    colored_hair_match = sum(any(sum((a-b)**2 for a,b in zip(rgb,c)) <= 30**2 for c in chromatic) for rgb in colors)/len(colors)
                    if core_match < .85 and ear < .6 and hair_color_match < .5: decoration = True
                    elif hair_color_match > .75 and accessory < .015 and (hair > .001 or colored_hair_match > .75): decoration = False
            garment_chain = sum(w for ident,w in score.items() if ident in garment_hair_bones)
            if is_hair and garment_chain > .5: decoration = True
            footwear = not is_hair and leg > .55 and lower_leg > .12
            # Sparse color-sampling misses on bare knees/toenails are anatomy, not imaginary socks.
            bare_skin_fragment = footwear and bare_leg and accessory < .001 and len(vertices) < 80
            skin_contact = sum(tuple(round(mesh["vertices"][v][a], 5) for a in "xyz") in skin_positions for v in vertices) / len(vertices)
            # A small UV color miss fully surrounded by the original skin shares its boundary vertices.
            skin_gap = not is_hair and len(vertices) < 80 and accessory < .001 and skin_contact >= .9
            head = next((b["matrix"] for b in bones.values() if b["name"] == "Head"), None)
            extent = [max(mesh["vertices"][v][a] for v in vertices)-min(mesh["vertices"][v][a] for v in vertices) for a in "xyz"]
            # Body prefabs also carry the small skin stub inside the face, weighted to Head/Neck.
            neck_stub = (not is_hair and head is not None and accessory < .001 and head_attachment > .5
                         and len(vertices) < 40 and max(extent) < .08
                         and all(abs(sum(mesh["vertices"][v][a] for v in vertices)/len(vertices)-head[axis*4+3]) < .08 for axis,a in enumerate("xyz")))
            for face, triangle in group:
                if is_hair and not decoration:
                    assignments[id(face), triangle] = "hair"
                elif bare_skin_fragment or skin_gap or neck_stub:
                    assignments[id(face), triangle] = "body_skin"
                elif footwear:
                    assignments[id(face), triangle] = "footwear"
                else:
                    # Original triangles are routed by their centroid; no new cut vertices.
                    y = sum(mesh["vertices"][v]["y"] for v in triangle) / 3
                    # Raised arms and a collar following Neck still belong to the torso side of the head attachment.
                    above = neck is not None and y >= neck and (is_hair or head_attachment > .5)
                    assignments[id(face), triangle] = "headwear" if above else "clothing"
            audit.append(dict(renderer=mesh["name"], vertices=len(vertices), triangles=len(group),
                              hair_reference_match=core_match, accessory_weight=accessory,
                              hair_color_match=hair_color_match,
                              chromatic_hair_match=colored_hair_match,
                              garment_hair_chain_weight=garment_chain,
                              leg_weight=leg, lower_leg_weight=lower_leg, head_attachment_weight=head_attachment,
                              decoration=decoration, footwear=footwear, bare_skin_fragment=bare_skin_fragment,
                              skin_boundary_contact=skin_contact, skin_gap=skin_gap, neck_stub=neck_stub))
        grouped = defaultdict(list)
        for face, triangle in records:
            category = assignments.get((id(face), triangle), face["category"])
            part = "clothing" if category in APPAREL else "body"
            grouped[part, category, face["material"]].extend(triangle)
        mesh["faces"] = [dict(part=p, category=c, material=m, triangles=t) for (p,c,m),t in grouped.items()]
    counts = Counter()
    for mesh in data["meshes"]:
        for face in mesh["faces"]: counts[face["category"]] += len(face["triangles"]) // 3
    data["segmentation"] = dict(strategy="broad_apparel_v2", boundary_bone="Neck", boundary_y=neck,
                                categories=dict(counts), empty_apparel=[c for c in APPAREL if not counts[c]],
                                components=audit, hair_reference_used=bool(reference))
    data["warnings"] = ["Skin uses face-palette/UV sampling. Hair decorations use intact components, bone ancestry and an optional supplied bare-head reference. Review semantic classification. No missing surfaces reconstructed."]
    return sorted(counts)
