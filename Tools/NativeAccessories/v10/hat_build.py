import os,sys,json,copy,hashlib,xml.etree.ElementTree as X
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
from head_assembly_math import rigdata,readlocals,compose,shared_pose,deform
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V10');MOD=V/'UMA-V10';O=V/'HatRepair';M=O/'gfx/models/portraits/uma/0001';M.mkdir(parents=True,exist_ok=True);P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');rows=json.loads((V/'Reports/clothing-registration.json').read_text())['families'];C=np.diag([-97.6403989,97.6403989,-97.6403989]);C4=np.eye(4);C4[:3,:3]=C;CI=np.linalg.inv(C4);results=[]
headbase=MOD/'gfx/models/portraits/uma/0001/uma_0001_head_female.mesh';ho=P.read_meshfile(str(headbase)).find('object')[0];HD=rigdata(ho.find('skeleton'));hclip=MOD/'gfx/models/portraits/uma/animation/head/uma_head_native_idle.anim';HW=np.array([compose(HD,readlocals(P,hclip,f))for f in range(61)]);hindex=HD['names'].index('bn_h_head')
def normals_tangents(p,tri,uv):
 n=np.zeros_like(p);cross=np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]])
 for j in range(3):np.add.at(n,tri[:,j],cross)
 n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12);e1=uv[tri[:,1]]-uv[tri[:,0]];e2=uv[tri[:,2]]-uv[tri[:,0]];den=e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0];den=np.where(abs(den)<1e-12,1,den);tt=((p[tri[:,1]]-p[tri[:,0]])*e2[:,1,None]-(p[tri[:,2]]-p[tri[:,0]])*e1[:,1,None])/den[:,None];t=np.zeros_like(p)
 for j in range(3):np.add.at(t,tri[:,j],tt)
 t-=n*np.sum(t*n,axis=1)[:,None];t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-12);t[np.linalg.norm(t,axis=1)<.1]=[1,0,0];return n,np.c_[t,np.ones(len(p))]
