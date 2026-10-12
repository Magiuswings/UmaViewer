"""V8 independent typed rigs/contracts. Never modifies V7 or finalmodel.

Preserve every retained inverse-bind exactly; remove only true Ear/Tail subtrees and
uma_head_base (reparent children); alias actor2 stock facial bones; build242 union.
Import helpers are used by root's later stage rewrite, not executed on final meshes here.
"""
import os,json,sys,copy,re,argparse
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
import xml.etree.ElementTree as ET
V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7');DEFAULT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');REPO=Path('E:/UmaViewer-Workspace/UmaViewer-source');sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
P=parser_only(Path('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'));COMMON={'head_root','bn_h_l_clavicle','bn_h_r_clavicle'}
def is_ear_tail(name):
 native=name.removeprefix('uma_src_')
 return name.startswith('bn_h_ear')or native.startswith(('Ear','Sp_He_Ear','Tail','Sp_Hi_Tail','Sp_He_Tail'))or name.startswith(('bn_h_tail','bn_sp_tail','bn_tail'))or native.startswith('tail_')
def alias_name(name,actor):
 return 'uma_1002_'+name if str(actor)=='1002'and name.startswith('bn_h_')and name not in COMMON else name
def bone_world(sk):return np.linalg.inv(inverse_bind(sk))
def transform_skeleton(source,actor=None,head=True):
 old=list(source);names=[b.tag for b in old];parents=[b.get('pa',[None])[0]for b in old];removed={i for i,n in enumerate(names)if is_ear_tail(n)};branch_roots=removed.copy();changed=True
 while changed:
  changed=False
  for i,pa in enumerate(parents):
   if pa in removed and i not in removed:removed.add(i);changed=True
 if head and'uma_head_base'in names:removed.add(names.index('uma_head_base'))
 retained=[i for i in range(len(old))if i not in removed];index={i:j for j,i in enumerate(retained)};out=ET.Element('skeleton');mapping={};reparented=[];root_normalization=None
 def ancestor(i):
  seen=set()
  while i in removed:
   if i in seen:raise ValueError('cycle in removed branch')
   seen.add(i);i=parents[i]
   if i is None:return None
  return i
 for i in retained:
  node=copy.deepcopy(old[i]);node.tag=alias_name(node.tag,actor);node.set('ix',[index[i]]);pa=ancestor(parents[i])if parents[i]is not None else None
  # Specialized neck bridge intentionally uses identity head_root and mixed bodyThor coordinates.
  # External bodyThor*inverse(carrierRoot) cancels sharedRoot=-d for lower-ring root weights.
  # Preserve all original tx bytes; same-name bind equality is not valid for this bridge.
  if pa is None:node.attrib.pop('pa',None)
  else:node.set('pa',[index[pa]])
  if pa!=parents[i]:reparented.append(dict(bone=names[i],old_parent=names[parents[i]]if parents[i]is not None else None,new_parent=names[pa]if pa is not None else None))
  out.append(node);mapping[names[i]]=node.tag
 fallback={}
 for i in range(len(old)):
  pa=ancestor(i);fallback[i]=index[pa]if pa is not None else None
 assert len({n.tag for n in out})==len(out)
 for oldix,newix in index.items():
  if names[oldix]!='head_root'or not root_normalization:assert old[oldix].get('tx')==out[newix].get('tx')
 info=dict(actor=actor,source_bones=len(old),target_bones=len(out),old_to_new_name=mapping,old_index_to_new_index={str(i):j for i,j in index.items()},removed=[dict(name=names[i],index=i,branch=is_ear_tail(names[i])or i in branch_roots,reason='structural attachment helper'if names[i]=='uma_head_base'else'actual Ear/Tail subtree')for i in sorted(removed)],reparented=reparented,worldbind_exact_for_all_retained=True,head_root_original_bind_preserved=True,head_root_normalization=None,additive_used=False)
 return out,info,fallback
