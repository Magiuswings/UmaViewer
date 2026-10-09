"""Validate and package the local canonical body rebuild without game data in Git."""
import argparse,hashlib,json,shutil,sys,zipfile
from collections import defaultdict
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')

def main():
    p=argparse.ArgumentParser()
    for name in ('repo','root','mod','model','plugin'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--register-mod-dir',type=Path);a=p.parse_args();sys.path.insert(0,str(a.repo/'Tools/PDXExporter'))
    from build_ck3_mod import parser_only,clausewitz,one,values
    pdx=parser_only(a.plugin);validation=json.loads((a.mod/'validation.json').read_text(encoding='utf8'));verification=json.loads((a.model/'verification.json').read_text(encoding='utf8'))
    assert validation['passed'] and verification['passed']
    folder=a.mod/'gfx/models/portraits/uma/0001';mesh=pdx.read_meshfile(str(folder/'uma_0001_body_base.mesh'));obj=mesh.find('object')[0];node=obj.find('mesh')
    asset=clausewitz((folder/'uma_0001_body_base.asset').read_text(encoding='utf-8-sig'));body=one(asset,'pdxmesh');settings=one(body,'meshsettings');assert one(settings,'name')==obj.tag
    assert len(node.attrib['p'])//3==3510 and len(node.attrib['tri'])//3==5472 and len(obj.find('skeleton'))==134
    variants=['base','none','b0','b1','b3','b4','s1','s2','h0','h2']
    for variant in variants:assert sha(folder/('uma_0001_body_'+variant+'.mesh'))==sha(a.model/'meshes'/('uma_0001_body_'+variant+'.mesh'))
    assert sha(folder/'uma_0001_body_base.mesh')==sha(folder/'uma_0001_body_none.mesh')
    assert len(values(body,'animation'))==173 and len(values(body,'additive_animation'))==15 and len(values(body,'blend_shape'))==26
    types=one(clausewitz((a.mod/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig')),'uma')
    for name,key in [('uma_male','minimum_age'),('uma_female','minimum_age'),('uma_boy','maximum_age'),('uma_girl','maximum_age')]:assert str(one(one(types,name),key))=='18'
    assert all(f.read_bytes().startswith(b'\xef\xbb\xbf')for f in a.mod.rglob('*.txt'))
    names=defaultdict(list)
    for f in(a.mod/'gfx').rglob('*'):
        if f.is_file():names[f.name.casefold()].append(str(f))
    assert all(len(v)==1 for v in names.values())
    name='UMA Canonical Body Rebuild';descriptor='name="'+name+'"\nsupported_version="1.20.*"\n';(a.mod/'descriptor.mod').write_text(descriptor,encoding='utf8')
    modfile=a.root/(a.mod.name+'.mod');modfile.write_text(descriptor+'path="'+a.mod.as_posix()+'"\n',encoding='utf8')
    if a.register_mod_dir:
        a.register_mod_dir.mkdir(parents=True,exist_ok=True);shutil.copy2(modfile,a.register_mod_dir/'uma_canonical_body_rebuild.mod')
    models=a.root/'Models/0001';models.mkdir(parents=True,exist_ok=True);shutil.copy2(a.model/'uma_0001_body.blend',models/'uma_0001_body.blend')
    records=a.root/'Evidence';records.mkdir(exist_ok=True)
    for f in a.model.iterdir():
        if f.suffix.lower()in ('.json','.png'):shutil.copy2(f,records/f.name)
    # Code package has no raw game meshes, textures, encrypted data, or DB.
    toolroot=a.root/'Tools/NativeBody';toolroot.mkdir(parents=True,exist_ok=True)
    for f in(a.repo/'Tools/NativeBody').iterdir():
        if f.suffix in ('.py','.md')and f.is_file():shutil.copy2(f,toolroot/f.name)
    report=dict(passed=True,mod_name=name,shared_body='0001',vertices=3510,triangles=5472,bones=134,
                no_added_mesh_samples=True,all_body_endpoint_files_match_verified_source=True,neutral_placeholder_exact_basis=True,
                vanilla_body_animations=173,vanilla_additive_animations=15,stock_bs_entries=26,
                age_thresholds_unchanged=True,txt_utf8_bom=True,gfx_basenames_unique=True,
                maximum_asset_absolute_path=max(len(str(f))for f in a.mod.rglob('*')if f.is_file()),
                runtime_visual_verified=False,windows_ui_control_error='Computer Use native pipe unavailable (os error 2)',
                model_sha256=sha(models/'uma_0001_body.blend'),engine_verification=verification)
    assert report['maximum_asset_absolute_path']<256
    write(a.root/'release-verification.json',report)
    description='''# UMA Canonical Body Rebuild

新入口从未细分的通用 0004 / 0009 源模型重建，不使用上一版 14,787 顶点网格或待机法线补偿。

- 原始与重建：3,510 顶点、5,472 三角面；保留原有顶点、UV 和所有 BS 的一一对应，包裹区没有新增补片。
- 先重建皮肤和平滑衣物轮廓，再使用 UMA 原生 69 骨调整并固化 A 姿势、尺寸、位置及脚底接地，最后绑定原版 134 骨。
- 颈部 95 个顶点按原版表面重取样权重，处理颈部压缩后的动画梯度。
- 1 个共享 Basis，8 个单变量端点（胸型 4、体型 2、源身高参考 2）；游戏身高继续使用原版 additive_animation。
- 28 组已提供源组合通过可加验证；另外 17 组没有源模型，只能合成，不能写成源数据验证通过。
- body 保留原版 asset 排版、173 个普通动画及 15 个 additive 声明、26 个 BS 条目；动画相对路径访问原版 female_body。
- 通用躯干在 0001，头部在 1001，共用头部动画在 animation；shader 使用 uma_portrait.shader，所有 TXT 使用 UTF-8-BOM，四组的 18 岁阈值不变。

验证包含最终 Blender 工程重开、81 个实际动画/BS 求值、9 个端点的 PDX IO 往返、原版 188 声明共 47,893 帧的数值和边长检查；游戏原版动作文件不改。

启动器启用 UMA Canonical Body Rebuild，关闭此前的其他 UMA 测试版。选择玛蒂尔达后用 effect set_ethnicity = uma_ethnicity。本轮 Windows 界面控制的 native pipe 返回 os error 2，未进入游戏复测画面；离线通过不代表 CK3 实机验收完成。

Models/0001/uma_0001_body.blend 打开默认播放原版 idle，骨骼覆盖隐藏；在 Outliner 可显示骨架、切换 Rest Position 检查 A 姿势。SOURCE_REFERENCES_DO_NOT_EXPORT 集合含原始泳装 T 姿势、重建皮肤 T 姿势和拟合后的原生 UMA 骨架。

Evidence/canonical-density-wireframe.png：从左至右原始泳装、重建皮肤、固化 A 姿势。skin-surface-comparison.png：左为原始几何，右为重建几何，不使用 diffuse。rest-and-native-animation.png：原版与新模型的实际动作对照。rest-feet-side.png：左为新模型、右为原版。

Tools/NativeBody/README.md 提供新流程和旧版故障重现边界。所有生成物存放 E 盘，源工程和旧包保留。
'''
    (a.root/'DELIVERY.md').write_text(description,encoding='utf8')
    artifacts=[]
    for zipname,folders in [('UMA-Canonical-Body-Rebuild.zip',[a.mod]),('UMA-Canonical-Body-Models.zip',[a.root/'Models',records]),('UMA-Canonical-Body-Tools.zip',[a.root/'Tools'])]:
        file=a.root/zipname
        with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for source in folders:
                for f in source.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(a.root).as_posix())
            z.write(a.root/'DELIVERY.md','DELIVERY.md');z.write(a.root/'release-verification.json','release-verification.json')
            if folders==[a.mod]:z.write(modfile,modfile.name)
        with zipfile.ZipFile(file)as z:assert z.testzip()is None
        artifacts.append(dict(file=zipname,bytes=file.stat().st_size,sha256=sha(file)))
    write(a.root/'packages.json',dict(artifacts=artifacts));print(json.dumps(dict(passed=True,artifacts=artifacts,max_path=report['maximum_asset_absolute_path']),indent=2))

if __name__=='__main__':main()
