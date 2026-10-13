"""One head asset per actor, common bind space, single character core independent of costume."""
import sys,json,copy,shutil,hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from paths_v9 import ROOT,MOD,REPO,V8,PLUGIN
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v8')]
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
from configure_assets_v8 import render
P=parser_only(PLUGIN);INDEX=json.loads((ROOT/'RigRepair/ready-components-index.json').read_text());OLD=json.loads((ROOT/'Reports/head-registration.json').read_text());DATA=INDEX['head_components'];REPORT=[]
def save_tree(file,tree):file.write_text(render(tree)+'\n',encoding='utf8')
def basename_material(tree):
    for mat in tree.iter('material'):
        for k,v in list(mat.attrib.items()):mat.set(k,[Path(a.replace('\\','/')).name if isinstance(a,str)and a.endswith('.dds')else a for a in v])
def asset_mesh(path,name):
    tree=P.read_meshfile(str(path));nodes=[]
    for ob in tree.find('object'):
        for mi,m in enumerate(ob.findall('mesh')):
            mat=m.find('material');settings=[('name',ob.tag),('index',str(mi)),('texture_diffuse',mat.get('diff')[0]),('texture_normal',mat.get('n')[0]),('texture_specular',mat.get('spec')[0])]
            if mat.get('ssao'):settings.append(('texture',[('file',mat.get('ssao')[0]),('index','3')]))
            settings += [('shader',mat.get('shader')[0]),('shader_file','gfx/FX/uma_portrait.shader')];nodes.append(('meshsettings',settings))
    pm=[('name',name+'_mesh'),('file',path.name),('streaming','Never')]+nodes
    entity=[('name',name+'_entity'),('pdxmesh',name+'_mesh'),('game_data',[('portrait_entity_user_data',[('color_mask_remap_interval',[('interval',[(None,'0.0'),(None,'1.0')])])])])]
    return [('pdxmesh',pm),('entity',entity)]
