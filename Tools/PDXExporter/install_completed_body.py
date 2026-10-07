"""Install verified single-skin bodies into a new copy of the working skin/neck mod."""
import argparse
import copy
import json
import math
from pathlib import Path
import shutil
import sys
from PIL import Image

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-mod',type=Path,required=True)
    p.add_argument('--delivery',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pdx-tools',type=Path,required=True)
    p.add_argument('--pdx-plugin',type=Path,required=True)
    p.add_argument('--factor',type=float,default=105)
    args=p.parse_args()
    if not math.isfinite(args.factor) or args.factor<=0:p.error('Factor must be finite and positive')
    sys.path.insert(0,str(args.pdx_tools))
    import build_ck3_mod as b
    from scale_body_probe import scaled_mesh,element_equal
    src=args.source_mod.resolve();out=args.output.resolve();delivery=args.delivery.resolve()
    if out.exists() or out.is_relative_to(src) or src.is_relative_to(out) or out.is_relative_to(delivery) or delivery.is_relative_to(out):raise ValueError('Use a new separate mod folder')
    verification=json.loads((delivery/'verification.json').read_text(encoding='utf8'))
    if verification.get('passed') is not True:raise ValueError('Input delivery is not verified')
    manifest=json.loads((delivery/'export-manifest.json').read_text(encoding='utf8'))
    group=next(g for g in manifest['morph_groups'] if g['purpose']=='body_type')
    pdx=b.parser_only(args.pdx_plugin)
    rootrel=Path('gfx/models/portraits/uma');source_root=src/rootrel
    asset_tree=b.clausewitz((source_root/'uma_body.asset').read_text(encoding='utf-8-sig'))
    original_body=b.one(asset_tree,'pdxmesh')
    active_refs={b.one(original_body,'file')}|{b.one(s,'type') for s in b.values(original_body,'blend_shape')}
    new_refs={'delivery/'+group['base_mesh']}|{'delivery/'+t['mesh'] for t in group['targets']}
    if active_refs!=new_refs:raise ValueError('Whole-body BS names differ from current mod; refusing an implicit gene rewrite')
    source_head_hash=b.sha(source_root/'uma_head.mesh')
    source_portrait_hash=b.sha(src/'common/portrait_types/uma_portrait_types.txt')
    source_gene_hashes={str(f.relative_to(src)):b.sha(f) for f in (src/'common/genes').rglob('*') if f.is_file()}
    head_asset=b.one(b.clausewitz((source_root/'uma_head.asset').read_text(encoding='utf-8-sig')),'pdxmesh')
    head_refs={b.one(head_asset,'file')}|{b.one(s,'type') for s in b.values(head_asset,'blend_shape')}|{b.one(s,'type') for s in b.values(head_asset,'animation')}
    body_anims={b.one(s,'type') for s in b.values(original_body,'animation')}
    animation_and_head_hashes={f:b.sha(source_root/f) for f in head_refs|body_anims}
    shutil.copytree(src,out)
    root=out/rootrel
    # Replace the three body bases and their one whole-combination morph group.
    changed=set()
    for folder in ('components','morphs'):
        source=delivery/folder
        for file in source.rglob('*'):
            if not file.is_file():continue
            rel=Path('delivery')/file.relative_to(delivery);dst=root/rel
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dst)
            if file.suffix=='.mesh':changed.add(rel.as_posix())
    scaled=[]
    for relative in sorted(active_refs):
        original=pdx.read_meshfile(str(source_root/relative))
        new=pdx.read_meshfile(str(root/relative));expected=copy.deepcopy(new)
        scaled_mesh(expected,args.factor)
        for old_obj,new_obj in zip(original.find('object'),expected.find('object')):
            old_bones=old_obj.find('skeleton');new_bones=new_obj.find('skeleton')
            assert [n.tag for n in old_bones]==[n.tag for n in new_bones]
            error=max(abs(a-c) for old,new_b in zip(old_bones,new_bones) for a,c in zip(old.attrib['tx'],new_b.attrib['tx']))
            assert error<=1e-4,('Existing animation bind frame changed',error)
            for old,new_b in zip(old_bones,new_bones):
                assert {k:v for k,v in old.attrib.items() if k!='tx'}=={k:v for k,v in new_b.attrib.items() if k!='tx'}
        pdx.write_meshfile(str(root/relative),expected)
        reread=pdx.read_meshfile(str(root/relative));assert element_equal(expected,reread)
        scaled.append(dict(file=relative,factor=args.factor,existing_animation_bind_frame_preserved=True,single_skin_slot=True))
    def settings(relative):
        mesh_path=root/relative;mesh=pdx.read_meshfile(str(mesh_path));result=[]
        for obj in mesh.find('object'):
            for index,node in enumerate(obj.findall('mesh')):
                material=node.find('material').attrib
                assert material['shader']==['portrait_skin']
                diffuse=mesh_path.parent/material['diff'][0];original=diffuse.read_bytes();raw=bytearray(original)
                assert raw[:4]==b'DDS ' and raw[84:88]==b'DXT5' and (len(raw)-128)%16==0
                for off in range(128,len(raw),16):raw[off:off+8]=bytes(8)
                name=diffuse.stem+'__pdx_no_palette.dds';target=diffuse.with_name(name);target.write_bytes(raw)
                with Image.open(diffuse) as old,Image.open(target) as new:
                    assert old.convert('RGB').tobytes()==new.convert('RGB').tobytes()
                    assert new.convert('RGBA').getchannel('A').getextrema()==(0,0)
                neutral=mesh_path.parent/'uma_skin_neutral_ssao.dds'
                Image.new('RGBA',(4,4),(255,255,255,0)).save(neutral,pixel_format='DXT5')
                s=[('name',obj.tag),('index',str(index)),('texture_diffuse',name)]
                for key,label in (('n','texture_normal'),('spec','texture_specular')):
                    if material.get(key):s.append((label,material[key][0]))
                s += [('texture',[('file',neutral.name),('index','3')]),('shader','portrait_skin'),('shader_file','gfx/FX/uma_portrait.shader')]
                result.append(('meshsettings',s))
        assert len(result)==1,('Completed body still has multiple material slots',relative)
        return result
    updated=[]
    for filename in ('uma_body.asset','uma_verified_library.asset'):
        path=root/filename;tree=b.clausewitz(path.read_text(encoding='utf-8-sig'))
        for i,(key,node) in enumerate(tree):
            if key!='pdxmesh':continue
            relative=b.one(node,'file')
            if relative not in changed:continue
            new=[(k,v) for k,v in node if k!='meshsettings' and not (relative in active_refs and k=='scale')]
            new+=settings(relative)
            tree[i]=(key,new)
            updated.append(dict(asset=filename,name=b.one(node,'name'),file=relative,material_slots=1,shader='portrait_skin',body_unit_scale_baked=args.factor if relative in active_refs else None))
        path.write_text(b.script_block(tree)+'\n',encoding='utf8')
    assert b.sha(root/'uma_head.mesh')==source_head_hash
    assert b.sha(out/'common/portrait_types/uma_portrait_types.txt')==source_portrait_hash
    assert all(b.sha(out/f)==h for f,h in source_gene_hashes.items())
    assert all(b.sha(root/f)==h for f,h in animation_and_head_hashes.items())
    for relative in sorted(active_refs):
        rootdata=pdx.read_meshfile(str(root/relative))
        assert len(rootdata.find('object'))==1
        slots=rootdata.find('object')[0].findall('mesh');assert len(slots)==1
        assert slots[0].find('material').attrib['shader']==['portrait_skin']
        assert len(slots[0].attrib['tri'])//3==5472
    report=dict(passed=True,source_mod=str(src),source_delivery=str(delivery),delivery_verification_passed=True,
                active_body_meshes=scaled,updated_assets=updated,competitive_swimsuit_material_slots_in_completed_bodies=0,
                body_triangle_count_per_profile=5472,head_mesh_unchanged=True,head_neck_fix_retained=True,
                head_source_sha256=source_head_hash,portrait_file_unchanged=True,portrait_source_sha256=source_portrait_hash,
                gene_files_unchanged=True,source_gene_hashes=source_gene_hashes,body_animation_files_unchanged=True,
                head_and_animation_files_verified=len(animation_and_head_hashes),head_and_animation_hashes=animation_and_head_hashes,
                whole_combination_bs_ids_unchanged=True,ck3_runtime_verified=False)
    history=out/'history';history.mkdir(exist_ok=True)
    for filename in ('validation.json','skin-material-repair.json'):
        path=out/filename
        if path.exists():path.rename(history/('before-skin-completion-'+filename))
    b.write_json(out/'validation.json',report)
    b.write_json(out/'active-completed-skin-assets.json',updated)
    (out/'descriptor.mod').write_text('name="UMA Complete Skin Test"\nsupported_version="1.20.*"\n',encoding='utf8')
    (out/'launcher-entry.mod').write_text('name="UMA Complete Skin Test"\npath="mod/'+out.name+'"\n',encoding='utf8')
    (out/'README.md').write_text('''# UMA 完整皮肤底模

默认底模采用竞技泳装 0004 的完整原始网格，合并相同 height/shape/bust 的 0009 露肤覆盖后，所有剩余区域直接用 0004 网格填补。所有 5472 个三角面只使用 portrait_skin；竞技泳装不再是底模的独立材质。填补色来自原始默认 diffuse 的面积加权皮肤采样，0009 新增区域使用对应原贴图皮肤色。

固定 0004 拓扑保留了原始点、UV、权重和完整组合 BS 顶点对应。身体在 PDX 中继续烘焙 105 倍，默认 asset 无 scale=100。原始 Blender 工程保持源单位。头颈向下 4.55 cm 的修复及 619 个头部动画处理来自上一版，四组 portrait type、原版 18 岁年龄字段和已有基因保持不变。

底模是贴身泳装形状的皮肤代理，没有另造衣服下面的解剖细节。旧服装组件继续作为服装资源保留；三套竞技泳装底模与其整套体型 BS 均已替换为单一皮肤材质。原报告放在 history。validation.json 记录当前静态和二进制检查，本轮没有 CK3 实机切换端点验收。

独立测试命令：effect set_ethnicity = uma_ethnicity
''',encoding='utf8')
    files=[dict(file=f.relative_to(out).as_posix(),bytes=f.stat().st_size,sha256=b.sha(f)) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest-hashes.json']
    b.write_json(out/'manifest-hashes.json',dict(files=files))
    print('COMPLETED_SKIN_MOD_INSTALLED',len(updated),'assets',flush=True)

if __name__=='__main__':main()
