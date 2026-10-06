"""Bake a requested uniform body size into a new mod, without asset scale."""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import shutil
import struct

from build_ck3_mod import clausewitz, one, parser_only, safe_relative, sha, values, write_json


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def scaled_mesh(root, factor):
    changes = []
    for obj in root.find('object'):
        for index, mesh in enumerate(obj.findall('mesh')):
            mesh.attrib['p'] = [f32(v * factor) for v in mesh.attrib['p']]
            if 'boundingsphere' in mesh.attrib:
                mesh.attrib['boundingsphere'] = [f32(v * factor) for v in mesh.attrib['boundingsphere']]
            bounds = mesh.find('aabb')
            if bounds is not None:
                for key in ('min', 'max'):
                    bounds.attrib[key] = [f32(v * factor) for v in bounds.attrib[key]]
            changes.append({'object': obj.tag, 'slot': index, 'vertices': len(mesh.attrib['p']) // 3})
        skeleton = obj.find('skeleton')
        if skeleton is not None:
            for bone in skeleton:
                assert len(bone.attrib['tx']) == 12
                bone.attrib['tx'][9:12] = [f32(v * factor) for v in bone.attrib['tx'][9:12]]
    locators = root.find('locator')
    if locators is not None:
        for locator in locators:
            if 'p' in locator.attrib:
                locator.attrib['p'] = [f32(v * factor) for v in locator.attrib['p']]
            if 'tx' in locator.attrib:
                assert len(locator.attrib['tx']) == 16
                locator.attrib['tx'][12:15] = [f32(v * factor) for v in locator.attrib['tx'][12:15]]
    return changes


def element_equal(a, b):
    return a.tag == b.tag and a.attrib == b.attrib and len(a) == len(b) and all(element_equal(x, y) for x, y in zip(a, b))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pdx-plugin', type=Path, required=True)
    p.add_argument('--factor', type=float, default=105.0)
    args = p.parse_args()
    src, out = args.source.resolve(), args.output.resolve()
    if not math.isfinite(args.factor) or args.factor <= 0:
        p.error('Factor must be finite and positive')
    if out.exists() or out.is_relative_to(src) or src.is_relative_to(out):
        p.error('Use a new separate output directory')
    shutil.copytree(src, out)
    pdx = parser_only(args.pdx_plugin)
    folder = out / 'gfx/models/portraits/uma'
    asset_path = folder / 'uma_body.asset'
    text = asset_path.read_text(encoding='utf-8-sig')
    asset = one(clausewitz(text), 'pdxmesh')
    mesh_refs = {one(asset, 'file')} | {one(s, 'type') for s in values(asset, 'blend_shape')}
    mesh_checks = []
    for relative in sorted(mesh_refs):
        path = folder / safe_relative(relative)
        original = pdx.read_meshfile(str(path))
        expected = copy.deepcopy(original)
        slots = scaled_mesh(expected, args.factor)
        pdx.write_meshfile(str(path), expected)
        reread = pdx.read_meshfile(str(path))
        assert element_equal(expected, reread), 'Scaled binary differs from expected structure: ' + relative
        for old_obj, new_obj in zip(original.find('object'), reread.find('object')):
            for old_mesh, new_mesh in zip(old_obj.findall('mesh'), new_obj.findall('mesh')):
                for key in ('n', 'ta', 'u0', 'u1', 'u2', 'tri'):
                    assert old_mesh.attrib.get(key) == new_mesh.attrib.get(key)
                assert element_equal(old_mesh.find('skin'), new_mesh.find('skin'))
                assert element_equal(old_mesh.find('material'), new_mesh.find('material'))
        mesh_checks.append({'mesh': relative, 'original_sha256': sha(src/'gfx/models/portraits/uma'/relative),
                            'scaled_sha256': sha(path), 'slots': slots, 'binary_structure_verified': True,
                            'normals_uv_topology_skin_material_unchanged': True})
    animations = []
    for node in values(asset, 'animation'):
        relative = one(node, 'type')
        path = folder / safe_relative(relative)
        original = pdx.read_meshfile(str(path))
        expected = copy.deepcopy(original)
        for bone in expected.find('info'):
            if 't' in bone.attrib:
                bone.attrib['t'] = [f32(v * args.factor) for v in bone.attrib['t']]
        samples = expected.find('samples')
        if samples is not None and 't' in samples.attrib:
            samples.attrib['t'] = [f32(v * args.factor) for v in samples.attrib['t']]
        pdx.write_animfile(str(path), expected)
        reread = pdx.read_meshfile(str(path))
        assert element_equal(expected, reread), 'Scaled animation differs from expected data'
        animations.append({'animation': relative, 'frames': reread.find('info').attrib['sa'][0],
                           'translation_scaled': True, 'quaternion_and_scale_tracks_unchanged': True})
        sidecar = path.with_suffix('.json')
        if sidecar.exists():
            meta = json.loads(sidecar.read_text(encoding='utf8'))
            meta.update(body_unit_scale_baked=args.factor, original_source_blend_preserved=True,
                        scaled_body_geometry_intentionally_changed=True)
            write_json(sidecar, meta)
    text, removed = re.subn(r'(?m)^\s*scale\s*=\s*[^\r\n]+\r?\n', '', text, count=1)
    assert removed == 1
    assert not values(one(clausewitz(text), 'pdxmesh'), 'scale')
    asset_path.write_text(text, encoding='utf8')
    assert sha(folder/'uma_head.mesh') == sha(src/'gfx/models/portraits/uma/uma_head.mesh')
    assert sha(out/'common/portrait_types/uma_portrait_types.txt') == sha(src/'common/portrait_types/uma_portrait_types.txt')
    for name in ('validation.json', 'asset-library.json'):
        (out/name).rename(out/('upstream-'+name))
    report = {'factor': args.factor, 'body_asset_scale_removed': True, 'scaled_meshes': mesh_checks,
              'scaled_animations': animations, 'head_mesh_unchanged': True, 'age_and_four_type_file_unchanged': True,
              'source_blend_and_original_mod_unchanged': True, 'runtime_result': None,
              'policy': 'Scale geometry, bounds, inverse-bind translations and pose translations uniformly; keep normals/UV/skin/parents/quaternions/scales'}
    write_json(out/'validation.json', report)
    (out/'README.md').write_text('''# UMA 身体 105 倍烘焙对照

用户明确要求的坐标缩放试验：删除默认身体 pdxmesh 的 scale=100，将它引用的基底和全部 BS 目标位置、包围盒、逆绑定骨骼位置、静态动画平移统一乘以105。法线、切线、全部UV、拓扑、权重、父链、旋转和动画scale保持原值。头部、原模组及源blend没有改动，四组和原版18岁阈值保持原样。

这里只缩放默认 UMA 身体及其完整形态目标；其他资产库组件仍是原有版本，不属于本轮显示测试。validation.json 是精确float32二进制结构检查，游戏结果另记录。
''', encoding='utf8')
    (out/'descriptor.mod').write_text('name="Uma Body 105 Baked Test"\nsupported_version="1.20.*"\n', encoding='utf8')
    (out/'launcher-entry.mod').write_text('name="Uma Body 105 Baked Test"\npath="mod/'+out.name+'"\n', encoding='utf8')
    write_json(out/'manifest-hashes.json', {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file() and p.name!='manifest-hashes.json'})
    print(json.dumps({'output': str(out), 'factor': args.factor, 'meshes': len(mesh_checks), 'asset_scale_removed': True}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
