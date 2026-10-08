"""Package verified UMA PDX exports into an isolated CK3 sample-based mod.

Only the requested output directory and its sibling ZIP are written. Existing
nonempty output is rejected. This performs structural/binary validation, not
game-engine validation, deployment, or animation retargeting.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import types
import zipfile

# Reuse the stock interface names, while each target remains a complete UMA
# combination. The neutral stock shape is exposed as bs_body_seated.
VANILLA_BODY_KEYS = {
    "height_1__shape_0__bust_1": ("female_bs_body_neutral", "bs_body_seated"),
    "height_1__shape_0__bust_2": ("female_bs_body_breast_size_max", "bs_body_breast_size_max"),
    "height_1__shape_1__bust_0": ("female_bs_body_breast_size_min", "bs_body_breast_size_min"),
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def parser_only(plugin):
    """Load pdx_data and relative external.six without io_pdx_mesh.__init__."""
    plugin = Path(plugin).resolve()
    name = "_uma_pack_pdx"
    package = types.ModuleType(name)
    package.__path__ = [str(plugin)]
    sys.modules[name] = package
    spec = importlib.util.spec_from_file_location(name + ".pdx_data", plugin / "pdx_data.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def slug(value):
    result = re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_")
    if not result:
        raise ValueError("Empty asset identifier")
    return result


def short_id(value):
    return slug(value)[:65] + "_" + hashlib.sha256(str(value).encode()).hexdigest()[:10]


def quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def clausewitz(text):
    """Strict brace/assignment parser, preserving repeated keys and curve rows."""
    pattern = re.compile(r'\s+|#[^\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#"]+')
    tokens, end = [], 0
    for match in pattern.finditer(text):
        if match.start() != end:
            raise ValueError(f"Unparsed Clausewitz text at character {end}")
        end = match.end()
        token = match.group()
        if not token.isspace() and not token.startswith("#"):
            tokens.append(json.loads(token) if token.startswith('"') else token)
    if end != len(text):
        raise ValueError("Unterminated quoted string")
    cursor = 0
    def block(nested=False):
        nonlocal cursor
        result = []
        while cursor < len(tokens):
            token = tokens[cursor]
            if token == "}":
                if not nested:
                    raise ValueError("Unexpected closing brace")
                cursor += 1
                return result
            if token == "=":
                raise ValueError("Assignment without key")
            if token == "{":
                cursor += 1
                result.append((None, block(True)))
                continue
            cursor += 1
            if cursor < len(tokens) and tokens[cursor] == "=":
                cursor += 1
                if cursor >= len(tokens) or tokens[cursor] in ("}", "="):
                    raise ValueError("Assignment without value")
                if tokens[cursor] == "{":
                    cursor += 1
                    value = block(True)
                else:
                    value = tokens[cursor]
                    cursor += 1
                result.append((token, value))
            else:
                result.append((None, token))
        if nested:
            raise ValueError("Unclosed brace")
        return result
    return block()


def values(node, key):
    return [value for name, value in node if name == key]


def one(node, key):
    found = values(node, key)
    if len(found) != 1:
        raise ValueError(f"Expected exactly one {key}, got {len(found)}")
    return found[0]


def script_atom(value):
    value = str(value)
    return value if re.fullmatch(r'[A-Za-z0-9_.@+-]+', value) else quote(value)


def script_block(node, level=0):
    lines = []
    for key, value in node:
        prefix = "\t" * level + (script_atom(key) + " = " if key is not None else "")
        if isinstance(value, list):
            lines += [prefix + "{", script_block(value, level + 1), "\t" * level + "}"]
        else:
            lines.append(prefix + script_atom(value))
    return "\n".join(lines)


def complete_portrait_types(sample_text, reference_path):
    """Add the four stock sex/age slots without inventing age boundaries."""
    reference_path = Path(reference_path).resolve()
    stock = one(clausewitz(reference_path.read_text(encoding="utf-8-sig")), "human")
    group = copy.deepcopy(one(clausewitz(sample_text), "uma"))
    result, contracts = [], []
    for stock_name in ("male", "female", "boy", "girl"):
        name = "uma_" + stock_name
        original = one(stock, stock_name)
        existing = values(group, name)
        if existing:
            if len(existing) != 1:
                raise ValueError("Duplicate portrait type: " + name)
            node = copy.deepcopy(existing[0])
        else:
            node = copy.deepcopy(original)
            if stock_name == "girl":
                female = one(group, "uma_female")
                node = [(k, one(female, k) if k in ("head", "torso") else v) for k, v in node]
        node = [(k, v) for k, v in node if k not in ("sex", "minimum_age", "maximum_age")]
        age_fields = [(k, copy.deepcopy(v)) for k, v in original if k in ("minimum_age", "maximum_age")]
        if len(age_fields) != 1:
            raise ValueError("Stock portrait age contract differs: " + stock_name)
        node = [("sex", one(original, "sex"))] + age_fields + node
        result.append((name, node))
        contracts.append({"type": name, "stock_type": stock_name, "sex": one(original, "sex"),
                          "age_fields": dict(age_fields), "head": one(node, "head"), "torso": one(node, "torso")})
    result += [(k, v) for k, v in group if k not in {"uma_male", "uma_female", "uma_boy", "uma_girl"}]
    return script_block([("uma", result)]) + "\n", {
        "reference": str(reference_path), "reference_sha256": sha(reference_path),
        "types": contracts, "stock_age_boundaries_preserved": True,
    }


def safe_relative(value):
    p = PurePosixPath(str(value).replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or not p.parts or ":" in p.parts[0]:
        raise ValueError(f"Unsafe relative path: {value}")
    return Path(*p.parts)


def mesh_info(pdx, path):
    root = pdx.read_meshfile(str(path))
    objects = root.find("object")
    if objects is None or not len(objects):
        raise ValueError(f"No mesh object: {path}")
    result = []
    for obj in objects:
        skeleton = obj.find("skeleton")
        bones = [b.tag for b in skeleton] if skeleton is not None else []
        parents = {b.tag: bones[b.attrib["pa"][0]] if "pa" in b.attrib else None for b in skeleton} if bones else {}
        slots = []
        for index, mesh in enumerate(obj.findall("mesh")):
            p = mesh.attrib.get("p", [])
            tri = mesh.attrib.get("tri", [])
            if len(p) % 3 or len(tri) % 3 or any(not math.isfinite(v) for v in p):
                raise ValueError(f"Invalid coordinates/topology: {path}")
            vertices = len(p) // 3
            if any(i < 0 or i >= vertices for i in tri):
                raise ValueError(f"Invalid triangle index: {path}")
            uvs = {k: list(v) for k, v in mesh.attrib.items() if re.fullmatch(r"u[0-3]", k)}
            if any(len(v) != vertices * 2 for v in uvs.values()):
                raise ValueError(f"Invalid UV count: {path}")
            material = mesh.find("material")
            if material is None:
                raise ValueError(f"Missing material: {path}")
            slots.append({"index": index, "vertices": vertices, "triangles": len(tri) // 3,
                          "tri": list(tri), "uvs": uvs, "material": dict(material.attrib)})
        result.append({"name": obj.tag, "bones": bones, "parents": parents, "slots": slots})
    return result


def compare_morph(base, target, source):
    if len(base) != len(target):
        raise ValueError(f"Morph object count mismatch: {source}")
    slots = []
    for a, b in zip(base, target):
        if a["name"] != b["name"] or len(a["slots"]) != len(b["slots"]):
            raise ValueError(f"Morph node/slot mismatch: {source}")
        if a["bones"] != b["bones"] or a["parents"] != b["parents"]:
            raise ValueError(f"Morph skeleton ordering/parents mismatch: {source}")
        for x, y in zip(a["slots"], b["slots"]):
            if x["vertices"] != y["vertices"] or x["tri"] != y["tri"] or x["uvs"] != y["uvs"]:
                raise ValueError(f"Morph vertex ordering/connectivity/UV mismatch: {source}")
            slots.append({"object": a["name"], "index": x["index"], "vertices": x["vertices"], "triangles": x["triangles"]})
    return slots


def copy_checked(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(source) != sha(target):
            raise ValueError(f"Conflicting packaged file: {target}")
    else:
        shutil.copy2(source, target)


class Packager:
    def __init__(self, delivery, output, pdx, state_aliases=()):
        self.delivery, self.output, self.pdx = delivery, output, pdx
        self.asset_root = output / "gfx/models/portraits/uma"
        self.cache, self.binary_checks, self.recipes = {}, [], []
        self.state_aliases = list(dict.fromkeys(["idle", "idle_entry"] + list(state_aliases)))

    def source(self, relative):
        path = self.delivery / safe_relative(relative)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    def info(self, relative):
        relative = str(safe_relative(relative).as_posix())
        if relative not in self.cache:
            self.cache[relative] = mesh_info(self.pdx, self.source(relative))
        return self.cache[relative]

    def copy_mesh(self, relative):
        source = self.source(relative)
        target = self.asset_root / "delivery" / safe_relative(relative)
        copy_checked(source, target)
        for obj in self.info(relative):
            for slot in obj["slots"]:
                for key in ("diff", "n", "spec"):
                    for filename in slot["material"].get(key, []):
                        name = safe_relative(filename)
                        candidates = [source.parent / name, self.delivery / "textures" / name]
                        texture = next((p for p in candidates if p.is_file()), None)
                        if texture is None:
                            raise FileNotFoundError(f"Missing DDS {filename} for {relative}")
                        copy_checked(texture, target.parent / name)
        if sha(source) != sha(target):
            raise AssertionError("Packaging changed binary mesh")
        return "delivery/" + safe_relative(relative).as_posix()

    def meshsettings(self, relative):
        lines, recipe = [], []
        for obj in self.info(relative):
            for slot in obj["slots"]:
                mat = slot["material"]
                lines.append("\tmeshsettings = {\n\t\tname = " + quote(obj["name"]) + "\n\t\tindex = " + str(slot["index"]))
                textures = {}
                for key, label in (("diff", "texture_diffuse"), ("n", "texture_normal"), ("spec", "texture_specular")):
                    if mat.get(key):
                        # CK3 resolves these overrides relative to the .mesh
                        # directory, not the .asset. A delivery/... prefix here
                        # is therefore duplicated by the engine's VFS lookup.
                        texture = safe_relative(mat[key][0])
                        if len(texture.parts) != 1:
                            raise ValueError(f"Expected adjacent binary DDS basename: {texture}")
                        textures[key] = texture.name
                        lines.append("\t\t" + label + " = " + quote(textures[key]))
                shader = mat["shader"][0]
                if shader not in ("portrait_skin", "portrait_attachment", "portrait_skin_face", "portrait_hair", "portrait_eye"):
                    raise ValueError(f"Unsupported verified shader: {shader}")
                lines += ["\t\tshader = " + quote(shader), '\t\tshader_file = "gfx/FX/uma_portrait.shader"', "\t}"]
                recipe.append({"node": obj["name"], "slot": slot["index"], "shader": shader, "textures": textures})
        return "\n".join(lines), recipe

    def asset(self, relative, mesh_name, entity_name, shapes=(), default=None, rest=False):
        file = self.copy_mesh(relative)
        settings, recipe = self.meshsettings(relative)
        lines = ["pdxmesh = {", "\tname = " + quote(mesh_name), "\tfile = " + quote(file),
                 "\tscale = 100", "\tstreaming = Never", settings]
        for shape in shapes:
            shape_file = self.copy_mesh(shape["mesh"])
            self.binary_checks.append({"base": relative, "target": shape["mesh"], "slots": compare_morph(self.info(relative), self.info(shape["mesh"]), shape["mesh"])})
            lines.append("\tblend_shape = { id = " + quote(shape["id"]) + " type = " + quote(shape_file) + " }")
        if rest:
            lines.append('\tanimation = { id = "uma_rest" type = "uma_static_rest.anim" }')
        lines += ["}", "", "entity = {", "\tname = " + quote(entity_name), "\tpdxmesh = " + quote(mesh_name)]
        if rest:
            lines += ["\tgame_data = { portrait_entity_user_data = { color_mask_remap_interval = { interval = { 0.0 1.0 } } portrait_decal = { body_part = torso } } }"]
        for shape in shapes:
            # CK3 prohibits nonzero BS defaults; the ethnicity gene selects
            # the default complete combination after portrait assembly.
            lines.append("\tattribute = { name = " + quote(shape["attribute"]) + " blend_shape = " + quote(shape["id"]) + " default = 0 }")
        if rest:
            lines += ['\tdefault_state = "idle"']
            lines += ["\tstate = { name = " + quote(name) + ' animation = "uma_rest" looping = yes }' for name in self.state_aliases]
        lines += ["}", ""]
        self.recipes.append({"entity": entity_name, "pdxmesh": mesh_name, "source_mesh": relative, "meshsettings": recipe,
                             "scale_metadata": 100, "animation": "uma_static_rest.anim" if rest else None,
                             "texture_resolution": "DDS basenames relative to source_mesh parent",
                             "static_state_aliases": self.state_aliases if rest else [],
                             "shape_attributes": {s["attribute"]: s["id"] for s in shapes}})
        return "\n".join(lines)


def profile_key(profile):
    if profile and all(k in profile for k in ("height", "shape", "bust")):
        return "height_" + str(profile["height"]) + "__shape_" + str(profile["shape"]) + "__bust_" + str(profile["bust"])
    return "source_base"


def static_animation_check(root):
    """Require a constant multiframe clip; report actual frame count."""
    info = root.find("info")
    frames = int(info.attrib.get("sa", [0])[0])
    if frames < 2:
        raise ValueError("Static animation must contain at least two frames; CK3 rejects one-sample animations")
    if not math.isfinite(info.attrib.get("fps", [0])[0]) or info.attrib.get("fps", [0])[0] <= 0:
        raise ValueError("Invalid animation FPS")
    samples = root.find("samples")
    if samples is None:
        raise ValueError("Animation has no samples block")
    widths = {"t": 0, "q": 0, "s": 0}
    for bone in info:
        channels = bone.attrib.get("sa", [""])[0]
        if any(c not in "tqs" for c in channels) or len(set(channels)) != len(channels):
            raise ValueError(f"Invalid animation channels for {bone.tag}: {channels}")
        for channel in channels:
            width = len(bone.attrib.get(channel, []))
            if width != {"t": 3, "q": 4}.get(channel, width) or channel == "s" and width not in (1, 3):
                raise ValueError(f"Invalid animation channel width: {bone.tag}.{channel}")
            widths[channel] += width
    if not any(widths.values()):
        raise ValueError("Static clip needs actual constant keyframe samples, not only a multiframe header")
    maximum = 0.0
    for channel, width in widths.items():
        data = samples.attrib.get(channel, [])
        if len(data) != frames * width or any(not math.isfinite(v) for v in data):
            raise ValueError(f"Animation sample count/values mismatch for {channel}")
        for frame in range(1, frames):
            maximum = max(maximum, max((abs(data[frame * width + i] - data[i]) for i in range(width)), default=0.0))
    if maximum > 1e-6:
        raise ValueError(f"Supplied static animation changes across frames: {maximum}")
    return {"frames": frames, "fps": info.attrib["fps"][0], "sample_widths": widths,
            "maximum_frame_difference": maximum, "constant_samples_verified": True}


def build_mod(sample, delivery, output, plugin, rest_animation, reuse_vanilla_body_asset=None, reuse_vanilla_gene_file=None, portrait_reference=None):
    sample, delivery, output = Path(sample).resolve(), Path(delivery).resolve(), Path(output).resolve()
    rest_animation = Path(rest_animation).resolve()
    if portrait_reference is None or not Path(portrait_reference).is_file():
        raise ValueError("Provide the original 00_human_types.txt to preserve all four age/type contracts")
    if output == delivery or output.is_relative_to(delivery) or delivery.is_relative_to(output):
        raise ValueError("Output must be separate from the input delivery")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output is nonempty; use a new directory to preserve existing mods")
    archive = Path(str(output) + ".zip")
    if archive.exists():
        raise FileExistsError(f"Archive already exists: {archive}")
    manifest_path = delivery / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    verification_path = delivery / "verification.json"
    verified = json.loads(verification_path.read_text(encoding="utf8"))
    if verified.get("passed") is not True or verified.get("in_progress"):
        raise ValueError("Delivery must have a completed passed verification.json")
    groups = manifest.get("morph_groups", [])
    vanilla_key_contract = None
    if reuse_vanilla_body_asset:
        stock_path = Path(reuse_vanilla_body_asset).resolve()
        stock_tree = clausewitz(stock_path.read_text(encoding="utf-8-sig"))
        stock_mesh = one(stock_tree, "pdxmesh")
        stock_entity = one(stock_tree, "entity")
        stock_shapes = {one(s, "id") for s in values(stock_mesh, "blend_shape")}
        stock_attributes = {one(a, "name"): one(a, "blend_shape") for a in values(stock_entity, "attribute") if values(a, "blend_shape")}
        for shape_id, attribute in VANILLA_BODY_KEYS.values():
            if shape_id not in stock_shapes or stock_attributes.get(attribute) != shape_id:
                raise ValueError("Stock body BS contract differs: " + attribute)
        vanilla_key_contract = {"source": str(stock_path), "sha256": sha(stock_path),
                                "mapping": {k: {"id": v[0], "attribute": v[1]} for k, v in VANILLA_BODY_KEYS.items()},
                                "scope": "Default UMA torso aliases only; stock game asset is read-only and is not packaged as an override"}
    vanilla_gene_contract = None
    if reuse_vanilla_gene_file:
        if not vanilla_key_contract:
            raise ValueError("Reusing the stock gene requires the verified stock body BS interface")
        gene_path = Path(reuse_vanilla_gene_file).resolve()
        stock_gene = one(one(clausewitz(gene_path.read_text(encoding="utf-8-sig")), "morph_genes"), "gene_bs_bust")
        rows = [{"template": name, "index": int(one(node, "index"))}
                for name, node in stock_gene if isinstance(node, list)]
        required = {"bust_clothes": "height_1__shape_0__bust_1",
                    "bust_clothes_light": "height_1__shape_1__bust_0",
                    "bust_default": "height_1__shape_0__bust_2"}
        if not set(required).issubset({r["template"] for r in rows}) or len({r["index"] for r in rows}) != len(rows):
            raise ValueError("Stock bust gene template contract differs")
        for row in rows:
            row["combination"] = required.get(row["template"], "height_1__shape_0__bust_1")
        vanilla_gene_contract = {"source": str(gene_path), "sha256": sha(gene_path), "gene": "gene_bs_bust",
                                 "templates": rows, "default_template": "bust_default",
                                 "scope": "UMA gene definitions only; original human gene files are not overridden"}
    bodies = [g for g in groups if g.get("purpose") == "body_type"]
    if not bodies:
        raise ValueError("No verified whole-body body_type morph group")
    def preferred(g):
        p = g.get("base_body_profile") or {}
        return (p.get("costume_id") != "0004", p.get("body_setting") != "00", str(g["name"]))
    default_group = min(bodies, key=preferred)
    if not rest_animation.is_file():
        raise FileNotFoundError(rest_animation)
    pdx = parser_only(plugin)
    rest_root = pdx.read_meshfile(str(rest_animation))
    info = rest_root.find("info")
    if info is None:
        raise ValueError("Rest animation has no info block")
    rest_names = [bone.tag for bone in info]
    default_info = mesh_info(pdx, delivery / safe_relative(default_group["base_mesh"]))
    expected_bones = default_info[0]["bones"]
    if set(rest_names) != set(expected_bones) or len(rest_names) != len(expected_bones):
        raise ValueError("Rest animation skeleton names differ from default body")
    static_clip = static_animation_check(rest_root)
    rest_metadata_path = rest_animation.with_suffix(".json")
    rest_metadata = json.loads(rest_metadata_path.read_text(encoding="utf8")) if rest_metadata_path.is_file() else None
    if rest_metadata and (rest_metadata.get("bones") != len(rest_names) or rest_metadata.get("frames") != static_clip["frames"]):
        raise ValueError("Static pose metadata differs from animation header")
    output.mkdir(parents=True, exist_ok=True)
    preserved = {}
    with zipfile.ZipFile(sample) as z:
        for entry in z.infolist():
            relative = safe_relative(entry.filename)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Sample ZIP contains a symbolic link")
            if entry.is_dir():
                (output / relative).mkdir(parents=True, exist_ok=True)
            else:
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(z.read(entry))
                preserved[relative.as_posix()] = sha(path)
    asset_root = output / "gfx/models/portraits/uma"
    portrait_path = output / "common/portrait_types/uma_portrait_types.txt"
    portrait_text, portrait_contract = complete_portrait_types(portrait_path.read_text(encoding="utf-8-sig"), portrait_reference)
    portrait_path.write_text(portrait_text, encoding="utf-8-sig")
    original_head = mesh_info(pdx, asset_root / "uma_head.mesh")
    original_body = mesh_info(pdx, asset_root / "uma_body.mesh")
    reference_contracts = {61: original_head[0], 134: original_body[0]}
    sample_body_text = (asset_root / "uma_body.asset").read_text(encoding="utf-8-sig")
    sample_body_entity = next(e for e in values(clausewitz(sample_body_text), "entity") if one(e, "name") == "uma_body_entity")
    sample_states = [one(s, "name") for s in values(sample_body_entity, "state")]
    # The sample comments out some valid vanilla entry states (idle_entry).
    # Preserve their names as aliases too, never their original animation refs.
    sample_states += re.findall(r'\bstate\s*=\s*\{[^{}]*?\bname\s*=\s*"([^"\n]+)"', sample_body_text)
    sample_states = list(dict.fromkeys(sample_states))
    pack = Packager(delivery, output, pdx, sample_states)
    for item in manifest.get("components", []):
        for obj in pack.info(item["mesh"]):
            contract = reference_contracts.get(len(obj["bones"]))
            if contract is None or set(obj["bones"]) != set(contract["bones"]) or obj["parents"] != contract["parents"]:
                raise ValueError(f"Sample skeleton names/parents mismatch: {item['mesh']}")
    for group in groups:
        for relative in [group["base_mesh"]] + [t["mesh"] for t in group.get("targets", [])]:
            for obj in pack.info(relative):
                contract = reference_contracts.get(len(obj["bones"]))
                if contract is None or set(obj["bones"]) != set(contract["bones"]) or obj["parents"] != contract["parents"]:
                    raise ValueError(f"Sample morph skeleton names/parents mismatch: {relative}")
    copy_checked(rest_animation, asset_root / "uma_static_rest.anim")
    if rest_metadata_path.is_file():
        copy_checked(rest_metadata_path, asset_root / "uma_static_rest.json")
    library, gene_lines, choices = [], ["morph_genes = {", "\tportrait_group = uma"], []
    default_key = None
    registrations = []
    for group in groups:
        gid = short_id(group["name"])
        is_default = group is default_group
        body_type = group.get("purpose") == "body_type"
        raw_shapes = [{"key": profile_key(group.get("base_body_profile")) if body_type else "source_base", "mesh": group["base_mesh"], "source_job": group.get("base_job")}]
        raw_shapes += list(group.get("targets", []))
        if len({slug(s["key"]) for s in raw_shapes}) != len(raw_shapes):
            raise ValueError(f"Duplicate combination key: {group['name']}")
        shapes = []
        for source in raw_shapes:
            key = slug(source["key"])
            prefix = "uma_combo_" if is_default else "uma_" + gid + "_"
            if is_default and vanilla_key_contract:
                if key not in VANILLA_BODY_KEYS:
                    raise ValueError("No verified stock BS alias for complete combination: " + key)
                shape_id, attribute = VANILLA_BODY_KEYS[key]
            else:
                shape_id, attribute = "female_bs_" + prefix + key, "bs_" + prefix + key
            shapes.append(dict(source, id=shape_id, attribute=attribute))
        if is_default:
            candidates = [s for s in shapes if s["key"] == "height_1__shape_0__bust_2"]
            if not candidates:
                raise ValueError("Default body group lacks verified height_1__shape_0__bust_2")
            selected = candidates[0]
            default_key = selected["key"]
            body_asset = pack.asset(group["base_mesh"], "uma_body_mesh", "uma_body_entity", shapes, selected["attribute"], rest=True)
            (asset_root / "uma_body.asset").write_text(body_asset, encoding="utf8")
        else:
            library.append(pack.asset(group["base_mesh"], "uma_library_" + gid + "_mesh", "uma_library_" + gid + "_entity", shapes))
        registrations.append({"group": group["name"], "purpose": group.get("purpose", "component"), "shapes": shapes, "default_portrait": is_default})
        if body_type:
            gene_name = ("gene_bs_bust" if vanilla_gene_contract else "gene_uma_body_combinations") if is_default else "gene_uma_body_" + gid
            gene_lines += ["\t" + gene_name + " = {", "\t\tgroup = body"]
            shape_by_key = {s["key"]: s for s in shapes}
            rows = vanilla_gene_contract["templates"] if is_default and vanilla_gene_contract else [
                {"index": i, "template": "uma_combo_" + slug(s["key"]), "combination": s["key"]} for i, s in enumerate(shapes)]
            for row in rows:
                i, template = row["index"], row["template"]
                selected = shape_by_key[row["combination"]]
                gene_lines += ["\t\t" + template + " = {", "\t\t\tindex = " + str(i), "\t\t\tvisible = yes", "\t\t\tuma_female = {"]
                for shape in shapes:
                    value = "1.0" if shape is selected else "0.0"
                    gene_lines.append("\t\t\t\tsetting = { attribute = " + quote(shape["attribute"]) + " value = { min = " + value + " max = " + value + " } }")
                gene_lines += ["\t\t\t}", "\t\t\tuma_male = { }", "\t\t\tuma_girl = uma_female", "\t\t\tuma_boy = uma_male", "\t\t}"]
                choices.append({"gene": gene_name, "template": template, "index": i, "attribute": selected["attribute"], "is_default": is_default and selected["key"] == default_key})
            gene_lines.append("\t}")
    gene_lines += ["}", ""]
    (output / "common/genes/uma_genes_morph.txt").write_text("\n".join(gene_lines), encoding="utf-8-sig")
    # The immutable component recipes retain per-source DDS even where two
    # geometric morph targets use a base material. A BS cannot switch texture.
    for item in manifest.get("components", []):
        cid = short_id(item["name"])
        library.append(pack.asset(item["mesh"], "uma_component_" + cid + "_mesh", "uma_component_" + cid + "_entity"))
    (asset_root / "uma_verified_library.asset").write_text("\n".join(library), encoding="utf8")
    ethnicity_path = output / "common/ethnicities/uma_ethnicity.txt"
    ethnic_text = ethnicity_path.read_text(encoding="utf-8-sig")
    parsed_ethnicity = clausewitz(ethnic_text)
    original_ethnicity = one(parsed_ethnicity, "uma_ethnicity")
    if one(original_ethnicity, "portrait_group") != "uma":
        raise ValueError("Sample ethnicity does not use isolated portrait_group uma")
    # Preserve sample body, append verified default template weight to both IDs.
    ethnic_body = ethnic_text[ethnic_text.index("{") + 1:ethnic_text.rindex("}")]
    default_gene_name = "gene_bs_bust" if vanilla_gene_contract else "gene_uma_body_combinations"
    default_template = vanilla_gene_contract["default_template"] if vanilla_gene_contract else "uma_combo_" + slug(default_key)
    addition = '\n\t' + default_gene_name + ' = { 100 = { name = "' + default_template + '" range = { 1.0 1.0 } } }\n'
    ethnicity_path.write_text("uma_ethnicity = {" + ethnic_body + addition + "}\n\numa_ethnity = {" + ethnic_body + addition + "}\n", encoding="utf-8-sig")
    descriptor = 'version="1.0.0"\ntags={ "Graphics" }\nname="Uma PDX Combinations"\nsupported_version="1.20.*"\n'
    (output / "descriptor.mod").write_text(descriptor, encoding="utf8")
    (output / "launcher-entry.mod").write_text(descriptor + 'path="mod/' + output.name + '"\n', encoding="utf8")
    # Check every packaged script's brace structure. Validate generated asset
    # references and the explicit gene/attribute/BS bijection separately.
    script_checks = []
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in (".asset", ".txt", ".mod", ".shader"):
            if path.suffix == ".shader":
                continue  # shader includes HLSL, not Clausewitz-only syntax
            tree = clausewitz(path.read_text(encoding="utf-8-sig"))
            script_checks.append(path.relative_to(output).as_posix())
            if path.name in ("uma_body.asset", "uma_verified_library.asset"):
                assets = values(tree, "pdxmesh")
                entities = values(tree, "entity")
                assets_by_name = {one(a, "name"): a for a in assets}
                if len(assets_by_name) != len(assets):
                    raise ValueError("Duplicate generated pdxmesh names")
                for entity in entities:
                    asset = assets_by_name[one(entity, "pdxmesh")]
                    bs = {one(s, "id"): one(s, "type") for s in values(asset, "blend_shape")}
                    for attr in values(entity, "attribute"):
                        if one(attr, "blend_shape") not in bs:
                            raise ValueError("Entity attribute has no binary BS")
                        if float(one(attr, "default")) != 0.0:
                            raise ValueError("CK3 blend shape attributes require zero defaults")
                    for s in values(asset, "meshsettings"):
                        for field in ("texture_diffuse", "texture_normal", "texture_specular"):
                            for ref in values(s, field):
                                relative_texture = safe_relative(ref)
                                if len(relative_texture.parts) != 1:
                                    raise ValueError("Meshsettings DDS must be an adjacent basename: " + ref)
                                mesh_parent = (asset_root / safe_relative(one(asset, "file"))).parent
                                if not (mesh_parent / relative_texture).is_file():
                                    raise FileNotFoundError("Generated DDS reference: " + ref)
                if path.name == "uma_body.asset":
                    if values(assets[0], "import") or values(assets[0], "additive_animation") or len(values(assets[0], "animation")) != 1:
                        raise ValueError("Default body contains unretargeted animations")
                    if one(entities[0], "default_state") != "idle":
                        raise ValueError("Default body state is not idle")
                    states = values(entities[0], "state")
                    if {one(s, "name") for s in states} != set(pack.state_aliases) or any(one(s, "animation") != "uma_rest" for s in states):
                        raise ValueError("Default body state alias contract failed")
    gene_tree = clausewitz((output / "common/genes/uma_genes_morph.txt").read_text(encoding="utf-8-sig"))
    morph_genes = one(gene_tree, "morph_genes")
    if one(morph_genes, "portrait_group") != "uma":
        raise AssertionError("Morph genes lost portrait isolation")
    portrait_types = one(clausewitz((output / "common/portrait_types/uma_portrait_types.txt").read_text(encoding="utf-8-sig")), "uma")
    for contract in portrait_contract["types"]:
        name = contract["type"]
        node = one(portrait_types, name)
        if one(node, "sex") != contract["sex"]:
            raise ValueError("Sample portrait type contract differs: " + name)
        if {k: v for k, v in node if k in ("minimum_age", "maximum_age")} != contract["age_fields"]:
            raise ValueError("Original portrait age boundary changed: " + name)
    template_checks = []
    for registration in registrations:
        if registration["purpose"] != "body_type":
            continue
        expected_attributes = {s["attribute"] for s in registration["shapes"]}
        gene_name = default_gene_name if registration["default_portrait"] else "gene_uma_body_" + short_id(registration["group"])
        gene = one(morph_genes, gene_name)
        for template, node in gene:
            if not isinstance(node, list):
                continue
            if any(values(node, wrong) for wrong in ("female", "male", "girl", "boy")):
                raise ValueError("Gene uses a portrait type absent from the uma group")
            settings = values(one(node, "uma_female"), "setting")
            if one(node, "uma_male") != []:
                raise ValueError("Female combinations must not deform the sample male portrait")
            if one(node, "uma_girl") != "uma_female" or one(node, "uma_boy") != "uma_male":
                raise ValueError("All four portrait gene branches must preserve the stock child/adult relation")
            attributes = [one(setting, "attribute") for setting in settings]
            if len(attributes) != len(expected_attributes) or set(attributes) != expected_attributes:
                raise ValueError("Incomplete or duplicate mutually exclusive gene settings")
            chosen = []
            for setting in settings:
                fixed_value = one(setting, "value")
                strengths = [float(one(fixed_value, "min")), float(one(fixed_value, "max"))]
                if len(strengths) != 2 or strengths[0] != strengths[1] or strengths[0] not in (0.0, 1.0):
                    raise ValueError("Gene template is not a fixed full combination")
                if strengths[0] == 1.0:
                    chosen.append(one(setting, "attribute"))
            if len(chosen) != 1:
                raise ValueError("Combination template must activate exactly one target")
            template_checks.append({"gene": gene_name, "template": template, "chosen": chosen[0], "others_zero": True})
    protected = [p for p in preserved if p != "descriptor.mod" and p not in ("gfx/models/portraits/uma/uma_body.asset", "common/genes/uma_genes_morph.txt", "common/ethnicities/uma_ethnicity.txt", "common/portrait_types/uma_portrait_types.txt")]
    if any(sha(output / p) != preserved[p] for p in protected):
        raise AssertionError("Unrequested sample file modified")
    result = {"passed": True, "scope": "static parser/binary/path checks; no CK3 runtime acceptance", "sample": str(sample),
              "sample_sha256": sha(sample), "delivery": str(delivery), "input_manifest_sha256": sha(manifest_path),
              "sample_files_copied": len(preserved), "protected_sample_files_verified": len(protected),
              "skeleton_names_and_parents_match_sample": True, "mesh_bytes_unchanged": True,
              "body_morph_binary_checks": pack.binary_checks, "generated_scripts_parsed": script_checks,
              "default_combo": default_key, "combination_templates": template_checks,
              "vanilla_body_key_contract": vanilla_key_contract,
              "vanilla_gene_contract": vanilla_gene_contract,
              "portrait_type_contract": portrait_contract,
              "ethnicities": ["uma_ethnicity", "uma_ethnity"], "portrait_group": "uma",
              "texture_resolution": "meshsettings DDS basenames resolved from each mesh parent, matching CK3 VFS behavior",
              "sample_body_state_names": sample_states, "static_body_state_aliases": pack.state_aliases,
              "rest_animation": {"source": str(rest_animation), "bones": len(rest_names), **static_clip, "sha256": sha(rest_animation),
                                 "static_pose_metadata": rest_metadata, "checked": "bone names, multiframe header and constant samples; supplied pose may be relaxed, not bind rest"},
              "registrations": registrations, "library_recipes": pack.recipes,
              "limitations": ["Game loading, portrait assembly and Matilda console test are not performed.",
                              "Animation retargeting is not implemented; all sample body state aliases use the same supplied constant multiframe pose.",
                              "Shader compilation and CK3 schema/semantic validation are not performed.",
                              "Sample head and its existing animations are preserved; new head/component library entities have no animations.",
                              "Morphs change geometry only. Each source component entity preserves its own DDS recipe; genes do not switch diffuse textures.",
                              "Topology-incompatible Fat costumes remain independent component meshes, not fabricated blend shapes."]}
    write_json(output / "validation.json", result)
    write_json(output / "asset-library.json", {"recipes": pack.recipes, "genes": choices})
    readme = """# Uma PDX Combinations

