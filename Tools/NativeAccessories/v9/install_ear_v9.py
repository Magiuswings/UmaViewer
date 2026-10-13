import sys,json,copy,shutil
from pathlib import Path
from paths_v9 import ROOT,MOD,REPO,V8,PLUGIN
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v8')]
from build_ck3_mod import parser_only,clausewitz,one,values
from configure_assets_v8 import render
from merge_head_v9 import asset_mesh,row,basename_material
P=parser_only(PLUGIN)
def main():
    # Refresh the cropped hat while keeping its actual material and no-own-motion definition.
    source=ROOT/'RigRepair/StaticHeadwear/1002/uma_1002_headwear_00.mesh';file=MOD/'gfx/models/portraits/uma/1002/uma_1002_headwear_00.mesh';t=P.read_meshfile(str(source));basename_material(t);P.write_meshfile(str(file),t);file.with_suffix('.asset').write_text(render(asset_mesh(file,file.stem))+'\n',encoding='utf8')
    source=ROOT/'RigRepair/SeparatedEar/1002/uma_1002_ear_00.mesh';file=MOD/'gfx/models/portraits/uma/1002/uma_1002_ear_00.mesh';t=P.read_meshfile(str(source));basename_material(t);catalog={f.name:f for f in(MOD/'gfx').rglob('*.dds')}
    for m in t.iter('material'):
        m.set('diff',['uma_1002_hair_00_diffuse.dds']);m.set('spec',['uma_0001_shared_p00_properties.dds']);m.set('ssao',['uma_0001_shared_s00_ssao.dds'])
    normal=source.with_name('uma_1002_ear_00_normal.dds');shutil.copy2(normal,file.with_name(normal.name));P.write_meshfile(str(file),t)
    tree=asset_mesh(file,file.stem);pm=one(tree,'pdxmesh');pm.insert(3,('import',[('type','skeletal_animation_set'),('name','uma_native_ear')]))
    previous=clausewitz(file.with_name('uma_1002_ear_30.asset').read_text(encoding='utf-8-sig'));entity=copy.deepcopy(one(previous,'entity'));entity[:]=[(k,file.stem+'_entity'if k=='name'else file.stem+'_mesh'if k=='pdxmesh'else v)for k,v in entity];tree=[('pdxmesh',pm),('entity',entity)];file.with_suffix('.asset').write_text(render(tree)+'\n',encoding='utf8')
    pf=ROOT/'Reports/head-registration.json';rows=json.loads(pf.read_text());rows=[r for r in rows if not(r['actor']=='1002'and r['element']=='ear'and r['variant']=='00')];rows.append(row('1002','ear','00',file.stem,file,'bn_h_head',None))
    for r in rows:
        if r['actor']=='1002'and r['element']=='headwear'and r['variant']=='00':r.update(vertices=319,triangles=397)
    pf.write_text(json.dumps(rows,indent=2),encoding='utf8')
    file=MOD/'gfx/models/portraits/uma/0001/uma_0001_head_male.mesh';t=P.read_meshfile(str(file));t.find('object')[0].tag='uma_0001_head_male';P.write_meshfile(str(file),t);print('NEW1002_EAR_INSTALLED',flush=True)
if __name__=='__main__':main()
