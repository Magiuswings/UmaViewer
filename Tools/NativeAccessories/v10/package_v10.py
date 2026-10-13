import json,shutil,hashlib,zipfile
from pathlib import Path
from paths_v10 import ROOT,MOD,REPO
CODE=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def archive(path,entries):
    print('ARCHIVE_BEGIN',path.name,len(entries),flush=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=4)as z:
        for i,(f,n)in enumerate(entries,1):
            z.write(f,n)
            if i%250==0:print('ARCHIVE_PROGRESS',path.name,i,flush=True)
    with zipfile.ZipFile(path)as z:assert z.testzip()is None
    return dict(file=str(path),bytes=path.stat().st_size,sha256=sha(path),CRC_passed=True)
def main():
    for name in ['static-validation','task-contract-validation','native-attachment-validation','blender-sdk-native-validation','blender-native-assembly','heel-head-integration','independent-material-review']:
        r=json.loads((ROOT/f'Reports/{name}.json').read_text(encoding='utf-8-sig'));ok=r.get('passed')or r.get('static_passed')
        if name=='independent-material-review':ok=r.get('status')=='static_structure_and_CPU_cases_passed'and not r.get('confirmed_findings')
        assert ok,name
    sdk=json.loads((ROOT/'Reports/blender-sdk-native-validation.json').read_text())
    for m in sdk['modules']:assert sha(Path(m['mesh']))==m['mesh_sha256']and sha(Path(m['animation']))==m['animation_sha256']
    code=ROOT/'Code';code.mkdir(exist_ok=True)
    excluded={'cleanup_inventory.py','prepare_cleanup.py','remove_old_uma.ps1','stage_v10.py'}
    for f in CODE.iterdir():
        if f.suffix in ['.py','.md']and f.name not in excluded:shutil.copy2(f,code/f.name)
    for f in [REPO/'Tools/PDXExporter/build_ck3_mod.py',REPO/'Tools/NativeAccessories/v7/head_assembly_math.py']:shutil.copy2(f,code/f.name)
    shutil.copy2(CODE/'README.md',ROOT/'README.md')
    for folder in ['UMA-V10','Reports','Diagnostics','HatRepair','HeelPose','Database','AnimationCatalog']:
        for f in(ROOT/folder).rglob('*.txt'):assert f.read_bytes().startswith(b'\xef\xbb\xbf'),str(f)
    desc='name="UMA V10 Editor Palette Heel Test"\nsupported_version="1.20.*"\n';(MOD/'descriptor.mod').write_text(desc,encoding='utf8');(ROOT/'UMA-V10.mod').write_text(desc+'path="'+MOD.as_posix()+'"\n',encoding='utf8')
    inputs=sorted(f for f in MOD.rglob('*')if f.is_file());(ROOT/'Reports/release-input-hashes.json').write_text(json.dumps([dict(file=f.relative_to(MOD).as_posix(),bytes=f.stat().st_size,sha256=sha(f))for f in inputs],indent=2),encoding='utf8');files=[(f,'UMA-V10/'+f.relative_to(MOD).as_posix())for f in inputs]+[(ROOT/'UMA-V10.mod','UMA-V10.mod')]
    mod=archive(ROOT/'UMA-V10-1001-1002-Mod.zip',files)
    entries=files+[(f,f.relative_to(ROOT).as_posix())for folder in ['Code','Database','Reports','RigRepair','Editable','Preview','HatRepair','HeelPose','Diagnostics','AnimationCatalog','Cleanup']for f in(ROOT/folder).rglob('*')if f.is_file()and f.suffix!='.blend1']+[(ROOT/'README.md','README.md')]
    project=archive(ROOT/'UMA-V10-1001-1002-Project.zip',entries)
    catalog=archive(ROOT/'UMA-Animation-Catalog.zip',[(f,f.relative_to(ROOT).as_posix())for f in(ROOT/'AnimationCatalog').rglob('*')if f.is_file()])
    report=dict(mod_archive=mod,project_archive=project,animation_catalog_archive=catalog,mod_files=len(inputs),DDS_files=len(list(MOD.rglob('*.dds'))),runtime_CK3_executed=False,shader_compiled_by_CK3=False,Blender4_2_SDK_and_assembly_passed=True)
    (ROOT/'release-manifest.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V10_RELEASE_COMPLETE',json.dumps(report),flush=True)
if __name__=='__main__':main()