样例头部、贴图、shader 和既有头部动画已保留。新的默认身体使用 UMA 原网格、整组合形态键和所提供的多帧常量姿势动画；该文件可包含肩部放松的 A 姿势，仅改变骨骼姿势，没有重新采样或修改 mesh 点。scale=100 只写入 pdxmesh 元数据。portrait_group=uma，不修改 human 模板。uma_ethnicity 与兼容拼写 uma_ethnity 都已注册。材质 DDS 仅使用相邻文件名，由 CK3 按 mesh 所在目录解析。

默认组合：""" + str(default_key) + """。每个基因模板只激活一个完整组合，其他组合固定为零，避免把胸型和胖体型向量叠加。静态资产库包含所有已验证组件与形态组；未兼容的 Fat 服装独立注册。asset-library.json 记录每个原始实体的材质和 DDS 配方。形态键不能替换贴图，切换到另一来源的贴图配方需要选择其独立实体。

UMA portrait types 和每个形态基因模板完整包含 male/female/boy/girl 四个对应分支。成年类型 minimum_age、儿童类型 maximum_age 全部逐字段读取原版 00_human_types.txt；本次原版值均为 18，没有更改年龄阈值。uma_girl 继承 uma_female 的形态设置，uma_boy 继承空的 uma_male；女童继续使用 UMA 头部/身体，男童使用原版男童身体。

