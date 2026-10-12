"""Keep V7 immutable; normalise actual binary structures and accessory BS."""
import sys,json,shutil,copy
from pathlib import Path
from paths_v8 import ROOT,V7,REPO,PLUGIN,MOD
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
P=parser_only(PLUGIN);ROOT.mkdir(exist_ok=True);(ROOT/'Reports').mkdir(exist_ok=True)
source=V7/'UMA-V7';modelbase=source/'gfx/models/portraits/uma'
def ignore(folder,names):return ['animation']if Path(folder)==modelbase and'animation'in names else []
if not MOD.exists():shutil.copytree(source,MOD,ignore=ignore)
for group in ['head','body','ear','tail']:(MOD/'gfx/models/portraits/uma/animation'/group).mkdir(parents=True,exist_ok=True)
for name in ['configuration.json','head-registration.json','clothing-registration.json','palette-presets.json','source-skin-color-table.json']:
    txt=(V7/'Reports'/name).read_text(encoding='utf8').replace(str(source),str(MOD)).replace(source.as_posix(),MOD.as_posix());(ROOT/'Reports'/name).write_text(txt,encoding='utf8')
if not(ROOT/'Database').exists():shutil.copytree(V7/'Database',ROOT/'Database')
bs=set()
assets=[]
for file in(MOD/'gfx').rglob('*.asset'):
    tree=clausewitz(file.read_text(encoding='utf-8-sig'));assets.append((file,tree))
    for mesh in values(tree,'pdxmesh'):
        for target in values(mesh,'blend_shape'):
            name=one(target,'type');bs.add((file.parent/name).resolve())
records=[]
for number,file in enumerate((MOD/'gfx').rglob('*.mesh'),1):
    data=P.read_meshfile(str(file));target=file.resolve()in bs;body=file.name.startswith('uma_0001_body_');before=[]
    for obj in data.find('object'):
        before.append([x.tag for x in obj]);obj.tag=obj.tag.removesuffix('Shape')
        # Original working files serialise all meshes before the skeleton.
        children=list(obj);obj[:]=[x for x in children if x.tag=='mesh']+[x for x in children if x.tag!='mesh']
        if target and not body:
            for sk in obj.findall('skeleton'):obj.remove(sk)
            for mesh in obj.findall('mesh'):
                for skin in mesh.findall('skin'):mesh.remove(skin)
    P.write_meshfile(str(file),data);records.append({'file':file.relative_to(MOD).as_posix(),'bs':target,'body':body,'accessory_bs_skeleton_and_skin_removed':target and not body,'before_child_order':before,'after_child_order':[[x.tag for x in obj]for obj in data.find('object')],'object_names':[o.tag for o in data.find('object')]})
    if number%100==0:print('SCHEMA_NORMALISED',number,flush=True)
for file,tree in assets:
    for mesh in values(tree,'pdxmesh'):
        for settings in values(mesh,'meshsettings'):
            settings[:]=[(k,v.removesuffix('Shape')if k=='name'else v)for k,v in settings]
    file.write_text(script_block(tree)+'\n',encoding='utf8')
# Shape naming and binary ordering are rewritten together. Animation and
# genetic registration are generated in subsequent steps, never guessed here.
(ROOT/'Reports/binary-normalization.json').write_text(json.dumps(records,indent=2),encoding='utf8')
print('V8_STAGED',len(records),'binary files',sum(r['accessory_bs_skeleton_and_skin_removed']for r in records),'lean BS',flush=True)
