import os
import copy,json,re,shutil,sys
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import parser_only,clausewitz,one,values
pdx=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));mod=R/'UMA-V7';models=mod/'gfx/models/portraits/uma';index=json.loads((R/'HeadSources/Export/head-export-index.json').read_text());records=[]
body=clausewitz((models/'0001/uma_0001_body_base.asset').read_text());head=clausewitz((models/'0001/uma_0001_head_female.asset').read_text());keys={one(s,'name')for t in [body,head]for e in values(t,'entity')for s in values(e,'state')}
def register(row):
    if not row['present']:return
    actor=row['actor'];element=row['element'];variant=row.get('variant','base');prefix='uma_'+actor+'_'+element+'_'+variant;dst=models/actor;dst.mkdir(exist_ok=True);source=Path(row['mesh_path']);tree=pdx.read_meshfile(str(source));obj=tree.find('object')[0];obj.tag=prefix+'Shape';mesh=obj.find('mesh');mat=mesh.find('material');refs={}
    for k,suffix in [('diff','diffuse'),('n','normal'),('spec','properties')]:
        old=mat.attrib[k][0];src=source.parent/old
        if not src.is_file():
            # DDS sources can be explicit paths in the component delivery.
            src=Path(row.get('textures',{}).get(k,str(src)))
        if not src.is_file():raise FileNotFoundError(src)
        name=prefix+'_'+suffix+'.dds';shutil.copy2(src,dst/name);refs[k]=name
    mat.attrib={'shader':[row['shader']],'diff':[refs['diff']],'n':[refs['n']],'spec':[refs['spec']]};pdx.write_meshfile(str(dst/(prefix+'.mesh')),tree)
    asset='pdxmesh = {\n\tname = "'+prefix+'_mesh"\n\tfile = "'+prefix+'.mesh"\n\tstreaming = Never\n\n\tmeshsettings = {\n\t\tname = "'+prefix+'Shape"\n\t\tindex = 0\n'
    for k,label in [('diff','texture_diffuse'),('n','texture_normal'),('spec','texture_specular')]:asset+='\t\t'+label+' = "'+refs[k]+'"\n'
    ssao=source.parent/(row.get('texture_prefix',source.stem)+'_ssao.dds');assert ssao.is_file(),ssao;ssaoname=prefix+'_ssao.dds';shutil.copy2(ssao,dst/ssaoname)
    asset+='\t\ttexture = { file = "'+ssaoname+'" index = 3 }\n\t\tshader = "'+row['shader']+'"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n';clips=row.get('animations',[])
    for clip in clips:
        src=Path(clip.get('file',clip.get('path','')))
        if not src.is_absolute():src=source.parent/src
        if not src.is_file():raise FileNotFoundError(src)
        folder=models/'animation'/('tail'if element=='tail'else'ear');folder.mkdir(exist_ok=True);animname=prefix+'_'+clip['state']+'.anim';shutil.copy2(src,folder/animname);asset+='\tanimation = { id = "'+clip['state']+'"\t\t\ttype = "../animation/'+folder.name+'/'+animname+'" }\n'
    asset+='}\n\nentity = {\n\tname = "'+prefix+'_entity"\n\tpdxmesh = "'+prefix+'_mesh"\n\tgame_data = {\n\t\tportrait_entity_user_data = {\n\t\t\tcolor_mask_remap_interval = { interval = { 0.0 1.0 } }\n\t\t}\n\t}\n'
    if clips:
        asset+='\tdefault_state = "idle"\n'
        for key in sorted(keys|{'idle','idle_entry','frontEnd_middle_entry'}):
            animation=key if key in ['idle_entry','frontEnd_middle_entry']else'idle';entry=key.endswith('_entry');asset+='\tstate = { name = "'+key+'"\t\tanimation = "'+animation+'" looping = '+('no next_state = "idle"'if entry else'yes')+' }\n'
    asset+='}\n';(dst/(prefix+'.asset')).write_text(asset,encoding='utf8');record={'actor':actor,'element':element,'variant':variant,'prefix':prefix,'entity':prefix+'_entity','accessory_id':'uma_'+actor+'_'+element+'_'+variant,'gene':'uma_'+element,'template':'uma_'+actor+'_'+element+'_'+variant,'present':True,'optional':row.get('optional_expression_overlay',False),'node':row.get('attachment_node'),'shared_pose':row.get('shared_pose_entity'),'mesh':str(dst/(prefix+'.mesh')),'vertices':len(mesh.attrib['p'])//3,'triangles':len(mesh.attrib['tri'])//3,'bones':len(obj.find('skeleton'))};records.append(record)
for actor in index['heads']:
    delivery=json.loads(Path(actor['delivery_json']).read_text())
    for row in delivery['components']:register(row)
patchfile=R/'HeadSources/NeckPatch/neck-patch-delivery.json'
if patchfile.exists():
    for row in json.loads(patchfile.read_text())['rows']:
        if not any(r['actor']==row['actor']and r['variant']==row['variant']and r['element']==row['element']for r in records):register(row)
neckfile=R/'HeadSources/NeckBridge/neck-delivery.json'
if neckfile.exists():
    neck=json.loads(neckfile.read_text())
    for row in neck.get('components',neck.get('rows',[])):
        row=dict(row,present=True,mesh_path=row.get('mesh_path',row.get('mesh')),shared_pose_entity=row.get('shared_pose_entity',row.get('shared_pose','head')));register(row)
for tailfile in sorted((R/'HeadSources/Export').glob('tail_*/tail-delivery.json')):
    row=json.loads(tailfile.read_text());row.update(present=True,variant='base');register(row)
(R/'Reports/head-registration.json').write_text(json.dumps(records,indent=2),encoding='utf8');print('HEAD_PARTS_REGISTERED',len(records),flush=True)
