# 无 UI 的 UMA 原始数据命令行读取器

读取本机游戏 `Persistent` 目录或分卷 ZIP，参照 UmaViewer 的原始数据库、哈希资源寻址、依赖和 AssetBundle 解码逻辑。无需 Unity Editor、UmaViewer UI、登录或网络下载。命名后的 UnityFS 可直接交给 `../HeadlessExporter` 和 Blender4.2/PDX 流程。

支持 Windows x64 上的加密 meta：使用原仓库 `Assets/Plugins/sqlite3mc_x64.dll`，以只读方式配置 cipher=3，按 `GenFinalKey` 的规则在内存读取仓库运行配置；JP/Global 自动探测。原始配置和每文件解码 seed 不打印，也不写入 JSON、CSV 或源码包。可读的普通 SQLite 使用 Python 标准库只读连接。非 Windows 的加密 meta 需要对应平台 native runtime，当前未实现。

需要 Python3.10+；解析验证需要 UnityPy。当前可直接使用 `Tools/HeadlessExporter/.venv`；分卷 ZIP 使用本机已安装的 7-Zip，目录输入不需要7-Zip。所有缓存/TEMP/TMP/TMPDIR都在 `--workspace` 下。工作区和命名输出必须位于原数据目录外，命名输出使用新目录。

## 本机命令

以下命令在仓库根目录运行；`--source` 可以是 `E:/uma`、`E:/uma/Persistent.zip`，或包含 `meta/master/dat` 的实际 Persistent 目录。工具在分卷包中只提取数据库和所选资源，不复制整个原始数据。

```powershell
# 检查数据和本地可用性
Tools/RawAssets/run.cmd --source E:/uma --workspace E:/UmaViewer-Workspace/UmaRaw-CLI doctor --report E:/UmaViewer-Exports/raw-doctor.json

# 列出通用脸，恢复有意义的资源名
Tools/RawAssets/run.cmd --source E:/uma --workspace E:/UmaViewer-Workspace/UmaRaw-CLI list --prefix 3d/chara/head/chr0001_00/pfb_chr0001_00_face --limit 20

# 查看指定角色实际体型和肤色
Tools/RawAssets/run.cmd --source E:/uma --workspace E:/UmaViewer-Workspace/UmaRaw-CLI master --table chara_data --columns id,bust,skin,height,shape --id 1001

# 解码一个逻辑资源及全部依赖，可重复 --name 和 --prefix
Tools/RawAssets/run.cmd --source E:/uma --workspace E:/UmaViewer-Workspace/UmaRaw-CLI extract --name 3d/chara/head/chr1001_80/pfb_chr1001_80 --output E:/UmaViewer-Exports/new-head --zip E:/UmaViewer-Exports/new-head.zip

# 解析并查看 Unity 对象类型
Tools/RawAssets/run.cmd --source E:/uma --workspace E:/UmaViewer-Workspace/UmaRaw-CLI inspect --name 3d/chara/head/chr0001_00/pfb_chr0001_00_face000 --output E:/UmaViewer-Exports/new-face-inspect

# 通用泳装的实际贴图由游戏运行时选择，需要把相关 textures 也选进来
Tools/RawAssets/run.cmd --source E:/uma --workspace E:/UmaViewer-Workspace/UmaRaw-CLI extract --name 3d/chara/head/chr1001_80/pfb_chr1001_80 --name 3d/chara/body/bdy0004_00/pfb_bdy0004_00_00_1_0_2 --prefix 3d/chara/body/bdy0004_00/textures/tex_bdy0004_00_00_ --output E:/UmaViewer-Exports/new-character

# 直接接原有命令行模型解析，无须 Copy-All 或 Unity UI
Tools/HeadlessExporter/.venv/Scripts/python.exe -X utf8 -B Tools/HeadlessExporter/export_assets.py E:/UmaViewer-Exports/new-character --output E:/UmaViewer-Exports/new-character-decoded --generic-skin 1 --name 1001=SpecialWeek
```

使用独立 Python 时可运行 `python uma_raw.py`，并指定 `--umaviewer-source E:/UmaViewer-Workspace/UmaViewer-source`。安装在本仓库 `Tools/RawAssets` 后此参数默认自动指向仓库根目录。7-Zip不在默认位置时使用 `--seven-zip`。

## 命令与边界

- `doctor`：读取加密meta/普通master，统计逻辑资源、本地原始文件、未下载条目和通用脸；报告源布局与缓存位置。
- `list`：按资源名的 `--prefix` / `--contains` 搜索，`--limit` 控制显示数量，`--json` 保存安全索引。文件名是meta的n，原始dat位置是 `dat/h前两字符/h`。文件字节数来自实际目录或ZIP，不能把meta的s列当成字节数。
- `extract`：选择资源，递归解析分号分隔的依赖，检测缺失和循环，按逻辑目录输出。默认遇到缺失依赖/本地文件就拒绝本次导出；显式 `--allow-missing` 可做标明不完整的导出。可指定 `--no-dependencies` 和 `--skip-validate`，只用于明确需要的局部/快速读取。
- `inspect`：以同样方式解码指定依赖闭包，并输出Unity对象类型。Prefab网格、材质、骨骼的进一步解析由现有HeadlessExporter执行。
- `master`：只读选定表/列/ID；SQL标识符检查，所有数据库均只读，不执行包内代码。

AssetBundle解码保持头256字节，后续按原文件绝对偏移使用仓库AB运行配置和每文件标记进行XOR。UnityFS默认由UnityPy实际读取验证。非UnityFS文件保持原字节复制，不能把它们标为已经完成专门的音频/视频解码；HCA/USM等专用转换未实现。输出manifest在命名目录外，避免现有Package加载器把报告混入游戏资产。

本工具不会下载缺失文件，不读取游戏存档、账号登录文件，也不把原始数据库或解码配置上传到仓库。源码包只包含程序和验证说明；数据库和实际资源保留本地。

## 真实本地验证（2026-10-08）

用户提供 `E:/uma/Persistent.z01~z04 + Persistent.zip`，总20,186,954,694字节。328032个ZIP成员含文件夹，327004个文件，其中327000个哈希资源。meta369676条逻辑记录，本地327000条可用、42676条未下载；这些缺失不是解码错误。master有173个角色、1113个Mob，原始通用face000~009全部在包中。

已实际解码10种通用脸＋特别周80头＋胸型2泳装及依赖，共29个加密UnityFS，29次UnityPy读取全部成功。补齐泳装textures后又完成134个加密资源验证。特别周80 prefab与泳装prefab的解码字节分别和用户此前BSTest Copy-All明文逐字节一致。随后现有HeadlessExporter解析出2个实际任务、0错误：头部7个Renderer/3709顶点，泳装3510顶点；骨骼、UV、材质、贴图均可解析。

五项回归覆盖256字节边界、绝对偏移、负long标记、未加密透传、只读数据库、私有字段不打印及路径检查。对全327000文件尚未逐个解码/网格验收；当前是全索引＋实际抽样闭环验证，未运行Unity或游戏UI。
```
python -X utf8 -B -m unittest discover -s Tools/RawAssets -p test_*.py
```
