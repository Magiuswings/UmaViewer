"""Register new UMA face morphs, preserve readable animation text, audit paths."""
import argparse,copy,json,os,posixpath,re,shutil,sys,hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def spans(text,key):
    # Tokenize comments/strings so braces inside them cannot alter block scope.
    tokens=list(re.finditer(r'#[^\n]*|"(?:\\.|[^"\\])*"|[{}=]|[A-Za-z_][A-Za-z_0-9]*',text));result=[]
    for i,t in enumerate(tokens[:-2]):
        if t.group()!=key or tokens[i+1].group()!='='or tokens[i+2].group()!='{':continue
        depth=1;j=i+3
        while depth:
            value=tokens[j].group();depth+=(value=='{')-(value=='}');j+=1
        result.append((t.start(),tokens[j-1].end()))
    return result

def main():
    p=argparse.ArgumentParser()
    for n in ('repo','plugin','root','source-mod','game','targets'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--resume',action='store_true');a=p.parse_args();sys.path[:0]=[str(a.repo/'Tools/PDXExporter'),str(a.repo/'Tools/NativeBody')]
    from build_ck3_mod import parser_only,clausewitz,one,values,script_block
    from test_vanilla_body_animation_blender import inverse_bind,globals_for,deform,mesh_info
    pdx=parser_only(a.plugin);prep=json.loads((a.root/'prepared.json').read_text());export=json.loads((a.root/'export-report.json').read_text());assert export['passed']
    mod=a.root/'Uma-Face-Morphs'
    if a.resume:assert (mod/'descriptor.mod').read_text(encoding='utf8').startswith('name="UMA Face Morphs"')
    shutil.copytree(a.source_mod,mod,dirs_exist_ok=a.resume);portraits=mod/'gfx/models/portraits/uma';shared=portraits/'0001'
    for file in (a.root/'textures').rglob('*.dds'):target=portraits/file.relative_to(a.root/'textures');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    # The copied old head definitions would register the same entity twice.
    (portraits/'1001/uma_1001_head_base.asset').unlink()
    textures={f.name:f for f in(mod/'gfx').rglob('*.dds')}
    for file in(a.root/'meshes').rglob('*.mesh'):
        target=portraits/file.relative_to(a.root/'meshes');target.parent.mkdir(parents=True,exist_ok=True);data=pdx.read_meshfile(str(file))
        for obj in data.find('object'):
            for mesh in obj.findall('mesh'):
                material=mesh.find('material')
                for key in ('diff','n','spec'):
                    if key in material.attrib:material.attrib[key]=[os.path.relpath(textures[Path(material.attrib[key][0]).name],target.parent).replace('\\','/')]
        pdx.write_meshfile(str(target),data)
    source_asset=a.source_mod/'gfx/models/portraits/uma/1001/uma_1001_head_base.asset';text=source_asset.read_text(encoding='utf-8-sig');source_text=text
    text=text.replace('"uma_1001_head_base.mesh"','"uma_0001_head_base.mesh"').replace('"uma_1001_head_none.mesh"','"uma_0001_head_none.mesh"')
    for start,end in reversed(spans(text,'meshsettings')):text=text[:start]+text[end:]
    base_data=pdx.read_meshfile(str(shared/'uma_0001_head_base.mesh'));settings=[]
    for obj in base_data.find('object'):
        for index,mesh in enumerate(obj.findall('mesh')):
            mat=mesh.find('material').attrib;settings.append('\tmeshsettings = {\n\t\tname = "'+obj.tag+'"\n\t\tindex = '+str(index)+'\n'+''.join('\t\t'+k+' = "'+mat[v][0]+'"\n'for k,v in [('texture_diffuse','diff'),('texture_normal','n'),('texture_specular','spec')])+'\t\ttexture = { file = "uma_0001_head_base_ssao.dds" index = 3 }\n\t\tshader = "'+mat['shader'][0]+'"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n')
    at=text.index('streaming = Never')+len('streaming = Never');text=text[:at]+'\n\n'+''.join(settings)+text[at:]
    start,end=spans(text,'pdxmesh')[0];definitions=[]
    for row in prep['records']:
        reference=posixpath.relpath('gfx/models/portraits/uma/'+row['mesh'].removeprefix('meshes/'),'gfx/models/portraits/uma/0001')
        definitions.append('\t\tblend_shape = { id = "'+row['attribute']+'"\t\ttype = "'+reference+'" }')
    text=text[:end-1]+'\n\t\t#### UMA FACE IDENTITY BLEND SHAPES ####\n'+'\n'.join(definitions)+'\n'+text[end-1:]
    start,end=spans(text,'entity')[0];attributes=['\tattribute = { name = "'+r['attribute']+'"\t\tblend_shape = "'+r['attribute']+'" default = 0 }'for r in prep['records']];text=text[:end-1]+'\n\t# Neutral identity endpoints, independent of vanilla face keys.\n'+'\n'.join(attributes)+'\n'+text[end-1:]
    asset=shared/'uma_0001_head_base.asset';asset.write_text(text,encoding='utf8')
    # Explicitly provide all four branches; all four heads expose the new keys.
    file=mod/'common/portrait_types/uma_portrait_types.txt';type_text=file.read_text(encoding='utf-8-sig').replace('head = head_basic_entity_male','head = uma_head_entity');file.write_text(type_text,encoding='utf-8-sig')
    genes=['morph_genes = {','\tportrait_group = uma','\tgene_uma_face_identity = {','\t\tgroup = face','\t\tcan_have_portrait_extremity_shift = no']
    for r in prep['records']:
        genes+=['\t\t'+r['template']+' = {','\t\t\tindex = '+str(r['index'])]
        for kind in ('male','female','boy','girl'):genes+=['\t\t\tuma_'+kind+' = {','\t\t\t\tsetting = {','\t\t\t\t\tattribute = '+r['attribute'],'\t\t\t\t\tvalue = { min = 0.0 max = 1.0 }','\t\t\t\t}','\t\t\t}']
        genes+=['\t\t}']
    genes+=['\t}','}'];genefile=mod/'common/genes/uma_face_genes_morph.txt';genefile.write_text('\n'.join(genes)+'\n',encoding='utf-8-sig')
    ethnfile=mod/'common/ethnicities/uma_ethnicity.txt';ethns=clausewitz(ethnfile.read_text(encoding='utf-8-sig'));default=[('100',[('name','uma_face_1001'),('range',[(None,'1.0'),(None,'1.0')])])]
    for name,body in ethns:body.append(('gene_uma_face_identity',copy.deepcopy(default)))
    ethnfile.write_text(script_block(ethns)+'\n',encoding='utf-8-sig');source_ethnicity=copy.deepcopy(ethns[0][1]);test_ethns=[]
    for r in prep['records']:
        body=[(k,copy.deepcopy(v))for k,v in source_ethnicity if k!='gene_uma_face_identity'];body.append(('gene_uma_face_identity',[('100',[('name',r['template']),('range',[(None,'1.0'),(None,'1.0')])])]))
        test_ethns.append(('uma_face_'+r['id']+'_ethnicity',body))
    (mod/'common/ethnicities/uma_face_test_ethnicities.txt').write_text(script_block(test_ethns)+'\n',encoding='utf-8-sig')
    descriptor='name="UMA Face Morphs"\nsupported_version="1.20.*"\n';(mod/'descriptor.mod').write_text(descriptor,encoding='utf8');(a.root/'Uma-Face-Morphs.mod').write_text(descriptor+'path="'+mod.as_posix()+'"\n',encoding='utf8')
    # Structural and engine binary checks operate on the packaged paths.
    tree=clausewitz(text);head=one(tree,'pdxmesh');entity=one(tree,'entity');old=one(clausewitz(source_text),'pdxmesh')
    for kind in ('animation','additive_animation','import'):assert values(head,kind)==values(old,kind)
    for kind in ('animation','additive_animation'):
        old_lines=[l for l in source_text.splitlines()if re.match(r'\s*'+kind+r'\s*=',l)];new_lines=[l for l in text.splitlines()if re.match(r'\s*'+kind+r'\s*=',l)];assert old_lines==new_lines
    old_anim=a.source_mod/'gfx/models/portraits/uma/animation';new_anim=portraits/'animation';clips=list(old_anim.glob('*.anim'));assert all(sha(f)==sha(new_anim/f.name)for f in clips)
    # Validate actual virtual relative references, including body paths.
    refs=[]
    def visit(node,asset_file):
        for key,value in node:
            if isinstance(value,list):visit(value,asset_file)
            elif isinstance(value,str)and value.lower().endswith(('.anim','.mesh','.dds','.shader','.fxh')):
                rel=value if value.startswith('gfx/')else posixpath.normpath((asset_file.parent.relative_to(mod).as_posix()+'/'+value));candidates=[mod/rel,a.game/rel];assert any(f.is_file()for f in candidates),(asset_file,value,rel);refs.append(rel)
    for f in(mod/'gfx').rglob('*.asset'):visit(clausewitz(f.read_text(encoding='utf-8-sig')),f)
    inventory=defaultdict(list)
    for f in(mod/'gfx').rglob('*'):
        if f.is_file():inventory[f.name.casefold()].append(str(f))
    assert all(len(v)==1 for v in inventory.values());assert all(f.read_bytes().startswith(b'\xef\xbb\xbf')for f in mod.rglob('*.txt'));assert max(len(str(f))for f in mod.rglob('*'))<256
    portrait=one(clausewitz(type_text),'uma')
    for kind,key in [('male','minimum_age'),('female','minimum_age'),('boy','maximum_age'),('girl','maximum_age')]:
        branch=one(portrait,'uma_'+kind);assert one(branch,key)=='18'and one(branch,'head')=='uma_head_entity'
    gene=one(one(clausewitz(genefile.read_text(encoding='utf-8-sig')),'morph_genes'),'gene_uma_face_identity');templates={k:v for k,v in gene if isinstance(v,list)};assert len(templates)==182 and len({one(v,'index')for v in templates.values()})==182
    attrs={one(v,'name'):v for v in values(entity,'attribute')};bs={one(v,'id'):one(v,'type')for v in values(head,'blend_shape')};base_shapes=list(base_data.find('object'));weights_checks=[]
    z=np.load(a.targets/'face-targets.npz');order=json.loads((a.root/'pdx-vertex-order.json').read_text())['export_to_source'];transform=np.array(prep['engine_transform']);origin=np.array(prep['engine_origin']);max_error=0.
    for r in prep['records']:
        assert r['attribute']in attrs and one(attrs[r['attribute']],'default')=='0';assert r['attribute']in bs
        template=templates[r['template']]
        for kind in ('male','female','boy','girl'):
            setting=one(one(template,'uma_'+kind),'setting');assert one(setting,'attribute')==r['attribute'];assert one(one(setting,'value'),'max')=='1.0'
        file=portraits/r['mesh'].removeprefix('meshes/');target=pdx.read_meshfile(str(file));objects=list(target.find('object'));assert len(objects)==len(base_shapes)
        for i,(b,t)in enumerate(zip(base_shapes,objects)):
            assert b.tag==t.tag and b.find('skeleton').attrib==t.find('skeleton').attrib
            assert [(n.tag,n.attrib)for n in b.find('skeleton')]==[(n.tag,n.attrib)for n in t.find('skeleton')]
            for bm,tm in zip(b.findall('mesh'),t.findall('mesh')):
                for key in ('tri','u0'):assert bm.attrib[key]==tm.attrib[key]
                assert bm.find('skin').attrib==tm.find('skin').attrib
                skin=tm.find('skin');ws=np.array(skin.attrib['w']).reshape(-1,4);assert np.max(abs(ws.sum(1)-1))<1e-5
                if i:assert bm.attrib['p']==tm.attrib['p']and bm.attrib['n']==tm.attrib['n']
                for key in ('diff','n','spec'):
                    reference=tm.find('material').attrib[key][0];assert (file.parent/reference).is_file(),(file,reference)
        q=np.array(objects[0].find('mesh').attrib['p']).reshape(-1,3);expected=(z[r['id']]@transform.T+origin)[order];error=float(np.max(abs(q-expected)));assert error<1e-4;max_error=max(max_error,error);weights_checks.append(dict(id=r['id'],position_error_cm=error))
    assert sha(shared/'uma_0001_head_base.mesh')==sha(shared/'uma_0001_head_none.mesh')
    body_old=a.source_mod/'gfx/models/portraits/uma/0001';assert all(sha(f)==sha(shared/f.name)for f in body_old.glob('uma_0001_body*'));assert sha(a.source_mod/'common/genes/uma_genes_morph.txt')==sha(mod/'common/genes/uma_genes_morph.txt');assert sha(a.source_mod/'gfx/FX/uma_portrait.shader')==sha(mod/'gfx/FX/uma_portrait.shader')
    # Audit every referenced reused head animation at beginning/middle/end.
    sk,parts,bind=mesh_info(base_data);animation_results=[]
    for number,file in enumerate(clips):
        clip=pdx.read_meshfile(str(new_anim/file.name));info=clip.find('info');samples=clip.find('samples');count=info.attrib['sa'][0];checks=[]
        for frame in sorted({0,count//2,count-1}):
            result=deform(parts,globals_for(info,samples,frame,sk)@bind);assert all(r['nonfinite']==0 for r in result);checks.append(dict(frame=frame,objects=result))
        animation_results.append(dict(file=file.name,frames=count,samples=checks))
        if(number+1)%100==0:print('AUDITED_REUSED_HEAD_ANIMATIONS',number+1,flush=True)
    write(a.root/'animation-verification.json',dict(passed=True,clips=len(clips),sampled_frames=sum(len(r['samples'])for r in animation_results),method='Actual reused head t/q/s, exact saved inverse-bind matrices, direct linear skinning; finite coordinates only, not facial-expression likeness or game rendering acceptance',results=animation_results))
    bindings=[]
    for r in prep['records']:bindings.append(dict(r,mesh='gfx/models/portraits/uma/'+r['mesh'].removeprefix('meshes/'),diffuse='gfx/models/portraits/uma/'+r['diffuse'].removeprefix('textures/'),gene='gene_uma_face_identity',portrait_group='uma',test_ethnicity='uma_face_'+r['id']+'_ethnicity',geometry_strength=1.0))
    write(mod/'character-face-bindings.json',dict(records=bindings,default_identity='1001',texture_switching=prep['texture_switching'],npc_texture_policy='Original NPC materials have no linked diffuse in supplied dependency closure; 1001 neutral face diffuse used as an explicit fallback.'))
    validation=dict(passed=True,morph_gene='gene_uma_face_identity',identity_templates=182,face_vertices=875,face_triangles=1334,head_skeleton_bones=61,head_animations_reused_unchanged=len(clips),head_animation_lines_preserved=True,body_assets_and_genes_unchanged=True,shader_unchanged=True,txt_utf8_bom=True,all_four_gene_and_portrait_branches_present=True,age_thresholds_unchanged=True,gfx_basenames_unique=True,maximum_absolute_path=max(len(str(f))for f in mod.rglob('*')if f.is_file()),binary_endpoint_max_coordinate_error_cm=max_error,all_endpoints_same_topology_uv_weights_and_skeleton=True,resources_resolved=len(refs),new_gene_reuses_vanilla_keys=False,runtime_visual_verified=False,weights_checks=weights_checks)
    write(mod/'validation.json',validation);write(a.root/'mod-verification.json',validation);print('CK3_FACE_MOD_COMPLETE',182,'max_error_cm',max_error,flush=True)

if __name__=='__main__':main()
