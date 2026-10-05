# Blender 独立服装与身体导出

此 Fork 新增 Blender 导出面板。它把当前角色按网格／材质分区标记为 `Clothing`、`Body` 或 `Exclude`，分别生成带独立骨架和打包贴图的 `clothing.blend`、`body.blend`。原有 PMX 导出流程仍可使用。

## 编译和使用

1. 用项目指定的 **Unity 2022.3.62f3** 打开仓库，等待已有包和资源导入。
2. 打开 `Assets/Scenes/Version2.unity`，进入 Play，或构建 Windows 应用。上游发布的 EXE 没有此 Fork 的新代码。
3. 按上游说明配置现有赛马娘资产路径，加载角色和目标服装。需要中性绑定姿势时，先在 Viewer 调整到中性姿势再导出。
4. 点击窗口右上角 **Blender Export [F8]**，也可按 F8 开关面板。
5. 为每个材质分区选择 `Clothing` 或 `Body`；`Exclude` 不进入两个文件。自动建议只供起点使用，尤其需要检查 `bdy` 材质。头、眼、口腔、眉、发和尾通常建议归 Body。未知分区默认 Exclude。
6. 填入导出目录和 Blender 可执行文件路径；Windows 常规安装路径会自动检测。点击 **Export clothing.blend + body.blend**。转换在后台执行，完成状态会显示实际生成的文件。

导出目录有时间戳和随机后缀，不覆盖之前的模型。只给 Clothing 分配几何时，仅生成 `clothing.blend`；只给 Body 分配几何时，仅生成 `body.blend`。

按本次用户确认，**泳装或极其贴身的服装可作为身体基底，不需要补全裸体表面**。在 Viewer 原有服装列表中选择该角色的泳装／紧身服，打开导出面板后点击 **Swimsuit / tight outfit -> Body**；这会把当前所有分区归 Body，然后可手动排除头发、配件或其他不需要的部分，再导出 `body.blend`。该文件保留选定泳装／紧身服已有的几何与着色。

要同时获得目标外衣和上述身体基底：先加载目标服装，选择其外衣分区为 Clothing 并导出；再加载同一角色的泳装／紧身服，导出 Body。两个包各自保留其源骨架；建议使用相同角色、体型和中性姿势，便于后续在 Blender 配准。不会自动将不同服装的骨架或权重替换成另一套。

