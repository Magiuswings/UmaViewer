# UMA → Blender 4.2 / PDX Mesh

这一步处理已解密、具有实际文件名的 UnityFS 资产，复用 `../HeadlessExporter` 的真实 ZIP 解析结果。原始哈希/加密数据的第一步读取由 [RawAssets](../RawAssets/README.md) 提供。`run_pdx.py` 运行 Python，转换与验证脚本运行在 **Blender 4.2** 内；4.2 版本检查不接受 Blender 5.x 文件作为转换输入。

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

通用身体的基础模型按胸型分别制作。`body_profiles.py` 从 prefab 解析服装、子类型、身体设置、高度、体型和胸型，完整参数进入 `geometry_key`。`partitions.py` 仅在相同完整身体参数且整体拓扑／UV 对应时复用分类区域；不同胸型即使几何拓扑一致也不复用分类、不生成身体或服装 morph。`--families` 声明也不能绕过此限制，旧版缓存组再次按真实源字段检查。胸型未知的角色专属身体按角色独立保留，不猜胸型。

显式的 **整体体型 BS 模式** 是独立许可：`--character-db <master.mdb> --body-type-morphs` 先只读查询实际 `chara_data`，按角色的 `height/shape/bust` 选通用身体，并核对 `skin` 贴图。在相同通用衣装内，只有整体有向拓扑、全部 UV、骨架父链、语义权重与绑定矩阵通过后，才能把不同体型做成整体 BS。该模式不将胸型 1 的皮肤／服装分区覆盖到胸型 2，也不生成独立衣物跨胸型键；普通模式的隔离规则保持有效。

本次用户提供的数据库确认：1001 是 `height=1, shape=0, bust=2, skin=1, scale=158`，1003 是 `1,0,1,1,150`。共享体型工程用胸型 1 作 Basis，仅增加 `height_1__shape_0__bust_2` 键。角色在 `character-body-bindings.json` 中引用相应类型，不生成角色 ID 命名的躯干键。此 JSON 同时记录 `diffuse_overrides`：不同胸型的 diffuse 像素有差异，几何键不能替代材质切换。

原仓库另以 `scale/160.7529` 对整个角色根节点缩放；该数值只保存为元数据，导出时不缩放或平移 mesh。角色数据库的有限参数只证明通用衣装的模型选择路径，不能据此把含专属衣服的 `bdy1001_30`／`bdy1003_90` 等网格视为通用身体的完全等价模型。它们保留作独立服装来源。

例如本次两角色都使用 skin 1，先从已命名原始资产重新解析：

```powershell
python ..\HeadlessExporter\export_assets.py E:\named-assets.zip --output E:\skin1-inputs --generic-skin 1
python run_pdx.py --manifest E:\skin1-inputs\manifest.json --output E:\PDX-body-types --blender "C:\path\blender-4.2\blender.exe" --pdx-plugin E:\vendor\io_pdx_mesh --body-reference E:\references\female_body.mesh --head-reference E:\references\female_head.mesh --character-db E:\master.mdb --body-type-morphs
```

若缺少匹配参数的通用模型／肤色贴图，模式报告不匹配并拒绝生成体型组，不猜字段。`character-body-profiles.json` 保存实际数据库哈希、查询参数与对应资源；`body-type-validation.json` 保存拓扑、权重、骨架和容差验证。原始数据库不修改、不随公开程序包分发。

`body-bases.json` 列出每套基底的 `bust`、完整参数、原始来源以及 `.blend`／`.mesh` 路径。本次 `bdy0004_00_00_1_0_1` 与 `..._2` 分别作为胸型 1、2 的基底；保留各自皮肤 4009／4008 面、服装 1463／1464 面，不再统一此前的一个边界三角面。本轮 `partition-changes.json` 的变化面数为 0。当前皮肤拆分使用每个模型自身 UV 贴图，未使用小胸基底表面去扣除其他身体。

每个合格家族选择确定顺序中的第一个来源为基础，保留原 Basis 和原 Renderer 边界。`morphs/<group>/editable.blend` 含 Basis 与其余来源的 Shape Keys。PDX IO 的 **`as_blendshape=True`** 用于实际导出 `base.mesh` 和每个目标 `.mesh`；它不会自动把 Blender KeyBlocks 写成一个包含所有形态的 PDX 文件，所以工具显式生成每个完整目标。目标坐标逐点来自真实源变体，没有人工拟合。PDX 的 UV 分裂可能让二进制顶点数大于 Blender 原始顶点数，基础与每个目标的二进制顶点顺序和面连接仍必须对应。

