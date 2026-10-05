"""Batch-export named UmaViewer Copy-All UnityFS assets without Unity or a UI."""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import zipfile

import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from math3d import IDENTITY, components, inverse, multiply, normal, transform, trs, unity_matrix, vec

HERE = Path(__file__).resolve().parent
PREFAB = re.compile(r"(?:^|/)3d/chara/(head|body|tail)/([^/]+)/pfb_([^/]+)$")

def safe_name(text):
    return re.sub(r"[^\w.-]+", "_", str(text), flags=re.UNICODE).strip("._") or "unnamed"

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")

def key(obj):
    return (obj.assets_file.name, obj.path_id)

def bone_id(obj):
    return hashlib.sha256((key(obj)[0] + ":" + str(obj.path_id)).encode()).hexdigest()[:24]

class Package:
    def __init__(self, source):
        self.source = source
        self.env = UnityPy.Environment()
        self.sources, self.bundles, self.inventory = {}, {}, []
        self.parsed, self.worlds, self.transforms = {}, {}, {}
        def load(name, raw):
            if name in self.bundles: raise ValueError("Duplicate input asset path: " + name)
            if not raw.startswith(b"UnityFS\0"):
                self.inventory.append(dict(source=name, status="not_unityfs", size=len(raw)))
                return
            bundle = self.env.load_file(raw, name=name)
            self.bundles[name] = bundle
            self.inventory.append(dict(source=name, status="loaded", size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            def walk(item):
                if hasattr(item, "objects") and isinstance(item.objects, dict):
                    for obj in item.objects.values(): self.sources[key(obj)] = name
                elif hasattr(item, "files"):
                    for child in item.files.values(): walk(child)
            walk(bundle)
        if source.is_dir():
            for file in sorted(source.rglob("*")):
                if file.is_file(): load(file.relative_to(source).as_posix(), file.read_bytes())
        else:
            with zipfile.ZipFile(source) as archive:
                for member in sorted(archive.infolist(), key=lambda a: a.filename):
                    if member.is_dir(): continue
                    name = member.filename.replace("\\", "/")
                    if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                        raise ValueError("Unsafe ZIP member: " + name)
                    load(name, archive.read(member))
        self.objects = list(self.env.objects)
        for obj in self.objects:
            if obj.type.name == "Transform":
                data = self.read(obj)
                self.transforms[key(data.m_GameObject.deref())] = obj

    def read(self, obj):
        k = key(obj)
        if k not in self.parsed: self.parsed[k] = obj.parse_as_object()
        return self.parsed[k]

    def world(self, obj, visited=None):
        k = key(obj)
        if k in self.worlds: return self.worlds[k]
        visited = set() if visited is None else visited
        if k in visited: raise ValueError("Cyclic Unity transform hierarchy")
        visited.add(k)
        data = self.read(obj)
        local = trs(data.m_LocalPosition, data.m_LocalRotation, data.m_LocalScale)
        parent = self.world(data.m_Father.deref(), visited) if data.m_Father else IDENTITY
        self.worlds[k] = multiply(parent, local)
        visited.remove(k)
        return self.worlds[k]

    def name(self, obj):
        return self.read(self.read(obj).m_GameObject.deref()).m_Name

def skin_palette(package, character):
    """Infer a pale/dark skin reference from the character's own face diffuse image."""
    candidates = []
    pattern = re.compile(r"tex_chr" + re.escape(character) + r"_.*face_diff$")
    for obj in package.objects:
        if obj.type.name != "Texture2D": continue
        texture = package.read(obj)
        if not pattern.match(texture.m_Name): continue
        counts = collections.Counter()
        for r,g,b,*_ in texture.image.convert("RGB").resize((128,128)).getdata():
            if r >= g >= b and r-g >= 8 and g-b >= 5 and g > 70 and (r-b)/max(r,1) < .55:
                counts[(r//8*8+4, g//8*8+4, b//8*8+4)] += 1
        candidates.extend(color for color,_ in counts.most_common(1))
    return list(dict.fromkeys(candidates))[:15]

def infer_clothing(bone_names, weights, vertices, triangle):
    score = collections.Counter()
    for v in triangle:
        for name, weight in weights[v]: score[bone_names[name]] += weight / 3
    garment = [(name,w) for name,w in score.items() if w > .02]
    for token, category in (("Acc", "accessories"), ("Skirt", "skirt"), ("Mantle", "cape"), ("Jacket", "upper_clothing"), ("Ribbon", "accessories")):
        if sum(w for name,w in garment if token.lower() in name.lower()) > .18: return category
    if sum(w for name,w in garment if "ankle" in name.lower() or "toe" in name.lower()) > .48: return "shoes"
    if sum(w for name,w in garment if "knee" in name.lower() or "thigh" in name.lower()) > .55: return "socks_or_legwear"
    if sum(w for name,w in garment if any(t in name.lower() for t in ("wrist","thumb","finger","ring_","index_","middle_","little_"))) > .5: return "gloves"
    return "clothing"

def is_skin(triangle, uvs, image, palette, tolerance, scale, offset):
    points = [uvs[v][:2] for v in triangle]
    points += [[(points[a][c]+points[b][c])/2 for c in range(2)] for a,b in ((0,1),(1,2),(2,0))]
    points.append([sum(uvs[v][c] for v in triangle)/3 for c in range(2)])
    matches = 0
    pixels = image.load()
    for u,v in points:
        u = (u*scale[0]+offset[0]) % 1
        v = (v*scale[1]+offset[1]) % 1
        color = pixels[min(image.width-1,int(u*image.width)), min(image.height-1,int((1-v)*image.height))][:3]
        if any(sum((a-b)**2 for a,b in zip(color,p)) <= tolerance*tolerance for p in palette): matches += 1
    return matches >= 5, matches

class Extractor:
    def __init__(self, package, output, args):
        self.package, self.output, self.args = package, output, args
        self.textures, self.materials, self.errors, self.warnings = {}, {}, [], []
        self.resources = output / "resources"
        self.resources.mkdir(parents=True, exist_ok=True)

    def texture(self, obj):
        k = key(obj)
        if k not in self.textures:
            data = self.package.read(obj)
            relative = "textures/" + safe_name(data.m_Name) + "__" + bone_id(obj)[:10] + ".png"
            path = self.resources / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data.image.save(path)
            self.textures[k] = dict(path=relative, name=data.m_Name, source=self.package.sources[k], id=obj.path_id)
        return self.textures[k]["path"]

    def material(self, obj, character, source_kind):
        # Common tail material's source texture bindings must be adapted to the owning character.
        k = (key(obj), character, source_kind)
        if k in self.materials: return self.materials[k]
        data = self.package.read(obj)
        shader_name = "Unknown Unity shader"
        try:
            shader = self.package.read(data.m_Shader.deref())
            shader_name = getattr(shader, "m_Name", "") or "Unity shader"
        except (FileNotFoundError, KeyError):
            self.warnings.append("Shader dependency missing (parameters retained): " + data.m_Name)
        props = []
        saved = data.m_SavedProperties
        for name, value in (saved.m_Floats or []) + (getattr(saved,"m_Ints",None) or []):
            props.append(dict(name=name,type="Float",value=[value]))
        for name, value in saved.m_Colors or []:
            props.append(dict(name=name,type="Color",value=[value.r,value.g,value.b,value.a]))
        for name, value in saved.m_TexEnvs or []:
            ptr = value.m_Texture
            chosen = None
            if source_kind == "tail" and name in ("_MainTex","_ToonMap","_TripleMaskMap","_OptionMaskMap"):
                ending = {"_MainTex":"diff","_ToonMap":"shad_c","_TripleMaskMap":"base","_OptionMaskMap":"ctrl"}[name]
                tail_match = re.search(r"tail\d+_\d+",data.m_Name)
                prefix = "tex_" + tail_match.group() if tail_match else ""
                options = [o for o in self.package.objects if o.type.name == "Texture2D" and self.package.read(o).m_Name in (prefix+"_"+character+"_"+ending, prefix+"_0000_"+ending)]
                options.sort(key=lambda o: ("_"+character+"_") not in self.package.read(o).m_Name)
                chosen = options[0] if options else None
            prop = dict(name=name,type="Texture",scale=components(value.m_Scale,2),offset=components(value.m_Offset,2),srgb=name in ("_MainTex","_BaseMap","_ToonMap","_DirtTex","_EmissiveTex"))
            try:
                if chosen or ptr: prop["texture"] = self.texture(chosen or ptr.deref())
            except (FileNotFoundError, KeyError) as error:
                self.errors.append(dict(kind="missing_texture",material=data.m_Name,property=name,error=str(error)))
            props.append(prop)
        result = dict(name=data.m_Name, shader=shader_name, keywords=list(getattr(data,"m_ValidKeywords",[]) or []),
                      renderQueue=data.m_CustomRenderQueue if data.m_CustomRenderQueue >= 0 else (2450 if any(t in data.m_Name.lower() for t in ("alpha","tear","cheek","eye","mayu")) else 2000),properties=props)
        # Source assets often have white _CharaColor but no generic _Color property.
        tint = next((p for p in props if p["name"] == "_CharaColor"),None)
        if tint and not any(p["name"] in ("_Color","_BaseColor") for p in props): props.append(dict(tint,name="_Color"))
        self.materials[k] = result
        return result

    def prefab(self, source, source_kind, identifier, character, palette):
        package = self.package
        renderers = [o for o in package.objects if package.sources.get(key(o)) == source and o.type.name in ("SkinnedMeshRenderer","MeshRenderer")]
        bones, bind_worlds = {}, {}
        def add_bone(obj):
            ident = bone_id(obj)
            if ident in bones: return ident
            data = package.read(obj)
            parent = add_bone(data.m_Father.deref()) if data.m_Father else None
            bones[ident] = dict(id=ident,name=package.name(obj),parent=parent,matrix=package.world(obj),unity_transform_id=obj.path_id)
            return ident
        meshes, materials, audits = [], [], []
        for renderer_obj in renderers:
            renderer = package.read(renderer_obj)
            go_obj = renderer.m_GameObject.deref(); go = package.read(go_obj)
            tf = package.transforms[key(go_obj)]
            world = package.world(tf)
            is_skinned = renderer_obj.type.name == "SkinnedMeshRenderer"
            if is_skinned:
                mesh_obj = renderer.m_Mesh.deref()
            else:
                filters = [o for o in package.objects if o.type.name == "MeshFilter" and key(package.read(o).m_GameObject.deref()) == key(go_obj)]
                if not filters: continue
                mesh_obj = package.read(filters[0]).m_Mesh.deref()
            source_mesh = package.read(mesh_obj)
            variable = getattr(source_mesh,"m_VariableBoneCountWeights",None)
            if variable and variable.m_Data:
                raise ValueError("Variable-count skin weights require an additional decoder; refusing to truncate " + go.m_Name)
            handler = MeshHandler(source_mesh); handler.process()
            if not handler.m_Vertices: continue
            bone_names = {}
            if is_skinned:
                mapped = [add_bone(p.deref()) for p in renderer.m_Bones]
                bindposes = source_mesh.m_BindPose
                if len(mapped) != len(bindposes): raise ValueError("Bone/bindpose count differs: " + go.m_Name)
                for i,p in enumerate(renderer.m_Bones):
                    bone_names[mapped[i]] = package.name(p.deref())
                    candidate = multiply(world,inverse(unity_matrix(bindposes[i])))
                    if mapped[i] in bind_worlds and max(abs(a-b) for a,b in zip(bind_worlds[mapped[i]],candidate)) > .002:
                        self.warnings.append("Different source bind matrices for shared bone: " + go.m_Name + "/" + bone_names[mapped[i]])
                    bind_worlds.setdefault(mapped[i],candidate)
            else:
                mapped = [add_bone(tf)]; bone_names[mapped[0]] = go.m_Name
            vertex_weights, influences = [], []
            for v in range(len(handler.m_Vertices)):
                if is_skinned and handler.m_BoneIndices and handler.m_BoneWeights:
                    weights = [(mapped[b],w) for b,w in zip(handler.m_BoneIndices[v],handler.m_BoneWeights[v]) if w > 0]
                else:
                    ident = add_bone(tf); bone_names[ident] = go.m_Name
                    weights = [(ident,1.)]
                vertex_weights.append(weights)
                influences.extend(dict(vertex=v,bone=b,weight=w) for b,w in weights)
            data = dict(name=go.m_Name,vertices=[vec(transform(world,p)) for p in handler.m_Vertices],
                        normals=[normal(world,n) for n in handler.m_Normals] if handler.m_Normals else [],
                        colors=[vec(c) for c in handler.m_Colors] if handler.m_Colors else [],
                        uvs=[dict(channel=i,values=[vec(v) for v in getattr(handler,"m_UV"+str(i))]) for i in range(8) if getattr(handler,"m_UV"+str(i))],
                        weights=influences,faces=[],shapes=[],source=source,unity_mesh_id=mesh_obj.path_id,
                        active=bool(go.m_IsActive and renderer.m_Enabled))
            # Native sparse shape frames are transformed into the mesh's exported bind coordinates.
            shapes = source_mesh.m_Shapes
            if shapes and shapes.channels:
                for channel in shapes.channels:
                    frame_index = channel.frameIndex + channel.frameCount - 1
                    frame = shapes.shapes[frame_index]
                    delta = [[0.,0.,0.] for _ in handler.m_Vertices]
                    for item in shapes.vertices[frame.firstVertex:frame.firstVertex+frame.vertexCount]:
                        delta[item.index] = transform(world,item.vertex,direction=True)
                    data["shapes"].append(dict(name=channel.name,weight=0.,deltas=[vec(d) for d in delta]))
            seen, grouped = set(), collections.defaultdict(list)
            stats = dict(renderer=go.m_Name,source_triangles=0,duplicate_triangles=0,skin_votes=collections.Counter(),categories=collections.Counter())
            for sub,triangles in enumerate(handler.get_triangles()):
                base_vertex = source_mesh.m_SubMeshes[sub].baseVertex or 0
                mat_ptr = renderer.m_Materials[min(sub,len(renderer.m_Materials)-1)] if renderer.m_Materials else None
                material_index = -1
                mat = None
                if mat_ptr:
                    mat = self.material(mat_ptr.deref(),character,source_kind)
                    if mat not in materials: materials.append(mat)
                    material_index = materials.index(mat)
                main = next((p for p in (mat or {}).get("properties",[]) if p["name"] == "_MainTex" and p.get("texture")),None)
                image = None
                if main and source_kind == "body" and self.args.skin_mode == "auto" and palette:
                    from PIL import Image
                    image = Image.open(self.resources/main["texture"]).convert("RGBA")
                for triangle in triangles:
                    triangle = tuple(v+base_vertex for v in triangle)
                    stats["source_triangles"] += 1
                    # Uma body bundles include a duplicate backface index pass; Blender materials are two-sided.
                    signature = tuple(sorted(triangle))
                    if signature in seen:
                        stats["duplicate_triangles"] += 1; continue
                    seen.add(signature)
                    category = "other"
                    part = "body"
                    lower = (go.m_Name + " " + ((mat or {}).get("name",""))).lower()
                    if source_kind == "head":
                        if "eye" in ((mat or {}).get("name","")).lower(): category = "eyes"
                        elif "mayu" in lower: category = "eyebrows"
                        elif "hair" in lower: category = "hair"
                        elif "tear" in lower or "cheek" in lower: category = "face_effects"
                        else: category = "face"
                    elif source_kind == "tail": category = "tail"
                    elif source_kind == "body":
                        if image and handler.m_UV0:
                            skin,votes = is_skin(triangle,handler.m_UV0,image,palette,self.args.skin_tolerance,main["scale"],main["offset"])
                            stats["skin_votes"][str(votes)] += 1
                            category = "body_skin" if skin else infer_clothing(bone_names,vertex_weights,handler.m_Vertices,triangle)
                            part = "body" if skin else "clothing"
                        else:
                            category = "body_clothing_mixed"; part = "body"
                    stats["categories"][category] += 1
                    grouped[(part,category,material_index)].extend(triangle)
            for (part,category,material),triangles in grouped.items():
                data["faces"].append(dict(part=part,category=category,material=material,triangles=triangles))
            meshes.append(data); audits.append(stats)
        for ident,world in bind_worlds.items(): bones[ident]["matrix"] = world
        variant = identifier.split("_",1)[1] if "_" in identifier else "unknown"
        name = "chara"+character+"__"+self.args.names.get(character,"") if self.args.names.get(character) else "chara"+character
        name = safe_name(name)+"__"+source_kind+"_"+safe_name(identifier)
        snapshot = dict(version=1,name=name,pose="Source bind pose (inverse bind matrices)",bones=list(bones.values()),meshes=meshes,materials=materials,
                        warnings=["Skin separation uses face-palette/UV sampling; clothing labels use source bone names. Review classification. Missing body surfaces are not reconstructed."],
                        character_id=character,character_name=self.args.names.get(character,""),variant=variant,source_kind=source_kind,source=source,audits=audits)
        return snapshot

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path,help="Named Copy-All ZIP or directory")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--blender",type=Path,help="Blender 4.2+ executable; omit to export only decoded JSON/PNG")
    parser.add_argument("--name",action="append",default=[],metavar="ID=NAME")
    parser.add_argument("--skin-mode",choices=("auto","none"),default="auto")
    parser.add_argument("--skin-tolerance",type=float,default=42.,help="RGB distance from the source face palette (0-441)")
    parser.add_argument("--character",action="append",default=[],help="Filter character IDs; default all found")
    parser.add_argument("--native-coordinates",action="store_true",help="Keep native prefab origins instead of aligning head/tail to available body bones")
    parser.add_argument("--body-base-variant",default="auto",help="Keep a complete source outfit as the body base: auto (most skin triangles), none, or variant such as 30")
    args = parser.parse_args()
    args.names = dict(n.split("=",1) for n in args.name)
    source,output = args.input.resolve(),args.output.resolve()
    if source == output or (source.is_dir() and output.is_relative_to(source)):
        parser.error("Output must be outside the input directory")
    if not 0 <= args.skin_tolerance <= 441: parser.error("Invalid skin tolerance")
    if args.blender and not args.blender.is_file(): parser.error("Blender executable does not exist")
    if (output/"manifest.json").exists():
        previous=json.loads((output/"manifest.json").read_text(encoding="utf8"))
        if previous.get("input")!=str(source): parser.error("Output directory belongs to another input package; use a new directory")
    output.mkdir(parents=True,exist_ok=True)
    print("Loading named asset package...",flush=True)
    package = Package(source)
    extractor = Extractor(package,output,args)
    prefabs = [(n,PREFAB.search(n)) for n in package.bundles if PREFAB.search(n)]
    character_ids = sorted({m[2][3:].split("_")[0] for _,m in prefabs if m[1] in ("head","body") and int(m[2][3:].split("_")[0]) >= 1000})
    jobs = []
    for asset,match in prefabs:
        kind,identifier = match[1],match[2]
        ident_id = identifier[3 if kind in ("head","body") else 4:].split("_")[0]
        if kind == "tail":
            texture_ids = sorted({re.search(r"_(\d{4})_diff$",package.read(o).m_Name)[1] for o in package.objects
                if o.type.name == "Texture2D" and package.read(o).m_Name.startswith("tex_"+identifier+"_") and re.search(r"_(\d{4})_diff$",package.read(o).m_Name)})
            owners = [i for i in texture_ids if i in character_ids] or ["shared"]
        else: owners = [ident_id] if int(ident_id) >= 1000 else ["shared"]
        for character in owners:
            if args.character and character not in args.character: continue
            palette = skin_palette(package,character) if kind == "body" else []
            try:
                data = extractor.prefab(asset,kind,identifier,character,palette)
            except Exception as error:
                extractor.errors.append(dict(kind="prefab_decode_failed",source=asset,character_id=character,error=str(error)))
                print("FAILED",asset,str(error),flush=True)
                continue
            if not data["meshes"]: continue
            path = output/"snapshots"/(data["name"]+".uma.json")
            write_json(path,data)
            categories = sorted({f["category"] for mesh in data["meshes"] for f in mesh["faces"]})
            jobs.append(dict(name=data["name"],snapshot=path.relative_to(output).as_posix(),character_id=character,source=asset,
                             kind=kind,categories=categories,skin_palette=palette,classification="heuristic" if kind == "body" and palette and args.skin_mode == "auto" else "source_renderer_material"))
            print("Decoded",data["name"],categories,flush=True)
    # Match UmaViewer's MergeBone anchors using source bone names, while keeping each prefab's own rig.
    if not args.native_coordinates:
        bodies = [j for j in jobs if j["kind"] == "body"]
        for job in jobs:
            if job["kind"] == "body": continue
            choices = [j for j in bodies if j["character_id"] == job["character_id"]]
            if not choices: continue
            path = output/job["snapshot"]
            data = json.loads(path.read_text(encoding="utf8"))
            choices.sort(key=lambda j: (j["name"].split("_")[-1] != data["variant"], not j["name"].endswith("_00"), j["name"]))
            target = json.loads((output/choices[0]["snapshot"]).read_text(encoding="utf8"))
            anchor = "Neck" if job["kind"] == "head" else "Hip"
            source_bone = next((b for b in data["bones"] if b["name"] == anchor),None)
            target_bone = next((b for b in target["bones"] if b["name"] == anchor),None)
            if not source_bone or not target_bone: continue
            attachment = multiply(target_bone["matrix"],inverse(source_bone["matrix"]))
            for bone in data["bones"]:
                bone["native_matrix"] = bone["matrix"]
                bone["matrix"] = multiply(attachment,bone["matrix"])
            for mesh in data["meshes"]:
                mesh["vertices"] = [vec(transform(attachment,v)) for v in mesh["vertices"]]
                mesh["normals"] = [normal(attachment,v) for v in mesh["normals"]]
                for shape in mesh["shapes"]: shape["deltas"] = [vec(transform(attachment,v,direction=True)) for v in shape["deltas"]]
            data["attachment"] = dict(body_source=target["source"],anchor=anchor,matrix=attachment)
            job["attachment"] = data["attachment"]
            write_json(path,data)
    body_bases=[]
    if args.body_base_variant!="none":
        for character in character_ids:
            candidates=[]
            for job in jobs:
                if job["kind"]!="body" or job["character_id"]!=character: continue
                data=json.loads((output/job["snapshot"]).read_text(encoding="utf8"))
                total=sum(len(f["triangles"])//3 for m in data["meshes"] for f in m["faces"])
                skin=sum(len(f["triangles"])//3 for m in data["meshes"] for f in m["faces"] if f["category"]=="body_skin")
                if args.body_base_variant=="auto" and skin:
                    candidates.append((skin/max(total,1),job))
                elif args.body_base_variant==data["variant"]: candidates.append((1.,job))
            if candidates:
                candidates.sort(key=lambda item:(item[0],item[1]["name"]),reverse=True)
                score,job=candidates[0]
                body_bases.append(dict(name=job["name"],source=job["source"],character_id=character,selection=args.body_base_variant,
                                       skin_triangle_ratio=score if args.body_base_variant=="auto" else None,
                                       note="Complete original outfit retained; no missing body surfaces reconstructed"))
    manifest = dict(version=1,input=str(source),unitypy_version=UnityPy.__version__,skin_mode=args.skin_mode,skin_tolerance=args.skin_tolerance,body_bases=body_bases,
                    characters=character_ids,input_sha256=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None,
                    jobs=jobs,assets=package.inventory,textures=list(extractor.textures.values()),
                    errors=extractor.errors,warnings=sorted(set(extractor.warnings)),resources="resources",blender_outputs=[])
    write_json(output/"manifest.json",manifest)
    if args.blender and jobs:
        log = output/"blender.log"
        with log.open("w",encoding="utf8") as handle:
            result = subprocess.run([str(args.blender),"--background","--factory-startup","--python-exit-code","1","--python",str(HERE/"headless_blender.py"),"--",str(output/"manifest.json")],stdout=handle,stderr=subprocess.STDOUT)
        if result.returncode: raise RuntimeError("Blender failed; see " + str(log))
    print("DONE",str(output/"manifest.json"),"jobs",len(jobs),"errors",len(extractor.errors),flush=True)
    return 2 if extractor.errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
