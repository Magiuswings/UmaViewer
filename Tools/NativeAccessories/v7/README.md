# UMA V7：1001 / 1002 完整部件与衣装

这一版处理本地数据库中 1001 SpecialWeek、1002 SilenceSuzuka 的实际可用素材。共 71 个衣装家族：64 个共享，1001 专属 4 个，1002 专属 3 个。共享家族只注册一个 asset；两人的赛车袜纹分别使用真实 03 / 06 图集，在同一 asset 内切换材质与 entity，不复制基础网格。71 套可编辑 Blender 工程随 Project 包交付。

角色表有 173 条。`chara_data` 没有英文名字段；167 条英文名称按 https://umamusume.jp/character/ 的日文显示名匹配，另外 6 条使用 UmaViewer `Assets/Scripts/localfy/LocalizeEn.cs` 后备名称，逐条标注 `name_source`、`official_source_match`、`identifier_is_database_field=false`。PascalCase 标识是补充映射，不冒称数据库原字段。2008 的 ST2 等内部占位名没有编造官方名称。

## 改动

- male/female 两种透明占位头各 199 骨、3 点、1 个有效三角；复制相应性别的原版 129 个 BS 条目，指向相应的空目标。male/boy、female/girl 分别调用正确载体，18 岁阈值保持原样。male/boy 仍用原来的原版 torso，本轮实测角色范围为两名女性角色。
- 可见脸、眼、眉、发、耳、头饰及尾均是角色文件夹内的独立对象；不使用 `gene_uma_face_identity`。真实眉眼支点按角色校准；`uma_head_points` 只控制骨点平移，1002 使用原始支点布局，min=0 / max=1。
- 通用裸体和全部身体 BS 使用原核心 134 骨，加回 12 个无原版对应的参考点，共 146 骨。主体网格 3510 点 / 5472 三角及原 BS 网络、权重保持不变；不再固定启用 `bs_body_clothed`，它指向 no-op，脱衣得到完整基础身体。
- 所有衣装保留实际源骨点与原始源权重记录，运行权重映射到原版核心；六个端点复用 `bs_body_breast_shape_1..4`、`bs_body_gaunt_1`、`bs_body_fat_1`，每个部件的顶点、UV、三角和权重关系一致。衣服、头饰、鞋、袜是四个独立 customization 组，均有空选项。
- 头颈 joint 衔接用 `head_root=-d`、静态 `uma_head_base=+d`，d=(0,4.540153,-0.001887) cm。原身体和原脸表面之间实际另有 2.3–3.0 cm 缺口，新增每人 16 点 / 16 三角的低密度颈部连接，使用独立 inverse bind 同时跟随身体下环和头部上环，未挪动主体脸/身体。
- 7 个有证据的后颈皮肤块从 hair/headwear 分离为 `neck_patch`，使用 `portrait_skin_face`。1001_30 原本是深色覆盖，明确 absent，保留原覆盖。所有源 hair/ear/headwear/neck_patch 三角互斥、完整。
- 皮肤使用 skin=1 的真实 diffuse 面积加权统计 RGB=(254.838,229.753,202.112) 选择原版调色盘最近点。脸、身体先在线性 RGB 去除烘入基色，避免 unchanged shader 的 Diffuse*Palette 二次上色；保留原 DDS 与精确 BC3 Alpha 块。耳、发、眉、尾接受 hair color，白色前发束受保护。
- 原 skin/hair/eye 方形调色盘和 shader 逻辑保持原样；shader Code 块外的注释全部去除。头部动画放共用 animation，ear/tail 分目录。身体继续相对引用原版女性动画。SSAO 第 3 纹理槽沿用已验证版本。
- 非原版身体 BS 基因使用 `uma_` 名字，custom key/value 不含 accessory；引擎语法 `accessory_genes`/`accessory` 仍按原版使用。TXT 为 UTF-8-BOM，gfx basename 全局唯一，文件名无哈希串。

## 验证与实际限制

所有最终资产经过严格路径/命名/编码/父链/权重/BS 顶点网络检查。头部与耳尾实际经过未改动的 IO PDX Mesh v0.91、Blender 4.2.23 回读；两人的两种载体及 00/80 共 8 个装配 case 经过真实待机、宫廷、耳尾动作检查。颈部连接在所有 idle/court 帧中纯数值误差 <0.000005 cm，实际 Blender 误差 <0.00035 cm；保存和重开后的对象约束也检查过。只使用 `*_neck_repaired_assembly.blend` / `uma_v7_dual_actor_neck_repaired.blend`，旧 snapshot 标为 superseded，不随交付包附带。