形态继承基础款的 rig、权重、材质槽和贴图；来源变体自己的 rig、权重和贴图仍保存在其独立组件。材质颜色不能通过几何 Shape Key 变化。`morph.asset` 是 PDX `blend_shape` 引用片段，需在实际模组里配置 mesh 名称、人物基因与 entity；本工具不安装或改写游戏模组。

## 肤色与验证

`skin-colors.json` 保留角色、组件和每套服装的独立记录，以及优先使用 `80` 变体的面部参考。每个皮肤三角面在顶点、边中点和中心采样共七次，使用面积加权，并过滤透明区、源肤色范围之外的眼睛／口部／服装图集区域。记录包含 sRGB、0–255 RGB、linear RGB、采样数量、阈值和源路径；统计来自原始 PNG，未受 DDS 压缩和场景照明影响。源贴图本身的阴影仍在统计中，不称为固有反射率测量。

默认独立进程重开全部部件，逐源索引检查顶点／UV，核对原版父链、源到目标的权重合并和归一化，再实际调用同一 PDX 插件导入每个输出。二进制检查 renderer 数量、每个材质槽／面数、索引、有限值、权重、坐标与骨骼。所有 morph 的 KeyBlock 逐点与源目标比对，二进制目标按基础导出顺序检查位置、全部 UV、三角形和骨骼属性。`verification.json` 只有整轮通过才设 `passed=true`。

2026-10-06 的原始两个输入包此前重新解析为 57 + 116 个 Blender 4.2 工程，分别完成重开验证；合并后 24 个任务，10 个重复任务去重。胸型修订又实际合并 485 个原始 bundle，重新解析 24 个任务，零错误，确认同时选择两套胸型基底，原网格、骨骼和材质精确不变。完整原始泳衣两个胸型均为 3,510 个顶点、5,472 面，源坐标最大差约 0.0091；相同拓扑不意味着可以跨胸型复用基底。

胸型分离后的最终 96 个部件、96 次 PDX 插件回读、12 组形态和 47 个目标均通过独立验证。此前跨胸型的整身、皮肤和泳衣三个形态组已撤回，其余兼容组件保留。所有源类别的有向三角集合也与各自源模型核对；独立测试确认旧版统一分类的胸型 2 皮肤和服装会被此检查拒绝。角色专属宽衣物和裙子仍没有跨角色严格对应，保留独立模型及拒绝原因。当前没有 CK3 游戏内或原版动画的本轮运行验收。

随后的实际数据库体型模式完成 **96 个部件、96 次 PDX 回读、13 组形态／48 个目标** 验证。其中只有一个身体类组，目标键只按体型命名，角色专用躯干键为 0。BS 端点对源模型和目标二进制的位置误差为 0；原始语义权重误差为 0，源绑定矩阵最大差 `2.566707e-6`，在 `1e-5` 浮点容差内。表中 173 个角色有 23 种 `(height,shape,bust)` 参数组合，当前素材只实际验证所提供的两个目标类型，其他组合不称为已完成模型验收。

## 新增平胸与肥胖来源

加入 `SpecialFat (1).zip` 后合并为 48 个任务，实际交付通过 **193 个部件、193 次 PDX 回读、31 组形态／99 个目标** 验证，包含 224 个 `.blend` 与 323 个 `.mesh`。新增通用泳装 `pfb_bdy0004_00_00_1_1_0` 与原有两种胸型都是 3,510 个顶点、5,472 面，整体拓扑、全部 UV、语义权重与骨架绑定在规定容差内对应。整体体型工程保持胸型 1 为 Basis，两个目标分别是 `height_1__shape_0__bust_2` 与 `height_1__shape_1__bust_0`；每个目标是一套完整组合，没有拆成胸型与体型的独立向量。

实际数据库对应 1001、1002、1003 三位角色。`--character-id` 可重复指定需要建立数据库绑定的角色，例如 `--character-id 1001 --character-id 1002 --character-id 1003`；其他角色的已提供部件仍全部导出。1071 与 1105 的专属服装已导出，但当前包没有相应通用泳装参数模型，不能称为通用身体表验证通过。

