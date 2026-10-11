import os
import json,sys,shutil
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"))
sys.path.insert(0,str(REPO/'Tools/HeadlessExporter'))
from export_assets import Package,Extractor,write_json
merged=ROOT/'named-models';merged.mkdir(exist_ok=False)
for source in [Path('E:/UmaViewer-Exports/2026-10-08-Raw/named-character-smoke'),ROOT/'named-native',ROOT/'more-native']:
    for f in source.rglob('*'):
        if f.is_file():
            dest=merged/f.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==f.read_bytes()
            else:shutil.copy2(f,dest)
out=ROOT/'parsed';out.mkdir();package=Package(merged);extractor=Extractor(package,out,SimpleNamespace(names={'1001':'SpecialWeek'},generic_skin='1',generic_skin_reference='0',skin_mode='auto',skin_tolerance=42.));selection=json.loads((ROOT/'resource-selection.json').read_text())
for kind,name in [('head','3d/chara/head/chr1001_80/pfb_chr1001_80'),('tail',selection['tail_prefab']),('body',selection['clothing'])]:
    ident=name.rsplit('/',1)[-1].removeprefix('pfb_');data=extractor.prefab(name,kind,ident,'1001',[]);write_json(out/(kind+'.json'),data);print('PARSED_NATIVE_MODEL',kind,[(m['name'],len(m['vertices']))for m in data['meshes']],flush=True)
targets=[]
for obj in package.objects:
    if obj.type.name=='MonoBehaviour':
        try:
            tree=obj.read_typetree()
            if '_earTarget'in tree:targets.append(tree)
        except Exception:pass
write_json(out/'ear-driven-targets.json',targets);print('EAR_DRIVEN_TABLES',len(targets),flush=True)