Blender 不在本机时，可以先点击 **Export package**。目录中包含 `model.uma.json`、`textures/`、独立的导入脚本和 README。带到安装了 **Blender 4.2 或更新版本**的电脑后执行：

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-exit-code 1 --python 'D:\Exports\UmaBlender_example\uma_blender_import.py' -- 'D:\Exports\UmaBlender_example\model.uma.json' --split
```

脚本也支持 `--part clothing`、`--part body`，或默认输出同时包含两个独立 Collection 的 `all.blend`。可以用 `--output 'D:\Exports\character.blend'` 指定单文件输出位置；`--split` 固定写在 JSON 旁边。

## 模型、骨骼和形态键

- 每个 `.blend` 只保留该类别的面及其使用的顶点，不把被排除的衣服顶点留在身体文件中。原分区、材质槽、UV0–UV7、顶点颜色和法线保留。
- 保留引用的骨骼及父链，包括脸、头发、尾和服装辅助骨骼；重复骨骼名通过稳定 ID 映射，不合并成一根骨骼。
- 使用全部源权重，不强行截断到四个影响。静态网格和无权重点绑定到相应 Renderer 节点。
- **导出时的当前姿势作为 Blender 骨架的 rest pose**。可见网格通过 `BakeMesh` 取样，角色动画、表情、物理开关及 `sharedMesh` 不被改写。原 Unity 矩阵保存在骨骼属性中。
- 源网格已有的 shape keys 会保留。已取样的当前 shape influence 先从 Basis 扣除，避免重新打开时变形叠加两遍。多帧 shape key 暂使用最后一帧，并写入 warning；Unity 脸部驱动骨骼会保留，但不会自动变成上游 PMX 导出器生成的额外表情键。
- GPU 网格读回保留所有 vertex streams、索引格式、原始 submesh descriptors 和 `baseVertex`；骨骼权重、绑定矩阵、形态数据另从原网格读取。遇到无效绑定或无法读取的数据会报错。
- 模型转换为 Blender 的 Z-up、米制坐标并转换左右手坐标系与三角形绕序。

没有导出动画轨道、Unity 布料或物理组件。骨架在 Blender 中可编辑并可驱动网格。

## “裸体／身体”的边界

`Body` 表示由你选定的现有身体分区或泳装／紧身服身体基底。它不会凭空生成未存在于游戏资产中的躯干、臀部或其他被服装遮挡的表面。若原模型只保留露出的皮肤，身体导出也会有相同缺口。

皮肤和衣服若在同一材质、同一 submesh 内，此版本不会根据皮肤颜色猜测逐面类别。可先保留该混合分区，在 Blender 编辑模式中选择需要的面并分离，再保存独立文件。完整无缺口的基础身体需要合适的源模型或另外建模。

## 材质和着色

实际加载材质的 Shader 名、keywords、renderQueue、所有可枚举颜色／数值／向量参数、2D 贴图与 UV scale/offset 都保存在包和 Blender 自定义属性中。贴图按引用分配独立文件名，避免同名纹理相互覆盖；所有图片打包进入 `.blend`。

EEVEE 节点重建 diffuse × tint、两档 toon 光照和常见透明贴图。Cycles 有独立的 Principled 输出，并连接常用法线图。当前配色表的六个 `_MaskColor*` 值进入可编辑节点；`USE_MASK_COLOR` 的区域配色预览按每通道 1=第一颜色、0.5=第二颜色解释，可调整 area band 节点。

**这是可编辑的近似着色，不是 Unity Shader 的完整移植。** 不同地区／材质的 area mask 编码、眼睛图集、脸部定向阴影、描边、特殊高光、SSS、动态 Shader 参数和特殊纹理仍可能需要调整。所有源纹理节点和参数保留，便于继续还原。不能将节点存在或贴图打包通过当作角色视觉一致性的证明。

## 验证和复现

普通 Python 创建不含游戏数据的合成样本，再用 Blender 实际转换和重开：

```powershell
python Tests/Blender/create_fixture.py Tests/Local/fixture
blender --background --factory-startup --python-exit-code 1 --python Assets/StreamingAssets/Blender/uma_blender_import.py -- Tests/Local/fixture/model.uma.json --split
blender --background --factory-startup --python-exit-code 1 --python Tests/Blender/verify_blends.py -- Tests/Local/fixture
blender --background --factory-startup --python-exit-code 1 --python Tests/Blender/check_validation.py
```

样本故意把身体和衣服放在同一 Renderer 的不同材质分区，含共享顶点、应排除的顶点、六个权重影响、重名骨骼、已有非零形态权重和透明贴图。重开检查独立几何、层级、权重归一化、UV／颜色／材质、图像打包、形态键不重复叠加，以及真实骨架变形。

Unity 中通过菜单 **UmaViewer → Tests → Blender export snapshot** 可检查可读与 `UploadMeshData(true)` 的 GPU 网格、多顶点流、非零 `baseVertex`、骨骼权重、形态键及源状态保留。需要图形设备，不能使用 `-nographics`：

```powershell
Unity.exe -batchmode -quit -projectPath '<repo>' -executeMethod BlenderExportSmokeTest.Run -logFile '<log>'
```

另提供 `Tests/Blender/compile_exporter.ps1`：使用实际 Unity managed DLL 与两个接入类型 stub 做 C# 编译检查。此检查不能替代整个 Unity 工程编译或运行。

2026-10-05 本机已实际通过 **Blender 4.2.23 LTS 和 Blender 5.2.1 LTS** 的转换、重开及骨架驱动检查；C# Unity API 引用编译已通过。Unity Editor 菜单 smoke test、完整 Windows 构建和真实赛马娘角色的导出／外观检查尚未执行。证据详见 `VALIDATION.md`。

Fork CI 自动执行 Blender 合成样本检查。继承的 Unity Windows 构建默认只在上游或显式设置 `UNITY_BUILD_ENABLED=true` 的仓库运行；要在 Fork 构建 EXE，还需按照原工作流配置 Unity license、账号等 Secrets。