肥胖运动服 `pfb_bdy0002_01_03_1_0_2` 有 6,812 个顶点、9,074 面；目前提供的普通运动服 `pfb_bdy0002_01_00_1_0_1` 有 6,604 个顶点、8,860 面，两者拓扑不同，而且胸型也不同。因此肥胖来源保持独立部件，未生成虚构 BS。需要同胸型普通来源 `pfb_bdy0002_01_00_1_0_2` 才能继续验证是否有兼容的完整目标。

## CK3 样例打包

`build_ck3_mod.py` 从已验证的交付和用户自己的 `uma_3d.zip` 生成一个新的模组目录及 ZIP，不改写已有模组。它保留样例头部、shader、贴图和头部动画，注册组件资产库与完整形态组，采用 `portrait_group=uma`。`uma_ethnicity` 和用户测试命令使用的兼容拼写 `uma_ethnity` 均保留。

```powershell
blender --background --factory-startup --python-exit-code 1 --python export_mod_pose.py -- --blend E:\PDX-output\morphs\<body-type-group>\editable.blend --output E:\pose\uma_idle.anim --pdx-plugin E:\vendor\io_pdx_mesh --frames 30
python build_ck3_mod.py --sample E:\uma_3d.zip --delivery E:\PDX-output --output E:\Uma-Combination-Mod --pdx-plugin E:\vendor\io_pdx_mesh --rest-animation E:\pose\uma_idle.anim --portrait-reference "D:\path\CK3\game\common\portrait_types\00_human_types.txt"
```

姿势脚本只在内存中改变肩部骨骼姿势，不修改 mesh 点或保存源 `.blend`，通过实际 PDX IO 导出 30 帧的恒定 `t/q/s` 采样。各身体动画状态暂时映射到这个常量姿势，未完成原版动作重定向。`scale=100` 仅写入游戏资产元数据，原 `.mesh` 字节保持不变。

CK3 材质覆盖的 DDS 名称必须相对于对应 `.mesh` 所在目录；BS 属性的 entity 默认值必须为 0；基因的人像类型必须与样例注册名一致。本次实机排查发现此前打包版存在这些配置错误，已修正工具。**文件结构验证不等于 CK3 实机验收**：新基因的人像组绑定仍在实机排查，崩溃版本保留作为诊断现场，不应作为可用模组安装。最终运行证据另记录在交付的运行报告中。

### 复用原版 BS 接口的可选试验

`build_ck3_mod.py --reuse-vanilla-body-asset <原版 female_body.asset>` 会先只读核对原版合同，然后仅在 UMA 默认身体中复用以下名称。目标仍指向 UMA 真实完整端点；原版身体 asset 不随本模式覆盖。

| UMA 完整组合 | 原版 BS ID | 原版 attribute |
| --- | --- | --- |
| `height_1__shape_0__bust_1` | `female_bs_body_neutral` | `bs_body_seated` |
| `height_1__shape_0__bust_2` | `female_bs_body_breast_size_max` | `bs_body_breast_size_max` |
| `height_1__shape_1__bust_0` | `female_bs_body_breast_size_min` | `bs_body_breast_size_min` |

再加 `--reuse-vanilla-gene-file <原版 01_genes_morph.txt>` 会在 `morph_genes` 的 UMA 组内使用 `gene_bs_bust`，替代本工具的 `gene_uma_body_combinations`。原版全部 11 个模板名和 index 从实际文件读取并保留：`bust_clothes` 对应 Basis，`bust_clothes_light` 对应完整平胸组合，`bust_default` 对应完整胸型 2；其余八个原版模板在 UMA 组内确定映射为 Basis。默认 ethnicity 选择 `bust_default`。所有模板都是完整端点的互斥选择，未复制原版曲线/年龄/服装控制语义，未覆盖 human 基因文件。

这两个模式已实际构建并在 CK3 1.20.0.3 的独立 profile 中测试，均仍发生 `C0000005`。属性查找、错误人像类型和非零默认值报错均为零。只复用 BS key 时，新增 `gene_uma_body_combinations` 缺失 DNA 记录为 445 条；同时复用原版 gene 时，记录变为 `gene_bs_bust` 445 条，而原版 DNA 本身已有此字段，因此仍需定位肖像组/DNA 解析。不能把复用接口称为已解决崩溃。

