"""Generate a small non-game fixture for the real Blender conversion test."""
import json
from pathlib import Path
import struct
import sys
import zlib


def create(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "textures").mkdir(exist_ok=True)
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    def png(path, pixels):
        raw = b"".join(b"\0" + bytes(row) for row in pixels)
        content = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0))
        content += chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
        path.write_bytes(content)
    png(directory / "textures/color.png", [[255, 40, 20, 255, 10, 160, 230, 128], [10, 200, 20, 255, 255, 255, 255, 0]])
    png(directory / "textures/area.png", [[255, 0, 0, 255, 128, 0, 0, 255], [0, 255, 0, 255, 0, 0, 128, 255]])
    def v(x=0, y=0, z=0, w=0):
        return dict(x=x, y=y, z=z, w=w)
    bones = []
    for i in range(6):
        bones.append(dict(id=f"b{i}", name="Duplicate" if i in (1, 2) else f"Bone{i}", parent=f"b{i-1}" if i else None,
                          matrix=[1, 0, 0, 0, 0, 1, 0, i * 0.15, 0, 0, 1, 0, 0, 0, 0, 1]))
    # One renderer, two material sections, shared vertex, plus an excluded vertex.
    basis = [v(0, 0), v(1, 0), v(1, 1), v(0, 1), v(-1, 0), v(-1, 1), v(0, 2), v(99, 99, 99)]
    vertices = [dict(p, x=p["x"] + 0.03) for p in basis]
    weights = [dict(vertex=i, bone=f"b{b}", weight=(b + 1) / 21) for i in range(8) for b in range(6)]
    materials = []
    for name, alpha in (("ClothAlpha", True), ("Skin", False)):
        properties = [dict(name="_MainTex", type="Texture", texture="textures/color.png", scale=[1, 1], offset=[0, 0], srgb=True),
                      dict(name="_MaskColorTex", type="Texture", texture="textures/area.png", scale=[1, 1], offset=[0, 0], srgb=False),
                      dict(name="_Color", type="Color", value=[0.8, 0.6, 0.4, 1])]
        for index, key in enumerate(("R1", "R2", "G1", "G2", "B1", "B2")):
            properties.append(dict(name="_MaskColor" + key, type="Color", value=[(index + 1) / 6, 0.4, 0.7, 1]))
        materials.append(dict(name=name, shader="Uma/BodyAlpha" if alpha else "Uma/Body", renderQueue=2450 if alpha else 2000,
                              keywords=["USE_MASK_COLOR"], properties=properties))
    data = dict(version=1, name="Synthetic Uma fixture", pose="Current pose becomes the armature rest pose", bones=bones, materials=materials, warnings=["Synthetic test geometry"],
                meshes=[dict(name="MixedRenderer", vertices=vertices, normals=[v(0, 0, 1) for _ in basis], colors=[v(1, 0.5, 0.25, 1) for _ in basis],
                             uvs=[dict(channel=c, values=[v(p["x"], p["y"]) for p in basis]) for c in (0, 1)], weights=weights,
                             faces=[dict(part="clothing", material=0, triangles=[0, 1, 2, 0, 2, 3]), dict(part="body", material=1, triangles=[0, 5, 4, 0, 6, 5])],
                             shapes=[dict(name="Smile", weight=0.3, deltas=[v(0.1, 0, 0) for _ in basis])])])
    path = directory / "model.uma.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(create(Path(sys.argv[1]).resolve()))
