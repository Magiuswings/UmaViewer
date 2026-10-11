import os
"""Package the verified V7 mod, source code and local verification evidence."""
import hashlib,json,os,shutil,zipfile
from pathlib import Path
R=Path(os.environ.get('UMA_V7_ROOT',str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')))));REPO=Path(os.environ.get('UMA_V7_REPO',str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')))));mod=R/'UMA-V7';scripts=Path(__file__).resolve().parent
static=json.loads((R/'Reports/static-validation.json').read_text());assert static['passed']and static['wardrobe_families']==71
assert json.loads((R/'Reports/body-undress-animation.json').read_text())['passed']
assert json.loads((R/'HeadSources/AssemblyQA/blender-neck-repair-qa.json').read_text())['passed']
assert(R/'HeadSources/NeckBridge/neck-delivery.json').is_file()
desc='name="UMA V7 1001 1002 Native Rig"\nsupported_version="1.20.*"\n';(mod/'descriptor.mod').write_text(desc,encoding='utf8');(R/'UMA-V7.mod').write_text(desc+'path="'+mod.as_posix()+'"\n',encoding='utf8')
code=R/'Code';code.mkdir(exist_ok=True)
for f in scripts.iterdir():
    if f.suffix in ['.py','.md']:shutil.copy2(f,code/f.name)
readme=scripts/'README.md'
if readme.exists():shutil.copy2(readme,R/'README.md')
def zipfiles(dest,entries):
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=4)as z:
        for file,arc in entries:z.write(file,arc)
    with zipfile.ZipFile(dest)as z:assert z.testzip()is None
    digest=hashlib.sha256()
    with dest.open('rb')as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    print('ARCHIVE_VERIFIED',dest.name,dest.stat().st_size,flush=True);return{'file':str(dest),'bytes':dest.stat().st_size,'sha256':digest.hexdigest()}
files=[(f,'UMA-V7/'+f.relative_to(mod).as_posix())for f in mod.rglob('*')if f.is_file()];files.append((R/'UMA-V7.mod','UMA-V7.mod'));gamezip=zipfiles(R/'UMA-V7-1001-1002-Mod.zip',files)
entries=files+[(f,f.relative_to(R).as_posix())for folder in ['Code','Database','Reports','Rigs']for f in(R/folder).rglob('*')if f.is_file()]
for folder in ['HeadSources/AssemblyQA','HeadSources/NeckBridge','HeadSources/NeckPatch']:
    entries.extend((f,f.relative_to(R).as_posix())for f in(R/folder).rglob('*')if f.is_file()and(f.suffix in ['.json','.png']or(f.suffix=='.blend'and'neck_repaired'in f.name)))
entries.extend((f,'EditableClothes/'+f.name)for owner in ['0001','1001','1002']for f in(R/'ClothingParts'/owner).rglob('*.blend'))
entries.extend((f,'SourceBoneReferences/'+f.relative_to(R/'ClothingParts').as_posix())for owner in ['0001','1001','1002']for f in(R/'ClothingParts'/owner).rglob('native-source-points.json'))
entries.extend((f,f.relative_to(R).as_posix())for f in(R/'HeadSources/Export').rglob('*.json'))
entries.extend((f,f.relative_to(R).as_posix())for f in(R/'SkinMaterialSources').glob('*.dds'))
ab=R/'ClothingParts/AB-bdy1002_00';entries.extend((f,'Reports/Skirt1002/'+f.name)for f in ab.iterdir()if f.is_file()and f.suffix in ['.json','.png']);entries.append((ab/'Dlocal/local-clearance.json','Reports/Skirt1002/local-clearance.json'))
if(R/'README.md').is_file():entries.append((R/'README.md','README.md'))
projectzip=zipfiles(R/'UMA-V7-1001-1002-Project.zip',entries)
manifest={'mod_archive':gamezip,'project_archive':projectzip,'source_character_count':173,'all_mod_files':len(files)-1,'runtime_game_verified':False,'blender_version':'4.2.23','txt_encoding':'UTF-8-BOM','palettes_unchanged':True};(R/'release-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');print('V7_RELEASE_COMPLETE',flush=True)