原版 `gene_bs_bust` 和 `gene_age` 也会控制部分同名属性；当前 UMA 模板内部互斥已验证，最终运行权重是否受其他控制入口影响仍未验收。复用模式的完整合同保存在 `validation.json` 中。

### 四组肖像类型与年龄边界

根据用户指出的载入要求，当前 builder 完整定义 `uma_male`、`uma_female`、`uma_boy`、`uma_girl`；每个形态基因模板也必须有全部四个对应分支。`uma_girl = uma_female`、`uma_boy = uma_male` 保留原版常用的儿童/成年继承方式，不能只定义成年两组。

新增必需参数 `--portrait-reference` 指向实际原版 `00_human_types.txt`。程序逐字段复制原版 `sex`、`minimum_age` 与 `maximum_age`，本机原版成年 `minimum_age=18`、儿童 `maximum_age=18`，保持边界和原值不变，不改成其他数值或重新解释包含关系。女童使用 UMA 头部与身体，男童使用原版男童身体；原有头部挂接关系保留。

`portrait_type_contract` 记录参考文件 SHA-256、四组模型与原版年龄字段，静态校验会拒绝年龄字段变动或基因分支不完整。本次修订恢复全部 BS、原材质和资产库重新实机测试；此前未包含儿童两组的失败试验仍保留为历史诊断证据，不能当作四组完整版本的运行结果。

四组版本已在 CK3 1.20.0.3 实际进入 1066 玛蒂尔达地图，日志确认对 7757 应用 `uma_ethnicity`，本轮未复现此前的启动闪退。实机截图中完整 BS 版本的紫色泳装躯干已显示；头部仍缺失、皮肤呈黑色，全部形态端点切换也尚未运行验收。跨组属性查找、旧 DNA 警告仍有记录，不能把“能进入游戏”扩展为完整视觉/基因兼容验收。年龄边界仍逐字段等于原版 18。

### 身体单位烘焙对照

用户随后明确要求删掉身体 asset 的 `scale=100`，将生成身体 mesh 放大到原始坐标的 105 倍。这是对前述保留坐标要求的指定试验例外，原始转换结果和源 `.blend` 保留不变。

```powershell
python scale_body_probe.py --source E:\Uma-Combination-BS-Mod-four-types --output E:\Uma-Body-Baked105-Test --pdx-plugin E:\vendor\io_pdx_mesh --factor 105
```

工具在新目录中统一缩放默认身体基底及两个完整 BS 目标：顶点、包围盒、包围球、逆绑定骨骼平移和静态动画平移都按精确 float32 的 `原值*105` 写入。法线、切线、UV、拓扑、权重、骨骼索引/父链/旋转、动画 quaternion/scale 原值不变。身体 asset 删除 scale 行，头部、四组/18岁边界及基因不变；其他资产库组件不属于本次缩放范围。

本轮已实际进入玛蒂尔达地图并应用 `uma_ethnicity`，头部从此前缺失变为可见；皮肤黑色仍未修复，各 BS 端点切换和完整视觉仍未验收。该 105 倍替代旧 asset 的 100 倍设置，名义显示大小约为此前的 1.05 倍，未重复叠乘。

## 完整皮肤代理底模

`complete_body_skin.py` 接收一个或多个真实解码 manifest，按相同 `(height, shape, bust)` 匹配 0004 竞技泳装与 0009 露脐装的露肤覆盖。输出固定采用完整 0004 拓扑，保留原始顶点、全部 UV、骨骼、权重和形态。每面七个位置采样，默认最近皮肤距离不超过源单位 0.015 m、法线夹角余弦至少 0.5，至少五个采样命中才计入 0009 新增皮肤覆盖。它记录覆盖并集，不声称做了网格 Boolean 或精确解剖重建。

所有剩余面直接使用竞技泳装的完整网格作为缺失皮肤代理，不按缺失比例跳过。最终全部面归为 `body_skin`，只保留一个 `portrait_skin` 材质，竞技泳装的独立材质槽为零。填补色从默认 `_MainTex` 原始 PNG 的露肤面做面积加权采样；0009 新增覆盖使用其对应皮肤 texel 的采样色。原始 diffuse 及其衣服导出保持不变，生成单独的完成版贴图。