def transform_component_tree(tree,actor,head=True):
 """Root may call on final stage trees. All geometry/UV/weights untouched; indices remapped.
 Positive removed-branch weights explicitly fail instead of silently moving visible parts.
 Ear independent-native-pose trees must not call this head branch pruner.
 """
 reports=[]
 for obj in tree.find('object'):
  oldsk=obj.find('skeleton')
  if oldsk is None:continue
  newsk,info,fallback=transform_skeleton(oldsk,actor,head);changed_ix=0;unused=0
  for mesh in obj.findall('mesh'):
   skin=mesh.find('skin')
   if skin is None:continue
   ix=np.array(skin.attrib['ix'],int);w=np.array(skin.attrib['w'],float);newix=ix.copy()
   for i in np.unique(ix[ix>=0]):
    retained=str(int(i))in info['old_index_to_new_index'];affected=ix==i
    if not retained and np.any(w[affected]>0):raise ValueError('positive weight on removed Ear/Tail/helper in component: '+oldsk[int(i)].tag)
    if retained:newix[affected]=info['old_index_to_new_index'][str(int(i))]
    else:newix[affected]=-1;unused+=int(sum(affected))
   changed_ix+=int(sum(newix!=ix));skin.set('ix',newix.tolist());assert np.all(newix[w>0]>=0);assert np.all(newix[w>0]<len(newsk))
  obj.remove(oldsk);obj.append(newsk);obj.attrib['lod']=[0];nodes=list(obj);obj[:]=[n for n in nodes if n.tag=='mesh']+[n for n in nodes if n.tag!='mesh'];info.update(shape=obj.tag,changed_skin_index_slots=changed_ix,removed_zero_weight_slots=unused,skin_weights_exact=True,geometry_uv_tri_exact=True);reports.append(info)
 return tree,reports
def rig_json(sk,label):
 names=[b.tag for b in sk];world=bone_world(sk);parents=[b.get('pa',[None])[0]for b in sk];locals=[]
 for i,pa in enumerate(parents):locals.append((np.linalg.inv(world[pa])@world[i]if pa is not None else world[i]).tolist())
 return dict(label=label,names=names,parents=parents,world=world.tolist(),inverse_bind=inverse_bind(sk).tolist(),bind_local=locals,bones=len(sk),index_by_name={n:i for i,n in enumerate(names)},skeleton_attributes=[dict(name=b.tag,attributes=b.attrib)for b in sk],xml_order_equals_ix=all(b.get('ix')==[i]for i,b in enumerate(sk)),parents_before_children=all(pa is None or pa<i for i,pa in enumerate(parents)),head_root_point_cm=world[names.index('head_root'),:3,3].tolist()if'head_root'in names else None,additive_used=False,worldbind_source_precision='original float32 inverse-bind bytes retained')
def write_rig(path,template,sk,label):
 tree=copy.deepcopy(template)
 for obj in tree.find('object'):
  for oldsk in obj.findall('skeleton'):obj.remove(oldsk)
  obj.append(copy.deepcopy(sk));obj.tag=obj.tag.removesuffix('Shape');obj.attrib['lod']=[0];nodes=list(obj);obj[:]=[n for n in nodes if n.tag=='mesh']+[n for n in nodes if n.tag!='mesh']
  for mesh in obj.findall('mesh'):
   skin=mesh.find('skin')
   if skin is not None:skin.set('ix',[0 if w>0 else-1 for w in skin.attrib['w']])
 P.write_meshfile(str(path),tree);back=P.read_meshfile(str(path));actual=back.find('object')[0].find('skeleton');assert np.array_equal(inverse_bind(actual),inverse_bind(sk));assert[n.tag for n in actual]==[n.tag for n in sk];record=rig_json(actual,label);record['pdx_readback_exact']=True;record['template_only_not_body_geometry']=True;path.with_suffix('.json').write_text(json.dumps(record,indent=2),encoding='utf8');return record
