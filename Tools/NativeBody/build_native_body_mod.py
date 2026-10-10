"""Build a short-name UMA mod from the installed vanilla female-body contract.

Stock animation/import/state/additive declarations are kept verbatim as parsed
data. No stock body animation is copied, rewritten or shadowed in the mod.
Unsupported morph entries point to a complete neutral endpoint; genes never
address those unsupported attributes. All generated .txt uses UTF-8 BOM.
"""
import argparse,copy,json,re,shutil,sys
from pathlib import Path
from collections import defaultdict

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['repo','plugin','game','source-mod','meshes','delivery','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--character-id',default='1001');a=p.parse_args()
    if not re.fullmatch(r'\d{4}',a.character_id):raise ValueError('Character ID must be four digits')
    if a.output.exists():raise FileExistsError(a.output)
    sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b
    pdx=b.parser_only(a.plugin);stockfolder=a.game/'gfx/models/portraits/female_body';src=a.source_mod/'gfx/models/portraits/uma';root=a.output/'gfx/models/portraits/uma'/a.character_id;root.mkdir(parents=True)
    prefix=a.character_id+'_';renames={};copies={}
    def name(element,variant,role=None,suffix='.mesh'):return prefix+element+'_'+variant+('_'+role if role else '')+suffix
    def copyfile(source,newname):
        source=Path(source).resolve();dest=root/newname
        if dest.exists():assert b.sha(source)==b.sha(dest)
        else:shutil.copy2(source,dest)
        copies[str(source)]=dest.relative_to(a.output).as_posix();renames[source.name]=newname;return newname
    mesh_names={};source_meshes={};logical={'base':'base','s1':'shape_1','s2':'shape_2','h0':'height_0','h2':'height_2','b0':'bust_0','b1':'bust_1','b3':'bust_3','b4':'bust_4'}
    for file in sorted(a.meshes.glob('*.mesh')):
        stem=file.stem;match=re.fullmatch(r'\d{4}_body_(base|s1|s2|h0|h2|b0|b1|b3|b4)',stem)
        if match:stem=logical[match[1]]
        variant={'base':'base','shape_1':'s1','shape_2':'s2','height_0':'h0','height_2':'h2','bust_0':'b0','bust_1':'b1','bust_3':'b3','bust_4':'b4'}[stem]
        source_meshes[stem]=file
        mesh_names[stem]=copyfile(file,name('body',variant))
    neutral=copyfile(source_meshes['base'],name('body','none'))
    textures={}
    oldtextures=src/'delivery/body_vectors'
    for n in range(4):textures[n]=copyfile(oldtextures/f'uma_body_skin_{n}__pdx_no_palette.dds',name('body','skin'+str(n),'diffuse','.dds'))
    normal=copyfile(oldtextures/'neutral_normal.dds',name('body','base','normal','.dds'))
    properties=copyfile(oldtextures/'neutral_properties.dds',name('body','base','properties','.dds'))
    ssao=copyfile(oldtextures/'uma_skin_neutral_ssao.dds',name('body','base','ssao','.dds'))
    # Rewrite the material embedded in every body endpoint, even though CK3's
    # meshsettings override it. This keeps standalone PDX imports reproducible.
    for file in root.glob(prefix+'body_*.mesh'):
        data=pdx.read_meshfile(str(file))
        for obj in data.find('object'):
            for m in obj.findall('mesh'):
                material=m.find('material')
                if material is not None:
                    material.attrib.update(shader=['portrait_skin'],diff=[textures[1]],n=[normal],spec=[properties])
                    for k,v in list(material.attrib.items()):
                        if k not in ['shader','diff','n','spec']:material.attrib[k]=[renames.get(x,x)if isinstance(x,str)else x for x in v]
        pdx.write_meshfile(str(file),data)
    base=pdx.read_meshfile(str(root/mesh_names['base']));stock=b.clausewitz((stockfolder/'female_body.asset').read_text(encoding='utf-8-sig'));body=copy.deepcopy(b.one(stock,'pdxmesh'));entity=copy.deepcopy(b.one(stock,'entity'))
    supported={'female_bs_body_fat_1':mesh_names['shape_2'],'female_bs_body_gaunt_1':mesh_names['shape_1']}
    bust_map={1:0,2:1,3:3,4:4}
    for shape,value in bust_map.items():supported['female_bs_body_breast_shape_'+str(shape)]=mesh_names['bust_'+str(value)]
    shader_name=name('portrait','base',suffix='.shader');shader_path='gfx/FX/'+shader_name
    settings=[('name',base.find('object')[0].tag),('index','0'),('texture_diffuse',textures[1]),('texture_normal',normal),('texture_specular',properties),('texture',[('file',ssao),('index','3')]),('shader','portrait_skin'),('shader_file',shader_path)]
    for i,(k,v) in enumerate(body):
        if k=='name':body[i]=(k,'uma_body_mesh')
        elif k=='file':body[i]=(k,mesh_names['base'])
        elif k=='meshsettings':body[i]=(k,settings)
        elif k=='blend_shape':body[i]=(k,[(key,supported.get(b.one(v,'id'),neutral)if key=='type'else value)for key,value in v])
    for i,(k,v)in enumerate(entity):
        if k=='name':entity[i]=(k,'uma_body_entity')
        elif k=='pdxmesh':entity[i]=(k,'uma_body_mesh')
    write=lambda file,tree:file.write_text(b.script_block(tree)+'\n',encoding='utf-8-sig'if file.suffix.lower()=='.txt'else'utf8')
    write(root/name('body','base',suffix='.asset'),[('pdxmesh',body),('entity',entity)])
    # Preserve the working head and its dependency closure, with globally unique
    # basenames. Old inactive libraries and obsolete static body clips are excluded.
    head=b.clausewitz((src/'uma_head.asset').read_text(encoding='utf-8-sig'));headset=b.clausewitz((src/'uma_natural_common_head.asset').read_text(encoding='utf-8-sig'))
    headtexturemap={'uma_face_diffuse.dds':name('face','base','diffuse','.dds'),'uma_hair_diffuse.dds':name('hair','base','diffuse','.dds'),'uma_eyes_diffuse.dds':name('eye','base','diffuse','.dds'),'uma_head_normal.dds':name('head','base','normal','.dds'),'uma_head_properties.dds':name('head','base','properties','.dds')}
    for old,new in headtexturemap.items():copyfile(src/old,new)
    headmeshes={'uma_head.mesh':name('head','base'),'uma_head_neutral.mesh':name('head','none')}
    for old,new in headmeshes.items():
        copyfile(src/old,new);data=pdx.read_meshfile(str(root/new))
        for obj in data.find('object'):
            for m in obj.findall('mesh'):
                material=m.find('material')
                if material is not None:
                    for k,v in list(material.attrib.items()):material.attrib[k]=[headtexturemap.get(Path(x).name,x)if isinstance(x,str)else x for x in v]
        pdx.write_meshfile(str(root/new),data)
    animations={}
    def gather(node):
        for k,v in node:
            if isinstance(v,list):gather(v)
            elif k=='type'and str(v).endswith('.anim'):animations[v]=None
    gather(head);gather(headset)
    for n,file in enumerate(sorted(animations),1):animations[file]=copyfile(src/b.safe_relative(file),name('head',f'{n:04}','animation','.anim'))
    def rewrite_head(node):
        result=[]
        for k,v in node:
            if isinstance(v,list):v=rewrite_head(v)
            elif k=='type'and v in animations:v=animations[v]
            elif k in ['file','type']and v in headmeshes:v=headmeshes[v]
            elif k in ['texture_diffuse','texture_normal','texture_specular']and v in headtexturemap:v=headtexturemap[v]
            elif k=='shader_file'and v=='gfx/FX/uma_portrait.shader':v=shader_path
            result.append((k,v))
        return result
    write(root/name('head','base',suffix='.asset'),rewrite_head(head));write(root/name('head','common',suffix='.asset'),rewrite_head(headset))
    (a.output/'gfx/FX').mkdir();shutil.copy2(a.source_mod/'gfx/FX/uma_portrait.shader',a.output/'gfx/FX'/shader_name)
    # Keep four portrait slots and the exact stock age boundary.
    portrait=b.clausewitz((a.source_mod/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig'))
    folder=a.output/'common/portrait_types';folder.mkdir(parents=True);write(folder/'uma_portrait_types.txt',portrait)
    attrs={b.one(v,'name'):v for v in b.values(entity,'attribute')};supportedattrs={n for n,v in attrs.items()if b.values(v,'blend_shape')and b.one(v,'blend_shape')in supported}
    additiveattrs={n for n,v in attrs.items()if b.values(v,'additive_animation')}
    unsupportedattrs={n for n,v in attrs.items()if b.values(v,'blend_shape')and n not in supportedattrs}
    gene_source=b.clausewitz((a.game/'common/genes/01_genes_morph.txt').read_text(encoding='utf-8-sig'));stockgenes=b.one(gene_source,'morph_genes');morph=[('portrait_group','uma')];removed=[]
    allowed=supportedattrs|additiveattrs|{'head_body_height'}
    def filter_node(node):
        result=[]
        for k,v in node:
            if k=='decal':continue
            if k=='setting'and b.one(v,'attribute')not in allowed:
                removed.append(b.one(v,'attribute'));continue
            if isinstance(v,list):v=filter_node(v)
            elif k in ['male','female','boy','girl']and v in ['male','female','boy','girl']:v='uma_'+v
            result.append(('uma_'+k if k in ['male','female','boy','girl']else k,v))
        return result
    for key in ['gene_height','gene_bs_body_type','gene_bs_body_shape']:
        node=filter_node(copy.deepcopy(b.one(stockgenes,key)))
        # Every template must explicitly offer all four portrait slots, including
        # templates whose stock definition only provides adult branches.
        for _,template in node:
            if not isinstance(template,list)or not b.values(template,'index'):continue
            for sex in ['male','female','boy','girl']:
                if not b.values(template,'uma_'+sex):template.append(('uma_'+sex,'uma_'+('female'if sex=='girl'else'male')if sex in ['boy','girl']else[]))
        morph.append((key,node))
    # Endpoint fits leave >1 mm local errors. Use exact categorical breast-shape
    # keys instead of pretending the source bust profiles form one linear slider.
    bust=[('group','body')]
    for template,original in b.one(stockgenes,'gene_bs_bust'):
        if not isinstance(original,list)or not b.values(original,'index'):continue
        metadata=[(k,copy.deepcopy(v))for k,v in original if k not in ['male','female','boy','girl']]
        match=re.fullmatch(r'bust_shape_([1-4])_(half|full)',template);active=int(match[1])if match else None;amount='.5'if match and match[2]=='half'else'1.0'
        branch=[]
        for index in range(1,5):
            # Inactive shapes use the entity's neutral default; a 0-to-0
            # setting does not constitute a usable morph range.
            if active!=index:continue
            value=amount;setting=[('attribute','bs_body_breast_shape_'+str(index)),('value',[('min',value),('max',value)])]
            if active==index:setting.append(('age','age_preset_puberty'))
            branch.append(('setting',setting))
        metadata += [('uma_male',[]),('uma_female',branch),('uma_boy','uma_male'),('uma_girl','uma_female')];bust.append((template,metadata))
    morph.append(('gene_bs_bust',bust))
    genepath=a.output/'common/genes';genepath.mkdir(parents=True)
    # Macros are local to the new file; age presets remain supplied by the base game.
    # Vanilla caps female BS strength at 0.8. Our exported files are complete
    # source endpoints, so their selected template must be able to reach 1.0.
    write(genepath/'uma_genes_morph.txt',[(k,'1.0'if k=='@femaleBsMax'else v)for k,v in gene_source if k and k.startswith('@')]+[('morph_genes',morph)])
    ethnic=[]
    for key in ['uma_ethnicity','uma_ethnity']:
        node=[('portrait_group','uma')]
        for gene,template in [('gene_height','normal_height'),('gene_bs_body_type','body_fat_head_fat_full'),('gene_bs_body_shape','body_shape_average'),('gene_bs_bust','bust_default')]:
            node.append((gene,[('100',[('name',template),('range',[(None,'.5'),(None,'.5')])])]))
        ethnic.append((key,node))
    ep=a.output/'common/ethnicities';ep.mkdir(parents=True);write(ep/'uma_ethnicity.txt',ethnic)
    bindings=json.loads((a.delivery/'character-body-bindings.json').read_text(encoding='utf8'))
    actors=bindings['characters'];shape_strength={0:.5,1:0.,2:1.};bust_template={0:'bust_shape_1_full',1:'bust_shape_2_full',2:'bust_default',3:'bust_shape_3_full',4:'bust_shape_4_full'}
    for actor in actors:
        profile=actor['parameters'];actor['vanilla_genes']={'gene_bs_body_type':dict(template='body_fat_head_fat_full',strength=shape_strength[profile['shape']]),'gene_bs_body_shape':dict(template='body_shape_average',strength=0.),'gene_bs_bust':dict(template=bust_template[profile['bust']],strength=1.)}
        actor['height_policy']='gene_height uses unchanged vanilla additive_animation; source height endpoints retained as editable reference, not an additional live height BS'
        actor['diffuse']=textures[profile['skin']]
    b.write_json(a.output/'character-body-bindings.json',bindings);shutil.copy2(a.delivery/'skin-colors.json',a.output/'skin-colors.json')
    # Validate actual references, skeletons, unsupported-gene removal, filenames,
    # encoding and the stock animation/state contract before packaging anything.
    for key in ['animation','additive_animation','import']:assert b.values(body,key)==b.values(b.one(stock,'pdxmesh'),key)
    for key in ['state','default_state']:assert b.values(entity,key)==b.values(b.one(stock,'entity'),key)
    assert [v for v in b.values(entity,'attribute')if b.values(v,'additive_animation')]==[v for v in b.values(b.one(stock,'entity'),'attribute')if b.values(v,'additive_animation')]
    actualattrs=set()
    def scan(node):
        for k,v in node:
            if k=='attribute':actualattrs.add(v)
            if isinstance(v,list):scan(v)
    scan(morph);assert not actualattrs&unsupportedattrs
    stocksk=pdx.read_meshfile(str(stockfolder/'female_body.mesh')).find('object')[0].find('skeleton');reference_sk=base.find('object')[0].find('skeleton')
    assert [(n.tag,n.attrib.get('pa'),n.attrib.get('ix'))for n in reference_sk]==[(n.tag,n.attrib.get('pa'),n.attrib.get('ix'))for n in stocksk]
    for file in root.glob(prefix+'body_*.mesh'):
        sk=pdx.read_meshfile(str(file)).find('object')[0].find('skeleton');assert [(n.tag,n.attrib)for n in sk]==[(n.tag,n.attrib)for n in reference_sk]
    gfxnames=defaultdict(list)
    for file in (a.output/'gfx').rglob('*'):
        if file.is_file():gfxnames[file.name.casefold()].append(file.relative_to(a.output).as_posix())
    duplicates={k:v for k,v in gfxnames.items()if len(v)>1};assert not duplicates
    txt=list(a.output.rglob('*.txt'));assert all(f.read_bytes().startswith(b'\xef\xbb\xbf')for f in txt)
    longest=max((len(str(f.resolve())),str(f.resolve()))for f in a.output.rglob('*')if f.is_file());assert longest[0]<256
    activehead=rewrite_head(head);activeheadset=rewrite_head(headset)
    def refs(node):
        for k,v in node:
            if isinstance(v,list):yield from refs(v)
            elif k in ['type','file','texture_diffuse','texture_normal','texture_specular']and Path(str(v)).suffix in ['.mesh','.anim','.dds']:yield str(v)
    for reference in list(refs(activehead))+list(refs(activeheadset)):
        assert(root/reference).is_file(),reference
    for reference in refs([('pdxmesh',body)]):
        assert(root/reference).is_file()or(stockfolder/reference).is_file(),reference
    report=dict(passed=True,vanilla_asset=str(stockfolder/'female_body.asset'),vanilla_asset_sha256=b.sha(stockfolder/'female_body.asset'),stock_body_animations_preserved=len(b.values(body,'animation')),stock_additives_preserved=len(b.values(body,'additive_animation')),stock_imports_states_and_additive_defaults_exact=True,vanilla_skeleton_structure_exact=True,all_endpoint_bind_matrices_exact_to_basis=True,vanilla_bind_matrices_exact=[(n.tag,n.attrib)for n in reference_sk]==[(n.tag,n.attrib)for n in stocksk],stock_bs_entries=len(b.values(body,'blend_shape')),supported_bs=supported,unsupported_bs_placeholder=neutral,unsupported_gene_attributes_removed=sorted(set(removed)|unsupportedattrs),active_gene_attributes=sorted(actualattrs),genes=['gene_height','gene_bs_body_type','gene_bs_body_shape','gene_bs_bust'],portrait_group='uma',txt_utf8_bom=len(txt),gfx_duplicate_basenames=duplicates,longest_absolute_path=longest,head_animation_files_renamed=len(animations),source_mod_preserved=True,ck3_runtime_verified=False,height_source_geometry_exact=False)
    b.write_json(a.output/'validation.json',report);b.write_json(a.output/'filename-index.json',dict(character_id=a.character_id,shared_body=True,files=copies,animation_names=animations,bust_profiles=bust_map,body_shape_profiles={'gaunt_1':1,'fat_1':2}))
    (a.output/'descriptor.mod').write_text('name="UMA Native Body Animation"\nsupported_version="1.20.*"\n',encoding='utf8')
    (a.output.parent/(a.output.name+'.mod')).write_text('name="UMA Native Body Animation"\npath="'+a.output.resolve().as_posix()+'"\nsupported_version="1.20.*"\n',encoding='utf8')
    print('NATIVE_BODY_MOD_BUILT',json.dumps({k:v for k,v in report.items()if k in ['stock_body_animations_preserved','stock_additives_preserved','stock_bs_entries','txt_utf8_bom','longest_absolute_path']}),flush=True)

if __name__=='__main__':main()
