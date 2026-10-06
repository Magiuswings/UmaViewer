# UMA → Blender 4.2 / PDX Mesh

这一步处理已解密、具有实际文件名的 UnityFS 资产，复用 `../HeadlessExporter` 的真实 ZIP 解析结果。文件名解密仍不在本工具内。`run_pdx.py` 运行 Python，转换与验证脚本运行在 **Blender 4.2** 内；4.2 版本检查不接受 Blender 5.x 文件作为转换输入。

用户指定的策略：保留源网格顶点坐标、对象变换、UV、面连接和 Basis；按 CK3 原版骨架名称、父链和朝向适配绑定点。直接对应的关节落在 UMA 的现有源关节点，缺少的辅助骨骼按参考父骨局部关系与实测比例生成。未匹配的源骨骼权重沿源父链合并到对应关节，服装链按同类骨骼链和位置匹配。每顶点最多四项权重并归一化，截断量与全部映射写在 `.rig.json`。

**不做 mesh 配准、缩放、平移、A/T 姿势变换、重拓扑或身体补全。** 源 Unity→Blender 坐标转换及既有头尾接点处理发生在上一步，PDX 阶段对其结果逐点保持。原版没有对应的头发／尾巴辅助骨骼会合并到语义祖先；没有重建 Unity 布料、头发或尾巴物理。适配的 bind pose 不等于可以直接套用原版动画的所有平移轨道，动画与游戏内验收需要另做。

## 材质

| 组件 | PDX shader |
| --- | --- |
| `body_skin` | `portrait_skin` |
| `face`、`face_effects` | `portrait_skin_face` |
| `hair`、`eyebrows`、`tail` | `portrait_hair` |
| `eyes` | `portrait_eye` |
| `clothing`、`headwear`、`footwear` | `portrait_attachment` |

完整 `body_base` 保留身体全部几何，并按原有分区分别使用皮肤和附件 shader。服装仍遵循宽分类：颈部以下服饰并入衣物，鞋袜及其附着物归 footwear，头部装饰归 headwear；不强制拆成裙子、袖子和小饰品。

PDX 材质节点直接接入源 diffuse 的 DDS DXT5。眼睛图集 `scale=(0.25,1)` 烘焙对应第一页成独立贴图，UV 不变。normal／properties 是明确标记的中性 PDX 贴图，没有把 Unity control mask 误用成法线，也没有声称还原 Unity shader。纹理放在 `.mesh` 同目录并打包进 `.blend`，便于插件回读。硬链接减少本机重复存储；打包 ZIP 后是普通文件。

## 用法

先用 `HeadlessExporter/export_assets.py` 的 `--blender` 指定 **Blender 4.2**，从原始 ZIP 重新生成快照／贴图／可编辑工程。安装 Python 依赖参照 HeadlessExporter 的 `requirements.txt`；本步骤另使用 Pillow 的 DDS 写入。

单包可直接使用其 `manifest.json`。多包先合并，源文件保持不变：

```powershell
python merge_inputs.py --manifest E:\input1003\manifest.json --manifest E:\input1001\manifest.json --output E:\combined-inputs
```

相同名称只有几何、骨架、权重和材质快照完全相同时才去重；冲突的记录保留独立名称。未知归属的共用身体保持 `shared`，不将其强行标成某位角色。

```powershell
python run_pdx.py --manifest E:\combined-inputs\manifest.json --output E:\PDX-output --blender "C:\path\blender-4.2\blender.exe" --pdx-plugin E:\vendor\io_pdx_mesh --body-reference E:\references\female_body.mesh --head-reference E:\references\female_head.mesh
```

`--pdx-plugin` 指向已有 `io_pdx_mesh` 包目录，不是 Blender 插件安装目录的上层。参考文件应是原版 CK3 的女性身体／头部 `.mesh`；当前实现检查 134 / 61 个骨骼契约。已有插件不修改；此项目实际使用 IO PDX Mesh 0.91，源码提交 `2249e35f80a1cc04ba4c2b8e4c650f36b18085db`。没有把原版参考、角色资源或 Blender 程序提交到公开仓库。

`TEMP/TMP/TMPDIR`、插件的临时 AppData 设置仅对本次进程及其子进程指向输出目录；不改变 Windows 全局环境。建议所有输出放在容量充足的 E 盘。程序包采用 `PDXExporter` / `HeadlessExporter` 目录时，每个目录内附有 `uma_blender_import.py`，可独立运行。

