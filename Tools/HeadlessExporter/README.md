# 无 UI 的 UmaViewer 已命名资产批量导出器

直接读取 UmaViewer `Loaded Assets -> Copy all` 导出的 **ZIP 或目录**，用 Python/UnityPy 解析网格、材质、贴图、Transform、骨骼和绑定矩阵，再调用后台 Blender 保存 `.blend`。无需 Unity Editor 或 UmaViewer UI。

后续 CK3 骨骼适配、PDX shader、肤色统计和严格拓扑形态导出见 [PDXExporter](../PDXExporter/README.md)。PDX 流程要求 Blender **4.2**，本次两个泳装包已从原始 ZIP 在 4.2.23 重新生成并独立重开验证，不能使用此前的 5.x 工程替代。

第一步的原始文件名映射、资源密钥解密和游戏数据库查询没有实现；输入必须已经是带有意义路径的 UnityFS 数据包。`.zip` 直接在内存读取，不执行包内脚本，也不把包中的文件解压到任意位置。

## 安装和运行

需要 Python 3.10+（本机验证 3.12.14）和 Blender 4.2+（本次真实资产验证 5.2.1）。此目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.cmd 'C:\Users\33775\Downloads\SpecialWeek1.zip' --output 'E:\UmaExports\SpecialWeek1' --name 1001=SpecialWeek --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

也可用 `.venv/Scripts/python.exe export_assets.py ...`；省略 `--blender` 时，只导出真实解析的中间 JSON/PNG，随后运行：

```powershell
blender --background --factory-startup --python-exit-code 1 --python headless_blender.py -- '<output>\manifest.json'
```

ZIP 与目录使用相同解析逻辑。一次处理输入包内找到的所有普通角色头／身体／尾 prefab；`--character 1001` 可限制角色。可重复提供 `--name ID=NAME`；没有名字时使用可靠的源角色 ID。共用尾通过专用 diffuse 纹理中的角色 ID 关联；无法明确归属的共用模型标记为 `shared`，不凭空指定角色。

`--output` 不能位于输入目录里面。同一输入可以在相同输出目录重新生成该程序命名的结果；不同输入包应使用不同输出目录。

程序会将本次 Python 进程和后台 Blender 的 `TEMP`／`TMP`／`TMPDIR` 指向输出目录内的 `.temp`，避免输出选在 E 盘时仍把临时文件写到 C 盘。该设置只影响本次进程及其子进程，不修改 Windows 全局环境变量或系统分页设置。

## 输出和命名

`blends/chara1001/` 中的文件包含角色 ID、可选名字、源身体或头部 ID、服装变体及内容，例如：

```text
chara1001__SpecialWeek__head_chr1001_00__face.blend
chara1001__SpecialWeek__head_chr1001_00__eyes.blend
chara1001__SpecialWeek__head_chr1001_00__eyebrows.blend
chara1001__SpecialWeek__head_chr1001_00__hair.blend
chara1001__SpecialWeek__body_bdy1001_00__body_skin.blend
chara1001__SpecialWeek__body_bdy1001_00__clothing.blend
chara1001__SpecialWeek__body_bdy1001_00__footwear.blend
chara1001__SpecialWeek__head_chr1001_00__headwear.blend
chara1001__SpecialWeek__body_bdy1001_30__body_base.blend
chara1001__SpecialWeek__tail_tail0001_00__tail.blend
charashared__body_bdy0004_00_00_1_0_2__clothing.blend
```

还会保留每个源 prefab 的 `__source_reference.blend`，包含未按人体／服装类别删减的整体几何。所有部件文件自带可编辑骨架、权重、UV、法线和打包贴图，可独立打开。

`manifest.json` 记录输入 SHA256、每个包文件 SHA256、角色／变体／来源、自动分类方法、面数、贴图与错误。`snapshots/` 保留原顶点与按类别拆分的索引；`.blend` 对象保留来源 PathID 和原顶点索引属性 `uma_source_vertex`，便于回查。用户输入 ZIP 不被修改。

## 身体和衣服的分离

头／脸、眼、眉、尾依据原 Renderer 和材质分区识别。附加泪、腮红等归 `face_effects`，保留原活动状态。头发中的服饰附件另归头饰；头发与耳朵留在底模。

**2026-10-05 第二版取消服装细分。** 衣物只输出以下三组，不再按 `Skirt`、`Jacket`、`Acc` 等名称硬拆裙子、上衣、披肩、手套或普通饰品：

| 类别 | 内容 |
| --- | --- |
| `clothing` | 头与躯干接点以下的全部服饰，排除鞋袜及其附着物 |
| `headwear` | 头部区域的全部服饰，如发带、蝴蝶结、花饰等 |
| `footwear` | 鞋、袜及其沿腿／脚骨骼绑定的附着物，合并输出 |

