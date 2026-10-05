"""Package program source and private local Blender outputs separately."""
from pathlib import Path
import sys
import zipfile

here=Path(__file__).resolve().parent
output=Path(sys.argv[1]).resolve()
program=output.parent/"UmaViewer_HeadlessExporter.zip"
models=output.parent/(output.name+"-Blender-Exports.zip")
files=["export_assets.py","headless_blender.py","math3d.py","segmentation.py","verify_exports.py","preview_exports.py","preview_segmentation.py","requirements.txt","README.md","run.cmd","inspect_assets.py"]
core=here.parents[1]/"Assets/StreamingAssets/Blender/uma_blender_import.py"
with zipfile.ZipFile(program,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name in files: archive.write(here/name,name)
    archive.write(core,"uma_blender_import.py")
with zipfile.ZipFile(models,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for file in sorted(output.rglob("*")):
        if file.is_file(): archive.write(file,file.relative_to(output).as_posix())
print(str(program),program.stat().st_size)
print(str(models),models.stat().st_size)