当前真实输入 `BSTest.zip` 加上此前提供的泳装/平胸解码数据，得到三套 3510 顶点、5472 面的完成底模：`height_1__shape_0__bust_1` 为 Basis，完整组合目标为 `height_1__shape_0__bust_2`、`height_1__shape_1__bust_0`。胸型 2 的 0009 新增覆盖为 530 面，剩余填补 934 面；平胸体型新增 531 面，填补 955 面。胸型 1 没有同体型 0009 来源，填补 1463 面。三套填补色均为默认 skin=1 diffuse 采样的 sRGB `(255,230,202)`；数值不包含场景灯光。

```powershell
python Tools/HeadlessExporter/decode_skin_inputs.py --package C:/path/BSTest.zip --output E:/BSTest-decoded --headless-tools Tools/HeadlessExporter --generic-skin 1
python Tools/PDXExporter/complete_body_skin.py --manifest E:/previous/manifest.json --manifest E:/BSTest-decoded/manifest.json --output E:/completed-inputs --blender C:/path/blender-4.2/blender.exe --headless-tools Tools/HeadlessExporter --pdx-tools Tools/PDXExporter
python Tools/PDXExporter/run_pdx.py --manifest E:/completed-inputs/manifest.json --output E:/PDX-completed-skin --blender C:/path/blender-4.2/blender.exe --pdx-plugin E:/vendor/io_pdx_mesh --body-reference C:/path/female_body.mesh --head-reference C:/path/female_head.mesh --character-db C:/path/master.mdb --character-id 1001 --character-id 1002 --character-id 1003 --body-type-morphs --only body_base
blender --background --factory-startup --python-exit-code 1 --python Tools/PDXExporter/preview_skin_completion_blender.py -- E:/PDX-completed-skin/config.json
python Tools/PDXExporter/install_completed_body.py --source-mod E:/Uma-Skin-Neck-Fix-Test --delivery E:/PDX-completed-skin --output E:/Uma-Complete-Skin-Test --pdx-tools Tools/PDXExporter --pdx-plugin E:/vendor/io_pdx_mesh
```

完成输入附带 `raw-inputs/manifest.json` 和所选源模型/贴图，可将它作为下一次 `--manifest` 重跑，不必再传完整游戏数据包。输出必须使用新目录。Blender 生成运行必须带 `--python-exit-code 1`，完成后复用 PDX 独立重开/回读验证。

真实本轮已通过三个组件、三次 PDX IO 回读、一组完整 BS 的验证，三套正背面肤色图和覆盖图均已生成。`install_completed_body.py` 在新的模组副本中安装单皮肤模型：默认身体继续烘焙 105 倍，沿用上一版头颈位置和动画修复，核对头部/动画、四组 portrait type、18 岁年龄字段与基因保持不变。用于 CK3 的 diffuse alpha 为 0，以关闭 portrait_skin 的调色板混合；它是肤色 mask，源 Blender diffuse 的不透明 alpha 仍保留。本轮完成版尚未在 CK3 中切换 BS 端点运行验收。


## 单变量通用躯干（2026-10-08）

新的显式 [BodyVectors](../BodyVectors/README.md) 流程只读取 `bdy00…` 通用模型，采用原始竞技泳装的 28 套体型和同参数 0009 露肤并集重建单皮肤底模；源坐标不做位移。以 height=1 / shape=0 / bust=2 为 Basis，提供 height 3 种、shape 3 种、bust 5 种取值键，其中 8 个非零、3 个零位移默认值。28 个真实组合全部能由纯单变量向量相加重建，覆盖实际 master 的 173 条角色记录，不生成每角色或每组合躯干键。

这一流程独立验证原始顶点编号、有向拓扑、完全相同的 UV0 和语义权重，并明确复用 Basis 的附加 UV 与骨架。它不会放宽普通部件/服装的全部 UV 严格复用规则，也不会改变旧的完整组合工具模式。源骨骼点随体型有所变化，共用 Shape Key 工程没有给每个键移动骨骼；完整动画仍未验收。肥胖运动服 setting03 与泳装拓扑不同，没有伪造为精确向量。

实际完成 11 个 Blender4.2 取值键、28 种组合求值、PDX 二进制组合及 9 个插件回读检查；四种肤色仍通过真实 diffuse 和 JSON 独立索引。新的可选安装器使用 gene_uma_height / gene_uma_shape / gene_uma_bust，逐字段保留四组 portrait type、原年龄阈值与既有头颈修复；身体继续按用户要求烘焙105。当前未完成本轮 CK3 实机端点/动画验收。
