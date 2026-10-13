"""Package final validated V9, preserving V8 and original game inputs."""
import hashlib,json,shutil,zipfile
from pathlib import Path
from paths_v9 import ROOT,MOD,REPO
CODE=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def zipfiles(path,entries):
    print('ARCHIVE_BEGIN',path.name,len(entries),flush=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=4)as z:
        for i,(f,n)in enumerate(entries,1):
            z.write(f,n)
            if i%200==0:print('ARCHIVE_PROGRESS',path.name,i,len(entries),flush=True)
    print('ARCHIVE_CRC_CHECK',path.name,flush=True)
    with zipfile.ZipFile(path)as z:assert z.testzip()is None
    return dict(file=str(path),bytes=path.stat().st_size,sha256=sha(path),CRC_passed=True)
def main():
    for name in ['static-validation','native-attachment-validation','final-preservation-designer-audit','blender-sdk-native-validation','blender-native-assembly']:
        d=json.loads((ROOT/f'Reports/{name}.json').read_text());assert d['passed'],name
    sdk=json.loads((ROOT/'Reports/blender-sdk-native-validation.json').read_text())
    for m in sdk['modules']:
        assert sha(Path(m['mesh']))==m['mesh_sha256'];assert sha(Path(m['animation']))==m['animation_sha256']
    code=ROOT/'Code';code.mkdir(exist_ok=True)
    for f in CODE.iterdir():
        if f.suffix in ['.py','.md']:shutil.copy2(f,code/f.name)
    for dep in [REPO/'Tools/PDXExporter/build_ck3_mod.py',REPO/'Tools/NativeBody/test_vanilla_body_animation_blender.py',REPO/'Tools/NativeAccessories/v7/head_assembly_math.py']:shutil.copy2(dep,code/dep.name)
    shutil.copy2(CODE/'README.md',ROOT/'README.md')
    desc='name="UMA V9 Head Neck Repair"\nsupported_version="1.20.*"\n';(MOD/'descriptor.mod').write_text(desc,encoding='utf8');(ROOT/'UMA-V9.mod').write_text(desc+'path="'+MOD.as_posix()+'"\n',encoding='utf8')
    payload=sorted(f for f in MOD.rglob('*')if f.is_file());hashes=[dict(file=f.relative_to(MOD).as_posix(),bytes=f.stat().st_size,sha256=sha(f))for f in payload]
    (ROOT/'Reports/release-input-hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf8')
    files=[(f,'UMA-V9/'+f.relative_to(MOD).as_posix())for f in payload]+[(ROOT/'UMA-V9.mod','UMA-V9.mod')]
    modzip=zipfiles(ROOT/'UMA-V9-1001-1002-Mod.zip',files)
    entries=files+[(f,f.relative_to(ROOT).as_posix())for folder in ['Code','Database','Reports','Rigs','RigRepair','Editable','Preview','Diagnostics']for f in(ROOT/folder).rglob('*')if f.is_file()and f.suffix!='.blend1']+[(ROOT/'README.md','README.md')]
    projectzip=zipfiles(ROOT/'UMA-V9-1001-1002-Project.zip',entries)
    report=dict(mod_archive=modzip,project_archive=projectzip,mod_files=len(payload),mod_uncompressed_bytes=sum(f.stat().st_size for f in payload),binary_meshes=len(list(MOD.rglob('*.mesh'))),DDS_files=len(list(MOD.rglob('*.dds'))),CK3_game_executed=False,ruler_designer_crash_cause_confirmed=False,Blender4_2_SDK_and_assembly_passed=True,original_game_and_V8_untouched=True)
    (ROOT/'release-manifest.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V9_RELEASE_COMPLETE',json.dumps(report),flush=True)
if __name__=='__main__':main()
