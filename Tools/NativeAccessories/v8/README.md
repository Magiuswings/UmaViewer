# UMA V8：原生模块动画、无骨骼装饰 BS 与共享 DDS

基于 V7 的 1001 SpecialWeek / 1002 SilenceSuzuka 全部部件、71 个衣装家族修复。本版不修改原游戏文件，不修改 V7；大文件、日志和临时目录均放在 E 盘。64 个衣装家族共享一个 asset，1001 / 1002 另有 4 / 3 个专属家族。

## 已完成的文件修复

- mesh 与 asset 的名称同步去掉 `Shape` 后缀，二进制对象统一先写 mesh，再写 skeleton。所有 282 个 meshsettings 的名称和 material index 已按真实二进制检查。
- 1,082 个装饰 BS 目标删除 skeleton 和 skin，保留全部位置、法线、切线、UV、三角和轻量 material 节点。对应 base 保留完整骨骼、蒙皮及参考点。身体 BS 保留 146 骨，与基础身体的 inverse bind 完全相同；没有重写 mesh 坐标。
- 所有自定义 accessory 修改使用 `mode = add`。ethnicity 只保留普通身体基因和三种调色盘基因，不再注册 accessory。角色和衣装选择由 portrait modifiers 完成。
- male/female 占位头分开，各有一个实际三角，分别保留对应性别的原版空 BS 声明。它们使用同一个 242 骨骨架，但没有混用男女 BS 条目。
- 去掉 `uma_head_points`、`uma_head_base` 和旧 additive 动画引用。通过 UMA 自己的 head_root 及三处 joint attachment 衔接头部，1002 使用自身面部核心骨名与点位。身体原版 BS attribute / gene key 保留，其余自定义基因以 `uma_` 开头。
- 保留颈桥的专用 identity inverse bind。其下环是 thoracic 局部坐标，不能机械地改成普通头 root 的 inverse bind；完整附件变换会抵消偏移。`Reports/bridge-root-normalization-rejected.json` 保存了错误方案造成约 4.54 cm 裂缝的实算反证。
- TXT 为 UTF-8-BOM；四个年龄/性别 portrait type、18 岁阈值和原调色盘文件引用不变。Shader 名称、逻辑和文件尾部保持 V7 已确认版本，没有新增 Code 块外注释。

## 原生日常待机的诊断口径

四个模块使用独立私有 `skeletal_animation_set`，reference_skeleton 都指向实际存在的 UMA pdxmesh；所有模块的普通动作 ID 指向各自同一个实际动画文件。

|模块|目录与文件|骨数|帧数|源|
|---|---|---:|---:|---|
|头|animation/head/uma_head_native_idle.anim|242|61|home body 同时采样的 Head/Neck + loop_face 表情定位表|
|身体|animation/body/uma_body_native_idle.anim|146|61|anm_hom_type01_000_001_loop|
|耳|animation/ear/uma_ear_native_idle.anim|169|460|ear_03，八个变体分别使用自己的真实驱动表|
|尾|animation/tail/uma_tail_native_idle.anim|9|65|tail_10|

头和身体没有 Ear/Tail 轨道；耳/头饰保留全部正权骨、祖先链和 Ear 参考点，变体骨名分 namespace，尾骨点保留。没有用正弦或倍率制造动作。Unity 的 `Eye_base_info` 等 shader 参数不能作为骨骼平移，它们已保留为随父骨的静态参考点。`info.j`、骨名、顺序、constant helpers 均与实际模块骨架一致。

这一版把宫廷、事件、前端等普通姿态 ID 也接到同一个站立待机，符合本轮确认的测试口径，**不代表已经制作宫廷坐姿、眨眼或完整情绪动画**。身高 additive 暂不驱动，六个身体形态端点继续使用原版 BS key。头身姿态和脚底校准只改动画，不改基础模型、BS 的坐标或绑定。

## 大小与真实日志证据

