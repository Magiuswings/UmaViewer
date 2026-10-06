"""Package verified private assets separately from redistributable exporter source."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE=Path(__file__).resolve().parent

def main():
    out=Path(sys.argv[1]).resolve()
    verification=json.loads((out/'verification.json').read_text(encoding='utf8'))
    if verification.get('passed') is not True:raise SystemExit('Refusing to package an unverified model export')
    program=out.parent/'UmaViewer-PDX-Blender42-Tools.zip'
    assets=out.parent/'UmaViewer-PDX-Blender42-Models.zip'
    core=HERE/'uma_blender_import.py'
    if not core.exists():core=HERE.parents[1]/'Assets/StreamingAssets/Blender/uma_blender_import.py'
    with zipfile.ZipFile(program,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in sorted(HERE.iterdir()):
            if file.is_file() and file.suffix in ('.py','.md','.cmd','.txt'):
                archive.write(file,'PDXExporter/'+file.name)
        archive.write(core,'PDXExporter/uma_blender_import.py')
        headless=HERE.parent/'HeadlessExporter'
        if headless.is_dir():
            for file in sorted(headless.iterdir()):
                if file.is_file() and file.suffix in ('.py','.md','.cmd','.txt'):
                    archive.write(file,'HeadlessExporter/'+file.name)
            archive.write(core,'HeadlessExporter/uma_blender_import.py')
    with zipfile.ZipFile(assets,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in sorted(out.rglob('*')):
            if not file.is_file():continue
            relative=file.relative_to(out)
            if any(p.startswith('.') for p in relative.parts):continue
            archive.write(file,relative.as_posix())
    results=[]
    for file in (program,assets):
        with zipfile.ZipFile(file) as archive:
            error=archive.testzip()
            if error:raise ValueError('ZIP CRC failure: '+error)
            results.append(dict(path=str(file),bytes=file.stat().st_size,entries=len(archive.namelist()),
                                sha256=hashlib.sha256(file.read_bytes()).hexdigest(),crc_passed=True))
    (out.parent/'packages.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    for result in results:print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
