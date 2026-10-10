# 通用脸 BS → CK3 头部变体

输入为 FaceTopology 的额头修复版：875 顶点、1,334 三角面、182 个中性身份目标。使用 Blender 4.2 和现有 PDX IO，输出完整、同序的 PDX blend-shape 端点。原始研究工程及已发布躯干包不修改。

`prepare_head.py` 把统一脸的 Head 局部坐标按已验证 UMA 头部的 Head/Neck 骨距转换到厘米，并对齐既有 bn_h_head 关节点。全部目标使用同一个变换。沿用完整的 61 骨逆绑定矩阵；统一权重来自 1001 的共同网络映射，新额头节点插值其源边两端权重。

`export_head_blender.py` 创建可编辑的 Basis + 182 个形态键，并用 PDX IO `as_blendshape=True` 明确导出每个完整目标。875 节点皮肤壳之外，保留 1001 的口腔/眼白附片、眉、发、眼组件作为固定测试附件；这些附件不随身份 BS 改变。全部目标的五个对象、UV、皮肤权重和 61 骨完全一致。Basis 几何为 1003，默认选择 1001。

`build_head_mod.py` 基于最终已交付躯干包生成独立副本。共用模型为 `0001/uma_0001_head_base.mesh`，角色端点为 `1003/uma_1003_head_80.mesh`，NPC 端点为 `0001/uma_0001_head_npc003.mesh`。角色 diffuse 用 `uma_1003_face_80_diffuse.dds`。共享动画保留在 `animation`，既有名字、文件字节、animation/additive_animation 声明排版均不变；shader 保留 `uma_portrait.shader`，皮肤/眉发/眼分别使用 portrait_skin_face、portrait_hair、portrait_eye。全部 TXT 为 UTF-8-BOM，gfx basename 在整个模组内唯一，最终绝对路径小于 256 字符。

新建 `morph_genes` 下的 `gene_uma_face_identity`，声明 `portrait_group = uma`。182 个模板各控制一个新 `uma_bs_face_*` 属性，0→1 对应 Basis→指定身份，实体默认全部为 0；不复用原版脸部基因或 BS 属性。模板显式包含 uma_male/female/boy/girl。四组的 head 均引用新 UMA 头部，18 岁边界不改，male/boy 的 torso 仍为原来的人类躯干。原躯干资产、基因和动作不改。

默认 `uma_ethnicity` / `uma_ethnity` 选 1001；额外注册 `uma_face_1003_ethnicity` 等测试入口，用 `effect set_ethnicity = uma_face_1003_ethnicity` 可切换到相应完整脸型端点。索引在 character-face-bindings.json。测试 ethnicity 仅用于脸型：沿用默认躯干参数、默认 1001 附件和材质，不声称自动还原该角色全部外观。

角色真实 diffuse 按共同 UV 三角对应转移，并单独导出索引。几何 morph 不会自动切换贴图。NPC 原始通用材质无直接 diffuse 绑定，当前明确采用 1001 中性脸贴图作回退，不能称为 NPC 原版纹理。新增中性法线/properties/SSAO 只满足 PDX 槽位，未还原 Unity 全部着色。

## 执行

先运行已有 HeadlessExporter venv 的 Python：

```powershell
python -X utf8 -B prepare_head.py --repo E:/UmaViewer-Workspace/UmaViewer-source --targets E:/repaired/Targets-v1 --research E:/face-research --source-mod E:/final-body-mod --plugin E:/vendor/io_pdx_mesh --output E:/new-face-delivery
blender --background --factory-startup --python-exit-code 1 --python export_head_blender.py -- --repo E:/UmaViewer-Workspace/UmaViewer-source --targets E:/repaired/Targets-v1 --root E:/new-face-delivery --source-mod E:/final-body-mod --plugin E:/vendor/io_pdx_mesh
python -X utf8 -B build_head_mod.py --repo E:/UmaViewer-Workspace/UmaViewer-source --targets E:/repaired/Targets-v1 --root E:/new-face-delivery --source-mod E:/final-body-mod --plugin E:/vendor/io_pdx_mesh --game "D:/steam/steamapps/common/Crusader Kings III/game"
blender --background --factory-startup --python-exit-code 1 --python verify_head_blender.py -- --repo E:/UmaViewer-Workspace/UmaViewer-source --targets E:/repaired/Targets-v1 --root E:/new-face-delivery --plugin E:/vendor/io_pdx_mesh
python -X utf8 -B package_head.py --repo E:/UmaViewer-Workspace/UmaViewer-source --root E:/new-face-delivery
```

Windows PowerShell 含空格路径应使用引号。TEMP/TMP/TMPDIR 和 Blender 本次 APPDATA/LOCALAPPDATA 应先指向 E 盘目录，设置仅作用于当前进程及其子进程。工具依赖本仓库 PDXExporter/NativeBody/BodyVectors 辅助函数，代码包不是包含 Blender/游戏资产的独立运行环境。

prepare 的 `--resume` 仅续用同一次输入已完成的 DDS。export 的 `--reuse-exports` 会逐点和逐连接核对已有端点，不能用存在性代替匹配检查。build 的 `--resume` 只允许同一名 UMA Face Morphs 的生成副本，重建配置与验证；不用来改写用户现有模组。

验收包含全部目标二进制的网络、权重、骨架、坐标核对；所有共用头动画首/中/末帧的实际 t/q/s 数值求值；最终 Blender 重开、全部身份的端点和中间权重、真实待机矩阵对照、所有目标的 PDX IO 回读以及渲染。它们不能替代 CK3 实机验收，也不证明闭眼、张嘴等表情与原始角色完全一致。不同脸型的眼口、耳部、附件贴合仍需继续处理。