def row(actor,element,variant,prefix,file,node=None,shared='head',optional=False):
    t=P.read_meshfile(str(file));obs=t.find('object');return dict(actor=actor,element=element,variant=variant,prefix=prefix,entity=prefix+'_entity',accessory_id=prefix,gene='uma_'+element,template=prefix,present=True,optional=optional,node=node,shared_pose=shared,mesh=str(file),vertices=sum(len(m.get('p'))//3 for o in obs for m in o.findall('mesh')),triangles=sum(len(m.get('tri'))//3 for o in obs for m in o.findall('mesh')),bones=len(obs[0].find('skeleton')),version='V9')
def main():
    headsk=P.read_meshfile(INDEX['common245_carriers'][0]).find('object')[0].find('skeleton');newrows=[];paths=set();sources=[]
    for sex,source in zip(['female','male'],INDEX['common245_carriers']):
        file=MOD/f'gfx/models/portraits/uma/0001/uma_0001_head_{sex}.mesh';t=P.read_meshfile(source);t.find('object')[0].tag=f'uma_0001_head_{sex}';basename_material(t);P.write_meshfile(str(file),t)
    shutil.copy2(INDEX['head_clip'],MOD/'gfx/models/portraits/uma/animation/head/uma_head_native_idle.anim')
    for actor in ['1001','1002']:
        folder=MOD/f'gfx/models/portraits/uma/{actor}';prefix=f'uma_{actor}_head_00';file=folder/(prefix+'.mesh');tree=ET.Element('File',{'pdxasset':[1,0]});obj=ET.SubElement(ET.SubElement(tree,'object'),prefix,{'lod':[0]});slots=[]
        for part,var in [('face','80'),('face_parts','80'),('neck_patch','80'),('neck','base')]:
            src=next(r for r in DATA if r['actor']==actor and r['element']==part and r['variant']==var);raw=P.read_meshfile(src['mesh']);sources.append(src['source_mesh']);
            for ob in raw.find('object'):
                assert [b.tag for b in ob.find('skeleton')]==[b.tag for b in headsk]
                for m in ob.findall('mesh'):obj.append(copy.deepcopy(m));slots.append(dict(element=part,source=src['mesh'],index=len(slots)))
        obj.append(copy.deepcopy(headsk));basename_material(tree);P.write_meshfile(str(file),tree);newrows.append(row(actor,'head','00',prefix,file));paths.add(file);asset=asset_mesh(file,prefix)
        # Expression overlays share this asset; keep optional activation instead of making opaque white tears permanent.
        for part in ['cheek','tear']:
            src=next(r for r in DATA if r['actor']==actor and r['element']==part and r['variant']=='80');pfx=f'uma_{actor}_{part}_00';pf=folder/(pfx+'.mesh');t=P.read_meshfile(src['mesh']);t.find('object')[0].tag=pfx;basename_material(t);P.write_meshfile(str(pf),t);asset+=asset_mesh(pf,pfx);newrows.append(row(actor,part,'00',pfx,pf,optional=True));paths.add(pf)
        af=folder/(prefix+'.asset');save_tree(af,asset);REPORT.append(dict(actor=actor,canonical_variant='80',head_asset=str(af),core_mesh=str(file),core_parts=slots,expression_overlays_same_asset=True,core_vertices=newrows[-3]['vertices'],head_assets_per_actor=1,costume_duplicates_removed=True))
        for part in ['eye','brow']:
            src=next(r for r in DATA if r['actor']==actor and r['element']==part and r['variant']=='80');pfx=f'uma_{actor}_{part}_00';pf=folder/(pfx+'.mesh');t=P.read_meshfile(src['mesh']);t.find('object')[0].tag=pfx;basename_material(t);P.write_meshfile(str(pf),t);save_tree(pf.with_suffix('.asset'),asset_mesh(pf,pfx));newrows.append(row(actor,part,'00',pfx,pf));paths.add(pf)
        for src in DATA:
            if src['actor']!=actor or src['element']!='hair':continue
            pf=folder/(src['prefix']+'.mesh');t=P.read_meshfile(src['mesh']);basename_material(t);P.write_meshfile(str(pf),t);save_tree(pf.with_suffix('.asset'),asset_mesh(pf,src['prefix']));newrows.append(row(actor,'hair',src['variant'],src['prefix'],pf));paths.add(pf)
    for src in INDEX['headwear_components']:
        pfx=Path(src['mesh']).stem;pf=MOD/f"gfx/models/portraits/uma/{src['actor']}/{pfx}.mesh";t=P.read_meshfile(src['mesh']);basename_material(t);P.write_meshfile(str(pf),t);save_tree(pf.with_suffix('.asset'),asset_mesh(pf,pfx));newrows.append(row(src['actor'],'headwear',src['variant'],pfx,pf,'bn_h_head',None));paths.add(pf)
    for old in OLD:
        if old['element']not in ['ear','tail']:continue
        r=copy.deepcopy(old);r['node']='body_root'if r['element']=='tail'else'bn_h_head';r['version']='V9';newrows.append(r);paths.add(Path(r['mesh']))
    removed=[]
    for old in OLD:
        oldfile=Path(old['mesh']);oldasset=oldfile.with_suffix('.asset')
        if oldfile not in paths:
            if oldfile.exists():oldfile.unlink();removed.append(str(oldfile))
            if oldasset.exists():oldasset.unlink();removed.append(str(oldasset))
        elif old['element']in ['cheek','tear']and oldasset.exists():oldasset.unlink();removed.append(str(oldasset))
    # Imported animation sets apply only to carrier, ears and tails. Static headwear has no state or own motion.
    for af in(MOD/'gfx').rglob('*.asset'):
        t=clausewitz(af.read_text(encoding='utf-8-sig'))
        for pm in values(t,'pdxmesh'):
            f=one(pm,'file')if values(pm,'file')else None
            if f and f.startswith(('uma_1001_headwear','uma_1002_headwear')):
                pm[:]=[(k,v)for k,v in pm if k not in ['import','animation','additive_animation']]
        save_tree(af,t)
    (ROOT/'Reports/head-registration.json').write_text(json.dumps(newrows,indent=2),encoding='utf8');(ROOT/'Reports/head-merge.json').write_text(json.dumps(dict(actors=REPORT,removed_old_files=removed,neck_independent_removed=True,common_head_bones=245,canonical_geometry_preserved_except_bridge_lower_rebase=True,headwear_own_animation=False),indent=2),encoding='utf8');print('V9_HEAD_MERGED',len(newrows),len(removed),flush=True)
if __name__=='__main__':main()
