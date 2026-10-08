# 单变量通用躯干与 Blender / PDX

只查询 `3d/chara/body/bdy00…` 的通用模型索引，不扫描或解码角色专属躯干。实际几何只选择竞技泳装 `bdy0004_00_00` 的 28 套参数模型、相同参数的 `bdy0009_00/01_00` 露肤覆盖，以及四个 `bdy0002` 普通/肥胖对照源。当前依赖闭包 249 个资源、34,362,408 字节；原始分卷包不改动、不展开整包。

使用只读 `chara_data` 确认参数和角色索引：173 条角色记录、23 种实际角色组合；通用泳装有 28 种源组合，覆盖全部表中角色。`height=[0,1,2]`、`shape=[0,1,2]`、`bust=[0,1,2,3,4]` 保留数据库原值，`skin=[0,1,2,3]` 通过真实 diffuse 和颜色 JSON 单独处理。

Basis 选择 `height=1,shape=0,bust=2`，因为这个点可取得每个变量的所有纯单变量端点。单个取值向量是 `源端点 - Basis`，组合是 `Basis + Δheight + Δshape + Δbust`。Blender 包含 11 个取值 KeyBlocks 和 Basis；默认值 height_1/shape_0/bust_2 为零位移，8 个取值有位移。PDX 显式导出 Basis 和 8 个完整非零端点，三个零位移 ID 引用同一个 base.mesh。无每组合键、角色 ID 躯干键、拟合坐标或交互纠正键。

28 套原始模型的顶点编号和有向拓扑相同，UV0 逐点相同，语义骨骼权重相同。完整 UV 层并不全部相同；其中一个源模型的额外 UV1 有异常大数值。因此这个显式整体向量流程复用 Basis 的全部 UV 层，不能据此放宽旧服装/普通部件的全 UV 严格复用规则。形态参数也会改变原始骨骼绑定点，最大差约 0.0068 源单位；本工程固定使用按 CK3 结构适配的 Basis 骨架，Shape Key 不移动骨骼。没有完成所有形态下的原版动作重定向。

皮肤保持此前策略：0009 仅提供同参数露肤覆盖/采样色，最终全身使用完整竞技泳装拓扑填补，所有面属于 body_skin、只有 portrait_skin，无独立泳装材质。源顶点、Basis、权重、UV0 不做平移或缩放；源 Blender 工程单位保持不变。安装模组时按用户既有要求把 PDX 身体烘焙 105 倍，并移除 asset scale=100。四组 portrait type 与原版年龄字段不改动，头颈修复沿用现有已验证副本。

## 可复现流程

需要已有本仓库 RawAssets / HeadlessExporter / PDXExporter、Windows 加密数据库 DLL、UnityPy/Pillow、Blender4.2 和 PDX IO。解码配置仅由 RawAssets 在内存读取，不打印或打包。所有输出和临时目录放在 E 盘，输出使用新目录。

在仓库根目录执行，下列路径可自行替换：

```powershell
$py = 'Tools/HeadlessExporter/.venv/Scripts/python.exe'
$repo = 'E:/UmaViewer-Workspace/UmaViewer-source'
$out = 'E:/UmaViewer-Exports/new-vector-run'
$blender = 'C:/path/blender-4.2/blender.exe'
$plugin = 'E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'

& $py -X utf8 -B Tools/BodyVectors/prepare_vector_body_inputs.py --repo $repo --source E:/uma --workspace E:/UmaViewer-Workspace/UmaRaw-CLI --output $out --decode
& $py -X utf8 -B Tools/BodyVectors/decode_common_bodies.py --repo $repo --named "$out/named-common" --output "$out/decoded"
& $py -X utf8 -B Tools/PDXExporter/complete_body_skin.py --manifest "$out/decoded/manifest.json" --output "$out/completed" --blender $blender --headless-tools "$repo/Tools/HeadlessExporter" --pdx-tools "$repo/Tools/PDXExporter"
& $blender --background --factory-startup --python-exit-code 1 --python Tools/BodyVectors/analyze_vector_body_blender.py -- --repo $repo --manifest "$out/completed/manifest.json" --inventory "$out/common-body-inventory.json" --output "$out/analysis"
& $py -X utf8 -B Tools/BodyVectors/run_body_vectors.py --repo $repo --completed-manifest "$out/completed/manifest.json" --decoded-manifest "$out/decoded/manifest.json" --inventory "$out/common-body-inventory.json" --analysis "$out/analysis/vector-analysis.json" --output "$out/delivery" --blender $blender --pdx-plugin $plugin --body-reference C:/path/female_body.mesh
```

生成后默认独立进程重开 Blender 工程，逐点比对所有单变量源端点，实际求值 28 个组合，校验语义权重/骨架和根骨变形，再逐个用 PDX IO 回读 9 个真实网格。还直接相加 PDX 二进制中的端点位移，复查所有 28 种组合。`character-body-bindings.json` 是全表到三个参数键、实际 skin diffuse 和平均肤色的索引；角色 scale/160.7529 只记录、不施加。它不会自动修改 CK3 人物种族或 DNA。

可选模组安装沿用旧版本作为参考，在新目录中工作：

```powershell
& $blender --background --factory-startup --python-exit-code 1 --python Tools/PDXExporter/export_mod_pose.py -- --blend "$out/delivery/uma_common_body_vectors.blend" --output "$out/delivery/rest.anim" --pdx-plugin $plugin --pose relaxed
& $py -X utf8 -B Tools/BodyVectors/install_vector_body_mod.py --repo $repo --source-mod E:/Uma-Complete-Skin-Test --delivery "$out/delivery" --output "$out/Uma-Common-Body-Vectors-Mod" --pdx-plugin $plugin --rest-animation "$out/delivery/rest.anim"
```

模组使用独立的 `gene_uma_height`、`gene_uma_shape`、`gene_uma_bust`。一个基因只清零/设置自己的变量，不影响另外两个；默认 ethnicity 选 Basis 对应的三个取值。所有模板保留 male/female/boy/girl 四个分支，portrait group 从已有样例实际读取，年龄阈值原样保留。alpha=0 的游戏肤色 mask 保留 DDS RGB，Blender 原始贴图 alpha 不改。

## 验证边界

- 28 个已提供源组合通过；45 个数学组合中有 17 个缺少原始模型，不能称为源端点验证完成。
- `body_setting=03` 肥胖运动服是 6610 顶点/8698 面，和泳装 3510/5472 的拓扑不同；没有伪造为本底模的精确 fat 向量，原始肥胖与普通对照模型保留在解码数据中。
- 本轮没有 CK3 实机各端点和完整动画验收。静态绑定复用 Basis；不同形态下的头颈接口和动态穿插仍需运行检查。
- 原始加密 meta/master、运行解码配置、SaveData、账号文件、Blender 程序和 CK3 原版资产不提交或打包到公开工具仓库。
