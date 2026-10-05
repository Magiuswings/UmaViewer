"""Check malformed snapshots are rejected before creating Blender scene data."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import sys

root = Path(__file__).resolve().parents[2]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
fixture = load(root / "Tests/Blender/create_fixture.py", "fixture")
importer = load(root / "Assets/StreamingAssets/Blender/uma_blender_import.py", "uma_importer")
import json
with tempfile.TemporaryDirectory(prefix="uma_validation_") as temp:
    directory = Path(temp)
    data = json.loads(fixture.create(directory).read_text())
    importer.validate(data, directory)
    def rejects(label, mutate):
        altered = copy.deepcopy(data)
        mutate(altered)
        try:
            importer.validate(altered, directory)
        except ValueError:
            print("REJECTED " + label)
        else:
            raise AssertionError("Accepted invalid " + label)
    rejects("version", lambda d: d.update(version=9))
    rejects("bone cycle", lambda d: d["bones"][0].update(parent="b5"))
    rejects("duplicate ID", lambda d: d["bones"][1].update(id="b0"))
    rejects("triangle index", lambda d: d["meshes"][0]["faces"][0].update(triangles=[0, 1, 500]))
    rejects("unsafe texture", lambda d: d["materials"][0]["properties"][0].update(texture="../outside.png"))
    rejects("bad weight", lambda d: d["meshes"][0]["weights"][0].update(weight=float("nan")))
    rejects("missing bone", lambda d: d["meshes"][0]["weights"][0].update(bone="missing"))
    rejects("shape count", lambda d: d["meshes"][0]["shapes"][0].update(deltas=[]))
print("UMA_SCHEMA_VALIDATION_OK")
