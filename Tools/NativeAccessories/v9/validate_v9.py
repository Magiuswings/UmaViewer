"""Validate the engine-facing basename, public-node, color-order and designer contracts."""
import sys,json,re,hashlib,collections
from pathlib import Path
import numpy as np
from paths_v9 import ROOT,MOD,REPO,GAME,PLUGIN,V8
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7')]
from build_ck3_mod import parser_only,clausewitz,one,values
from head_assembly_math import rigdata
P=parser_only(PLUGIN);errors=[]
def check(ok,msg):
    if not ok:errors.append(msg)
def leaves(t):
    for k,v in t:
        if isinstance(v,list):yield from leaves(v)
        else:yield k,v
def main():
    catalog={};duplicates=[]
    for f in(MOD/'gfx').rglob('*'):
        if f.is_file():
            n=f.name.lower()
            if n in catalog:duplicates.append(n)
            catalog[n]=f;check(len(str(f))<256,'long absolute file name '+str(f))
    check(not duplicates,'duplicate gfx basenames '+str(duplicates));meshes={};entities={};macros={};settings=0;cache={}
    def binary(f):
        if f not in cache:cache[f]=P.read_meshfile(str(f))
        return cache[f]
    for f in(MOD/'gfx').rglob('*.asset'):
        t=clausewitz(f.read_text(encoding='utf-8-sig'))
        for k,v in leaves(t):
            if isinstance(v,str)and v.lower().endswith(('.dds','.mesh','.anim')):
                check('/'not in v and '\\'not in v,'asset nonshader resource contains path '+f.name+' '+v);check(v.lower()in catalog,'missing global resource '+v+' '+f.name)
        for kind,table in [('pdxmesh',meshes),('entity',entities),('skeletal_animation_set',macros)]:
            for v in values(t,kind):
                name=one(v,'name');check(name not in table,'duplicate definition '+name);table[name]=(f,v)
    bs=set();bodybs=set();bsdecl=0
    for name,(af,m)in meshes.items():
        f=catalog[one(m,'file').lower()];tree=binary(f);obj={o.tag:o for o in tree.find('object')}
        for setting in values(m,'meshsettings'):
            key=one(setting,'name');i=int(one(setting,'index'));check(key in obj,'meshsettings missing name '+name);check(key not in obj or i<len(obj[key].findall('mesh')),'material index out of range '+name);settings+=1
        for b in values(m,'blend_shape'):
            bf=catalog[one(b,'type').lower()];bs.add(bf);bsdecl+=1
            if name=='uma_body_mesh':bodybs.add(bf)
            base=list(tree.find('object'));target=list(binary(bf).find('object'));check(len(base)==len(target),'BS object count '+bf.name)
            for a,b in zip(base,target):
                check(len(a.findall('mesh'))==len(b.findall('mesh')),'BS slots '+bf.name)
                for am,bm in zip(a.findall('mesh'),b.findall('mesh')):
                    check(len(am.get('p'))==len(bm.get('p')),'BS vertices '+bf.name)
                    for k in ['tri','u0','u1']:check(am.get(k)==bm.get(k),'BS network '+k+' '+bf.name)
        if 'headwear'in name:check(not values(m,'import')and not values(m,'animation'),'headwear own motion '+name)
    modules=[]
    for name,(f,m)in macros.items():
        ref=one(m,'reference_skeleton');check(ref in meshes,'undefined animation reference '+name)
        if ref not in meshes:continue
        rfile=catalog[one(meshes[ref][1],'file').lower()];sk=binary(rfile).find('object')[0].find('skeleton');decl=values(m,'animation');ids=[one(a,'id')for a in decl];check(len(ids)==len(set(ids)),'duplicate animation ID '+name);clips={one(a,'type')for a in decl};check(len(clips)==1,'multiple source files '+name)
        cf=catalog[next(iter(clips)).lower()];data=P.read_meshfile(str(cf));info=data.find('info');check(info.get('j')==[len(sk)],'animation j mismatch '+name);check([n.tag for n in info]==[n.tag for n in sk],'animation joint order mismatch '+name);modules.append(dict(set=name,bones=len(sk),frames=info.get('sa')[0],ids=len(ids),clip=cf.name,sha256=hashlib.sha256(cf.read_bytes()).hexdigest()))
    for name,(f,e)in entities.items():
        ref=one(e,'pdxmesh');check(ref in meshes,'undefined entity mesh '+name)
        if ref not in meshes:continue
        m=meshes[ref][1];allowed={one(a,'id')for a in values(m,'animation')}
        for imp in values(m,'import'):
            mn=one(imp,'name');check(mn in macros,'missing macro '+mn)
            if mn in macros:allowed|={one(a,'id')for a in values(macros[mn][1],'animation')}
        for s in values(e,'state'):
            for a in values(s,'animation'):check(a in allowed,'unresolved state animation '+name+' '+a)
    for f in(MOD/'gfx').rglob('*.mesh'):
        for o in binary(f).find('object'):
            check(o[0].tag=='mesh','skeleton before mesh '+f.name);sk=o.find('skeleton');target=f in bs
            if target and f not in bodybs:check(sk is None and all(m.find('skin')is None for m in o.findall('mesh')),'accessory BS rig present '+f.name)
            if f in bodybs:check(sk is not None,'body BS lost rig '+f.name)
            if sk is not None:
                D=rigdata(sk);check(len(sk)<256 and len(D['names'])==len(set(D['names'])),'bad rig size/unique names '+f.name);check(all(p is None or p<i for i,p in enumerate(D['parents'])),'bad parent chain '+f.name)
            for m in o.findall('mesh'):
                p=np.asarray(m.get('p')).reshape(-1,3);check(np.isfinite(p).all(),'nonfinite mesh '+f.name);skin=m.find('skin')
                if skin is not None:
                    ix=np.asarray(skin.get('ix'));w=np.asarray(skin.get('w'));check(sk is not None and np.all(ix[w>0]>=0)and np.all(ix[w>0]<len(sk)),'skin key mismatch '+f.name)
                for mat in m.findall('material'):
                    for vv in mat.attrib.values():
                        for v in vv:
                            if isinstance(v,str)and v.endswith('.dds'):check('/'not in v and '\\'not in v and v.lower()in catalog,'binary DDS not globally valid '+f.name+' '+v)
    acces=clausewitz((MOD/'gfx/portraits/accessories/uma_parts.txt').read_text(encoding='utf-8-sig'));genes=one(one(clausewitz((MOD/'common/genes/uma_parts.txt').read_text(encoding='utf-8-sig')),'special_genes'),'accessory_genes');ag={k:{n for n,v in group if isinstance(v,list)}for k,group in genes if isinstance(group,list)}
    for name,entry in acces:
        for e in values(entry,'entity'):
            check(one(e,'entity')in entities,'accessory entity absent '+name)
            for node in values(e,'node'):check(node in ['bn_h_head','body_root'],'invalid external node '+node)
    for k,e in clausewitz((MOD/'common/ethnicities/uma_ethnicity.txt').read_text(encoding='utf-8-sig')):check(not any(n in ag for n,v in e),'ethnicity accessory '+k)
    for f in MOD.rglob('*.txt'):
        text=f.read_text(encoding='utf-8-sig');check(f.read_bytes().startswith(b'\xef\xbb\xbf'),'TXT no BOM '+f.name);check(not re.search(r'uma_(skin|hair|eye)_color',text),'custom color key retained '+f.name);t=clausewitz(text)
        if f.name=='uma_customization.txt':
            for key,group in t:
                for item,v in group:
                    if isinstance(v,list)and values(v,'dna_modifiers'):
                        for a in values(one(v,'dna_modifiers'),'accessory'):check(one(a,'mode')=='add'and one(a,'gene')in ag and one(a,'template')in ag[one(a,'gene')],'customization accessory invalid '+str(item))
        if f.name in ['uma_customization.txt','uma_ethnicity.txt','000_uma_genes_color.txt']:
            # Validate numeric leaves inside color sections, not unrelated morph coordinates.
            def colors(tree,active=False):
                for k,v in tree:
                    iscolor=active or k in ['color','color_genes','hair_color','skin_color','eye_color']
                    if isinstance(v,list):colors(v,iscolor)
                    elif iscolor and re.fullmatch(r'-?\d*\.\d+',str(v)):check(len(str(v).split('.')[1])<=2,'color precision '+f.name+' '+str(v))
            colors(t)
    color=one(clausewitz((MOD/'common/genes/000_uma_genes_color.txt').read_text(encoding='utf-8-sig')),'color_genes');original=one(clausewitz((GAME/'common/genes/00_genes_color.txt').read_text(encoding='utf-8-sig')),'color_genes');check([(k,v)for k,v in color if k!='portrait_group']==original,'stock color definitions changed');check('000_uma_genes_color.txt'<'00_genes_color.txt','wrong color load order')
    types=one(clausewitz((MOD/'common/portrait_types/000_uma_portrait_types.txt').read_text(encoding='utf-8-sig')),'uma');check('000_uma_portrait_types.txt'<'00_human_types.txt','wrong types load order')
    for k in ['uma_male','uma_female']:check(one(one(types,k),'minimum_age')=='18','changed adult age')
    for k in ['uma_boy','uma_girl']:check(one(one(types,k),'maximum_age')=='18','changed child age')
    check(len(values(one(types,'attach'),'joint_attachment'))==1,'extra clav attachments retained')
    for actor in ['1001','1002']:
        folder=MOD/f'gfx/models/portraits/uma/{actor}';check(len(list(folder.glob(f'uma_{actor}_head_*.asset')))==1,'multiple head assets '+actor);check(not list(folder.glob('*neck*.asset'))and not list(folder.glob('*face*.asset')),'independent face/neck assets '+actor);check(not list(folder.glob('*cheek*.asset'))and not list(folder.glob('*tear*.asset')),'expression asset split '+actor)
    report=dict(passed=not errors,errors=errors,pdxmesh=len(meshes),entities=len(entities),meshsettings=settings,binary_meshes=len(cache),BS_declarations=bsdecl,accessory_targets_without_rig=len(bs-bodybs),body_BS_skeleton_retained=len(bodybs),modules=modules,global_basename_contract=True,color_stock_definitions=True,color_precision_max=2,external_nodes_public=True,CK3_engine_executed=False,ruler_designer_crash_cause_confirmed=False)
    (ROOT/'Reports/static-validation.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V9_VALIDATION',report['passed'],len(errors),[(m['set'],m['bones'])for m in modules],flush=True)
    if errors:print('\n'.join(errors[:50]));raise SystemExit(1)
if __name__=='__main__':main()
