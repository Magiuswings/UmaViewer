"""Apply audited head rigs and lossless shared textures to an isolated V8 stage."""
import sys,json,copy,hashlib
from pathlib import Path
from paths_v8 import ROOT,MOD,REPO,PLUGIN,V7
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import parser_only,clausewitz,values,script_block
from v8_rigs import transform_component_tree
from texture_optimize import remap_reference
P=parser_only(PLUGIN)

def geometry(tree):
    return [[dict((k,v)for k,v in m.attrib.items()if k in ['p','n','ta','u0','u1','tri'])for m in o.findall('mesh')]for o in tree.find('object')]

def material_remap(tree,file,manifest):
    count=0
    for n in tree.iter():
        for k,v in list(n.attrib.items()):
            if not isinstance(v,list):continue
            new=[]
            for a in v:
                if isinstance(a,str)and a.lower().endswith('.dds'):
                    mapped=remap_reference(a,file,MOD,manifest);count+=mapped!=a;new.append(mapped)
                else:new.append(a)
            n.set(k,new)
    return count

def text_remap(tree,file,manifest):
    count=0
    for i,(k,v)in enumerate(tree):
        if isinstance(v,list):count+=text_remap(v,file,manifest)
        elif isinstance(v,str)and v.lower().endswith('.dds'):
            new=remap_reference(v,file,MOD,manifest);count+=new!=v;tree[i]=(k,new)
    return count

def main():
    contract=json.loads((ROOT/'Rigs/rig-contract.json').read_text());textures=json.loads((ROOT/'Reports/texture-sharing.json').read_text());head={r['source_relative_to_mod']:r for r in contract['components']};carrierfiles={f'gfx/models/portraits/uma/0001/uma_0001_head_{sex}.mesh':ROOT/f'Rigs/headcarrier_{sex}.mesh'for sex in ['male','female']};report=[]
    for i,file in enumerate(sorted((MOD/'gfx').rglob('*.mesh')),1):
        rel=file.relative_to(MOD).as_posix();tree=P.read_meshfile(str(file));before=geometry(tree);infos=[]
        if rel in head:tree,infos=transform_component_tree(tree,head[rel]['actor'],True)
        elif rel in carrierfiles:
            sk=P.read_meshfile(str(carrierfiles[rel])).find('object')[0].find('skeleton')
            for obj in tree.find('object'):
                for old in obj.findall('skeleton'):obj.remove(old)
                obj.append(copy.deepcopy(sk));obj.set('lod',[0]);infos.append({'placeholder':True,'bones':len(sk)})
        changed=material_remap(tree,file,textures)
        for obj in tree.find('object'):
            children=list(obj);obj[:]=[n for n in children if n.tag=='mesh']+[n for n in children if n.tag!='mesh']
        assert geometry(tree)==before,'geometry changed '+rel
        P.write_meshfile(str(file),tree)
        report.append(dict(file=rel,head_rig_remap=infos,texture_references_changed=changed,geometry_exact=True))
        if i%150==0:print('APPLIED_RIG_DDS',i,flush=True)
    textcount=0
    for file in sorted((MOD/'gfx').rglob('*.asset')):
        tree=clausewitz(file.read_text(encoding='utf-8-sig'));textcount+=text_remap(tree,file,textures);file.write_text(script_block(tree)+'\n',encoding='utf8')
    # JSON paths are recursive values, not replacement on escaped JSON source.
    def paths(value):
        if isinstance(value,dict):return {k:paths(v)for k,v in value.items()}
        if isinstance(value,list):return [paths(v)for v in value]
        if isinstance(value,str):return value.replace(str(V7/'UMA-V7'),str(MOD)).replace((V7/'UMA-V7').as_posix(),MOD.as_posix())
        return value
    for name in ['head-registration.json','clothing-registration.json','configuration.json']:
        f=ROOT/'Reports'/name;f.write_text(json.dumps(paths(json.loads(f.read_text(encoding='utf8'))),ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'Reports/model-rig-texture-application.json').write_text(json.dumps(dict(models=report,asset_texture_references_changed=textcount),indent=2),encoding='utf8');print('MODEL_RIG_DDS_APPLIED',len(report),len(head),textcount,flush=True)

if __name__=='__main__':main()