for family in ['bdy0008_08_00','bdy0008_09_00']:
 r=next(r for r in rows if r['family']==family);part=r['parts']['headwear'];snapshot=json.loads(Path(r['source_snapshot']).read_text());sourcebones=snapshot['bones'];bn={b['id']:b for b in sourcebones};H=np.array(next(b for b in sourcebones if b['name']=='Head')['matrix']).reshape(4,4);trans=C4@np.linalg.inv(H);K=np.eye(4);K[:3,3]=trans[:3,3];tree=P.read_meshfile(part['base_mesh']);src=copy.deepcopy(tree);oldhash=hashlib.sha256(Path(part['base_mesh']).read_bytes()).hexdigest();sk=X.Element('skeleton');X.SubElement(sk,'head_root',{'ix':[0],'tx':np.eye(4)[:3].T.ravel().tolist()});X.SubElement(sk,'bn_h_head',{'ix':[1],'pa':[0],'tx':np.eye(4)[:3].T.ravel().tolist()});ids={};pointrecords=[]
 def add(bid):
  if bid in ids:return ids[bid]
  b=bn[bid];parent=add(b['parent'])if b.get('parent')else 1;i=len(sk);name='uma_hat_'+family[3:]+'_'+b['name'];world=trans@np.array(b['matrix']).reshape(4,4)@CI;inv=np.linalg.inv(world);X.SubElement(sk,name,{'ix':[i],'pa':[parent],'tx':inv[:3].T.ravel().tolist()});ids[bid]=i;pointrecords.append({'source_id':bid,'source_name':b['name'],'source_parent':b.get('parent'),'new_name':name,'index':i,'new_parent_index':parent,'original_unity_world':b['matrix'],'head_local_world_cm':world.tolist(),'original_source_helper_retained':True});return i
 for b in sourcebones:add(b['id'])
 assert len(sk)==len(sourcebones)+2 and not any('ear'in b['name'].lower()for b in sourcebones)
 node_reports=[];weighted={};old_aabb=[];new_aabb=[];mesh_index=0
 for o in tree.find('object'):
  olds=o.find('skeleton');o.remove(olds);o.append(copy.deepcopy(sk))
  for n in o.findall('mesh'):
   sm=part['source_maps'][mesh_index];native=snapshot['meshes'][sm['mesh']];vid=sm['source_vertex_ids'];npraw=np.array([[native['vertices'][i][c]for c in 'xyz']for i in vid]);p=npraw@trans[:3,:3].T+trans[:3,3];oldp=np.array(n.get('p')).reshape(-1,3);old_aabb.append([oldp.min(0).tolist(),oldp.max(0).tolist()]);tri=np.array(n.get('tri')).reshape(-1,3);uv=np.array(n.get('u0')).reshape(-1,2);normal,tangent=normals_tangents(p,tri,uv);n.attrib['p']=p.ravel().tolist();n.attrib['n']=normal.ravel().tolist();n.attrib['ta']=tangent.ravel().tolist();skin=n.find('skin');ix=np.full((len(p),4),-1);ix[:,0]=1;w=np.zeros((len(p),4));w[:,0]=1;skin.attrib['ix']=ix.ravel().tolist();skin.attrib['w']=w.ravel().tolist();n.find('aabb').attrib.update(min=p.min(0).tolist(),max=p.max(0).tolist());center=(p.min(0)+p.max(0))/2;n.attrib['boundingsphere']=center.tolist()+[float(np.linalg.norm(p-center,axis=1).max())];new_aabb.append([p.min(0).tolist(),p.max(0).tolist()]);vset=set(vid)
   for z in native['weights']:
    if z['vertex']in vset:weighted[bn[z['bone']]['name']]=weighted.get(bn[z['bone']]['name'],0)+z['weight']
   rawtri=np.array(next(x for x in native['faces']if x['material']==sm['material'])['triangles']).reshape(-1,3);actual=np.array(vid)[tri];expected=rawtri[sm['source_triangle_indices']];assert np.array_equal(actual,expected),'source tri identity changed'
   node_reports.append({'map_index':mesh_index,'source_mesh':sm['mesh'],'source_material':sm['material'],'source_vertex_ids':vid,'source_triangle_ids':sm['source_triangle_indices'],'vertices':len(p),'triangles':len(tri),'source_triangles_equal_in_original_order':True,'uv_exact_unchanged':True,'source_mesh_world_vertices_recovered_head_local':True});mesh_index+=1
 base=M/Path(part['base_mesh']).name;P.write_meshfile(str(base),tree);targets=[]
 for key,path in part['shape_targets'].items():
  bs=copy.deepcopy(tree)
  for o in bs.find('object'):
   o.remove(o.find('skeleton'))
   for n in o.findall('mesh'):n.remove(n.find('skin'))
  dest=M/Path(path).name;P.write_meshfile(str(dest),bs);bsread=P.read_meshfile(str(dest))
  assert all(o.find('skeleton')is None and all(n.find('skin')is None for n in o.findall('mesh'))for o in bsread.find('object'));targets.append({'key':key,'source':path,'candidate':str(dest),'decorative_body_shape_identity_target':True,'no_skeleton':True,'no_skin':True})
 read=P.read_meshfile(str(base));newobject=read.find('object')[0];SD=rigdata(newobject.find('skeleton'));maximum=0;finite=True
 for f in range(61):
  for n in newobject.findall('mesh'):
   actual=deform(n,SD,shared_pose(SD,HD,HW[f]));p=np.array(n.get('p')).reshape(-1,3);expected=p@HW[f,hindex,:3,:3].T+HW[f,hindex,:3,3];maximum=max(maximum,float(np.linalg.norm(actual-expected,axis=1).max()));finite=finite and bool(np.isfinite(actual).all())
 assert maximum<1e-5 and finite
 for ao,bo in zip(src.find('object'),read.find('object')):
  for a,b in zip(ao.findall('mesh'),bo.findall('mesh')):
   for key in ['tri','u0']:assert a.get(key)==b.get(key)
 ast=clausewitz(Path(r['asset_path']).read_text(encoding='utf-8-sig'));stem=part['mesh_name'];entity=part['entity'];blocks=[(k,v)for k,v in ast if k in ['pdxmesh','entity']and one(v,'name')in [stem,entity]];assert len(blocks)==2;asset=M/f'uma_0001_headwear_{family[3:]}_repair.asset';asset.write_text(script_block(blocks)+'\n',encoding='utf-8-sig')
 partition=json.loads(Path(r['source_partition']).read_text());components=[c for c in partition['meshes'][0]['components']if c['category']=='headwear'];rec={'family':family,'original_base':part['base_mesh'],'original_base_sha256':oldhash,'candidate_base':str(base),'candidate_asset':str(asset),'shape_targets':targets,'base_plus_bs_mesh_count':1+len(targets),'header_bones':len(sk),'source_bones_retained':len(sourcebones),'source_points':pointrecords,'source_snapshot':r['source_snapshot'],'source_renderer_transform_evidence':'Tools/HeadlessExporter/export_assets.py vertices are transform(renderer world,p), snapshot pose=source inverse-bind; source vertices already native world-space, so use inverse converted native Head reference and never reapply renderer world.','source_head_matrix':H.tolist(),'source_to_head_local_matrix':trans.tolist(),'head_axis_scale':C.tolist(),'old_bodyspace_aabb_cm':old_aabb,'new_headlocal_aabb_cm':new_aabb,'maps':node_reports,'native_weight_mass':weighted,'classification_components':[{'id':c['component'],'source_triangle_ids':c['source_triangle_indices'],'source_vertex_ids':c['source_vertex_ids'],'source_bounds':[c['bounds_min'],c['bounds_max']],'native_head_mass':c['head_mass'],'category':c['category'],'reason':c['reason']}for c in components],'old_clothing_triangle_ids_unchanged':True,'headwear_triangle_ids_added_removed':{'added':[],'removed':[]},'lower_boundary_tradeoff':'The original hood extends below the neck and has chest/shoulder weights in its lower rim; all original hood islands retained (no separate clothing island moved). Rigid public-head attachment intentionally follows head as one static hood. Lower rim no longer deforms with chest. This is evaluated numerically for source idle and must be visually checked with body at stronger head poses.','attachment_contract':{'accessory_id':'uma_'+family+'_headwear','shared_pose_entity':'head','node':None,'positive_skin_bone':'bn_h_head','head_root_bind':'identity','bn_h_head_bind':'identity','all_source_helpers_static_retained':True,'own_animation_import':None,'entity_animation_states':[],'ear_bones':False},'all61_static_shared_head_equivalence_max_cm':maximum,'all61_finite':finite,'pdx_readback':True,'runtime_verified':False,'visual_verified':False}
 assert hashlib.sha256(Path(part['base_mesh']).read_bytes()).hexdigest()==oldhash;results.append(rec);print('HAT_REPAIRED',family,len(sk),part['vertices'],part['triangles'],'headlocal_bounds',new_aabb,'all61err',maximum,flush=True)
