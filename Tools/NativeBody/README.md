# 通用躯干重建、A 姿势固化与原版动画绑定

当前入口为 `rebuild_body_rest_blender.py`。旧版的包裹区细分、只改绑定方向、待机法线补偿均已被游戏截图否定，不能再作为最终生成流程。2026-10-09 用户明确授权基础网格和所有 BS 做姿势、尺寸、位置适配；此前“不移动 mesh”的条件不再适用于本流程。

只读取已解码的 bdy00 通用 0004 和 0009 两个子型的 84 份源快照，不扫描所有角色差分。保留原始 0004 的 3,510 顶点、5,472 三角面和 UV 顶点编号；先跨 UV 分裂点建立几何焊接关系，用 0009 实际皮肤作共同重心映射，再平滑整个衣物包裹区域及过渡区，去除原来肩带、裤口的表面高频轮廓。没有细分或新增高密度补片；未提供皮肤的区域仍以平滑后的 0004 表面作代理，不声称恢复了隐藏真实解剖。

之后在原生 69 骨 UMA 坐标和语义关节上构建固定变换，把 T 姿势、腿脚角度、关节长度和颈部高度适配到本机女性躯干基础模型。所有 28 组几何同步固化同一组线性变换和脚底接地校正，再创建原版 134 骨骨架、合并语义权重并使用原版准确的逆绑定矩阵。顺序不能反过来。保留原始 T 姿势和重建 T 姿势作为隐藏参考集合；可编辑成品打开时播放实际原版 idle。

使用 Blender 4.2、PDX IO。必要参数为 `--repo --plugin --config --stock --textures --output`，其中 config 是已完成真实皮肤分类的通用源索引，stock 是安装中的 female_body.mesh，textures 是包含可读 uma_0001_body_* DDS 的目录。输出目录必须不存在，源目录不可覆盖。

颈部姿势压缩会把源模型的颈骨/胸骨权重梯度也压缩。最终绑定阶段对颈部 95 个顶点按原版表面重心重取样权重，避免祈祷、转头时细颈边出现约 14 倍拉长；相同权重用于全部差分。

导出后可用 `seal_canonical_blend.py --repo ... --root ... --textures ...` 设置默认正交全身视图和隐藏骨骼覆盖，并按照本机原版 UnpackRRxGNormal 和 PDX IO 节点为 Blender 预览解码法线的 Green/Alpha 通道。只调整预览和材料节点，断言基础几何、形态键、UV 和对象变换均保持不变。

`verify_canonical_rest_blender.py` 使用 `--repo --plugin --root --stock` 独立重开成品，检验 28 组源组合、9 个基础/差分端点的 PDX 往返、81 个实际动画和 BS 求值样本，以及原版 188 条动画声明的全部帧和相对边长变化。PDX IO 的顶点排序是按遍历到的三角面局部排序，必须使用 `pdx-vertex-order.json`，不能把导出顺序当成源顶点编号。逐帧数值和 Blender 渲染仍不等于 CK3 实机验收。

`render_canonical_rest_blender.py` 输出相同相机/光照的源模型、重建皮肤、A 姿势、原版模型和实际动画对照。皮肤近景禁用 diffuse，仅检查几何与跨 UV 接缝的平滑法线。

源工程保持不变。最终body资产以本机当前female_body.asset为依据，只改实体/网格名称、模型与纹理引用、材质和BS文件引用；普通动画、additive_animation、common_body导入、状态和附加动画默认值的解析内容必须与原版一致。模组不复制或改写任何原版body动画，也不把body动作替换为静态rest动画。

|接口|用途|
|---|---|
|gene_height / body_height|原版身高附加动画，保留head_body_height同步与原版年龄曲线|
|gene_bs_body_shape / body_body_shape_*|原版体型附加动画|
|gene_bs_body_type / bs_body_gaunt_1、bs_body_fat_1|分别接入通用shape1较窄、shape2较宽端点；不代表拓扑不同的setting03肥胖衣装|
|gene_bs_bust / bs_body_breast_shape_1…4|精确对应源bust0、1、3、4；bust2为Basis|

胸型采用分类端点，避免把源中间胸型强行拟合为size_min/max的一维插值。gene_bs_bust保留原版模板名称和index：bust_default为Basis，四个bust_shape_*_full选择真实端点，half模板为对应端点的半值。原版size相关BS仍声明，但指向中性网格；新基因没有任何设置引用这些占位BS属性。

原版所有26个body BS声明和实体属性保留。其中未实现的BS统一指向与本版Basis一致的零位移模型，不能误指向旧版中性网格。基因文件声明portrait_group=uma，使用原版gene_height、gene_bs_body_type、gene_bs_body_shape、gene_bs_bust。每个模板显式补齐uma_male、uma_female、uma_boy、uma_girl；肖像组原版18岁阈值保留。原版缺失的头部BS、肌肉、怀孕、婴儿、缩衣等属性不留在新基因设置中。此文件的女性BS上限标准化为1.0，确保完整端点可选到；身高范围宏和原版年龄曲线不改。独立验证会实际求值173条角色记录的模板与强度，不能只检查基因名称存在。

