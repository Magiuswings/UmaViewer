## V9：头部合并与 root-only 颈部修复

最新修复工作流见 [v9/README.md](v9/README.md)。非 shader 资源引用统一 basename，恢复原版颜色 key 与前置载入文件，头部按角色合并，1002 默认耳朵与静态头饰分离。245 骨头部使用三个真实身体驱动的颈部参考点，只保留 root 挂接；全 61 帧数值检查和四套 Blender 4.2 装配、重开通过。设计器注册与定义已清理，沉默退出的实机根因仍未确认；对照资料独立保存，不自动启用。

## V8：原生动画与资源精简

最新的 1001 / 1002 修复工作流在 [v8/README.md](v8/README.md)。四模块使用真正的 UMA 待机和精确骨骼表；装饰 BS 去骨骼与蒙皮，纯色 DDS 统一 1×1 共享，并修复注册、accessory add、ethnicity、头根和 foot rest 的问题。新版保留网格及身体 BS 的绑定，只在动画中校准站姿。验证报告区分完整静态检查、Blender PDX 实际回读与尚未重跑的 CK3 实机。V7 是保留的历史输入。

> V7 已扩展为 1001 / 1002 全量衣装及独立鞋袜，取消固定 clothed，男女空头分开。最新实现、输入契约和验证限制见 [v7/README.md](v7/README.md)。本文件继续保留 V6 基线说明。

# 1001 native accessory workflow

基于用户提供的 `uma_v5.zip`，本轮只处理 1001 SpecialWeek。可见头部使用原始 `pfb_chr1001_80` 无头饰基准头，保持原始顶点网络和 UV，不再使用统一脸型或身份 BS。普通衣装使用真实 `pfb_bdy1001_00`。这是有明确输入边界的 1001 命令行工作流，不代表已经完成所有角色。

输出使用 Blender 4.2.23 LTS 和 IO PDX Mesh v0.91；游戏参考来自本机 CK3 1.20.0.4。最终结构为通用 `0001`、角色 `1001`、共用 `animation` 和其独立 `ear` / `tail` 子目录。TXT 为 UTF-8-BOM；gfx basename 全局唯一；最终资产路径最大 162 字符。

## 已实现

脸 1292 顶点/1854 三角，原始口部描线 44/40，眼 46/48，眉 62/52，去耳后的发 1846/2108，原生耳 335/440，尾 281/388。衣服主件 6397/6440，鞋袜与腿饰 1929/2296。九个独立 accessory；衣服与鞋袜共享同一 atlas，服装不再硬拆上衣和裙子。

所有可见头部文件放在 1001。占位头放在 0001，61 个 UMA 布局骨点、3 顶点、1 有效三角面、标准 PDX aabb；透明小面位于头内部。复制原版 female head 的 129 个 BS 声明及其属性，指向同拓扑的空目标；不建立原版面部 BS 基因。当前 mod 删除全部 `gene_uma_face_identity` 及身份 BS 的调用。

头部原点以原始 Head 世界点为准：顶点和原生耳骨共同减去 `(0,.05520761758,.00401945878)`，再换轴/单位并挂到同一头骨，消除重复原点偏移。源眉眼点对 carrier 对应点距离小于 0.74 mm。原版头动画保留在共用目录，未改动其根轨道；CK3 的三处 `joint_attachment` 对齐 root 和两侧 clavicle。Blender 完整预览用三处骨世界约束替换头动画的身体高度位移，避免叠加两次。

皮肤旧差异来自 effect 和 SSAO：v5 body 使用平涂 `MOE_TOON`、不接受阴影，face 使用另一套光照。现在两者均使用连续表面光照、相同皮肤响应/补光/SSAO，face effect 不接受原版 complexion texture override。原 Unity body 没有 normal texture；保留真实顶点法线，用中性 CK3 packed normal，不把 ctrl/base/toon 当法线。CK3 G/A 解码法线，hair 的 B 单独作为 hair color mask；skin/eye 使用 diffuse alpha。hair mask 是适配策略，保护白色额前发束。眉使用原坐标的后置 alpha pass、关闭 depth test/write；实际排序仍需游戏确认。shader 文件仍叫 `uma_portrait.shader`。

耳保留 15 骨原生链，独立 entity 挂 `bn_h_head`；尾保留 8 骨，独立挂 `body_root`。两者不共享 head/torso pose，从真实 Unity AnimationClip / ear driven-key 目标表导出六个动作，没有生成摆动或放大幅度。耳幅度约 60/64/88°，尾约 88/100/100°；用于 idle_entry、idle、frontEnd_middle_entry，另覆盖原状态名以便观察。耳 idle 和尾 idle 的源首尾连续，Blender 工程同样提供循环。

