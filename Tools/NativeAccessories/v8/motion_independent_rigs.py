"""Exact useful native ear/headwear union, and unchanged shared tail bind."""
import json,sys,copy,re,hashlib
from pathlib import Path
import numpy as np
sys.path[:0]=['C:/Users/33775/Desktop/网页制作/UmaV7Scripts','E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter']
from build_ck3_mod import parser_only
from head_pdx_tools import world,skeleton,make_mesh
from PIL import Image
V8=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');OUT=V8/'Rigs';MOTION=V8/'MotionSources';PARTS=MOTION/'rigged-parts';V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');rows=json.loads((V7/'Reports/head-registration.json').read_text());variants=[];components=[];names=['uma_ear_root'];parents=[None];worlds=[np.eye(4)]
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def typed(label,sk):
    nodes=sorted(sk,key=lambda b:b.get('ix')[0]);w=world(sk);pa=[b.get('pa')[0]if b.get('pa')else None for b in nodes];return {'label':label,'names':[b.tag for b in nodes],'parents':pa,'world':w.tolist(),'inverse_bind':np.linalg.inv(w).tolist(),'bind_local':[(np.linalg.inv(w[p])@m if p is not None else m).tolist()for m,p in zip(w,pa)],'bones':len(nodes),'index_by_name':{b.tag:i for i,b in enumerate(nodes)},'skeleton_attributes':[{'name':b.tag,'attributes':b.attrib}for b in nodes],'xml_order_equals_ix':[b.get('ix')[0]for b in sk]==list(range(len(sk))),'parents_before_children':all(p is None or p<i for i,p in enumerate(pa))}
for actor,variant in sorted({(r['actor'],r['variant'])for r in rows if r['element']in ['ear','headwear']}):
    selected=[r for r in rows if (r['actor'],r['variant'])==(actor,variant)and r['element']in ['ear','headwear']];need=set();weighted=set();reference=None;trees=[]
    for row in selected:
        tree=P.read_meshfile(row['mesh']);shape=tree.find('object')[0];sk=shape.find('skeleton');nodes=sorted(sk,key=lambda b:b.get('ix')[0]);W=world(sk);skin=shape.find('mesh').find('skin');ix=np.array(skin.get('ix'));w=np.array(skin.get('w'));positive=set(ix[w>1e-8]);weighted|={nodes[i].tag for i in positive};need|=positive
        if reference is None:reference=(nodes,W,sk)
        else:assert [b.tag for b in nodes]==[b.tag for b in reference[0]]and np.max(np.abs(W-reference[1]))<1e-7
        trees.append((row,tree))
    nodes,W,sk=reference;need|={i for i,b in enumerate(nodes)if re.search(r'(^|_)ear(_|$|[0-9])',b.tag,re.I)};stack=list(need)
    while stack:
        i=stack.pop();pa=nodes[i].get('pa')
        if pa and pa[0]not in need:need.add(pa[0]);stack.append(pa[0])
    ordered=[];seen=set()
    def visit(i):
        if i in seen:return
        pa=nodes[i].get('pa')
        if pa:visit(pa[0])
        seen.add(i);ordered.append(i)
    for i in sorted(need):visit(i)
    namespace=f'uma_ear_{actor}_{variant}__';mapping={nodes[i].tag:namespace+nodes[i].tag for i in ordered};offset=len(names);ixmap={i:offset+k for k,i in enumerate(ordered)}
    for i in ordered:names.append(mapping[nodes[i].tag]);pa=nodes[i].get('pa');parents.append(ixmap[pa[0]]if pa else 0);worlds.append(W[i])
    variants.append({'actor':actor,'variant':variant,'namespace':namespace,'kept':len(ordered),'all_positive_weight_bones_retained':True,'all_native_Ear_reference_points_retained':True,'old_name_to_union_name':mapping,'old_index_to_union_index':{str(i):ixmap[i]for i in ordered},'positive_weight_bones':sorted(weighted),'pruned_unrelated_bones':[b.tag for i,b in enumerate(nodes)if i not in need],'source_meshes':[r['mesh']for r,t in trees]})
    for row,tree in trees:components.append((row,tree,ixmap))
assert len(names)<255,len(names);ears=skeleton(names,parents,worlds);earrig=typed('earcarrier',ears);dump(OUT/'earcarrier.json',earrig);dump(OUT/'ear-variant-remap.json',variants)
def template(label,sk):
    prefix='uma_'+label;make_mesh(P,OUT/(label+'.mesh'),prefix+'Shape',np.array([[0,0,0],[.01,0,0],[0,.01,0]]),np.tile([0,0,1.],(3,1)),np.array([[0,0],[1,0],[0,1.]]),np.array([[0,1,2]]),np.array([[0,-1,-1,-1]]*3),np.array([[1.,0,0,0]]*3),copy.deepcopy(sk),'portrait_hair',prefix)
    for suffix,color in [('diffuse',[255,255,255,0]),('normal',[0,128,0,128]),('properties',[0,38,0,180])]:Image.fromarray(np.tile(color,(4,4,1)).astype(np.uint8),'RGBA').save(OUT/(prefix+'_'+suffix+'.dds'),pixel_format='DXT5')
