"""Repeat final binary verification / packaging; no game launch is claimed."""
import argparse,os,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['verify','package'],default='verify')
    p.add_argument('--root',default='E:/UmaViewer-Exports/2026-10-13-UMA-V9')
    p.add_argument('--repo',default='E:/UmaViewer-Workspace/UmaViewer-source')
    p.add_argument('--plugin',default='E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')
    p.add_argument('--game',default='D:/steam/steamapps/common/Crusader Kings III/game')
    p.add_argument('--blender')
    a=p.parse_args();root=Path(a.root).resolve();code=Path(__file__).resolve().parent
    env=dict(os.environ,UMA_V9_ROOT=str(root),UMA_REPO=a.repo,UMA_PLUGIN=a.plugin,CK3_GAME=a.game,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TEMP=str(root/'Temp'),TMP=str(root/'Temp'))
    (root/'Temp').mkdir(exist_ok=True);(root/'Reports').mkdir(exist_ok=True)
    def py(name):subprocess.run([sys.executable,'-X','utf8','-B',str(code/name)],env=env,check=True)
    if a.mode=='verify':
        py('validate_v9.py');py('assembly_math_v9.py');py('final_audit_v9.py')
        if a.blender:
            py('prepare_preview_v9.py')
            for name in ['sdk_verify_v9_blender','assembly_v9_blender']:
                with(root/'Reports'/f'{name}.log').open('w',encoding='utf8')as f:
                    subprocess.run([a.blender,'--background','--factory-startup','--python-exit-code','1','--python',str(code/(name+'.py'))],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    else:py('package_v9.py')
if __name__=='__main__':main()
