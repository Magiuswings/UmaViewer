import os
"""Headless V7 registration, verification and release over staged source data."""
import argparse,os,subprocess,sys
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['register','verify','package','all'],default='verify')
    for key in ['root','repo','game','plugin']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--v6-root',type=Path,default=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')))));p.add_argument('--canonical',type=Path,default=Path(str(Path(os.environ.get('UMA_V7_CANONICAL','E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3')))));p.add_argument('--skin-colors',type=Path);a=p.parse_args();folder=Path(__file__).resolve().parent;env=os.environ.copy()
    env.update(UMA_V7_ROOT=str(a.root.resolve()),UMA_V7_REPO=str(a.repo.resolve()),UMA_V7_GAME=str(a.game.resolve()),UMA_V7_PLUGIN=str(a.plugin.resolve()),UMA_V6_INPUT=str(a.v6_root.resolve()),UMA_V7_CANONICAL=str(a.canonical.resolve()),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    if a.skin_colors:env['UMA_V7_SKIN_COLORS']=str(a.skin_colors.resolve())
    scratch=a.root/'.temp';scratch.mkdir(parents=True,exist_ok=True);runtime=a.root/'runtime';runtime.mkdir(exist_ok=True);logs=a.root/'Logs';logs.mkdir(exist_ok=True);env.update(TEMP=str(scratch),TMP=str(scratch),TMPDIR=str(scratch),APPDATA=str(runtime/'AppData'),LOCALAPPDATA=str(runtime/'LocalAppData'))
    def step(name):
        file=folder/name;assert file.is_file(),file;print('RUN',name,flush=True)
        with(logs/file.with_suffix('.log').name).open('w',encoding='utf8')as log:subprocess.run([sys.executable,'-X','utf8','-B',str(file)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    if a.mode in ['register','all']:
        assert(a.root/'HeadSources/Export/head-export-index.json').is_file();assert(a.root/'ClothingParts/clothing-registration.json').is_file();assert(a.root/'HeadSources/NeckBridge/neck-delivery.json').is_file(),'Complete the neck surface bridge first'
        for name in ['stage_mod.py','integrate_heads.py','integrate_clothes.py','palettes.py','neutralize_skin.py','configure_mod.py']:step(name)
    if a.mode in ['verify','all']:
        for name in ['body_qa.py','validate_mod.py']:step(name)
    if a.mode in ['package','all']:step('package_v7.py')
    print('V7_WORKFLOW_COMPLETE',a.mode,flush=True)
if __name__=='__main__':main()