分界使用源 `Neck` 接点，并检查附件是否属于 `Head` 的骨骼父链，避免 T pose 抬高的手臂、手套和衣领被误归头饰。跨界三角面按面中心归组，不切出新顶点。头饰先检查完整几何组件的附件、头发和耳骨影响，再归入头部区域；如果包中有 `80` 头部变体，使用其已有头发几何作为无饰参考。该参考假设在当前 1001、1003 样本中成立，其他角色需要复核。

基础头发还提供自身颜色参照，用来保留直接绑定 `Head` 的同色发髻，并识别绑定 `Hair` 骨骼的异色布料。已经识别的布料会把同一发骨链控制的边饰一起带入服饰。1003 的 `43` 变体中，头纱上半归头饰，下半归服装，发髻保留在头发中。纹理本身存在配色掩码，所以这仍是带审计记录的启发式判断。

鞋袜根据完整服饰组件和骨骼父链归组：挂在 Knee／Ankle／Toe 下的绑带和装饰跟鞋袜一起输出；不会因名字包含 `Acc` 或 `Ribbon` 被单独拆出。完全赤脚的源泳装中，裸腿覆盖率超过 95%、无附件骨影响的少量肤色采样遗漏会回到 `body_skin`，避免凭空生成鞋袜。组件连接只用于归组；原顶点、权重、UV 和面均保留。

少量被肤色采样漏掉、与原皮肤共用至少 90% 边界顶点的细小面片也归回身体。躯干 prefab 内、由 Head／Neck 驱动的小型颈部皮肤接头根据其位置和范围归回身体，避免形成假头饰。上述修正均写入组件审计记录，属于局部启发式修正。

类别没有实际三角面时，在 `manifest.json` 的 `empty_apparel` 记录为空，不生成该类 `.blend`，也不造空 Mesh 对象。每个源 prefab 的同一类别集中在一个文件／Collection 内；原 Renderer 对象和材质区仍保留，不跨 prefab 强制合并骨架。

**源躯干通常不是独立的皮肤和服装网格。** `M_Body` 把皮肤、外衣、鞋袜和饰品放进一张图集。默认 `--skin-mode auto` 使用角色脸部 diffuse 的主要肤色作为参照，在三角形顶点、边中点和中心共 7 个 UV 位置采样；至少 5 个位置匹配肤色的面归 `body_skin`。其余服饰按上述三组输出。

**皮肤／服饰和发饰识别仍是启发式结果，需要复核。** 浅肤色布料、局部彩绘、特殊刚性发束和与头发焊接的装饰可能被误分。可调 `--skin-tolerance 42`，或用 `--skin-mode none` 禁用肤色拆分，保留 `body_clothing_mixed`。无论分类如何，所有类别的面合计必须与参照模型一致。

本次新包包含 `bdy0002`／`bdy0003`／`bdy0004` 共用身体。它们的材质原本没有贴图绑定，程序参照原仓库运行时规则，按完整 prefab 的服装和胸型参数绑定输入包已有贴图。`--generic-skin 0` 指定肤色贴图索引，默认 0；缺少角色数据库时不猜具体角色归属，保留 `shared`，也不猜具体角色配色。完整 prefab 名保留高度、体型等参数，避免同目录内不同身体重名。共用身体的肤色采样使用包内已有角色脸部参照。

使用实际角色表时按 `skin` 选择渲染贴图，本次 1001／1003 都是 skin 1。`--generic-skin-reference 0` 默认将同服装、同胸型的 skin 0 UV 图集仅用作稳定的皮肤区域分类参照；实际输出仍使用 `--generic-skin` 指定的 diffuse。这样不因肤色／高光像素变化而把皮肤改标为衣服，不跨胸型借用参照，不改几何。若参照缺失会记录 warning 并使用实际贴图分类。参照来源写入 renderer audit。

`--body-base-variant auto` 默认把现有躯干中“皮肤三角面比例最高”的完整服装模型另存为 `__body_base.blend`。这是候选选择，不是自动识别泳装的保证。SpecialWeek 实际选择变体 **30**，预览呈泳装。可以用 `--body-base-variant 30` 明确指定，或 `none` 禁用。底模保留选定服装的全部几何，不补全服装下面缺失的身体。

基础候选现在按 **角色归属＋胸型** 分组分别选择。通用 prefab 的六个字段依次是服装、子类型、身体设置、高度、体型、胸型；最后一位是 `bust`，不是肤色。本次同时提供 `_1_0_1` 和 `_1_0_2` 时会保留两套基底，不能让一个共用身体覆盖另一胸型。角色专属 `pfb_bdy1001_30` 没有该字段，记录 `unknown` 并按角色独立保存，不从服装编号猜胸型。

