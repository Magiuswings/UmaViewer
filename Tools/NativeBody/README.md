# 原版躯干动画与保持坐标的绑定修复

此流程读取已经解码、并集补肤和导出的通用躯干，不扫描或解码所有角色衣装。默认只修骨骼逆绑定矩阵的方向，保持输入的105倍烘焙PDX网格坐标、BS端点、UV、拓扑、权重和134个关节点。此前骨架虽然移动到UMA的T姿势关节位置，却沿用了CK3斜向下的手臂绑定方向；直接播放原版动画会使手臂折叠。新流程用语义关节链校正方向，基于同一Basis骨架处理所有端点。

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

## 当前发布步骤

上一轮build_native_body_mod.py产物只是输入阶段，不能再直接作为最终模组发布。先在Blender4.2运行correct_posed_skin_normals.py，输入上一轮模组的body网格目录、输出新的0001目录；再运行rebuild_readable_assets.py，传入--source-mod上一轮模组、--legacy-mod保留原布局的来源模组、--body-meshes法线修复目录、--game实际游戏目录和--output新模组目录。最后用update_shared_body_blend.py更新可编辑工程。源顶点、BS端点、UV、权重、骨骼不移动；修改n/ta以消除原版中性姿势下蒙皮法线与几何法线不吻合的问题。

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
