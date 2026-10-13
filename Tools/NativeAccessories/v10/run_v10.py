import argparse,os,subprocess,sys
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['verify','package'],default='verify');p.add_argument('--root',default='E:/UmaViewer-Exports/2026-10-13-UMA-V10');p.add_argument('--blender');a=p.parse_args();root=Path(a.root);code=Path(__file__).resolve().parent;env=dict(os.environ,UMA_V10_ROOT=str(root),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TEMP=str(root/'Temp'),TMP=str(root/'Temp'))
    def py(name):subprocess.run([sys.executable,'-X','utf8','-B',str(code/name)],env=env,check=True)
    if a.mode=='verify':
        for name in ['validate_v10.py','extra_validation_v10.py','assembly_math_v10.py']:py(name)
        if a.blender:
            py('prepare_preview_v10.py')
            for name in ['sdk_verify_v10_blender.py','assembly_v10_blender.py']:
                with(root/'Reports'/(Path(name).stem+'.log')).open('w',encoding='utf8')as f:subprocess.run([a.blender,'--background','--factory-startup','--python-exit-code','1','--python',str(code/name)],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    else:py('package_v10.py')
if __name__=='__main__':main()