1002_00 的前裙改为依据 native MSkirt 裁片的 D 权重，并对 424 点做局部腿/袜间隙补偿，最大 0.8 cm。七端点同改动，0 翻面；实际坐姿裙与裸腿相交从 58 降到 34，裙与袜从 152 降到 58。数字包括贴合和内部接触，最终归属图仍有一个很小的侧面袜面三角接触。手触衣服没有强行推开，不能声称所有衣装、所有帧均零穿模。4 类代表衣装有裸体坐姿实际图，其余全量已做 structural / stock LBS 检查，71 editable 工程已保存。

Blender PBR 彩色图显示颈部开口已闭合，低密度环的角度/阴影仍可见细边与角棱；1002 鼻嘴有原始低面数带来的棱状阴影。它不是 CK3 宫廷 shader 的实机结果。动画和宫廷 shader 沿用用户已确认的上一版；本轮新组合尚未在 CK3 引擎中重测，不把静态验证当游戏通过。

原版 eye palette 无法精确提供 1001 紫瞳，最近可用颜色为蓝色，deltaE76≈32.85；hair 的最近色也有误差。目标、palette RGB、XY、误差、源哈希都在 `Reports/palette-presets.json`，没有为了还原瞳色改动原版色盘。

## 文件与运行

`UMA-V7-1001-1002-Mod.zip` 是游戏包，`UMA-V7-1001-1002-Project.zip` 是模型、71 衣装工程、源码、角色表和诊断证据包。源码不包含游戏资源、Blender、PDX 插件或解密后的大数据。

`gfx/models/portraits/uma/0001` 放通用躯干、两个占位头和共享衣装；1001/1002 放专属部件与衣装。文件例：`uma_1001_face_00.mesh`、`uma_0001_clothes_0004_00_00_base.mesh`。四组 customization 为 `uma_custom_clothes`、`uma_custom_headwear`、`uma_custom_shoes`、`uma_custom_socks`。同一头饰 prefab 会同时切换匹配的发型、耳、脸部组件，避免在新头饰下叠加旧 80 发型。

只启用 UMA V7 这一版后选择玛蒂尔达，分别测试：

```text
effect set_ethnicity = uma_ethnicity
effect set_ethnicity = uma_1002_ethnicity
```

两人的肤色/发色/瞳色各只有一行精确 XY 矩形，写在同一个 `common/ethnicities/uma_ethnicity.txt` 文件。Body 与鞋袜可独立清空；事件、宫廷、捏人均需确认，不与旧 UMA 测试版同时启用。

命令行整合与静态复验：

```powershell
& 'E:\UmaViewer-Workspace\UmaViewer-source\Tools\HeadlessExporter\.venv\Scripts\python.exe' -X utf8 -B `
  'E:\UmaViewer-Workspace\UmaViewer-source\Tools\NativeAccessories\v7\run_v7.py' `
  --mode verify --root 'E:\UmaViewer-Exports\2026-10-11-UMA-V7' `
  --repo 'E:\UmaViewer-Workspace\UmaViewer-source' `
  --game 'D:\steam\steamapps\common\Crusader Kings III\game' `
  --plugin 'E:\UmaViewer-Workspace\PDX-vendor\io_pdx_mesh'
```

`register` 用已导出的 HeadSources、ClothingParts、Rigs 与先前 V6/canonical 输入重新生成注册和材质；`verify` 运行身体数值检查与完整资产检查；`package` 要求最新验证已成功；`all` 顺序执行三者。显式路径用 UMA_V7_ROOT/REPO/GAME/PLUGIN、UMA_V6_INPUT、UMA_V7_CANONICAL、UMA_V7_SKIN_COLORS 环境变量传给快照脚本。运行时数学库线程限制为 1，TEMP 与运行目录在输出盘。

原数据仍通过既有 `Tools/RawAssets` 与 `Tools/HeadlessExporter` 的命名、依赖闭包和 UnityPy 解析链读取。角色表和本轮 inventory 只读取对应表及 1001/1002 素材，不重新扫描所有角色差分身体。模型重建还需要 canonical-rest-v3 的 native-bone-transforms、fitted-body-profiles、source-skin-profiles、pdx-vertex-order；不把 registry 整合器冒充从空目录一键重建完整游戏资产。
