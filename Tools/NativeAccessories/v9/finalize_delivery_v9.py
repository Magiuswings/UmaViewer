"""Snapshot source and normalize delivered diagnostic paths before archiving."""
import json,shutil
from pathlib import Path
from paths_v9 import ROOT,REPO
CODE=Path(__file__).resolve().parent
def main():
    for name in ['static-validation','native-attachment-validation','blender-sdk-native-validation','blender-native-assembly','final-preservation-designer-audit']:
        assert json.loads((ROOT/f'Reports/{name}.json').read_text())['passed']
    plan=ROOT/'Reports/contracts/AB-config-drafts/AB-plan.json'
    if plan.exists():
        source=str(CODE/'AB-config-drafts')
        def relocate(v):
            if isinstance(v,dict):return{k:relocate(w)for k,w in v.items()}
            if isinstance(v,list):return[relocate(w)for w in v]
            if isinstance(v,str)and v.startswith(source):return str(plan.parent)+v[len(source):]
            return v
        plan.write_text(json.dumps(relocate(json.loads(plan.read_text())),indent=2,ensure_ascii=False),encoding='utf8')
    dest=REPO/'Tools/NativeAccessories/v9';dest.mkdir(exist_ok=True)
    copied=[]
    for f in CODE.iterdir():
        if f.suffix in ['.py','.md']:shutil.copy2(f,dest/f.name);copied.append(f.name)
    parent=REPO/'Tools/NativeAccessories/README.md';text=parent.read_text(encoding='utf8');title='## V9：头部合并与 root-only 颈部修复\n\n'
    intro='最新修复工作流见 [v9/README.md](v9/README.md)。非 shader 资源引用统一 basename，恢复原版颜色 key 与前置载入文件，头部按角色合并，1002 默认耳朵与静态头饰分离。245 骨头部使用三个真实身体驱动的颈部参考点，只保留 root 挂接；全 61 帧数值检查和四套 Blender 4.2 装配、重开通过。设计器注册与定义已清理，沉默退出的实机根因仍未确认；对照资料独立保存，不自动启用。\n\n'
    if not text.startswith(title):parent.write_text(title+intro+text,encoding='utf8')
    (ROOT/'Reports/source-snapshot.json').write_text(json.dumps(dict(repo=str(REPO),subfolder='Tools/NativeAccessories/v9',files=copied,code_only=True,game_runtime_executed=False),indent=2),encoding='utf8');print('V9_SOURCE_SYNC',len(copied),flush=True)
if __name__=='__main__':main()
