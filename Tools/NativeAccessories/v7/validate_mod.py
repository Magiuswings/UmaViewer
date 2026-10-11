import os
"""Resolve the final V7 registry and audit binary geometry, rigs and clothing BS."""
import hashlib,json,posixpath,re,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));GAME=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game'))));MOD=R/'UMA-V7';OLD=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'UMA-V6-1001'));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import clausewitz,one,values,parser_only
from test_vanilla_body_animation_blender import inverse_bind
pdx=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));resources=[];entities={};meshes={};assets=[];names=defaultdict(list)
def optional(node,k):
    v=values(node,k);return v[0]if v else None
def visit(node,file):
    for k,v in node:
        if isinstance(v,list):visit(v,file)
        elif isinstance(v,str)and v.lower().endswith(('.mesh','.anim','.dds','.shader')):
            rel=v if v.startswith('gfx/')else posixpath.normpath(file.parent.relative_to(MOD).as_posix()+'/'+v)
            assert(MOD/rel).is_file()or(GAME/rel).is_file(),(str(file),v,rel);resources.append(rel)
for file in MOD.rglob('*'):
    if file.is_file()and file.is_relative_to(MOD/'gfx'):names[file.name.casefold()].append(str(file))
    if file.suffix not in ['.asset','.txt']:continue
    content=file.read_text(encoding='utf-8-sig');tree=clausewitz(content);visit(tree,file)
    if file.suffix=='.txt':
        assert file.read_bytes().startswith(b'\xef\xbb\xbf'),file
        assert 'gene_uma_face_identity'not in content
        assert not re.search(r'\bmin\s*=\s*0(?:\.0+)?\s+max\s*=\s*0(?:\.0+)?\b',content),file
        assert not re.search(r'\buma_\w*accessory\w*\b',content),file
    else:
        assets.append(str(file))
        for k,table in [('entity',entities),('pdxmesh',meshes)]:
            for row in values(tree,k):name=one(row,'name');assert name not in table,(file,name);table[name]=row