游戏中的身高使用原版additive_animation。源height0/2仍可在Blender用HeightSource_0/2编辑或对照，模组不同时叠加另一套height BS。它们描述的源形态不能认作与原版身高曲线定量相同；角色scale元数据仍不自动施加。

最终文件放在gfx/models/portraits/uma/四位角色ID，最终通用底模存于0001，角色头部存于角色ID。名称例如uma_0001_body_base.mesh、uma_0001_body_b0.mesh、uma_0001_body_skin1_diffuse.dds、uma_1001_head_base.mesh。头部动作统一放在animation目录，使用uma_female_head_idle_1.anim等可读名称。shader保留通用uma_portrait.shader。四位ID、元素、差分和类型组成名称，不使用十六进制尾码。对整个gfx检查大小写不敏感的basename唯一性，不能用不同目录掩盖同名冲突。全部生成TXT用UTF-8-BOM。character-body-bindings.json提供173条数据库记录到共享body参数、肤色和原版基因模板的索引，不自动分配游戏人物的DNA。

## 旧版发布步骤（已弃用，保留作故障重现）

以下描述只记录已被实机否定的法线补偿版本，不能用于当前发布：先运行 correct_posed_skin_normals.py，再把法线修复目录传给 rebuild_readable_assets.py，最后 update_shared_body_blend.py。它没有改掉 T 姿势和细分泳装轮廓，因此即使文件检查通过，也不能解决用户所示错误。

body asset直接修补原版源文本，保持animation/additive_animation/blend_shape声明的原版单行排版、空白、引号，仅修改资源路径。body动画明确使用../../female_body/female_body_idle_1.anim等路径；无body动画副本或差分。新验证按asset所在虚拟目录解析路径，在模组/原版叠加目录查找，禁止用原版目录的同名文件兜底判定错误路径为通过。

## 早期流程（保留作输入重现）

使用Blender4.2、已有HeadlessExporter虚拟环境、PDXIO及本机CK3。原版游戏资产仅在用户本机读取，不提交到工具仓库。所有输出使用独立新目录；建议放在E盘。

```powershell
$repo='E:/UmaViewer-Workspace/UmaViewer-source'
$tools="$repo/Tools/NativeBody"
$py="$repo/Tools/HeadlessExporter/.venv/Scripts/python.exe"
$blender='C:/path/blender-4.2/blender.exe'
$plugin='E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'
$game='D:/steam/steamapps/common/Crusader Kings III/game'
$sourceMod='E:/previous/Uma-Inward-Skin-Envelope-Mod'
$sourceMeshes="$sourceMod/gfx/models/portraits/uma/delivery/body_vectors"
$delivery='E:/previous/vector-delivery'
$out='E:/UmaViewer-Exports/new-body-bind-run'

& $blender --background --factory-startup --python-exit-code 1 --python "$tools/transport_bind_pose_blender.py" -- --repo $repo --plugin $plugin --source $sourceMeshes --stock "$game/gfx/models/portraits/female_body/female_body.mesh" --output "$out/corrected"
& $py -X utf8 -B "$tools/build_native_body_mod.py" --repo $repo --plugin $plugin --game $game --source-mod $sourceMod --meshes "$out/corrected/1001" --delivery $delivery --output "$out/draft-mod"
& $blender --background --factory-startup --python-exit-code 1 --python "$tools/build_native_body_blend.py" -- --repo $repo --plugin $plugin --mod "$out/draft-mod" --game $game --output "$out/editable"
& $py -X utf8 -B "$tools/build_native_body_mod.py" --repo $repo --plugin $plugin --game $game --source-mod $sourceMod --meshes "$out/editable/roundtrip/1001" --delivery $delivery --output "$out/final-mod"
& $blender --background --factory-startup --python-exit-code 1 --python "$tools/verify_native_body_blender.py" -- --repo $repo --plugin $plugin --mod "$out/final-mod" --game $game --blend "$out/editable/1001_body_native.blend" --output "$out/reopen-verification.json"
```

Blender工程按厘米坐标保存，unit scale为0.01，包含真实原版待机、坐姿、骑乘（jockey_walk）动作。PDXIO不导出Shape Key的求值结果，因此脚本把每个端点显式写到临时普通Mesh后导出。Blender骨骼尾段适当延长以减少大坐标下的朝向精度损失；写出的引擎骨架再恢复为校正后的规范逆绑定矩阵，保持关节点一致。所有端点必须共享同一骨架。

test_vanilla_body_animation_blender.py读取原版body.asset中全部188项动画声明，在首、中、末帧检查真实矩阵皮肤及边长变化；其passed只证明样本有限数值正常，不证明所有姿态无穿插。render_native_animation_blender.py输出实际原版动作的对比图。verify_native_body_blender.py独立重开最终文件，逐点对比9个端点、3个动作、3个时刻的81次求值，并检查贴图已打包。verify_native_body_vectors.py验证28套已提供组合仍然可加，及PDX往返的共享拓扑、UV和语义权重；17个缺少源模型的组合不能记为源模型验证通过。

启用最终这一个UMA模组版本后，可选玛蒂尔达，用effect set_ethnicity = uma_ethnicity检查。最终验收仍需要CK3实机播放动作和切换基因；Blender渲染、数值检查或静态包检查不能替代游戏验收。
