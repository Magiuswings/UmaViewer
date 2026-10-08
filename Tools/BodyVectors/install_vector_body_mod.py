"""Install verified independent body vectors in a new copy of the working CK3 mod."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
from PIL import Image

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--source-mod',type=Path,required=True)
    p.add_argument('--delivery',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pdx-plugin',type=Path,required=True)
    p.add_argument('--rest-animation',type=Path,required=True)
    p.add_argument('--factor',type=float,default=105.)
    args=p.parse_args()
    sys.path.insert(0,str(args.repo/'Tools/PDXExporter'))
    import build_ck3_mod as b
    from scale_body_probe import scaled_mesh,element_equal,f32
    src=args.source_mod.resolve();out=args.output.resolve();delivery=args.delivery.resolve()
    if out.exists() or out.is_relative_to(src) or src.is_relative_to(out):raise ValueError('Use a new independent mod output')
    verification=json.loads((delivery/'verification.json').read_text(encoding='utf8'))
    if verification.get('passed') is not True:raise ValueError('Unverified vector delivery')
    export=json.loads((delivery/'export-manifest.json').read_text(encoding='utf8'));pdx=b.parser_only(args.pdx_plugin)
    rootrel=Path('gfx/models/portraits/uma');source_root=src/rootrel
    tree=b.clausewitz((source_root/'uma_body.asset').read_text(encoding='utf-8-sig'));original_body=b.one(tree,'pdxmesh');old_entity=b.one(tree,'entity')
    old_mesh=pdx.read_meshfile(str(source_root/b.one(original_body,'file')))
    portrait_hash=b.sha(src/'common/portrait_types/uma_portrait_types.txt')
    stable={f.relative_to(src).as_posix():b.sha(f) for f in source_root.rglob('*') if f.is_file() and (f.suffix=='.anim' or f.name in ('uma_head.asset','uma_head.mesh'))}
    head_asset=b.one(b.clausewitz((source_root/'uma_head.asset').read_text(encoding='utf-8-sig')),'pdxmesh')
    for relative in {b.one(head_asset,'file')}|{b.one(v,'type') for v in b.values(head_asset,'blend_shape')+b.values(head_asset,'animation')}:
        file=source_root/relative;stable[file.relative_to(src).as_posix()]=b.sha(file)
    shutil.copytree(src,out)
    root=out/rootrel;target=root/'delivery/body_vectors';target.mkdir(parents=True)
    for file in (delivery/'meshes').glob('*'):
        if file.is_file():shutil.copy2(file,target/file.name)
    meshes=[]
    for file in target.glob('*.mesh'):
        original=pdx.read_meshfile(str(file));expected=copy.deepcopy(original);scaled_mesh(expected,args.factor);pdx.write_meshfile(str(file),expected)
        assert element_equal(pdx.read_meshfile(str(file)),expected)
        assert len(expected.find('object'))==1 and len(expected.find('object')[0].findall('mesh'))==1
        meshes.append(file.relative_to(root).as_posix())
    base_mesh=pdx.read_meshfile(str(target/'base.mesh'))
    base_skeleton=base_mesh.find('object')[0].find('skeleton');old_skeleton=old_mesh.find('object')[0].find('skeleton')
    assert [b.tag for b in base_skeleton]==[b.tag for b in old_skeleton]
    bind_difference=max(abs(x-y) for old,new in zip(old_skeleton,base_skeleton) for x,y in zip(old.attrib['tx'],new.attrib['tx']))
    # A newly exported real static pose follows this Basis bind frame; old head animations stay byte-identical.
    rest=pdx.read_meshfile(str(args.rest_animation));assert rest.find('info').attrib['j']==[134]
    for bone in rest.find('info'):
        if 't' in bone.attrib:bone.attrib['t']=[f32(v*args.factor) for v in bone.attrib['t']]
    samples=rest.find('samples')
    if 't' in samples.attrib:samples.attrib['t']=[f32(v*args.factor) for v in samples.attrib['t']]
    rest_name='uma_vector_static_rest.anim';pdx.write_animfile(str(root/rest_name),rest)
    assert element_equal(rest,pdx.read_meshfile(str(root/rest_name)))
    original_diffuse=target/'uma_body_skin_1.dds';no_palette={}
    for file in sorted(target.glob('uma_body_skin_*.dds')):
        if '__pdx_no_palette' in file.stem:continue
        raw=bytearray(file.read_bytes());assert raw[:4]==b'DDS ' and raw[84:88]==b'DXT5'
        for offset in range(128,len(raw),16):raw[offset:offset+8]=bytes(8)
        dst=file.with_name(file.stem+'__pdx_no_palette.dds');dst.write_bytes(raw)
        with Image.open(file) as a,Image.open(dst) as c:
            assert a.convert('RGB').tobytes()==c.convert('RGB').tobytes()
            assert c.convert('RGBA').getchannel('A').getextrema()==(0,0)
        no_palette[file.name]=dst.name
    Image.new('RGBA',(4,4),(255,255,255,0)).save(target/'uma_skin_neutral_ssao.dds',pixel_format='DXT5')
    new_body=[(k,v) for k,v in original_body if k not in ('file','scale','blend_shape','meshsettings','animation')]
    new_body.append(('file','delivery/body_vectors/base.mesh'))
    for key in export['keys']:
        new_body.append(('blend_shape',[('id','female_bs_uma_'+key['key']),('type','delivery/body_vectors/'+Path(key['mesh']).name)]))
    for animation in b.values(original_body,'animation'):
        new_body.append(('animation',[(k,rest_name if k=='type' else v) for k,v in animation]))
    settings=[('name',base_mesh.find('object')[0].tag),('index','0'),('texture_diffuse',no_palette['uma_body_skin_1.dds']),
              ('texture_normal','neutral_normal.dds'),('texture_specular','neutral_properties.dds'),('texture',[('file','uma_skin_neutral_ssao.dds'),('index','3')]),
              ('shader','portrait_skin'),('shader_file','gfx/FX/uma_portrait.shader')]
    new_body.append(('meshsettings',settings))
    new_entity=[(k,v) for k,v in old_entity if k!='attribute']
    for key in export['keys']:new_entity.append(('attribute',[('name','bs_uma_'+key['key']),('blend_shape','female_bs_uma_'+key['key']),('default','0')]))
    (root/'uma_body.asset').write_text(b.script_block([('pdxmesh',new_body),('entity',new_entity)])+'\n',encoding='utf8')
    portrait=b.clausewitz((src/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig'))
    # Preserve the actual group in the already working sample, including its four portrait types.
    old_gene=src/'common/genes/uma_genes_morph.txt'
    old_morph=b.one(b.clausewitz(old_gene.read_text(encoding='utf-8-sig')),'morph_genes');portrait_group=b.one(old_morph,'portrait_group')
    morph=[('portrait_group',portrait_group)]
    for field in ('height','shape','bust'):
        field_keys=[k for k in export['keys'] if k['variable']==field]
        gene=[('group','body')]
        for key in field_keys:
            settings=[]
            for other in field_keys:
                value='1.0' if other['key']==key['key'] else '0.0'
                settings.append(('setting',[('attribute','bs_uma_'+other['key']),('value',[('min',value),('max',value)])]))
            branch=[('index',str(key['value'])),('visible','yes'),('uma_female',settings),('uma_male',[]),('uma_girl','uma_female'),('uma_boy','uma_male')]
            gene.append(('uma_'+key['key'],branch))
        morph.append(('gene_uma_'+field,gene))
    (out/'common/genes/uma_genes_morph.txt').write_text(b.script_block([('morph_genes',morph)])+'\n',encoding='utf-8-sig')
    ethnic_path=out/'common/ethnicities/uma_ethnicity.txt';ethnic=b.clausewitz(ethnic_path.read_text(encoding='utf-8-sig'))
    for index,(name,body) in enumerate(ethnic):
        if name not in ('uma_ethnicity','uma_ethnity'):continue
        new=[(k,v) for k,v in body if k!='gene_uma_body_combinations']
        for field,value in export['basis_profile'].items():
            new.append(('gene_uma_'+field,[('100',[('name','uma_'+field+'_'+str(value)),('range',[(None,'1.0'),(None,'1.0')])])]))
        ethnic[index]=(name,new)
    ethnic_path.write_text(b.script_block(ethnic)+'\n',encoding='utf-8-sig')
    assert b.sha(out/'common/portrait_types/uma_portrait_types.txt')==portrait_hash
    assert all(b.sha(out/f)==h for f,h in stable.items())
    # Evaluate the new gene definition as independent scalar one-hot settings.
    bindings=json.loads((delivery/'character-body-bindings.json').read_text(encoding='utf8'))['characters']
    for actor in bindings:
        composed={}
        for field in ('height','shape','bust'):
            gene=b.one(morph,'gene_uma_'+field);selected=b.one(gene,'uma_'+field+'_'+str(actor['parameters'][field]))
            assert {k for k,v in selected if k.startswith('uma_')}=={'uma_female','uma_male','uma_girl','uma_boy'}
            for setting in b.values(b.one(selected,'uma_female'),'setting'):
                attr=b.one(setting,'attribute');assert attr.startswith('bs_uma_'+field+'_')
                composed[attr.removeprefix('bs_uma_')]=float(b.one(b.one(setting,'value'),'min'))
        assert {k:v for k,v in composed.items() if v}==actor['keys']
    validation=dict(passed=True,delivery_verified=True,vector_keys=len(export['keys']),nonzero_keys=export['nonzero_keys'],body_meshes=meshes,body_unit_factor=args.factor,
                    common_gene_group=portrait_group,independent_genes=['gene_uma_height','gene_uma_shape','gene_uma_bust'],all_character_gene_compositions_verified=len(bindings),
                    portrait_file_sha256=portrait_hash,portrait_types_unchanged=True,age_thresholds_unchanged=True,
                    head_and_previous_animation_files_preserved=len(stable),stable_file_hashes=stable,baseline_bind_matrix_difference_from_previous_mod=bind_difference,
                    active_body_animation=rest_name,body_diffuse_alpha_zero=True,material_slots=1,shader='portrait_skin',old_combination_gene_active=False,ck3_runtime_verified=False)
    history=out/'history';history.mkdir(exist_ok=True)
    for filename in ('validation.json','active-completed-skin-assets.json','asset-library.json'):
        file=out/filename
        if file.exists():file.rename(history/('before-vector-body-'+filename))
    b.write_json(out/'validation.json',validation)
    b.write_json(out/'active-body-vector-assets.json',dict(base_mesh='gfx/models/portraits/uma/delivery/body_vectors/base.mesh',keys=export['keys'],basis_profile=export['basis_profile'],independent_genes=validation['independent_genes']))
    b.write_json(out/'character-body-bindings.json',dict(characters=bindings,count=len(bindings),scope='Index for selecting the three independent templates and the actual diffuse; does not auto-assign CK3 characters'))
    shutil.copy2(delivery/'skin-colors.json',out/'skin-colors.json')
    (out/'descriptor.mod').write_text('name="UMA Common Body Vectors"\nsupported_version="1.20.*"\n',encoding='utf8')
    (out/'launcher-entry.mod').write_text('name="UMA Common Body Vectors"\npath="mod/'+out.name+'"\n',encoding='utf8')
    (out/'README.md').write_text('''# UMA 单变量通用躯干

默认以 height=1 / shape=0 / bust=2 作 Basis。gene_uma_height、gene_uma_shape、gene_uma_bust 各自只控制本变量的属性，按取值同时相加；没有每角色或每组合的活动躯干键。11 个取值中 8 个有位移，3 个默认值是零位移。

使用 28 个实际 bdy0004_00_00 通用底模验证所有已有组合，覆盖 master 的全部 173 条角色记录。相同体型的 bdy0009 供露肤并集，缺失皮肤全部采用竞技泳装网格和真实 diffuse 肤色填补。身体只有 portrait_skin，UV0 对 28 套源模型完全一致。固定 Basis 骨架和附加 UV 通道；来源体型的独立骨骼点不是通过 Shape Key 变化的。

身体 PDX 烘焙 105 倍，asset 不含 scale=100。保留上一版头颈修复、头部/原动画、四个 portrait type 和原版年龄阈值，另导出匹配新 Basis 的真实静态姿势。皮肤 diffuse 的游戏调色 mask 为 alpha=0。其它肤色 DDS 在 delivery/body_vectors，character-body-bindings.json 提供角色到参数/肤色的索引，不会自动替游戏中的人物改种族或 DNA。

测试命令：effect set_ethnicity = uma_ethnicity

肥胖运动服 setting03 拓扑不同，未伪造为泳装底模的精确 BS；17 个没有原始源模型的参数组合没有源端点验收。当前仅静态、Blender 和 PDX 验证通过，尚未在 CK3 切换本轮各端点或验收动画。
''',encoding='utf8')
    b.write_json(out/'manifest-hashes.json',dict(files=[dict(file=f.relative_to(out).as_posix(),bytes=f.stat().st_size,sha256=b.sha(f)) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest-hashes.json']))
    print('VECTOR_BODY_MOD_INSTALLED',str(out),flush=True)

if __name__=='__main__':main()
