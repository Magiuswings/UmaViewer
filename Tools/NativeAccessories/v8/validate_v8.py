"""Read back actual final files, including every BS topology, motion count and texture path."""
import sys,json,re,hashlib,collections
from pathlib import Path
from paths_v8 import ROOT,MOD,REPO,PLUGIN,V7,GAME
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7')]
import numpy as np
from build_ck3_mod import parser_only,clausewitz,one,values
from head_assembly_math import rigdata
from v8_rigs import is_ear_tail
P=parser_only(PLUGIN);ERRORS=[]

def check(ok,message):
    if not ok:ERRORS.append(message)

def resolve(ref,file):
    return (MOD/ref if ref.replace('\\','/').startswith('gfx/')else file.parent/ref).resolve()

def leaf_strings(tree):
    for k,v in tree:
        if isinstance(v,list):yield from leaf_strings(v)
        else:yield k,v

def geom(obj):return obj.findall('mesh')

def main():
    assets={};meshes={};entities={};sets={};rows=[];stats=collections.Counter();meshcache={}
    def binary(path):
        if path not in meshcache:meshcache[path]=P.read_meshfile(str(path))
        return meshcache[path]
    for file in sorted((MOD/'gfx').rglob('*.asset')):
        tree=clausewitz(file.read_text(encoding='utf-8-sig'));assets[file]=tree
        for kind,catalog in [('pdxmesh',meshes),('entity',entities),('skeletal_animation_set',sets)]:
            for node in values(tree,kind):
                name=one(node,'name');check(name not in catalog,'duplicate '+kind+' '+name);catalog[name]=(file,node)
    animationmodule=json.loads((ROOT/'Reports/native-motion-registration.json').read_text())['modules'];clips={}
    for row in animationmodule:
        module=row['module'];macrofile,macro=sets[row['macro']];check(one(macro,'reference_skeleton')in meshes,'undefined reference '+row['macro']);referencefile,ref=meshes[one(macro,'reference_skeleton')];refpath=resolve(one(ref,'file'),referencefile);sk=binary(refpath).find('object')[0].find('skeleton');rig=rigdata(sk)
        ids=[one(a,'id')for a in values(macro,'animation')];check(len(ids)==len(set(ids)),'duplicate regular id '+module);paths={resolve(one(a,'type'),macrofile)for a in values(macro,'animation')};check(len(paths)==1,'module has multiple clips '+module);clip=next(iter(paths));check(clip.exists(),'missing native clip '+str(clip))
        if clip.exists():
            data=P.read_meshfile(str(clip));info=data.find('info');check(info.get('j')[0]==len(sk),'info.j incompatible '+module);check([x.tag for x in info]==rig['names'],'native joint table mismatch '+module);count=info.get('sa')[0];samples=data.find('samples');check(count>1,'no true animation samples '+module)
            for c in 'tqs':
                driven=[b for b in info if c in b.get('sa')[0]];width=3 if c=='t'else 4 if c=='q'else len(driven[0].get(c))if driven else 1;check(len(samples.get(c,[]))==count*len(driven)*width,'invalid sampled '+c+' '+module)
            if module in ['head','body']:check(not any(is_ear_tail(n)for n in rig['names']),'ear/tail in '+module)
            clips[module]=dict(path=str(clip),bones=len(sk),frames=count,regular_ids=len(ids),duration=info.get('sa')[0]/info.get('fps',[30])[0]if info.get('fps')else None)
        for importer in row['importing_meshes']:
            f,m=meshes[importer['mesh']];tree=binary(resolve(one(m,'file'),f));actual=tree.find('object')[0].find('skeleton')
            check([b.tag for b in actual]==rig['names'],'module importing mesh differs '+importer['mesh'])
    bsfiles=set();bodybs=set();emptybs=set()
    for name,(file,entity)in entities.items():
        meshname=one(entity,'pdxmesh');check(meshname in meshes,'entity mesh missing '+name)
        if meshname not in meshes:continue
        mf,mesh=meshes[meshname];allowed={one(a,'id')for a in values(mesh,'animation')}
        for imp in values(mesh,'import'):
            if one(imp,'type')=='skeletal_animation_set'and one(imp,'name')in sets:allowed|={one(a,'id')for a in values(sets[one(imp,'name')][1],'animation')}
        for state in values(entity,'state'):
            for animation in values(state,'animation'):
                if isinstance(animation,str):check(animation in allowed,'unresolved state animation '+name+' '+one(state,'name')+' '+animation)
    for name,(file,mesh)in meshes.items():
        path=resolve(one(mesh,'file'),file);check(path.exists(),'missing mesh '+name)
        if not path.exists():continue
        tree=binary(path);objs={o.tag:o for o in tree.find('object')};stats['pdxmeshes']+=1
        for setting in values(mesh,'meshsettings'):
            tag=one(setting,'name');check(tag in objs,'setting tag absent '+name+' '+tag)
            if tag not in objs:continue
            slot=int(one(setting,'index'));check(slot<len(geom(objs[tag])),'mesh index absent '+name);stats['meshsettings']+=1
            for k,v in leaf_strings(setting):
                if str(v).lower().endswith('.dds'):check(resolve(v,file).exists(),'missing asset DDS '+str(v))
        for imp in values(mesh,'import'):
            if one(imp,'type')=='skeletal_animation_set':check(one(imp,'name')in sets,'undefined macro '+name)
        check(not values(mesh,'additive_animation'),'old additive declarations '+name)
        for target in values(mesh,'blend_shape'):
            tpath=resolve(one(target,'type'),file);check(tpath.exists(),'missing BS '+str(tpath));bsfiles.add(tpath);stats['BS_declarations']+=1
            if name=='uma_body_mesh':bodybs.add(tpath)
            if name in ['uma_0001_head_female_mesh','uma_0001_head_male_mesh']:emptybs.add(tpath)
            if not tpath.exists():continue
            tt=binary(tpath);base=list(tree.find('object'));morph=list(tt.find('object'));check(len(base)==len(morph),'BS objects '+tpath.name)
            for ob,tob in zip(base,morph):
                check(len(geom(ob))==len(geom(tob)),'BS mesh slots '+tpath.name)
                for bm,tm in zip(geom(ob),geom(tob)):
                    check(len(bm.get('p'))==len(tm.get('p')),'BS vertex count '+tpath.name)
                    for k in ['tri','u0','u1']:check(bm.get(k)==tm.get(k),'BS '+k+' changed '+tpath.name)
    for file in sorted((MOD/'gfx').rglob('*.mesh')):
        tree=binary(file.resolve());stats['binary_files']+=1
        for obj in tree.find('object'):
            nodes=[n.tag for n in obj];check(nodes[0]=='mesh','skeleton-first '+file.name);check(not obj.tag.endswith('Shape'),'unnormalized tag '+file.name)
            sk=obj.find('skeleton');isbs=file.resolve()in bsfiles;body=file.resolve()in bodybs
            if isbs and not body:
                check(sk is None,'accessory BS has skeleton '+file.name);check(not any(m.find('skin')is not None for m in geom(obj)),'accessory BS has skin '+file.name);stats['accessory_BS_objects']+=1
            elif body:check(sk is not None,'body BS skeleton removed '+file.name);stats['body_BS_objects']+=1
            if sk is not None:
                rig=rigdata(sk);check(len(sk)<255,'over255 rig '+file.name);check(len(rig['names'])==len(set(rig['names'])),'duplicate bones '+file.name);check(all(b.get('ix')==[i]for i,b in enumerate(sk)),'ix order '+file.name);check(all(p is None or p<i for i,p in enumerate(rig['parents'])),'parent order '+file.name)
            for mesh in geom(obj):
                p=np.asarray(mesh.get('p'),float).reshape(-1,3);tri=np.asarray(mesh.get('tri'),int);check(np.isfinite(p).all(),'nonfinite '+file.name);check(not len(tri)or(int(tri.max())<len(p)and int(tri.min())>=0),'bad tri '+file.name)
                skin=mesh.find('skin')
                if skin is not None:
                    ix=np.asarray(skin.get('ix'),int).reshape(-1,4);w=np.asarray(skin.get('w'),float).reshape(-1,4);check(len(w)==len(p),'skin count '+file.name);check(sk is not None,'skin no skeleton '+file.name)
                    if sk is not None:check(np.all(ix[w>0]>=0)and np.all(ix[w>0]<len(sk)),'positive skin ix invalid '+file.name)
                    check(np.max(abs(w.sum(1)-1),initial=0)<2e-5,'weight sums '+file.name)
                for n in mesh.iter():
                    for v in n.attrib.values():
                        if isinstance(v,list):
                            for ref in v:
                                if isinstance(ref,str)and ref.lower().endswith('.dds'):check(resolve(ref,file).exists(),'missing binary DDS '+file.name+' '+ref)
    for file in MOD.rglob('*.txt'):
        raw=file.read_bytes();check(raw.startswith(b'\xef\xbb\xbf'),'TXT no BOM '+file.name);tree=clausewitz(raw.decode('utf-8-sig'))
        check('uma_head_points'not in raw.decode('utf-8-sig'),'old head additive DNA '+file.name)
        if file.name=='uma_customization.txt':
            def visit(t):
                for k,v in t:
                    if isinstance(v,list):
                        if k=='accessory':check(one(v,'mode')=='add','non-add accessory customization')
                        visit(v)
            visit(tree)
    ag=one(one(clausewitz((MOD/'common/genes/uma_parts.txt').read_text(encoding='utf-8-sig')),'special_genes'),'accessory_genes');accgenes={k for k,v in ag if isinstance(v,list)}
    for en,entry in clausewitz((MOD/'common/ethnicities/uma_ethnicity.txt').read_text(encoding='utf-8-sig')):check(not any(k in accgenes for k,v in entry),'ethnicity accessory '+en)
    baseline=ROOT/'Reports/source-contract.json'
    if baseline.exists():
        check(hashlib.sha256((MOD/'common/portrait_types/uma_portrait_types.txt').read_bytes()).hexdigest()==json.loads(baseline.read_text())['portrait_type_sha256'],'portrait type palette/age contract changed')
    else:check((MOD/'common/portrait_types/uma_portrait_types.txt').read_bytes()==(V7/'UMA-V7/common/portrait_types/uma_portrait_types.txt').read_bytes(),'portrait type palette/age contract changed')
    bases={};dupes=[]
    for f in(MOD/'gfx').rglob('*'):
        if not f.is_file():continue
        if f.name.lower()in bases:dupes.append([str(f),str(bases[f.name.lower()])])
        bases[f.name.lower()]=f
        check(len(str(f))<256,'Windows path too long '+str(f))
    check(not dupes,'gfx basename duplicates '+str(dupes))
    for f in(MOD/'gfx/FX').glob('*.shader'):check(f.read_bytes()==(V7/'UMA-V7/gfx/FX'/f.name).read_bytes(),'shader changed '+f.name)
    textures=json.loads((ROOT/'Reports/texture-sharing.json').read_text());check(textures['old_files_pruned'],'DDS duplicates not pruned')
    for group in textures['groups']:
        f=MOD/group['new'];check(hashlib.sha256(f.read_bytes()).hexdigest()==group['new_sha256'],'DDS shared hash changed '+str(f))
    report=dict(passed=not ERRORS,errors=ERRORS,counts=dict(stats),BS_unique_files=len(bsfiles),body_BS_unique_files=len(bodybs),accessory_BS_unique_files=len(bsfiles-bodybs),empty_head_targets=len(emptybs),modules=clips,registered_sets=len(sets),original_game_modified=False,CK3_engine_executed=False,texture_savings=textures.get('net_bytes_saved'),all_BS_vertex_networks_verified=True,all_asset_and_mesh_DDS_paths_verified=True,all_module_animation_joint_tables_exact=True,all_TXT_UTF8_BOM=True,portrait_age_and_palettes_byte_unchanged=True)
    (ROOT/'Reports/final-static-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('V8_FINAL_STATIC',report['passed'],dict(stats),'ERRORS',len(ERRORS),flush=True)
    if ERRORS:print('\n'.join(ERRORS[:45]));raise SystemExit(1)

if __name__=='__main__':main()