`--only` 与 `--job` 是可选的类别／精确任务过滤，只导出对应子集，不能称为全部交付。`--skip-verify` 会跳过独立验证，默认不使用。`--families families.json` 可以指定已确认相同服装的精确任务／源路径对应家族；声明家族仍不能跳过拓扑与 UV 检查。

已有完整部件需要重跑形态阶段时，可以使用 `--morphs-only`，它复用现有部件并重新执行全部独立验证；新输入和首次输出应使用完整流程。

## 形态与索引

`source-apparel-index.json` 保存原始宽分类兼容性；`apparel-index.json` 保存最终分类及所有角色／服装／组件的对应关系。只有同一已确认源服装家族且全部有向面连接、所有 UV 层精确对应时才能复用基础网格。不同角色的服装编号相同不视为同款证据。裙骨面、裙子连通组件仅建立虚拟索引，保存源面与顶点编号；不改变宽衣物对象。

同一通用服装的整体拓扑／UV 完全对应时，`partitions.py` 在输出目录里的快照副本上统一基础款的材质分类区域。这只改类别标签，源顶点、UV、连接、权重、法线和原始文件都保留；每个变化面写入 `partition-changes.json`。本次两个泳衣身体仅统一一个三角面的皮肤／衣物边界，使独立衣物与皮肤也能形成对应的 morph。

每个合格家族选择确定顺序中的第一个来源为基础，保留原 Basis 和原 Renderer 边界。`morphs/<group>/editable.blend` 含 Basis 与其余来源的 Shape Keys。PDX IO 的 **`as_blendshape=True`** 用于实际导出 `base.mesh` 和每个目标 `.mesh`；它不会自动把 Blender KeyBlocks 写成一个包含所有形态的 PDX 文件，所以工具显式生成每个完整目标。目标坐标逐点来自真实源变体，没有人工拟合。PDX 的 UV 分裂可能让二进制顶点数大于 Blender 原始顶点数，基础与每个目标的二进制顶点顺序和面连接仍必须对应。

形态继承基础款的 rig、权重、材质槽和贴图；来源变体自己的 rig、权重和贴图仍保存在其独立组件。材质颜色不能通过几何 Shape Key 变化。`morph.asset` 是 PDX `blend_shape` 引用片段，需在实际模组里配置 mesh 名称、人物基因与 entity；本工具不安装或改写游戏模组。

## 肤色与验证

`skin-colors.json` 保留角色、组件和每套服装的独立记录，以及优先使用 `80` 变体的面部参考。每个皮肤三角面在顶点、边中点和中心采样共七次，使用面积加权，并过滤透明区、源肤色范围之外的眼睛／口部／服装图集区域。记录包含 sRGB、0–255 RGB、linear RGB、采样数量、阈值和源路径；统计来自原始 PNG，未受 DDS 压缩和场景照明影响。源贴图本身的阴影仍在统计中，不称为固有反射率测量。

默认独立进程重开全部部件，逐源索引检查顶点／UV，核对原版父链、源到目标的权重合并和归一化，再实际调用同一 PDX 插件导入每个输出。二进制检查 renderer 数量、每个材质槽／面数、索引、有限值、权重、坐标与骨骼。所有 morph 的 KeyBlock 逐点与源目标比对，二进制目标按基础导出顺序检查位置、全部 UV、三角形和骨骼属性。`verification.json` 只有整轮通过才设 `passed=true`。

2026-10-06 的实际两个输入包重新解析为 57 + 116 个 Blender 4.2 工程，分别完成重开验证；合并后 24 个任务，10 个重复任务去重。完整原始泳衣两个尺寸变体均为 3,510 个顶点、5,472 面，最大源坐标差约 0.0091。角色专属宽衣物和裙子没有跨角色严格对应，保留独立模型并记录拒绝原因，不能宣称已经生成其无损跨角色裙子 morph。当前没有 CK3 游戏内或原版动画的本轮运行验收。

最终 96 个部件、96 次 PDX 插件回读、15 组形态和 50 个目标均通过独立验证。规范化后的独立泳衣服装有 886 顶点／1,463 面，皮肤有 2,654 顶点／4,009 面，均有实际形态输出。50 个目标中 11 个坐标差超过 1e-5，其他属于相同或近似相同源几何，不将它们称为新的实质体型。
