# UMA V10：编辑器注册、服装调色、衣帽位置及高跟鞋测试

资源文本中的文件名均加双引号。`pattern_mask` 使用以 `gfx/` 开头的模组相对路径，例如 `"gfx/models/portraits/uma/0001/shared/uma_0001_tint_mask.dds"`；普通 meshsettings 的 DDS 仍使用带引号的 basename。生成材质和打包时都会执行此规则。

输入为保留的 V9，继续包含 1001 SpecialWeek / 1002 SilenceSuzuka 全部部件及 71 个衣装家族。64 个家族共用同一资产，两人另有 4 / 3 个专属。当前原版参考是本机 CK3 1.20.0.4，Blender 使用迁到 E 盘的 4.2.23，PDX IO 为未修改 v0.91。

## 注册与着色

所有 portrait modifier 拆为 5 个 `usage = game` 默认组和 5 个 `usage = customization` 编辑器组，不再出现 `both`。角色 flag 条件只在 game 默认选择中存在。四个服装编辑器组按原版 `00_custom_clothes.txt` 使用 `add_accessory_modifiers`，覆盖全部 194 个实际 gene/template（含空选项）。独立角色／头发 preset 切换头、眼、眉、发、耳、尾和原色彩／身体模板，不再把头部组件藏在服装头饰选择中。

`modifier_overrides` 仅用于统治者设计器强制无角色条件的默认项；它不是 game 与 custom 的存档映射。Barber 的保存、重载和引擎优先级仍需实机验收，静态闭合不能替代这一步。

服装、头饰、鞋、袜的 `portrait_attachment` 保留通用 effect 名称，启用原版 variation/pattern 数据和四个 editor color override block。新增纹理均为共享 1×1，默认白色调色盘为 16×1。默认没有用户颜色 override 时保留原有彩色 diffuse；选颜色时按原纹理亮度染色，保留明暗细节，避免原彩色底图只能越乘越黑。原材质 Properties、法线和普通光照响应保留。当前每个部件提供整体染色区域，没有擅自给不同织物生成分区花纹。

颈部两个材质槽改为常规 `portrait_skin`，使用从实际身体颈环提取的同一基色 `[255,235,222,255]`、1×1 共用 DDS，并复用身体的 normal/properties。未移动颈部、脸、身体的网格、UV或蒙皮。原身体／BS和四条既有 native loop 保持输入字节；本轮新增高跟测试 loop 单独保存。

Shader 新逻辑仅在 Code 块中；没有在 Effect 尾部新增注释。游戏 shader 编译与实际理发店颜色操作没有在本轮代跑，不能把 Blender PBR／CPU样本当成 CK3 运行成功。

## 两件 hood／帽子的坐标

`bdy0008_08_00` 与 `bdy0008_09_00` 原件顶部约为 161–162.5 cm，旧流程误做 nearest-body fitting／权重转移，压到约143cm，并丢掉真实Head权重。这些是有胸肩下围的hood，不能把整件刚性跟头就当成完整修复。

HatRepair 保留原 source 三角、UV及对应关系。先前的 rigid head 试验留下约8cm衣帽缝隙，已作为否定候选保存；正式方案恢复真实 Head／Chest 语义、正确 inverse bind 和原骨点，并以原来重合的衣帽边界约束下围。基础与六个身体 BS 使用一致顶点网络，装饰 BS 不含 skeleton / skin。帽子没有自己的动画，继承已存在的身体与真实Head参考点。实际验证结果和前／侧图在 HatRepair/SharedBody 及 Reports。

## 高跟鞋测试

新增 `uma_heel_1001_idle.anim` 与私有 `uma_heel_1001_body` skeletal animation set，针对 1001 默认 `bdy1001_00` 的真实粗跟鞋。61帧、30fps、146骨和原父链保持；仅调整body_root高度和左右ankle/ftBall旋转。四处前掌／后跟支点最大离地约0.84mm，球部到脚趾方向保持水平，其余局部姿态和腿链长度保持。

新 body loop 与现有245骨head loop用全部61帧配对检查；同一整体 root 平移通过外部挂接只施加一次，颈桥helper的相对矩阵抵消它，因此不另造重复head动画。

正式版本保留普通裸足loop。`Diagnostics/1001-high-heels` 提供只切换torso entity的对照配置，供穿默认1001高跟鞋时使用；测试后恢复同名正式文件。没有按鞋gene自动切换set的机制，不将此动作称为所有鞋型通用。不要叠加启用两个同名完整模组。

## 动画数据库目录

AnimationCatalog 导出95,910条 `3d/motion/` 主资源命名记录与14,174条补充／音效配套候选，合计110,084条。按body、head_face、ear、tail、camera、position、prop、background和未分类分组；编号来源保留代码enum、数据库motion/event表及正式文本。文件名推断与数据库候选关联明确标为推断，不冒称全部记录已解码为AnimationClip，也不将cross_module空表解释为不存在跨模块动画。

主入口为 `animation_catalog_all.csv`、`module_summary.csv`、Modules 和 MasterTables。TXT／CSV带BOM。正文来源、SQL、范围及独立核对结果随清单附上；原始文件不从海量数据包全量解包。

## 使用、验证与清理

启动器条目为 `UMA V10 Editor Palette Heel Test`，只启用这一版后选择玛蒂尔达：

```text
effect set_ethnicity = uma_ethnicity
effect uma_select_1001_effect = yes
```

切换1002使用 `effect uma_select_1002_effect = yes`。四个服装组分别选择／清空，角色发型另选。四性别／年龄肖像、18岁阈值、原版skin/hair/eye基因key及原调色盘保持。颜色数字最多两位小数。原人类调色盘无法精确覆盖紫瞳／青瞳，这项色差限制沿用V9，不修改原盘。

本轮清理了40项旧UMA产物：C约1.32GiB，E约1.98GiB；当前保留V9/V10、原数据和所需原始中间缓存。当前Blender路径是 `E:\UmaViewer-Workspace\Blender-4.2.23-windows-x64\blender.exe`。迁移逐文件SHA一致且已启动确认；旧桌面工程／旧发行包已删除。Cleanup中仅留约3.53MiB旧源码备份与精确删除记录。

```powershell
& 'E:\UmaViewer-Workspace\UmaViewer-source\Tools\HeadlessExporter\.venv\Scripts\python.exe' -X utf8 -B `
  'E:\UmaViewer-Workspace\UmaViewer-source\Tools\NativeAccessories\v10\run_v10.py' `
  --mode verify --root 'E:\UmaViewer-Exports\2026-10-13-UMA-V10'
```

可加 `--blender 'E:\UmaViewer-Workspace\Blender-4.2.23-windows-x64\blender.exe'` 做实际导入／装配检查。原数据命名／解读继续使用 RawAssets / HeadlessExporter。本修复链读取已有V9和独立修复候选，不宣称从空目录重建全部资产。Reports区分实际PDX、Blender、数值验证与未运行CK3项目；V10能否解决沉默退出、理发店保存和宫廷场景效果均待实机确认。
