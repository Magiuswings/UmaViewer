"""Private native motion macros; preserve stock state IDs and compact stock .asset layout."""
import sys,json,copy,re
from pathlib import Path
from paths_v8 import ROOT,MOD,REPO,V7,GAME
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import clausewitz,one,values,script_atom

SUPPORTED={'bs_body_breast_shape_'+str(i)for i in range(1,5)}|{'bs_body_fat_1','bs_body_gaunt_1'}

def render(tree,depth=0):
    lines=[];tab='\t'*depth
    for k,v in tree:
        prefix=tab+(script_atom(k)+' = 'if k is not None else'')
        if isinstance(v,list):
            if k in ('animation','blend_shape')and all(not isinstance(a,list)for _,a in v):
                parts=[n+' = '+json.dumps(str(a),ensure_ascii=False)for n,a in v]
                lines.append(prefix+'{ '+parts[0].ljust(66)+'\t'+ '\t'.join(parts[1:])+' }')
            elif k=='import'and any(a=='skeletal_animation_set'for n,a in v):
                lines.extend([prefix+'{',tab+'\ttype = skeletal_animation_set',tab+'\tname = '+json.dumps(one(v,'name')),tab+'}'])
            else:lines.extend([prefix+'{',render(v,depth+1),tab+'}'])
        else:
            atom=json.dumps(str(v),ensure_ascii=False)if k in ('name','file','pdxmesh','shader','shader_file','reference_skeleton','blend_shape','additive_animation')and not isinstance(v,list)else script_atom(v)
            lines.append(prefix+atom)
    return '\n'.join(lines)

def setfield(tree,key,value):
    matches=[i for i,(k,v)in enumerate(tree)if k==key]
    if matches:tree[matches[0]]=(key,value)
    else:tree.append((key,value))

def remove_additive_attributes(entity):
    entity[:]=[(k,v)for k,v in entity if not(k=='attribute'and values(v,'additive_animation'))]

def original_ids(file,setname):
    tree=clausewitz(file.read_text(encoding='utf-8-sig'))
    macros=[m for m in values(tree,'skeletal_animation_set')if one(m,'name')==setname]
    assert len(macros)==1,(file,setname)
    return [one(a,'id')for a in values(macros[0],'animation')]

def main():
    headregs={r['prefix']+'_mesh':r for r in json.loads((ROOT/'Reports/head-registration.json').read_text())}
    carrier={'uma_0001_head_male_mesh','uma_0001_head_female_mesh'}
    headids=original_ids(V7/'UMA-V7/gfx/models/portraits/uma/animation/uma_common_head.asset','uma_natural_common_head')
    bodyids=original_ids(GAME/'gfx/models/portraits/male_body/male_body.asset','common_body')
    bodyids+=['idle_entry','idle','frontEnd_middle_entry'];headids+=['idle_entry','idle','frontEnd_middle_entry']
    modules={};changed=[];required={m:[]for m in ['head','body','ear','tail']}
    for file in sorted((MOD/'gfx').rglob('*.asset')):
        tree=clausewitz(file.read_text(encoding='utf-8-sig'));filemods={}
        for mesh in values(tree,'pdxmesh'):
            name=one(mesh,'name');module=None
            if name=='uma_body_mesh':module='body'
            elif name in carrier:module='head'
            elif name in headregs:
                r=headregs[name]
                if r['element']=='tail':module='tail'
                elif r.get('node')and r['element']in ('ear','headwear'):module='ear'
            mesh[:]=[(k,v)for k,v in mesh if k not in ('animation','additive_animation')and not(k=='import'and one(v,'type')=='skeletal_animation_set')]
            if module:
                mesh.insert(3,('import',[('type','skeletal_animation_set'),('name','uma_native_'+module)]));modules.setdefault(module,[]).append(dict(mesh=name,asset=file.relative_to(MOD).as_posix(),file=one(mesh,'file')));filemods[name]=module
                original=V7/'UMA-V7'/file.relative_to(MOD)
                if original.exists():
                    oldtree=clausewitz(original.read_text(encoding='utf-8-sig'))
                    for oldmesh in values(oldtree,'pdxmesh'):
                        if one(oldmesh,'name')==name:required[module].extend(one(a,'id')for a in values(oldmesh,'animation'))
        for entity in values(tree,'entity'):
            remove_additive_attributes(entity)
            module=filemods.get(one(entity,'pdxmesh'))
            if module:
                for state in values(entity,'state'):required[module].extend(v for v in values(state,'animation')if isinstance(v,str))
            if one(entity,'pdxmesh')=='uma_body_mesh':
                entity[:]=[(k,v)for k,v in entity if not(k=='attribute'and values(v,'blend_shape')and one(v,'name')not in SUPPORTED)]
            for joint in values(entity,'joint_attachment'):
                if values(joint,'head_root'):
                    pass
        file.write_text(render(tree)+'\n',encoding='utf8');changed.append(file.relative_to(MOD).as_posix())
    assert set(modules)=={'head','body','ear','tail'},modules.keys()
    refs={'head':'uma_0001_head_female_mesh','body':'uma_body_mesh','ear':'uma_1001_ear_00_mesh','tail':'uma_1001_tail_base_mesh'}
    records=[]
    for module in ['head','body','ear','tail']:
        ids=list(dict.fromkeys((headids if module=='head'else bodyids)+required[module]))
        macro=[('name','uma_native_'+module),('reference_skeleton',refs[module])]+[('animation',[('id',i),('type','uma_'+module+'_native_idle.anim')])for i in ids]
        dest=MOD/f'gfx/models/portraits/uma/animation/{module}/uma_{module}_animations.asset';dest.write_text(render([('skeletal_animation_set',macro)])+'\n',encoding='utf8')
        records.append(dict(module=module,macro='uma_native_'+module,reference_skeleton=refs[module],regular_ids=len(ids),single_file='uma_'+module+'_native_idle.anim',importing_meshes=modules[module]))
    # 1002 core has its own animation/bind names. The attachment joint uses its own Head.
    def alias_nodes(t,actor2=False):
        for i,(k,v)in enumerate(t):
            is2=actor2 or(k is not None and str(k).startswith('uma_1002_'))
            if isinstance(v,list):alias_nodes(v,is2)
            elif is2 and k=='node'and v=='bn_h_head':t[i]=(k,'uma_1002_bn_h_head')
    for relative in ['common/genes/uma_parts.txt','gfx/portraits/accessories/uma_parts.txt']:
        parts=MOD/relative;tree=clausewitz(parts.read_text(encoding='utf-8-sig'));alias_nodes(tree);parts.write_text(render(tree)+'\n',encoding='utf-8-sig')
    for row in headregs.values():
        if row['actor']=='1002'and row.get('node')=='bn_h_head':row['node']='uma_1002_bn_h_head'
    (ROOT/'Reports/head-registration.json').write_text(json.dumps(list(headregs.values()),ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'Reports/native-motion-registration.json').write_text(json.dumps(dict(modules=records,assets_rewritten=changed,no_additive_animation=True,retained_body_BS_attributes=sorted(SUPPORTED),stock_unchanged=True),indent=2),encoding='utf8');print('NATIVE_MODULE_MACROS',[(r['module'],r['regular_ids'],len(r['importing_meshes']))for r in records],flush=True)

if __name__=='__main__':main()