def build_union(carrier,actor2):
 union=copy.deepcopy(carrier);names={b.tag:i for i,b in enumerate(union)};required={i for i,b in enumerate(actor2)if b.tag.startswith('uma_1002_bn_h_')};todo=list(required)
 while todo:
  i=todo.pop();pa=actor2[i].get('pa',[None])[0]
  if pa is not None and pa not in required:required.add(pa);todo.append(pa)
 added=[];world=bone_world(union);actorworld=bone_world(actor2)
 for i,b in enumerate(actor2):
  if i not in required:continue
  if b.tag in names:
   assert np.array_equal(world[names[b.tag]],actorworld[i]),'common binding differs: '+b.tag
   continue
  if not(b.tag.startswith('uma_1002_bn_h_')or b.tag in COMMON):raise ValueError('non-stock actor2 ancestor unexpectedly required: '+b.tag)
  node=copy.deepcopy(b);newindex=len(union);node.set('ix',[newindex]);pa=b.get('pa',[None])[0]
  if pa is not None:assert actor2[pa].tag in names;node.set('pa',[names[actor2[pa].tag]])
  union.append(node);names[node.tag]=newindex;added.append(node.tag)
 assert len(union)<255,'union exceeds supported contract';return union,added
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(DEFAULT));args=ap.parse_args();root=Path(args.root).resolve();out=root/'Rigs'
 if'2026-10-11-UMA-V7'in str(root):raise ValueError('V7 output forbidden')
 out.mkdir(parents=True,exist_ok=True);carrierfile=V7/'UMA-V7/gfx/models/portraits/uma/0001/uma_0001_head_female.mesh';male=V7/'UMA-V7/gfx/models/portraits/uma/0001/uma_0001_head_male.mesh';carrier_tree=P.read_meshfile(str(carrierfile));carrier,carrierinfo,_=transform_skeleton(carrier_tree.find('object')[0].find('skeleton'),'1001',True);actor_rigs={};typed={};semantic={};sources={}
 for actor in ['1001','1002']:
  source=V7/f'Rigs/head_{actor}.mesh';tree=P.read_meshfile(str(source));sk,info,_=transform_skeleton(tree.find('object')[0].find('skeleton'),actor,True);actor_rigs[actor]=sk;typed[actor]=write_rig(out/f'head_{actor}.mesh',tree,sk,'actor'+actor+' native reference (not carrier)');semantic[actor]=info;original_map=json.loads((V7/f'Rigs/head_{actor}-source-map.json').read_text());mapped={native:info['old_to_new_name'].get(old)for native,old in original_map.items()};sources[actor]=mapped;(out/f'head_{actor}-source-map.json').write_text(json.dumps(mapped,indent=2),encoding='utf8')
 union,added=build_union(carrier,actor_rigs['1002']);uniontyped=write_rig(out/'headcarrier.mesh',carrier_tree,union,'shared male/female head carrier union');female=write_rig(out/'headcarrier_female.mesh',carrier_tree,union,'female identical head carrier union');maletyped=write_rig(out/'headcarrier_male.mesh',P.read_meshfile(str(male)),union,'male identical head carrier union');assert female['skeleton_attributes']==maletyped['skeleton_attributes'];bodytree=P.read_meshfile(str(V7/'Rigs/body.mesh'));body,binfo,_=transform_skeleton(bodytree.find('object')[0].find('skeleton'),None,False);bodytyped=write_rig(out/'body.mesh',bodytree,body,'body original stock134+source helpers');components=[];componentfolder=out/'component-rigs';componentfolder.mkdir(exist_ok=True);registered=json.loads((V7/'Reports/head-registration.json').read_text())
 for row in registered:
  if row.get('shared_pose')!='head'or row.get('independent_native_pose'):continue
  actor=str(row['actor']);tree=P.read_meshfile(row['mesh']);transformed,infos=transform_component_tree(tree,actor,True);records=[]
  for oi,obj in enumerate(transformed.find('object')):
   sk=obj.find('skeleton');record=rig_json(sk,row['prefix']+' object'+str(oi));posemap={n:uniontyped['index_by_name'].get(n)for n in record['names']};record['union_pose_index_by_name']=posemap;record['source_mesh']=row['mesh'];record['rig_remap']=infos[oi];weighted=set()
   for mesh in obj.findall('mesh'):
    skin=mesh.find('skin')
    if skin is not None:weighted.update(np.array(skin.attrib['ix'])[np.array(skin.attrib['w'])>0].tolist())
   assert all(posemap[record['names'][i]]is not None for i in weighted),'weighted component bone absent from carrier'
   error=max((float(np.max(abs(np.array(record['world'][i])-np.array(uniontyped['world'][posemap[record['names'][i]]]))))for i in weighted),default=0);bridge=row['element']=='neck'and row.get('variant')=='base'
   if not bridge:assert error<.0011,'weighted core bind differs beyond source float32 precision'
   record['weighted_union_bind_max_abs_error']=error;record['weighted_union_bind_tolerance_cm']=.0011;record['weighted_union_bones_missing']=0;record['specialized_neck_bridge_mixed_coordinates']=bridge;record['same_bind_equality_not_applicable']=bridge
   if bridge:record['bridge_contract']='Preserve identity component head_root and inverse(bodyThor)*bodyRing lower positions; sharedRoot=-d cancels external bodyThor*inverse(carrierRoot). Root validates actual attachment+joint override endpoints.'
   records.append(record)
  file=componentfolder/(row['prefix']+'.json');file.write_text(json.dumps(records,indent=2),encoding='utf8');components.append(dict(actor=actor,prefix=row['prefix'],source=row['mesh'],rig_contract=str(file),remap=infos,source_relative_to_mod=Path(row['mesh']).relative_to(V7/'UMA-V7').as_posix()))
 oldworld=bone_world(carrier);world2=bone_world(actor_rigs['1002']);index={b.tag:i for i,b in enumerate(carrier)};difference=[]
 for i,b in enumerate(actor_rigs['1002']):
  original=b.tag.removeprefix('uma_1002_')
  if b.tag in added and original in index:difference.append(dict(original_name=original,actor2_name=b.tag,bind_point_delta_cm=float(np.linalg.norm(world2[i,:3,3]-oldworld[index[original],:3,3]))))
 difference.sort(key=lambda x:-x['bind_point_delta_cm']);contract=dict(version=1,output_root=str(out),source_v7_read_only=True,final_models_modified=False,head_direct_root=dict(head_root_offset_cm=uniontyped['head_root_point_cm'],uma_head_base_removed=True,all_other_retained_worldbind_exact=True,no_additives=True),head_carrier=dict(bones=len(union),pruned_carrier_bones=len(carrier),actor2_core_added=len(added),same_male_female_skeleton=True,max_bones_exclusive=255,mesh=str(out/'headcarrier.mesh'),json=str(out/'headcarrier.json'),male_mesh=str(out/'headcarrier_male.mesh'),female_mesh=str(out/'headcarrier_female.mesh'),actor2_added_names=added,prune=carrierinfo),body=dict(bones=len(body),mesh=str(out/'body.mesh'),json=str(out/'body.json'),prune=binfo,exact_original146=len(body)==146 and not binfo['removed']),actor1=dict(mesh=str(out/'head_1001.mesh'),json=str(out/'head_1001.json'),mapping=semantic['1001']),actor2=dict(mesh=str(out/'head_1002.mesh'),json=str(out/'head_1002.json'),mapping=semantic['1002'],stock_original_to_new={b.removeprefix('uma_1002_'):b for b in added}),semantic_mappings=semantic,components=components,common_names=sorted(COMMON),alias_necessity_evidence=difference,unmatched_actor2_native_aux='Retained in actual component contracts; not all appended to common carrier. All current positive core skin remains represented by union names.',ear_independent_native_pose='Excluded from these transforms; independent union/pose contract belongs to root.',apply_api='v8_rigs.transform_component_tree(tree, actor, head=True); preserves p/n/ta/UV/tri/w, remaps ix and skeleton; do not call for independent ear components.')
 contract['specialized_bind_exceptions']=dict(components=['uma_1001_neck_base','uma_1002_neck_base'],preserve_all_original_inverse_bind=True,component_head_root='Identity; intentionally differs from carrier -d',same_name_worldbind_equality_required=False,full_attachment_equation='bodyThor * inverse(carrierRoot) * sharedRootPose * inverse(componentRootBind) * thoracic-local lowerVertex; +d and -d cancel only with componentRootBind=I',validation_reports=[str(root/'Reports/bridge-root-normalization-rejected.json'),str(root/'Reports/bridge-bind-exception.json'),str(root/'Reports/rest-attachment-validation.json')])
 (out/'rig-contract.json').write_text(json.dumps(contract,indent=2),encoding='utf8');(out/'semantic-map.json').write_text(json.dumps(semantic,indent=2),encoding='utf8');print('V8_RIG_CONTRACT','body',len(body),'carrier',len(union),'actor1',len(actor_rigs['1001']),'actor2',len(actor_rigs['1002']),'components',len(components),'max_core_point_difference_cm',difference[0]['bind_point_delta_cm'],flush=True)
if __name__=='__main__':main()