400 个纯色 DDS 合并为 9 个 1×1 共享文件，89 个非纯色、整文件字节一致的 DDS 合并为 31 个。实际解码的 RGB、Alpha、mip 层均已核对；有细节的纹理没有降采样。全部 DDS 从 573 个 / 293,116,560 bytes 降为 124 个 / 101,203,600 bytes，净省 191,912,960 bytes（183.02 MiB）。装饰 BS 精简另节省约 92.64 MiB，精确字节见 `Reports/accessory-bs-size-savings.json`。

共享 DDS 在 `0001/shared`，basename 全局唯一。asset 使用游戏根相对路径，二进制 material 使用 mesh 文件相对路径，未修改的 PDX 插件也可找到共享纹理。旧 DDS 只在全部真实引用和哈希验证后从 V8 列表内删除，V7 原文件保留。

用户 error.log 的 191 条材质失败和 191 条 out-of-sync 是同一批对象的两种诊断。去掉重复的文件/shape 后：187 个 skeleton-first 对象全报错，83 个 mesh-first 对象未报这两类错；两组 raw 名称都能与 meshsettings 匹配。对象顺序是本次样本的完整分界，尚未进行只改变这一项的 CK3 引擎 A/B，不能把相关性说成已证明的唯一原因。CSV 和完整证据见 `Reports/error-log-asset-comparison.*`。

## 测试与使用

`Reports/final-static-validation.json` 覆盖全部 1,354 个 mesh、1,388 条 BS 引用、状态到动画 ID 的完整闭合、全部材质路径、编码、父链、权重和顶点网络。`Reports/blender-sdk-native-validation.json` 记录 Blender 4.2.23 + 未修改 IO PDX Mesh 的四模块真实导入；`Reports/blender-native-assembly.json` 记录两角色 00 / 80 的真实约束、蒙皮和工程重开。Editable 内有四个 packed `.blend`，含身体和默认衣装的六个真实 Shape Key。

Preview 为最终模型的 Blender PBR 预览，不是 CK3 宫廷 shader 的运行截图。姿态、脚跟/脚尖和颈桥量化证据在 Reports / MotionSources；本版未声称新 CK3 游戏运行已通过。新工程保留低面数、原 UV 与原权重造成的局部棱角，不将数值不爆炸宣称为全衣装全帧零穿模。

裸足待机已按实际跟部/前掌校准，原鞋底曲面保留。带高跟的鞋仍需要配套足部姿态：当前统一裸足待机测试中，部分鞋底接地角度不完全匹配，不将它宣称为所有鞋型均已适配。这一版没有为不同鞋型增加独立身体动画或脚部 additive。

只启用 `UMA V8 Native Modules`，选择玛蒂尔达，默认 1001：

```text
effect set_ethnicity = uma_ethnicity
```

完整切换角色（同时设置用于默认头、衣装选择的角色 flag）：

```text
effect uma_select_1001_effect = yes
effect uma_select_1002_effect = yes
```

衣服、头饰、鞋、袜分别在四个 customization 组中选择或清空。颜色/身体 preset 是普通基因，不能靠 ethnicity 选择 accessory。不要与旧 UMA 测试包同时启用，同名 UMA gfx 定义会覆盖。

## 复验与工程

游戏包为 `UMA-V8-1001-1002-Mod.zip`；Project 包同时包含最终模组、四个可编辑工程、173 条角色映射、源码和诊断证据。官方英文标识为补充映射，来源在 Database 中，不冒称 master 的原始英文字段。

```powershell
& 'E:\UmaViewer-Workspace\UmaViewer-source\Tools\HeadlessExporter\.venv\Scripts\python.exe' -X utf8 -B `
  'E:\UmaViewer-Workspace\UmaViewer-source\Tools\NativeAccessories\v8\run_v8.py' `
  --mode verify --root 'E:\UmaViewer-Exports\2026-10-12-UMA-V8'
```

加 `--blender` 指向 Blender 4.2 可重新执行实际 SDK 和装配检查；`--mode package` 只接受通过的报告且四模块文件哈希须仍与已验证结果一致。不能用 Blender 5.3。SDK/plugin 与 Python 依赖不打入源码 Fork；原数据解读继续使用仓库既有 RawAssets / HeadlessExporter，当前 V8 修复脚本接收已有 V7 及已取样的原生资源，不伪称从空目录自动重建全量游戏资产。