`clothes/pfb_*_cloth*` 在本次包中主要是 Unity 布料／物理配置；实际服装几何来自身体 prefab 的 `M_Body`。此程序没有把这些物理配置误当作额外衣服网格，也没有重建布料模拟。

## 坐标、骨架和材质

网格使用源 bind pose，骨骼位置由 Renderer transform 与逆绑定矩阵求得，保留父链、原骨骼 ID 及四影响源权重。遇到额外的 variable-count 权重格式会报错，避免悄悄截断。

参照 UmaViewer `MergeBone` 的接点，头部用 `Neck`、尾部用 `Hip` 对齐同角色现有躯干：优先同服装变体，缺少时回退 `00` 或另一已有变体，并记录 attachment 矩阵。每个部件保持独立骨架，不强制合并或重定向到其他角色骨架。`--native-coordinates` 保留原 prefab 原点。

UnityFS body 网格的重复背面索引 pass 会去重，Blender 材质保持双面；源索引统计与去重数量写在 audits 中。**没有删掉真实不同的部件面**，程序用索引三元组识别重复 pass。

材质输出复用本 Fork 的 Blender 节点转换器。保存全部原始材质参数和已引用的 2D 贴图，重建 EEVEE 卡通／Cycles 着色。SpecialWeek 包没有包含 Unity shader 依赖，共 36 个材质因此记录 shader 缺失 warning；本次全部已引用 2D 贴图都可解析，missing-texture 为 0。没有声称完整还原 Unity 的脸部阴影、眼睛动态效果、描边或物理。

## 实际验证

2026-10-05 使用用户提供的 `SpecialWeek1.zip` 实际跑通整条链路。不是合成 JSON：输入含 228 个 UnityFS bundle，解析 10 个主要 prefab、41 个 Renderer，生成 66 个 `.blend`（10 个完整参照、55 个独立类别、1 个完整身体基底），引用 87 张实际贴图。

验证启动独立于导出的 Blender 进程，在其中逐个重新打开每个文件，并对照实际解析数据检查原索引／坐标、UV、权重、骨骼父链、贴图打包、默认姿势不变形和骨架驱动；另外检查类别分区的面数合计没有丢失或重复。完整参照模型合计 73,285 个三角面。生成了实际角色四套服装的 `preview.png` 并查看；这不等于全部自动分类已逐面人工验收。

```powershell
blender --background --factory-startup --python-exit-code 1 --python verify_exports.py -- '<output>\manifest.json'
blender --background --factory-startup --python-exit-code 1 --python preview_exports.py -- '<output>\manifest.json'
```

上述 66 文件是第一版历史验证；第二版实际使用 `1001_swim.zip` 和 `1003_swim.zip` 重新导出。后者同时包含 1001、1003 及四个共用身体，已覆盖真实多角色输入、不同体型名称和共用泳装贴图绑定。

| 第二版输入 | UnityFS bundle | 主要 prefab 导出任务 | 引用贴图 | 最终 `.blend` |
| --- | ---: | ---: | ---: | ---: |
| `1001_swim.zip` | 245 | 11 | 91 | 57 |
| `1003_swim.zip` | 470 | 23 | 174 | 116 |

包解析和躯干分组来自真实 ZIP；后续头饰修正复用这些真实快照。检查确认修正不改变原几何、骨骼或材质，且原 prefab 坐标下的当前规则与对齐快照的最终分类一致。

`verification.json` 记录所有最终文件逐一重开后的检查结果，并额外检查没有残留旧服装细分类、输出文件名唯一、空类别不输出几何。头部 `80` 参考和共用赤脚泳装的空类别均检查。可生成服饰拆分预览：

```powershell
blender --background --factory-startup --python-exit-code 1 --python preview_segmentation.py -- '<output>\manifest.json' --character 1001 --variant 30
blender --background --factory-startup --python-exit-code 1 --python preview_segmentation.py -- '<output>\manifest.json' --character 1001 --variant 00 --shared-body bdy0004_00_00_1_0_2
```

第二版输出建议使用新的目录，避免混入旧策略留下的文件。验证保证源几何、绑定和分类分区完整性，不等于逐面人工确认语义分类。缺少的身体表面、游戏动画和物理模拟不在此次交付中。


## 0009 露脐装的贴图绑定

通用 0009 的 diffuse/shad_c/base/ctrl 名称在肤色、胸型后还有服装颜色字段，默认使用 00，遵循原仓库 UmaContainerCharacter 的规则。肤色分类参考同样保留该字段，仅替换 skin。decode_skin_inputs.py 可单独从 Copy-All 包提取真实 0004/0009，输出 JSON/PNG，不启动 Unity 或 UI。完整皮肤底模见 ../PDXExporter/README.md。
