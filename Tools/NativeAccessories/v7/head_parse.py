import os
"""Parse every available real head/tail, retaining unweighted native transforms too."""
import json,sys,gc
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'HeadSources'));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path.insert(0,str(REPO/'Tools/HeadlessExporter'))
from export_assets import Package,Extractor,key,bone_id,write_json
catalog=json.loads((ROOT/'head-source-catalog.json').read_text(encoding='utf8'));records=[];prior_index=json.loads((ROOT/'head-parts-index.json').read_text(encoding='utf8'))if(ROOT/'head-parts-index.json').exists()else{}
def work(kind,char,variant,name,folder):
    out=ROOT/'parsed'/('chr'+char+'_'+variant if kind=='head'else'tail_'+char);out.mkdir(parents=True,exist_ok=True);package=Package(folder);ex=Extractor(package,out,SimpleNamespace(names={},generic_skin='1',generic_skin_reference='0',skin_mode='auto',skin_tolerance=42.))
    identifier=name.rsplit('/',1)[-1].removeprefix('pfb_');data=ex.prefab(name,kind,identifier,char,[]);original={b['id']:b for b in data['bones']};weighted={w['bone']for m in data['meshes']for w in m['weights']};transforms=[];renderers={}
    for o in package.objects:
        if package.sources.get(key(o))!=name:continue
        if o.type.name in ['SkinnedMeshRenderer','MeshRenderer']:
            renderer=package.read(o);go=renderer.m_GameObject.deref();renderers[key(go)]=o.type.name
        elif o.type.name=='Transform':transforms.append(o)
    transformed=[]
    for o in transforms:
        tf=package.read(o);ident=bone_id(o);parent=bone_id(tf.m_Father.deref())if tf.m_Father else None
        b=original.get(ident,dict(id=ident,name=package.name(o),parent=parent,matrix=package.world(o),unity_transform_id=o.path_id))
        b['native_role']='weighted_bone'if ident in weighted else'weighted_ancestor'if ident in original else'renderer_transform'if key(tf.m_GameObject.deref())in renderers else'unweighted_native_transform'
        transformed.append(b)
    # Preserve original source order and topologically sort all original nodes.
    byid={b['id']:b for b in transformed};ordered=[];seen=set()
    def add(b):
        if b['id']in seen:return
        if b['parent']in byid:add(byid[b['parent']])
        seen.add(b['id']);ordered.append(b)
    for b in transformed:add(b)
    absent={w['bone']for m in data['meshes']for w in m['weights']}-seen
    assert not absent,absent
    data['bones']=ordered;data['native_transform_policy']='All Transform nodes in the real source prefab, with original hierarchy. Weighted bind matrices from renderer inverse-binds override animated/rest Transform world where necessary. No unweighted native transform dropped.';data['weighted_bones']=len(weighted);data['extractor_initial_bone_count']=len(original);data['all_native_transform_count']=len(ordered)
    write_json(out/(kind+'.json'),data)
    targets=[]
    for o in package.objects:
        if o.type.name=='MonoBehaviour':
            try:
                tree=o.read_typetree()
                if '_targetFaces'in tree or '_earTarget'in tree or '_eyeTarget'in tree:targets.append({'unity_object_id':o.path_id,'source_asset':package.sources.get(key(o)),'data':tree})
            except Exception:pass
    if targets:write_json(out/'driven-targets.json',targets)
    rec={'character_id':char,'kind':kind,'variant':variant,'prefab':name,'parsed_json':str(out/(kind+'.json')),'texture_root':str(out/'resources'),'bones':len(ordered),'weighted_bones':len(weighted),'extractor_initial_bones':len(original),'unweighted_extra_native_transforms':len(ordered)-len(original),'driven_targets_json':str(out/'driven-targets.json')if targets else None,'meshes':[{'name':m['name'],'active':m['active'],'vertices':len(m['vertices']),'triangles':sum(len(f['triangles'])//3 for f in m['faces']),'materials':sorted({f['material']for f in m['faces']})}for m in data['meshes']],'warnings':data.get('warnings',[]),'source_original_unmodified':True}
    records.append(rec);write_json(ROOT/'head-parts-index.json',{**prior_index,'records':records,'complete':False});print('HEAD_SOURCE_PARSED',char,variant,kind,rec['bones'],[(m['name'],m['vertices'])for m in rec['meshes']],flush=True)
    del package,ex,data;gc.collect()
for h in catalog['head_prefabs']:
    if h['present']:work('head',h['character_id'],h['variant'],h['name'],ROOT/'decoded'/('chr'+h['character_id']+'_'+h['variant']))
for t in catalog['tails']:
    if t['prefab']and t['prefab']['present']:work('tail',t['character_id'],'00',t['prefab']['name'],ROOT/'decoded'/('tail_'+t['character_id']))
write_json(ROOT/'head-parts-index.json',{**prior_index,'records':records,'complete':True,'resource_availability_catalog':str(ROOT/'head-source-catalog.json'),'neck_report':str(ROOT/'head-neck-interface.json'),'native_bones_dropped':0,'runtime_not_tested':True})
print('ALL_HEAD_TAIL_SOURCE_PARSE_COMPLETE',len(records),flush=True)
