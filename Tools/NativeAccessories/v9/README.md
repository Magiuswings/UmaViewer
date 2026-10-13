# UMA V9：头部合并、颜色基因恢复与颈部衔接修复

基于 V8 的 1001 SpecialWeek / 1002 SilenceSuzuka，保留两人的全部部件与 71 个衣装家族（64 个共享，另有 4 / 3 个专属）。原版游戏文件、V7 和 V8 保留。大文件、日志和缓存均在 E 盘。

## 本次改动

- 非 shader 的 `.asset` 资源引用，以及二进制材质中的 DDS 引用，全部使用 basename。目录只作整理；全球文件名仍然唯一。所有 meshsettings 按实际二进制对象和材质槽验证。
- 颜色恢复 `skin_color` / `hair_color` / `eye_color`，不再定义 `uma_*_color`。复制原版颜色基因并加 `portrait_group = uma`，文件为 `000_uma_genes_color.txt`，早于原版 `00_genes_color.txt`；原版定义保持不变。肖像组改为 `000_uma_portrait_types.txt`，早于原版人类定义。调色盘文件和 18 岁阈值不改。
- 所有颜色坐标最多两位小数。颜色预设重新在可以由 0.01 XY 网格表达的原版调色盘位置中取最接近颜色，两个端点重合，保留每人一行。发色、肤色、瞳色的来源和量化误差在 `Reports/palette-presets.json`；不能将原调色盘覆盖不到的颜色说成完全复现。
  1001 紫瞳、1002 青瞳受原版人类调色盘覆盖限制，最近位置的 CIE Lab 色差仍约 32.85 / 29.10；预览可见差异。这里按“不更改调色盘”的要求保留最近值，不将它描述为原画色彩的精确还原。
- 每个角色仅一份 `uma_<ID>_head_00.asset`。基础脸、口部、后颈皮肤和颈桥成为同一个 head mesh 的四个材质槽。腮红、泪水作为同一 asset 中的可选子模型保留，默认不显示；避免将原有不透明泪水误并成永久面部。眼睛、眉毛各留一份；头发、头饰按真实衣装差异保留。
- 原来的 `neck_patch` 是从头发模型中分出的后颈皮肤，`neck_base` 是连接头身的 16 点颈桥，两者均不是服饰。现在没有单独 neck accessory 或 neck asset。
- 1002 的耳朵、头饰外部挂点统一为公共 `bn_h_head`。1002 私有 deform 骨仍保留，因为其真实眼转轴与 1001 相差约 0.27 cm；外部挂点不会再使用私有别名。
- 扣除耳朵后头饰无自身动画。1002 默认头饰原先包含五块真实耳网格，现分为 236 点 / 348 三角的独立耳朵与 319 点 / 397 三角的静态头饰；耳朵接原生循环与 hair color mask。1001 蝴蝶结虽有 Ear 权重但属于饰物，仍保留为静态头饰。

## 颈部修复与验证边界

旧离线检查在 root 挂接以外，还覆写两侧 clavicle 的完整世界矩阵，掩盖了实际只挂 root 时约 2.935 cm 的裂缝。V9 不再依赖额外锁骨挂接，只保留 `bn_sp_thoracic -> head_root`。

头部骨架由 242 增至 245 骨：保留所有原节点与私有 deform 分支，增加三个随实际身体胸椎 / 锁骨运动的 seam helper。头部动画将它们的相对矩阵明确写入。颈桥下方六点改用共同 bind 空间和身体真实权重，上方十点保持原 face / 后颈输入；身体、身体 BS、普通脸、眼、眉、头发坐标没有重做。

使用正式输出的二进制模型与动画，全 61 帧、两角色、00 / 80 的 root-only 数值检查中，颈桥下边界误差小于 0.00006 cm，上边界与头部点吻合。Blender 4.2.23、未修改 IO PDX Mesh v0.91 另运行实际动画导入与完整装配检查，结果在 Reports。Preview 是 Blender PBR 预览，不是 CK3 游戏截图。

`RigRepair/Head245/translation_only` 保留另一种挂接解释的配套 rig、bridge、clip，用于诊断；必须成套使用，不可和默认 full_root 混合。正式 Mod 使用 full_root。

## 统治者设计器沉默退出

没有本轮 error.log 或 crash 证据，用户明确说明为无日志退出。已对比 V7 / V8 定义并清理两项实际差异：删掉没有相应基因的 face 分类，隐藏失去设置的身体形态空模板。原版保留索引使用隐藏、无属性的空模板补齐；这些索引缺口在 V7 已存在，不能将它们认定为 V8 新闪退原因。合并重复选项后，所有选择到 gene/template/accessory/entity/pdxmesh 的注册闭包重新检查。

这些是已完成的文件修复，**没有证明沉默退出的唯一根因，也没有新 CK3 实机通过记录**。`Diagnostics/designer_without_custom_ui` 提供只关闭 UMA 自定义衣装 UI 的对照文件；它不删模型、基因、颜色或运行时附件，可用于把 UI 与模型加载分开复测。只替换同名配置，测试后恢复正式文件，不能同时载入两个同名模组。

## 保留的行为与限制

男女占位头分开，各有一实际三角，保留对应性别的原版空 BS。身体六个真实端点继续用原版 BS key；装饰 BS 无 skeleton / skin，身体 BS 保留骨骼。空 DDS 保持 1×1 共享，有真实细节的贴图不降采样。Shader 名称及代码与 V8 相同，没有新增尾部注释。所有 TXT 为 UTF-8-BOM。

头、身、耳、尾各用私有 `skeletal_animation_set` 与独立 animation 子目录；本轮普通姿态 key 继续统一到每模块同一原生循环。身体 146 骨 / 61 帧、头 245 骨 / 61 帧、耳 169 骨 / 460 帧、尾 9 骨 / 65 帧。当前为统一站立诊断口径，不代表已制作宫廷坐姿或完整表情。高跟鞋与不同鞋型仍需要配套足部姿态；不宣称所有衣装全帧零穿模。

## 使用与复验

游戏包是 `UMA-V9-1001-1002-Mod.zip`，工程包是 `UMA-V9-1001-1002-Project.zip`。工程包还包含四个 packed Blender 4.2 文件、前 / 侧 / 后预览、173 条角色名称映射、源码、修复合同和检查报告。官方英文名为补充映射，不冒称 master 原字段。

启动器只启用 `UMA V9 Head Neck Repair`。选择玛蒂尔达：

```text
effect set_ethnicity = uma_ethnicity
effect uma_select_1001_effect = yes
effect uma_select_1002_effect = yes
```

后两条分别完整切换角色及对应 flag，不需要同时执行。衣服、头饰、鞋、袜分别选择或清空；种族不直接选择 accessory。

```powershell
& 'E:\UmaViewer-Workspace\UmaViewer-source\Tools\HeadlessExporter\.venv\Scripts\python.exe' -X utf8 -B `
  'E:\UmaViewer-Workspace\UmaViewer-source\Tools\NativeAccessories\v9\run_v9.py' `
  --mode verify --root 'E:\UmaViewer-Exports\2026-10-13-UMA-V9'
```

`--blender` 可指定 Blender 4.2 执行 SDK 导入、动态装配、重开和渲染。`--mode package` 要求本轮报告通过且实际模型 / 动画哈希仍一致。此修复链读取 V8 和已有 RigRepair 候选；原数据命名和解读继续走 RawAssets / HeadlessExporter，不宣称从空目录自动生成整个数据库。