仅做了二进制顶点数量、三角形、UV、参考骨架层级、文件引用和脚本结构检查。新版本的游戏载入、头像拼装和控制台效果未验收。新身体未连接原版 additive/common_body 动画；样例所有身体状态名和 idle_entry 均映射到同一常量姿势，仅是兼容别名，并非完整动作重定向。新的头部资产库未套用样例既有动作。

手动安装时，把本目录复制到 CK3 的 mod 目录，并将 launcher-entry.mod 复制到其外层、按需要重命名。当前交付未部署到游戏或旧模组。控制台测试对象 Matilda 时，测试命令为 effect set_ethnicity = uma_ethnicity；游戏内结果尚待验证。

validation.json 是结构检查报告，manifest-hashes.json 是文件 SHA-256 清单。
"""
    (output / "README.md").write_text(readme, encoding="utf8")
    if vanilla_key_contract:
        with (output / "README.md").open("a", encoding="utf8") as stream:
            stream.write("\n本次试验复用原版 BS 接口名称：Basis 使用 bs_body_seated/female_bs_body_neutral，胸型 2 使用 bs_body_breast_size_max，平胸完整组合使用 bs_body_breast_size_min。当前基因入口为 " + default_gene_name + "，目标 mesh 指向 UMA 真实来源。原版身体 asset 只读取以核对名称，没有加入原版身体覆盖文件。该接口复用仍需实机验证其他基因是否叠加同名属性。\n")
    if vanilla_gene_contract:
        with (output / "README.md").open("a", encoding="utf8") as stream:
            stream.write("\n本版同时复用原版 gene_bs_bust 入口，替代上一试验的 gene_uma_body_combinations。保留原版全部模板名和 index；bust_clothes 对应 Basis，bust_clothes_light 对应完整平胸组合，bust_default 对应完整胸型 2，其余原版模板在 UMA 组内确定映射为 Basis。每个模板仍只启用一个完整端点，原版 human 基因文件未覆盖。具体映射见 validation.json 的 vanilla_gene_contract。\n")
    hashes = {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest-hashes.json"}
    write_json(output / "manifest-hashes.json", hashes)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                z.write(path, output.name + "/" + path.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as z:
        corrupt = z.testzip()
        if corrupt:
            raise ValueError("Corrupt ZIP member: " + corrupt)
        if len(z.infolist()) != len(hashes) + 1:
            raise AssertionError("ZIP file inventory differs from output manifest")
    return {"mod_directory": str(output), "zip": str(archive), "zip_sha256": sha(archive),
            "zip_crc_verified": True, "validation": str(output / "validation.json"), "passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pdx-plugin", type=Path, required=True)
    parser.add_argument("--rest-animation", type=Path, required=True)
    parser.add_argument("--portrait-reference", type=Path, required=True, help="Original 00_human_types.txt; all four types retain its exact age bounds")
    parser.add_argument("--reuse-vanilla-body-asset", type=Path, help="Read the stock female_body.asset to reuse verified stock BS IDs and attribute names for the default complete body combinations")
    parser.add_argument("--reuse-vanilla-gene-file", type=Path, help="Additionally reuse gene_bs_bust and all original template names/indices inside the UMA portrait group")
    args = parser.parse_args()
    print(json.dumps(build_mod(args.sample, args.delivery, args.output, args.pdx_plugin, args.rest_animation, args.reuse_vanilla_body_asset, args.reuse_vanilla_gene_file, args.portrait_reference), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