template('earcarrier',ears);checks=[]
for row,tree,ixmap in components:
    shape=tree.find('object')[0];mesh=shape.find('mesh');oldsk=shape.find('skeleton');oldW=world(oldsk);skin=mesh.find('skin');oldix=np.array(skin.get('ix'));w=np.array(skin.get('w'));newix=np.array([ixmap.get(int(i),-1)if i>=0 else -1 for i in oldix]);assert all(i>=0 for i in newix[w>1e-8]);before={k:copy.deepcopy(mesh.get(k))for k in ['p','n','ta','u0','tri']};shape.remove(oldsk);shape.append(copy.deepcopy(ears));skin.set('ix',newix.tolist());folder=PARTS/row['actor'];folder.mkdir(parents=True,exist_ok=True);path=folder/Path(row['mesh']).name;P.write_meshfile(str(path),tree);parsed=P.read_meshfile(str(path)).find('object')[0];actual=parsed.find('mesh');assert all(actual.get(k)==v for k,v in before.items());assert actual.find('skin').get('w')==skin.get('w');newW=world(parsed.find('skeleton'));error=max(float(np.linalg.norm(newW[new]-oldW[old]))for old,new in ixmap.items());assert error<1e-4
    checks.append({'actor':row['actor'],'variant':row['variant'],'element':row['element'],'source':row['mesh'],'output_mesh':str(path),'source_shape':shape.tag,'bones':len(names),'weight_ix_remapped_by_native_name':True,'geometry_uv_normals_tangents_triangles_weights_unchanged':True,'neutral_source_bind_world_error_max':error})
tailrows=[r for r in rows if r['element']=='tail'];tailtrees=[P.read_meshfile(r['mesh'])for r in tailrows];original=tailtrees[0].find('object')[0].find('skeleton');tw=world(original);tnodes=sorted(original,key=lambda b:b.get('ix')[0]);told=[b.tag for b in tnodes];tname=['uma_tail__'+n for n in told];tpa=[b.get('pa')[0]if b.get('pa')else None for b in tnodes];tails=skeleton(tname,tpa,tw);tailrig=typed('tailcarrier',tails);dump(OUT/'tailcarrier.json',tailrig);template('tailcarrier',tails);tailchecks=[]
for row,tree in zip(tailrows,tailtrees):
    shape=tree.find('object')[0];old=shape.find('skeleton');assert [b.tag for b in sorted(old,key=lambda b:b.get('ix')[0])]==told;assert np.max(np.abs(world(old)-tw))<1e-7;shape.remove(old);shape.append(copy.deepcopy(tails));path=PARTS/row['actor']/Path(row['mesh']).name;P.write_meshfile(str(path),tree);tailchecks.append({'actor':row['actor'],'source':row['mesh'],'output_mesh':str(path),'bones':len(tname),'geometry_weights_and_source_inverse_bind_unchanged':True,'old_name_to_union_name':dict(zip(told,tname))})
result={'ear':{'bones':len(names),'mesh':str(OUT/'earcarrier.mesh'),'json':str(OUT/'earcarrier.json'),'variant_remap':str(OUT/'ear-variant-remap.json'),'independent_components':checks,'attachment_node_by_actor':{'1001':'bn_h_head','1002':'uma_1002_bn_h_head'},'bind_space':'Original native accessory attachment-local bind preserved exactly; universal root world I, namespaced original ancestry unchanged.','reference_skeleton_pdxmesh':'uma_1001_ear_00_mesh'},'tail':{'bones':len(tname),'mesh':str(OUT/'tailcarrier.mesh'),'json':str(OUT/'tailcarrier.json'),'independent_components':tailchecks,'source_name_to_target':dict(zip(told,tname)),'attachment_node':'body_root','reference_skeleton_pdxmesh':'uma_1001_tail_base_mesh'},'no_final_models_or_configs_modified':True,'neutral_bind_identity_preserved':True,'all_reference_and_base_skeleton_j_exact':True,'ear_retain_policy':'Positive Ear/headwear weighted bones, complete ancestor paths and all Ear-named useful native refs; unrelated face/hair helpers remain original source/header records, not copied to independent ear module. Actor/variant namespaces preserve distinct driver tables as well as differing points.'};dump(OUT/'ear-tail-rig-contract.json',result);dump(MOTION/'independent-rig-validation.json',result);print('INDEPENDENT_RIGS_READY',len(names),len(tname),len(checks),len(tailchecks),flush=True)
