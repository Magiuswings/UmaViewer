"""Read-only asset inventory helper used to inspect the actual supplied bundle package."""
import collections
import json
from pathlib import Path
import sys
import zipfile
import UnityPy

source = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
env = UnityPy.Environment()
with zipfile.ZipFile(source) as z:
    for name in z.namelist():
        if not name.endswith("/"):
            env.load_file(z.read(name), name=name)
counts = collections.Counter(o.type.name for o in env.objects)
print("types", dict(counts))
inventory = []
for obj in env.objects:
    if obj.type.name not in ("Mesh", "GameObject", "SkinnedMeshRenderer", "MeshRenderer", "Material", "Transform", "Texture2D", "AssetBundle"):
        continue
    try:
        tree = obj.read_typetree()
    except Exception as error:
        print("FAIL", obj.type.name, obj.path_id, str(error)); continue
    entry = dict(type=obj.type.name, id=obj.path_id, file=obj.assets_file.name, name=tree.get("m_Name", ""))
    if obj.type.name == "SkinnedMeshRenderer":
        go = obj.read().m_GameObject.read()
        entry["gameobject"] = go.m_Name
        entry["materials"] = [m.read().m_Name for m in obj.read().m_Materials]
        entry["mesh"] = obj.read().m_Mesh.read().m_Name
        print("renderer", entry)
        (out / ("renderer_" + str(obj.path_id) + ".json")).write_text(json.dumps(tree, indent=2, default=lambda v: {'bytes_length': len(v)} if isinstance(v, bytes) else str(v)), encoding="utf8")
    elif obj.type.name == "Mesh":
        if not (out / "sample_mesh.json").exists():
            (out / "sample_mesh.json").write_text(json.dumps(tree, indent=2, default=lambda v: {'bytes_length': len(v)} if isinstance(v, bytes) else str(v)), encoding="utf8")
    elif obj.type.name == "Material":
        (out / ("material_" + str(obj.path_id) + ".json")).write_text(json.dumps(tree, indent=2, default=lambda v: {'bytes_length': len(v)} if isinstance(v, bytes) else str(v)), encoding="utf8")
    elif obj.type.name == "Transform":
        if not (out / "sample_transform.json").exists():
            (out / "sample_transform.json").write_text(json.dumps(tree, indent=2, default=lambda v: {'bytes_length': len(v)} if isinstance(v, bytes) else str(v)), encoding="utf8")
    elif obj.type.name == "AssetBundle":
        (out / ("bundle_" + str(obj.path_id) + ".json")).write_text(json.dumps(tree, indent=2, default=lambda v: {'bytes_length': len(v)} if isinstance(v, bytes) else str(v)), encoding="utf8")
    inventory.append(entry)
(out / "inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf8")
print("inventory", len(inventory))
