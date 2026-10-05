# 无 UI 的 UmaViewer 已命名资产批量导出器

直接读取 UmaViewer `Loaded Assets -> Copy all` 导出的 **ZIP 或目录**，用 Python/UnityPy 解析网格、材质、贴图、Transform、骨骼和绑定矩阵，再调用后台 Blender 保存 `.blend`。无需 Unity Editor 或 UmaViewer UI。

第一步的原始文件名映射、资源密钥解密和游戏数据库查询没有实现；输入必须已经是带有意义路径的 UnityFS 数据包。`.zip` 直接在内存读取，不执行包内脚本，也不把包中的文件解压到任意位置。

## 安装和运行

需要 Python 3.10+（本机验证 3.12.14）和 Blender 4.2+（本次真实资产验证 5.2.1）。此目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.cmd 'C:\Users\33775\Downloads\SpecialWeek1.zip' --output 'D:\UmaExports\SpecialWeek1' --name 1001=SpecialWeek --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

也可用 `.venv/Scripts/python.exe export_assets.py ...`；省略 `--blender` 时，只导出真实解析的中间 JSON/PNG，随后运行：

```powershell
blender --background --factory-startup --python-exit-code 1 --python headless_blender.py -- '<output>\manifest.json'
```

ZIP 与目录使用相同解析逻辑。一次处理输入包内找到的所有普通角色头／身体／尾 prefab；`--character 1001` 可限制角色。可重复提供 `--name ID=NAME`；没有名字时使用可靠的源角色 ID。共用尾通过专用 diffuse 纹理中的角色 ID 关联；无法明确归属的共用模型标记为 `shared`，不凭空指定角色。

`--output` 不能位于输入目录里面。同一输入可以在相同输出目录重新生成该程序命名的结果；不同输入包应使用不同输出目录。

## 输出和命名

`blends/chara1001/` 中的文件包含角色 ID、可选名字、源身体或头部 ID、服装变体及内容，例如：

```text
chara1001__SpecialWeek__head_chr1001_00__face.blend
chara1001__SpecialWeek__head_chr1001_00__eyes.blend
chara1001__SpecialWeek__head_chr1001_00__eyebrows.blend
chara1001__SpecialWeek__head_chr1001_00__hair.blend
chara1001__SpecialWeek__body_bdy1001_00__body_skin.blend
chara1001__SpecialWeek__body_bdy1001_00__skirt.blend
chara1001__SpecialWeek__body_bdy1001_00__shoes.blend
chara1001__SpecialWeek__body_bdy1001_00__socks_or_legwear.blend
chara1001__SpecialWeek__body_bdy1001_30__body_base.blend
chara1001__SpecialWeek__tail_tail0001_00__tail.blend
```

还会保留每个源 prefab 的 `__source_reference.blend`，包含未按人体／服装类别删减的整体几何。所有部件文件自带可编辑骨架、权重、UV、法线和打包贴图，可独立打开。

`manifest.json` 记录输入 SHA256、每个包文件 SHA256、角色／变体／来源、自动分类方法、面数、贴图与错误。`snapshots/` 保留原顶点与按类别拆分的索引；`.blend` 对象保留来源 PathID 和原顶点索引属性 `uma_source_vertex`，便于回查。用户输入 ZIP 不被修改。

## 身体和衣服的分离

头／脸、眼、眉、发、尾依据原 Renderer 和材质分区识别。附加泪、腮红等归 `face_effects`，保留原活动状态。

**源躯干通常不是独立的皮肤和服装网格。** 本次 SpecialWeek 包的 `M_Body` 把皮肤、外衣、鞋袜和饰品放进一张图集。默认 `--skin-mode auto` 使用该角色脸部 diffuse 的主要肤色作为参照，在三角形顶点、边中点和中心共 7 个 UV 位置采样；至少 5 个位置匹配肤色的面归 `body_skin`。其余面按源骨骼名称及权重推断裙子、上衣、披肩、鞋、袜／腿部衣物、手套和饰品，其余归 `clothing`。

**皮肤和细分服装名称是启发式结果，需要复核。** 浅肤色布料、局部彩绘、跨肤色边界和特殊部件可能被误分；`socks_or_legwear` 不保证全部都是袜子。可调 `--skin-tolerance 42`，或用 `--skin-mode none` 禁用肤色拆分，保留 `body_clothing_mixed`。无论分类如何，所有类别的面合计必须与参照模型一致。

`--body-base-variant auto` 默认把现有躯干中“皮肤三角面比例最高”的完整服装模型另存为 `__body_base.blend`。这是候选选择，不是自动识别泳装的保证。SpecialWeek 实际选择变体 **30**，预览呈泳装。可以用 `--body-base-variant 30` 明确指定，或 `none` 禁用。底模保留选定服装的全部几何，不补全服装下面缺失的身体。

`clothes/pfb_*_cloth*` 在本次包中主要是 Unity 布料／物理配置；实际服装几何来自身体 prefab 的 `M_Body`。此程序没有把这些物理配置误当作额外衣服网格，也没有重建布料模拟。

## 坐标、骨架和材质

网格使用源 bind pose，骨骼位置由 Renderer transform 与逆绑定矩阵求得，保留父链、原骨骼 ID 及四影响源权重。遇到额外的 variable-count 权重格式会报错，避免悄悄截断。

参照 UmaViewer `MergeBone` 的接点，头部用 `Neck`、尾部用 `Hip` 对齐同角色现有躯干：优先同服装变体，缺少时回退 `00` 或另一已有变体，并记录 attachment 矩阵。每个部件保持独立骨架，不强制合并或重定向到其他角色骨架。`--native-coordinates` 保留原 prefab 原点。

UnityFS body 网格的重复背面索引 pass 会去重，Blender 材质保持双面；源索引统计与去重数量写在 audits 中。**没有删掉真实不同的部件面**，程序用索引三元组识别重复 pass。

材质输出复用本 Fork 的 Blender 节点转换器。保存全部原始材质参数和已引用的 2D 贴图，重建 EEVEE 卡通／Cycles 着色。SpecialWeek 包没有包含 Unity shader 依赖，共 36 个材质因此记录 shader 缺失 warning；本次全部已引用 2D 贴图都可解析，missing-texture 为 0。没有声称完整还原 Unity 的脸部阴影、眼睛动态效果、描边或物理。

## 实际验证

2026-10-05 使用用户提供的 `SpecialWeek1.zip` 实际跑通整条链路。不是合成 JSON：输入含 228 个 UnityFS bundle，解析 10 个主要 prefab、41 个 Renderer，生成 66 个 `.blend`（10 个完整参照、55 个独立类别、1 个完整身体基底），引用 87 张实际贴图。

每个文件均在新的 Blender 进程里逐个重新打开，并对照实际解析数据检查原索引／坐标、UV、权重、骨骼父链、贴图打包、默认姿势不变形和骨架驱动；另外检查类别分区的面数合计没有丢失或重复。完整参照模型合计 73,285 个三角面。生成了实际角色四套服装的 `preview.png` 并查看；这不等于全部自动分类已逐面人工验收。

```powershell
blender --background --factory-startup --python-exit-code 1 --python verify_exports.py -- '<output>\manifest.json'
blender --background --factory-startup --python-exit-code 1 --python preview_exports.py -- '<output>\manifest.json'
```

`verification.json` 是实际检查结果。多角色大包的通用逻辑已实现，但本次输入只包含角色 1001，尚未用另一真实多角色包验证。缺少的身体表面、游戏动画和物理模拟不在此次交付中。