衣服与鞋袜共享 v5 body 的精确 134 骨、顺序、父链和 inverse bind。裙摆以连续空间权重分配到 root/thigh，六个端点使用原版 breast_shape_1..4、gaunt、fat 属性，与身体同基因输入。`bs_body_clothed` 仅覆盖区径向收缩，Basis 和原六个形态端点保持不变；1645 个裸露/保护顶点完全不动，覆盖 1865 点，最大收缩 2.58 cm，无新增翻面。原 `gene_bs_body_type` 的四个女性 clothed 模板启用强度 1，不创建脸型身份基因。

## 真实验证及限制

PDX IO 导出/回读、头部四类动画首中末 60 个组件样本、耳尾六个真实动作的首/峰/末重建、body/衣服/鞋袜的原版 idle 和 throne 首中末帧、三个 joint_attachment 世界矩阵，以及最终 `.blend` 保存、贴图打包、重开均已检查。两个服装分区与完整衣装七个姿态的 LBS 差为精确 0 cm。1,046 处引用解析通过。

膝袜误删面和鞋前露趾已修正，裙摆最大 edge stretch 从约12.1降至2.662。仍有真实相交：clothed 后 neutral 为165个服装三角，宫廷中帧359个，含交叉双臂/手接触、裙腰附着物和少量鞋袜表面。不能称为零穿模。所有图片为 Blender 的原动画预览，未运行 CK3 场景 shader，不能替代宫廷黑脸、眉毛 late pass、游戏 animation dispatch 或椅子接触的实机确认。

## 输入与 CLI

先通过既有 `Tools/RawAssets` / `Tools/HeadlessExporter` 获取命名资源和解析快照。当前构建需要 `ROOT/v5`（提供的 mod）、`parsed/head.json`、`tail.json`、`body.json` 与资源贴图、`native-motion-frames.npz`、`native-motion-index.json`、正确的耳目标表。原始大数据库留在 E 盘。`gather_v6.py` 只选1001真 prefab，排除 bust/cloth physics prefab；实质耳动作排除空占位。

服装还需要已经重建的 `canonical-rest-v3`：native-bone-transforms.json、rest-pose-fitting.json、fitted-body-profiles.npz、source-skin-profiles.npz、pdx-vertex-order.json。这是外部身体重建输入，不由本轮衣装链凭空生成。普通 Python 使用 HeadlessExporter venv（numpy/scipy/Pillow/UnityPy）；Blender 脚本只能在 4.2 运行。插件和 Blender 运行时不随代码包分发。

```powershell
& 'E:\UmaViewer-Workspace\UmaViewer-source\Tools\HeadlessExporter\.venv\Scripts\python.exe' -X utf8 -B `
  'E:\UmaViewer-Workspace\UmaViewer-source\Tools\NativeAccessories\run_native_accessories.py' `
  --mode verify --root 'E:\UmaViewer-Exports\2026-10-11-UMA-V6-1001' `
  --repo 'E:\UmaViewer-Workspace\UmaViewer-source' `
  --plugin 'E:\UmaViewer-Workspace\PDX-vendor\io_pdx_mesh' `
  --game 'D:\steam\steamapps\common\Crusader Kings III\game' `
  --blender 'C:\Users\33775\Desktop\网页制作\ck3-uma-body\vendor\blender-4.2.23-windows-x64\blender.exe'
```

模式 head 构建头/耳/尾；clothing 按完整衣装顺序构建并整合主衣/鞋袜；all 在已有命名/采样快照上完成两者及验证；verify 重做最终读取/动画/渲染/重开；package 在已有成功验证上打包。路径参数通过 UMA_V6_ROOT/REPO/PLUGIN/GAME/CANONICAL 传给快照脚本；原始命名资源缓存阶段的路径仍须按实际位置配置。

服装内部顺序是 prepare → skin_reference → source_render → refine → build → update_pdx → finish_blend → body_clothed → normal_audit → audit → audit_clothed → finalize → broad_split。refine 每轮只执行一次；重跑需要先 prepare。update_pdx 用同轮 build 的 mesh 作为模板，vertex order 是本轮生成。最终整合读取 split-delivery.json，原 fullkit 为内部对照。

## 游戏核对

本机启动器条目为 UMA V6 1001 Native Accessories。只启用此 UMA 测试版后，选择玛蒂尔达，执行 `effect set_ethnicity = uma_ethnicity`。分别观察捏人、事件肖像和宫廷；改变 skin/hair palette，观察脸身与头发/眉/尾，等待真实耳尾 idle；重点检查面部黑色、眉毛遮挡、坐姿衣摆/袜鞋。这一步目前没有实机结果。
