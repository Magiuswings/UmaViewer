"""Bounded, UI-free 1001 build/verification driver over staged source snapshots."""
import argparse,os,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['head','clothing','all','verify','package'],default='verify')
    for key in ['root','repo','plugin','game','blender']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--canonical',type=Path,default=Path(os.environ.get("UMA_V6_CANONICAL", "E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3")));a=p.parse_args();folder=Path(__file__).resolve().parent
    assert (a.root/'v5').is_dir(),'Stage the supplied v5 input first'
    assert a.blender.is_file()and a.plugin.is_dir()and a.game.is_dir()
    env=os.environ.copy();env.update(UMA_V6_ROOT=str(a.root),UMA_V6_REPO=str(a.repo),UMA_V6_PLUGIN=str(a.plugin),UMA_V6_GAME=str(a.game),UMA_V6_CANONICAL=str(a.canonical),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    scratch=a.root/'.temp';scratch.mkdir(exist_ok=True);env.update(TEMP=str(scratch),TMP=str(scratch),TMPDIR=str(scratch))
    runtime=a.root/'runtime';runtime.mkdir(exist_ok=True);env.update(APPDATA=str(runtime/'AppData'),LOCALAPPDATA=str(runtime/'LocalAppData'))
    logs=a.root/'Logs';logs.mkdir(exist_ok=True)
    args=['--root',str(a.root),'--repo',str(a.repo),'--plugin',str(a.plugin),'--game',str(a.game)]
    def step(name,blender=False,options=()):
        file=folder/name;assert file.is_file();cmd=([str(a.blender),'--background','--factory-startup','--python-exit-code','1','--python',str(file),'--']if blender else[sys.executable,'-X','utf8','-B',str(file)])+list(options)
        print('RUN',name,flush=True)
        with (logs/(file.stem+'.log')).open('w',encoding='utf8')as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    if a.mode in ['head','all']:
        for f in ['parsed/head.json','parsed/tail.json','native-motion-frames.npz','native-motion-index.json']:assert (a.root/f).is_file(),f
        step('prepare_v6.py',options=args[:4]);step('motion_build.py');step('motion_blender_verify.py',True);step('motion_finalize.py');step('export_head_v6.py',True,args[:6]);step('integrate_v6.py',options=args)
    if a.mode in ['clothing','all']:
        assert (a.root/'integration.json').is_file()and a.canonical.is_dir()
        for name,bpy in [('garment_prepare.py',False),('garment_skin_reference.py',False),('garment_source_render.py',True),('garment_refine_blender.py',True),('garment_build_blender.py',True),('garment_update_pdx.py',False),('garment_finish_blend.py',True),('garment_body_clothed.py',True),('garment_normal_audit.py',False),('garment_audit_blender.py',True),('garment_audit_clothed_blender.py',True),('garment_finalize.py',False),('garment_broad_split.py',False)]:step(name,bpy)
        step('integrate_clothing_v6.py',options=args[:6])
    if a.mode in ['all','clothing','verify']:
        step('validate_v6.py',options=args);step('verify_v6_blender.py',True,args);step('verify_full_v6.py',True,args)
    if a.mode=='head':step('validate_v6.py',options=args)
    if a.mode=='package':step('package_v6.py',options=args+['--scripts',str(folder)])
    print('NATIVE_ACCESSORY_WORKFLOW_COMPLETE',a.mode,flush=True)
if __name__=='__main__':main()
