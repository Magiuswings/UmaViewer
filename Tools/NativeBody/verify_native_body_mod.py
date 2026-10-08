"""Independent installed-file contract and endpoint-gene checks."""
import argparse,json,math,re,sys
from pathlib import Path
from collections import defaultdict

def point(bone):
    t=bone.attrib['tx'];r=[[t[0],t[3],t[6]],[t[1],t[4],t[7]],[t[2],t[5],t[8]]];v=[-t[9],-t[10],-t[11]]
    def det(m):return m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0])
    denominator=det(r);result=[]
    for column in range(3):
        a=[row[:]for row in r]
        for i in range(3):a[i][column]=v[i]
        result.append(det(a)/denominator)
    return result

def main():
    p=argparse.ArgumentParser()
    for name in ['repo','plugin','mod','game','before','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--character-id',default='1001');a=p.parse_args();sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b;pdx=b.parser_only(a.plugin)
    root=a.mod/'gfx/models/portraits/uma'/a.character_id;prefix=a.character_id+'_body_';bodytree=b.clausewitz((root/(prefix+'base.asset')).read_text(encoding='utf-8-sig'));body=b.one(bodytree,'pdxmesh');entity=b.one(bodytree,'entity');stock=b.clausewitz((a.game/'gfx/models/portraits/female_body/female_body.asset').read_text(encoding='utf-8-sig'))
    for key in ['animation','additive_animation','import']:assert b.values(body,key)==b.values(b.one(stock,'pdxmesh'),key)
    for asset in root.glob('*.asset'):
        def shader_refs(node):
            for k,v in node:
                if k=='shader_file':yield v
                if isinstance(v,list):yield from shader_refs(v)
        for reference in shader_refs(b.clausewitz(asset.read_text(encoding='utf-8-sig'))):assert(a.mod/reference).is_file(),reference
    for key in ['state','default_state']:assert b.values(entity,key)==b.values(b.one(stock,'entity'),key)
    assert [x for x in b.values(entity,'attribute')if b.values(x,'additive_animation')]==[x for x in b.values(b.one(stock,'entity'),'attribute')if b.values(x,'additive_animation')]
    types=b.one(b.clausewitz((a.mod/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig')),'uma');stocktypes=b.one(b.clausewitz((a.game/'common/portrait_types/00_human_types.txt').read_text(encoding='utf-8-sig')),'human');age={}
    for sex in ['male','female','boy','girl']:
        node=b.one(types,'uma_'+sex);reference=b.one(stocktypes,sex);age[sex]={k:v for k,v in node if k in ['sex','minimum_age','maximum_age']};assert age[sex]=={k:v for k,v in reference if k in ['sex','minimum_age','maximum_age']}
    genetics=b.clausewitz((a.mod/'common/genes/uma_genes_morph.txt').read_text(encoding='utf-8-sig'));morph=b.one(genetics,'morph_genes');assert b.one(morph,'portrait_group')=='uma';macros={k:float(v)for k,v in genetics if k and k.startswith('@')}
    number=lambda x:macros[x]if str(x).startswith('@')else float(x)
    def branch(template,key):
        found=b.one(template,key);return branch(template,found)if isinstance(found,str)else found
    def interpolate(rows,strength):
        coords=[[number(x)for _,x in row]for _,row in rows]
        if strength<=coords[0][0]:return coords[0][1]
        for (x0,y0),(x1,y1)in zip(coords,coords[1:]):
            if strength<=x1:return y0+(y1-y0)*(strength-x0)/(x1-x0)
        return coords[-1][1]
    def settings(template,strength):
        result={}
        for s in b.values(branch(template,'uma_female'),'setting'):
            attr=b.one(s,'attribute')
            if b.values(s,'value'):
                v=b.one(s,'value');result[attr]=number(b.one(v,'min'))+(number(b.one(v,'max'))-number(b.one(v,'min')))*strength
            else:result[attr]=interpolate(b.one(s,'curve'),strength)
        return result
    for key in ['gene_height','gene_bs_body_type','gene_bs_body_shape','gene_bs_bust']:
        for _,template in b.one(morph,key):
            if isinstance(template,list)and b.values(template,'index'):assert all(b.values(template,'uma_'+sex)for sex in ['male','female','boy','girl'])
    actors=json.loads((a.mod/'character-body-bindings.json').read_text(encoding='utf8'))['characters'];actorchecks=[];shapealiases={1:'bs_body_gaunt_1',2:'bs_body_fat_1'};bustaliases={0:'bs_body_breast_shape_1',1:'bs_body_breast_shape_2',3:'bs_body_breast_shape_3',4:'bs_body_breast_shape_4'}
    for actor in actors:
        composed={}
        for key,definition in actor['vanilla_genes'].items():composed.update(settings(b.one(b.one(morph,key),definition['template']),definition['strength']))
        expected={}
        if actor['parameters']['shape']in shapealiases:expected[shapealiases[actor['parameters']['shape']]]=1.
        if actor['parameters']['bust']in bustaliases:expected[bustaliases[actor['parameters']['bust']]]=1.
        actual={k:v for k,v in composed.items()if k.startswith('bs_')and abs(v)>1e-8};assert actual==expected,(actor['character_id'],actual,expected)
        actorchecks.append(actor['character_id'])
    shapes={b.one(s,'id'):b.one(s,'type')for s in b.values(body,'blend_shape')};attrs={b.one(v,'name'):b.one(v,'blend_shape')for v in b.values(entity,'attribute')if b.values(v,'blend_shape')};unsupported={n for n,s in attrs.items()if shapes[s]==prefix+'none.mesh'};used=[]
    def attrs_used(node):
        for k,v in node:
            if k=='attribute':used.append(v)
            if isinstance(v,list):attrs_used(v)
    attrs_used(morph);assert not set(used)&unsupported
    primary=pdx.read_meshfile(str(root/(prefix+'base.mesh'))).find('object')[0];base_mesh=primary.find('mesh');sk=primary.find('skeleton');source_sk=pdx.read_meshfile(str(a.before/'base.mesh')).find('object')[0].find('skeleton');point_error=max(math.dist(point(x),point(y))for x,y in zip(sk,source_sk));assert point_error<.0001
    variants={'base':'base','h0':'height_0','h2':'height_2','s1':'shape_1','s2':'shape_2','b0':'bust_0','b1':'bust_1','b3':'bust_3','b4':'bust_4'};geometry=[]
    for v,source in variants.items():
        target=pdx.read_meshfile(str(root/(prefix+v+'.mesh'))).find('object')[0];old=pdx.read_meshfile(str(a.before/(source+'.mesh'))).find('object')[0];assert target.find('mesh').attrib['p']==old.find('mesh').attrib['p'],v;assert [(n.tag,n.attrib)for n in target.find('skeleton')]==[(n.tag,n.attrib)for n in sk],v;geometry.append(dict(variant=v,coordinates_exact=True))
    neutral=pdx.read_meshfile(str(root/(prefix+'none.mesh'))).find('object')[0].find('mesh');assert neutral.attrib['p']==base_mesh.attrib['p']and neutral.attrib['tri']==base_mesh.attrib['tri']
    names=defaultdict(list);modelnames=[]
    for file in (a.mod/'gfx').rglob('*'):
        if not file.is_file():continue
        names[file.name.casefold()].append(file.relative_to(a.mod).as_posix())
        if file.suffix.lower()in ['.mesh','.anim','.dds']:
            assert re.fullmatch(r'\d{4}_(body|head|face|eye|hair)_[a-z0-9_]+\.(mesh|anim|dds)',file.name),file.name;assert file.parent.name==a.character_id
            modelnames.append(file.name)
    assert all(len(files)==1 for files in names.values());txt=list(a.mod.rglob('*.txt'));assert all(f.read_bytes().startswith(b'\xef\xbb\xbf')for f in txt);longest=max(len(str(f.resolve()))for f in a.mod.rglob('*')if f.is_file());assert longest<256
    report=dict(passed=True,body_coordinates_preserved_from_baked105_source=True,geometry=geometry,bone_points_preserved_max_error_cm=point_error,bone_names_order_parents_and_all_endpoint_bind_matrices_verified=True,original_age_fields_exact=age,stock_animation_declarations_exact=True,ordinary_body_animations=len(b.values(body,'animation')),body_additives=len(b.values(body,'additive_animation')),stock_bs_entries=len(shapes),unsupported_bs_gene_settings_absent=True,actual_character_gene_endpoint_checks=len(actorchecks),gene_strengths_checked_before_original_age_modifiers=True,female_bs_strength_limit=macros['@femaleBsMax'],gfx_names_unique=True,short_model_names_verified=len(modelnames),txt_bom_verified=len(txt),longest_absolute_path_chars=longest,ck3_runtime_verified=False)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('NATIVE_BODY_MOD_INDEPENDENTLY_VERIFIED',len(actorchecks),'character gene endpoints',point_error,'cm point drift',flush=True)

if __name__=='__main__':main()
