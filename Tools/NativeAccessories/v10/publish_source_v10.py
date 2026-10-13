import json,shutil
from pathlib import Path
from paths_v10 import ROOT,REPO
CODE=Path(__file__).resolve().parent
excluded={'cleanup_inventory.py','prepare_cleanup.py','remove_old_uma.ps1','stage_v10.py'}
dest=REPO/'Tools/NativeAccessories/v10';dest.mkdir(exist_ok=True)
for f in CODE.iterdir():
    if f.suffix in ['.py','.md']and f.name not in excluded:shutil.copy2(f,dest/f.name)
entry=REPO/'Tools/NativeAccessories/README.md';s=entry.read_text(encoding='utf8');title='## V10：编辑器注册、调色、衣帽与高跟鞋测试\n\n'
if not s.startswith(title):entry.write_text(title+'当前工作流见 [v10/README.md](v10/README.md)。game 与 customization 注册分离，服装选择使用原版 helper；服装颜色接入原生 variation，颈部改常规皮肤基色；两件 hood 恢复真实 Head／Chest 绑定及六个 BS 接缝。提供1001默认高跟鞋私有动画集及110,084条分模块资源命名目录。PDX／Blender及数值检查与尚未代跑的 CK3 编译、理发店持久化明确分开。Blender工具已迁至E盘，旧发行产物完成限定清理。\n\n'+s,encoding='utf8')
(ROOT/'Reports/source-snapshot-v10.json').write_text(json.dumps(dict(repo=str(REPO),source_directory=str(dest),destructive_cleanup_scripts_excluded=True,CK3_executed=False),indent=2),encoding='utf8')
print('V10_SOURCE_SYNC_COMPLETE',flush=True)
