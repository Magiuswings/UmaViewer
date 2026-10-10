# UMA 1001 Accessory Test

基于用户提供的“调色盘无效，动画错位.zip”修改，只导出和验证 1001。另以“调色盘有效.zip”的材质作为只读对照。原始压缩包及安装中的游戏文件未修改。

原型错误的两个证据：body diffuse Alpha 全为 0（调色版本为 255），直接关闭了皮肤调色 mask；原版头与 UMA 的眼球旋转支点相差约 11.18 cm，却在 accessory 中共享原版头的姿势。对同一虹膜做正负15°的转眼支点探针，旧支点俯仰偏移约2.91 cm，匹配后的支点偏移0.041 cm。该探针是绑定几何诊断，不是游戏内帧测量。

这版用自定义空头（零渲染几何、61骨）驱动姿势，所有面部 accessory 使用完全相同的骨名、顺序、父链和逆绑定。原版 head 模型不再出现在 UMA portrait type 中。面部875顶点/1334面、附片455顶点、眉62顶点、发2704顶点、眼46顶点，各自成为 shared_pose_entity=head 的独立 accessory；眼睛使用原版 eye_accessory/normal_eyes 模板的接入形式。

面部 accessory 不带 portrait_decal/body_part=head 标记，本模组的 uma_portrait.shader 仅在 portrait_skin_face effect 中移除 ENABLE_TEXTURE_OVERRIDE，保留 effect 名称和 shader 文件名。原版 complexion 的 texture_override 可指定 female_head_diffuse/normal；这版显式阻止其替换马娘面部材质。所有 meshsettings 都指向自己的 UMA DDS，未修改或覆盖原版贴图、法线、模型、shader。

body的4张肤色DDS只改BC3 Alpha块为255，压缩RGB块、解码RGB和所有mipmap保持不变；body的mesh、骨架、权重、asset和原版动画引用逐字节保留。它继续接受同一uma portrait group的肤色调色盘。

新脸型morph基因 gene_uma_face_identity 仅含1001模板，min=0.0 max=1.0；ethnicity和portrait modifier明确选择强度1。body morph中36个无效0→0 setting删除，空模板继续依靠实体的中性默认值，不把互斥BS全部改成1。四组分支及18岁阈值保留。所有TXT为UTF-8-BOM，gfx basename全局唯一，共用0001/角色1001/独立animation的命名规范不变。

验证范围：7个PDX IO实际导入（空头、5个accessory、1个1001 BS端点）；5个BS强度；待机、宫廷、祈祷事件、愤怒情绪的首/中/末帧，共60个组件求值；8个转眼支点探针；6张实际Blender渲染；最终工程重开和贴图打包。不扫描其它角色，也不将这些结果当作CK3实机验收。

本机当前没有运行中的CK3，未实际进入游戏复测。只启用 UMA 1001 Accessory Test，关闭其它UMA测试版。选择玛蒂尔达，控制台 effect set_ethnicity = uma_ethnicity。重点分别检查宫廷、捏人界面和事件小肖像的眼睛；改变肤色调色盘，确认头身都会响应。新的空头/accessory接入方式仍需要这一步游戏内验证。

Models/1001/uma_1001_head_accessory.blend 含空头控制骨架、五个可编辑组件、1001脸型BS和四个已复用动作；默认1001、真实待机。Evidence/1001_*.png 为对应渲染，1001_gaze_minus15/plus15为独立转眼诊断。动画渲染跟随头部取景；它不是CK3场景截图。

脚本依赖原仓库PDXExporter/NativeBody和已有Blender4.2/PDX IO，不包含原始游戏程序。生成物放E盘，脚本临时工作副本放当前获准工作区。
