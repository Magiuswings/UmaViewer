"""Package only validated V8 files; original game files, V7 and raw caches are untouched."""
import sys,json,shutil,hashlib,zipfile
from pathlib import Path
from paths_v8 import ROOT,MOD,REPO
CODE=Path(__file__).resolve().parent
def sha(file):
    h=hashlib.sha256()
    with file.open('rb')as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def zipfiles(file,entries):
    with zipfile.ZipFile(file,'w',zipfile.ZIP_DEFLATED,compresslevel=4)as z:
        for f,n in entries:z.write(f,n)
    with zipfile.ZipFile(file)as z:assert z.testzip()is None
    return dict(file=str(file),bytes=file.stat().st_size,sha256=sha(file))
def main():
    for report in ['final-static-validation','native-attachment-validation','body-native-motion','blender-sdk-native-validation','blender-native-assembly']:
        data=json.loads((ROOT/f'Reports/{report}.json').read_text());assert data['passed'],report
    sdk=json.loads((ROOT/'Reports/blender-sdk-native-validation.json').read_text())
    for m in sdk['modules']:
        assert sha(Path(m['mesh']))==m['mesh_sha256'];assert sha(Path(m['animation']))==m['animation_sha256']
    code=ROOT/'Code';code.mkdir(exist_ok=True)
    for f in CODE.iterdir():
        if f.suffix in ['.py','.md']:shutil.copy2(f,code/f.name)
    for dep in [REPO/'Tools/PDXExporter/build_ck3_mod.py',REPO/'Tools/NativeBody/test_vanilla_body_animation_blender.py',REPO/'Tools/NativeAccessories/v7/head_assembly_math.py']:shutil.copy2(dep,code/dep.name)
    if(CODE/'README.md').exists():shutil.copy2(CODE/'README.md',ROOT/'README.md')
    desc='name="UMA V8 Native Modules"\nsupported_version="1.20.*"\n';(MOD/'descriptor.mod').write_text(desc,encoding='utf8');(ROOT/'UMA-V8.mod').write_text(desc+'path="'+MOD.as_posix()+'"\n',encoding='utf8')
    files=[(f,'UMA-V8/'+f.relative_to(MOD).as_posix())for f in MOD.rglob('*')if f.is_file()]+[(ROOT/'UMA-V8.mod','UMA-V8.mod')]
    modzip=zipfiles(ROOT/'UMA-V8-1001-1002-Mod.zip',files);entries=files+[(f,f.relative_to(ROOT).as_posix())for folder in ['Code','Database','Reports','Rigs','Editable','Preview']for f in(ROOT/folder).rglob('*')if f.is_file()]
    for name in ['native-source-local-frames.npz','native-source-local-index.json','native-animation-delivery.json','retarget-formula-numerical-proof.json','independent-rig-validation.json','native-motion-validation.json','allframes-head-body-attachment.json','body-native-skin-allframes.json','flatfoot-heel-forefoot-allframes.json']:
        f=ROOT/'MotionSources'/name
        if f.exists():entries.append((f,f.relative_to(ROOT).as_posix()))
    if(ROOT/'README.md').exists():entries.append((ROOT/'README.md','README.md'))
    projectzip=zipfiles(ROOT/'UMA-V8-1001-1002-Project.zip',entries);textures=json.loads((ROOT/'Reports/texture-sharing.json').read_text());bs=json.loads((ROOT/'Reports/accessory-bs-size-savings.json').read_text());report=dict(mod_archive=modzip,project_archive=projectzip,mod_files=len(files)-1,mod_uncompressed_bytes=sum(f.stat().st_size for f,n in files[:-1]),DDS_net_bytes_saved=textures['net_bytes_saved'],accessory_BS_net_bytes_saved=bs['net_bytes_saved'],combined_net_bytes_saved=textures['net_bytes_saved']+bs['net_bytes_saved'],runtime_CK3_executed=False,Blender4_2_SDK_and_native_assembly_passed=True,original_game_and_V7_untouched=True)
    (ROOT/'release-manifest.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V8_RELEASE_COMPLETE',json.dumps(report),flush=True)
if __name__=='__main__':main()
