from pathlib import Path
from paths_v10 import REPO
src=REPO/'Tools/NativeAccessories/v9';dst=Path(__file__).resolve().parent
def adapt(s):
    s=s.replace('from paths_v9 import ROOT,MOD,REPO,PLUGIN,V8','from paths_v10 import ROOT,MOD,REPO,PLUGIN,V9\nV8=V9')
    s=s.replace('from paths_v9 import ROOT,MOD,REPO,V8','from paths_v10 import ROOT,MOD,REPO,V9\nV8=V9')
    s=s.replace('from paths_v9 import ROOT,MOD,REPO,GAME,PLUGIN,V8','from paths_v10 import ROOT,MOD,REPO,GAME,PLUGIN,V9\nV8=V9')
    s=s.replace('from paths_v9 import ROOT,MOD,REPO,PLUGIN','from paths_v10 import ROOT,MOD,REPO,PLUGIN')
    s=s.replace('from paths_v9 import ROOT,MOD,REPO','from paths_v10 import ROOT,MOD,REPO')
    s=s.replace('assembly_math_v9','assembly_math_v10').replace('V9_','V10_')
    return s
for name in ['validate','assembly_math','assembly','prepare_preview','sdk_verify']:
    suffix='_blender'if name in ['assembly','sdk_verify']else''
    source=src/f'{name}_v9{suffix}.py';s=adapt(source.read_text());
    if name=='sdk_verify':
        start=s.index('modules=[');stop=s.index('\nfor module,file in modules:',start)
        s=s[:start]+"modules=[('body',MOD/'gfx/models/portraits/uma/0001/uma_0001_body_base.mesh'),('head',MOD/'gfx/models/portraits/uma/0001/uma_0001_head_female.mesh'),('heel',MOD/'gfx/models/portraits/uma/0001/uma_0001_body_base.mesh')]"+s[stop:]
        s=s.replace("clip=MOD/f'gfx/models/portraits/uma/animation/{clip_module}/uma_{clip_module}_native_idle.anim';", "clip=MOD/'gfx/models/portraits/uma/animation/body/uma_heel_1001_idle.anim'if module=='heel'else MOD/f'gfx/models/portraits/uma/animation/{clip_module}/uma_{clip_module}_native_idle.anim';")
        s=s.replace("for actor in ['1001','1002']:\n    file=MOD/f'gfx/models/portraits/uma/{actor}/uma_{actor}_clothes_00_base.mesh'", "for hat in ['08','09']:\n    load(MOD/f'gfx/models/portraits/uma/0001/uma_0001_headwear_0008_{hat}_00_base.mesh')\nfor actor in ['1001','1002']:\n    file=MOD/f'gfx/models/portraits/uma/{actor}/uma_{actor}_clothes_00_base.mesh'")
    (dst/f'{name}_v10{suffix}.py').write_text(s,encoding='utf8')
print('V10_CHECKS_PREPARED',flush=True)