(O/'hat-repair.json').write_text(json.dumps({'results':results,'original_mod_modified':False,'no_ear_or_animation':True,'all_existing_bs_targets_retained':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8-sig')
(O/'hat-contract.txt').write_text('两帽候选：bdy0008_08_00 / bdy0008_09_00\n每帽base+6现有BS共7mesh。原源三角ID/UV/纹理/低密度网格全部保留。恢复source Head相对顶点，头饰不再使用cloth nearest-body投影。\n静态public head跟随：shared_pose_entity=head，node不设置；base skin唯一正权bn_h_head，bn_h_head/head_root bind均I；所有75源骨/辅助点在head-local header静态保留，无ear、无自身动画import/state。\n每帽6个BS为同拓扑装饰identity target，不带skeleton/skin。两个asset候选只含原headwear pdxmesh/entity；集成时替换原wardrobe asset相应两个blocks，不重复注册同名entity。\n原hood下部含胸/肩权，源拓扑岛沿帽围延至领口；不搬移衣服独立岛。改为整体跟头后，下帽围不再跟胸变形，此为静态头饰适配取舍，需强头部姿势视觉确认。\n源Renderer已经在source snapshot vertices世界变换中烘焙，不能二次应用。详见hat-repair.json逐源点矩阵及源三角索引。\n',encoding='utf-8-sig')
