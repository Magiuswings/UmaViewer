"""Verification/package runner for an already staged V8 and its local dependencies."""
import argparse,os,subprocess,sys
from pathlib import Path
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['verify','package'],default='verify');ap.add_argument('--root',default='E:/UmaViewer-Exports/2026-10-12-UMA-V8');ap.add_argument('--repo',default='E:/UmaViewer-Workspace/UmaViewer-source');ap.add_argument('--plugin',default='E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');ap.add_argument('--game',default='D:/steam/steamapps/common/Crusader Kings III/game');ap.add_argument('--blender');a=ap.parse_args();root=Path(a.root).resolve();scripts=Path(__file__).resolve().parent;temp=root/'.temp';temp.mkdir(exist_ok=True);env=os.environ.copy();env.update(UMA_V8_ROOT=str(root),UMA_REPO=a.repo,UMA_PLUGIN=a.plugin,CK3_GAME=a.game,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TEMP=str(temp),TMP=str(temp))
    names=['validate_v8.py','assembly_math_v8.py','body_motion_check_v8.py']if a.mode=='verify'else['package_v8.py']
    for name in names:subprocess.run([sys.executable,'-X','utf8','-B',str(scripts/name)],env=env,check=True)
    if a.mode=='verify'and a.blender:
        for name in ['sdk_verify_v8_blender.py','assembly_v8_blender.py']:subprocess.run([a.blender,'--background','--factory-startup','--python-exit-code','1','--python',str(scripts/name)],env=env,check=True)
if __name__=='__main__':main()