assert all(len(v)==1 for v in names.values()),{k:v for k,v in names.items()if len(v)>1}
maxpath=max(len(str(f))for f in MOD.rglob('*')if f.is_file());assert maxpath<256,maxpath
group=one(clausewitz((MOD/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig')),'uma')
for kind,age in [('male','minimum_age'),('female','minimum_age'),('boy','maximum_age'),('girl','maximum_age')]:
    branch=one(group,'uma_'+kind);assert one(branch,age)=='18';sex='male'if kind in ['male','boy']else'female';assert one(branch,'head')=='uma_0001_head_'+sex+'_entity'
carriers=[]
for sex in ['male','female']:
    prefix='uma_0001_head_'+sex;obj=pdx.read_meshfile(str(MOD/'gfx/models/portraits/uma/0001'/(prefix+'.mesh'))).find('object')[0];mesh=obj.find('mesh');assert len(mesh.attrib['p'])==9 and len(mesh.attrib['tri'])==3
    old=one(clausewitz((GAME/'gfx/models/portraits'/(sex+'_head')/(sex+'_head.asset')).read_text(encoding='utf-8-sig')),'pdxmesh');decl=meshes[prefix+'_mesh'];assert{one(v,'id')for v in values(old,'blend_shape')}=={one(v,'id')for v in values(decl,'blend_shape')};assert all(one(v,'type')==prefix+'_none.mesh'for v in values(decl,'blend_shape'));carriers.append({'sex':sex,'bones':len(obj.find('skeleton')),'bs':len(values(decl,'blend_shape'))})
binary=[];cache={}
for file in(MOD/'gfx').rglob('*.mesh'):
    data=pdx.read_meshfile(str(file));totalv=totalt=maxbones=0
    for obj in data.find('object'):
        skel=obj.find('skeleton');bone_names=[b.tag for b in skel];assert len(set(bone_names))==len(bone_names)and len(skel)<255,file;maxbones=max(maxbones,len(skel))
        for ix,b in enumerate(skel):assert b.attrib['ix']==[ix]and(not b.attrib.get('pa')or b.attrib['pa'][0]<ix),(file,b.tag,b.attrib)
        inverse=inverse_bind(skel);assert np.isfinite(inverse).all()
        for mesh in obj.findall('mesh'):
            p=np.array(mesh.attrib['p']).reshape(-1,3);tri=np.array(mesh.attrib['tri']).reshape(-1,3);skin=mesh.find('skin');w=np.array(skin.attrib['w']).reshape(-1,4);ix=np.array(skin.attrib['ix']).reshape(-1,4);assert np.isfinite(p).all()and np.isfinite(w).all();assert np.max(abs(w.sum(1)-1))<1e-5,file;assert ((ix>=0)|(w==0)).all()and ix.max()<len(skel);assert tri.min()>=0 and tri.max()<len(p)
            for key in ['diff','n','spec']:
                ref=mesh.find('material').attrib[key][0];assert(file.parent/ref).is_file();assert'female_head_'not in ref and'male_head_'not in ref
            totalv+=len(p);totalt+=len(tri)
    binary.append({'file':file.relative_to(MOD).as_posix(),'vertices':totalv,'triangles':totalt,'bones':maxbones});cache[file.name]=file
bodyfiles=[]
for file in(MOD/'gfx/models/portraits/uma/0001').glob('uma_0001_body*.mesh'):
    prev=pdx.read_meshfile(str(OLD/file.relative_to(MOD))).find('object')[0];now=pdx.read_meshfile(str(file)).find('object')[0];sk=now.find('skeleton');assert[(b.tag,b.attrib)for b in sk[:134]]==[(b.tag,b.attrib)for b in prev.find('skeleton')]
    assert [(m.attrib,m.find('skin').attrib)for m in now.findall('mesh')]==[(m.attrib,m.find('skin').attrib)for m in prev.findall('mesh')];bodyfiles.append(file.name)
body=meshes['uma_body_mesh']if'uma_body_mesh'in meshes else next(v for v in meshes.values()if optional(v,'file')=='uma_0001_body_base.mesh')
clothed=next(v for v in values(body,'blend_shape')if one(v,'id')=='female_bs_body_clothed');assert one(clothed,'type')=='uma_0001_body_none.mesh'
conf=json.loads((R/'Reports/configuration.json').read_text());families=json.loads((R/'Reports/clothing-registration.json').read_text())['families'];assert len(families)==71;assert len(set(f['asset_path']for f in families))==71;assert sum(f['shared_asset_once']for f in families)==64
bodygenes=one(clausewitz((MOD/'common/genes/uma_body_morphs.txt').read_text(encoding='utf-8-sig')),'morph_genes');geneattrs=[]
def settings(node):
    for k,v in node:
        if k=='setting':geneattrs.append(one(v,'attribute'))
        elif isinstance(v,list):settings(v)
settings(bodygenes);assert all(x in conf['supported_body_attributes']for x in geneattrs);assert'bs_body_clothed'not in geneattrs
for row in conf['registrations']:assert row['entity']in entities,row
genes=one(one(clausewitz((MOD/'common/genes/uma_parts.txt').read_text(encoding='utf-8-sig')),'special_genes'),'accessory_genes');gene_templates={key:{k for k,v in value}for key,value in genes if isinstance(value,list)}
for row in conf['registrations']:assert row['template']in gene_templates[row['gene']],row
for part in ['clothes','shoes','socks','headwear']:assert'uma_'+part+'_none'in gene_templates['uma_'+part]
bschecks=[]
for family in families:
    for kind,part in family['parts'].items():
        file=Path(part['base_mesh']);objects=pdx.read_meshfile(str(cache[file.name])).find('object');base=[(o.tag,m)for o in objects for m in o.findall('mesh')]
        for attr,target in part['shape_targets'].items():
            objects=pdx.read_meshfile(str(cache[Path(target).name])).find('object');endpoint=[(o.tag,m)for o in objects for m in o.findall('mesh')];assert len(base)==len(endpoint)
            for(ka,a),(kb,b)in zip(base,endpoint):assert ka==kb and len(a.attrib['p'])==len(b.attrib['p'])and a.attrib['tri']==b.attrib['tri']and a.find('skin').attrib==b.find('skin').attrib,(family['family'],kind,attr)
        bschecks.append({'family':family['family'],'part':kind,'targets':len(part['shape_targets'])})
shader=(MOD/'gfx/FX/uma_portrait.shader').read_text();outside=re.sub(r'\[\[.*?\]\]','',shader,flags=re.S);assert not any(x in outside for x in ['//','/*','#'])
report={'passed':True,'resources_resolved':len(resources),'asset_files':len(assets),'entities':len(entities),'mesh_definitions':len(meshes),'all_binary_meshes':binary,'carriers':carriers,'body_basis_and_bs_geometry_weights_original_core_exact':bodyfiles,'body_clothed_noop':True,'body_genes_supported_attributes_only':True,'body_bs_genes_retained':['gene_bs_body_type','gene_bs_body_shape','gene_bs_bust'],'clothing_bs_topology_checks':bschecks,'wardrobe_families':len(families),'gfx_basenames_unique':True,'txt_bom':True,'max_absolute_path':maxpath,'four_sex_age_branches_18_preserved':True,'shader_tail_comments_absent':True,'game_runtime_verified':False};(R/'Reports/static-validation.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V7_STATIC_VALIDATED',len(binary),'binary meshes',len(entities),'entities',maxpath,'max path',flush=True)
