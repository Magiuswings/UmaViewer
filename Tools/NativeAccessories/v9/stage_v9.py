"""Isolated V9 stage; do not overwrite user-edited or old version folders."""
import json,shutil,sys
from pathlib import Path
from paths_v9 import ROOT,V8,MOD,REPO
ROOT.mkdir(exist_ok=True);(ROOT/'Reports').mkdir(exist_ok=True);(ROOT/'Logs').mkdir(exist_ok=True);(ROOT/'.temp').mkdir(exist_ok=True)
if not MOD.exists():shutil.copytree(V8/'UMA-V8',MOD)
for folder in ['Database','Rigs']:
    if not(ROOT/folder).exists():shutil.copytree(V8/folder,ROOT/folder)
def updatepaths(obj):
    if isinstance(obj,dict):return {k:updatepaths(v)for k,v in obj.items()}
    if isinstance(obj,list):return [updatepaths(v)for v in obj]
    if isinstance(obj,str):return obj.replace(str(V8/'UMA-V8'),str(MOD)).replace((V8/'UMA-V8').as_posix(),MOD.as_posix())
    return obj
for name in ['head-registration.json','clothing-registration.json','configuration.json','palette-presets.json','texture-sharing.json','neck-delivery-source.json']:
    f=V8/'Reports'/name
    if f.exists():(ROOT/'Reports'/name).write_text(json.dumps(updatepaths(json.loads(f.read_text(encoding='utf8'))),ensure_ascii=False,indent=2),encoding='utf8')
print('V9_STAGE_READY',MOD,flush=True)
