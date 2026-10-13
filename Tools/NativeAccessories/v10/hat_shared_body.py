import os,sys,json,copy,hashlib
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only,clausewitz,one,script_block
from head_assembly_math import rigdata,readlocals,compose,shared_pose,deform
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V10');MOD=V/'UMA-V10';BASE=MOD/'gfx/models/portraits/uma';O=V/'HatRepair/SharedBody';M=O/'gfx/models/portraits/uma/0001';M.mkdir(parents=True,exist_ok=True);P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');rows=json.loads((V/'Reports/clothing-registration.json').read_text())['families'];C=np.diag([-97.6403989,97.6403989,-97.6403989]);B=rigdata(P.read_meshfile(str(BASE/'0001/uma_0001_body_base.mesh')).find('object')[0].find('skeleton'));H=rigdata(P.read_meshfile(str(BASE/'0001/uma_0001_head_female.mesh')).find('object')[0].find('skeleton'));BW=np.array([compose(B,readlocals(P,BASE/'animation/body/uma_body_native_idle.anim',f))for f in range(61)]);HW=np.array([compose(H,readlocals(P,BASE/'animation/head/uma_head_native_idle.anim',f))for f in range(61)]);bt=B['names'].index('bn_sp_thoracic');bh=B['names'].index('uma_src_Head');hh=H['names'].index('bn_h_head');hr=H['names'].index('head_root');visible=np.array([BW[f,bt]@np.linalg.inv(HW[f,hr])@HW[f,hh]for f in range(61)]);relative=np.linalg.inv(BW[:,bh])@visible;visible_bind=B['bind'][bh]@relative[0];results=[]
def normal_tangent(p,t,uv):
 n=np.zeros_like(p);fn=np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]])
 for k in range(3):np.add.at(n,t[:,k],fn)
 _,group=np.unique(np.round(p,5),axis=0,return_inverse=True);tot=np.zeros((group.max()+1,3));np.add.at(tot,group,n);n=tot[group];n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12);e1=uv[t[:,1]]-uv[t[:,0]];e2=uv[t[:,2]]-uv[t[:,0]];den=e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0];den=np.where(abs(den)<1e-12,1,den);ft=((p[t[:,1]]-p[t[:,0]])*e2[:,1,None]-(p[t[:,2]]-p[t[:,0]])*e1[:,1,None])/den[:,None];ta=np.zeros_like(p)
 for k in range(3):np.add.at(ta,t[:,k],ft)
 ta-=n*np.sum(ta*n,axis=1)[:,None];ta/=np.maximum(np.linalg.norm(ta,axis=1)[:,None],1e-12);ta[np.linalg.norm(ta,axis=1)<.1]=[1,0,0];return n,np.c_[ta,np.ones(len(p))]
for family in ['bdy0008_08_00','bdy0008_09_00']:
 r=next(r for r in rows if r['family']==family);part=r['parts']['headwear'];cp=r['parts']['clothes'];raw=json.loads(Path(r['source_snapshot']).read_text());native=raw['meshes'][0];rawp=np.array([[v[c]for c in 'xyz']for v in native['vertices']]);sm=part['source_maps'][0];vid=np.array(sm['source_vertex_ids']);coids=np.array(cp['source_maps'][0]['source_vertex_ids']);hp=rawp[vid];headbone=next(b for b in raw['bones']if b['name']=='Head');SH=np.array(headbone['matrix']).reshape(4,4);localhp=(np.c_[hp,np.ones(len(hp))]@np.linalg.inv(SH).T)[:,:3]@C.T;wanted=localhp@visible_bind[:3,:3].T+visible_bind[:3,3];tree=P.read_meshfile(part['base_mesh']);orig=copy.deepcopy(tree);o=tree.find('object')[0];SD=rigdata(o.find('skeleton'));n=o.find('mesh');tri=np.array(n.get('tri')).reshape(-1,3);uv=np.array(n.get('u0')).reshape(-1,2);sourcepoints=json.loads(Path(r['source_points']).read_text());mapping={x['source_id']:SD['names'].index(x['engine_name'])for x in sourcepoints['points']};weightlists={i:[]for i in vid}
 for w in native['weights']:
  if w['vertex']in weightlists:weightlists[w['vertex']].append((w['bone'],w['weight']))
 nativeheadw=np.array([sum(w for b,w in weightlists[i]if b==headbone['id'])for i in vid]);ix=np.full((len(vid),4),-1);weights=np.zeros((len(vid),4))
 for i,sourceid in enumerate(vid):
  entries=weightlists[sourceid];assert len(entries)<=4
  for slot,(bid,w)in enumerate(entries):ix[i,slot]=mapping[bid];weights[i,slot]=w
 assert abs(weights.sum(1)-1).max()<1e-6
 co=P.read_meshfile(cp['base_mesh']).find('object')[0];CD=rigdata(co.find('skeleton'));assert CD['names']==SD['names'];cm=co.find('mesh');ci=np.array(cm.find('skin').get('ix')).reshape(-1,4);cw=np.array(cm.find('skin').get('w')).reshape(-1,4);dist,nearest=cKDTree(rawp[coids]).query(hp);boundary=np.flatnonzero(dist<.00002);upper=np.flatnonzero((nativeheadw>.999)|(hp[:,1]>SH[1,3]+.10));assert not set(boundary)&set(upper)
 # Uniform harmonic correction on original source-position welded topology.
 # Real coincident coat boundary is Dirichlet; original upper hood is fixed.
 unique,group=np.unique(np.round(hp,5),axis=0,return_inverse=True);edges=np.vstack([group[tri[:,[0,1]]],group[tri[:,[1,2]]],group[tri[:,[2,0]]]]);edges=edges[edges[:,0]!=edges[:,1]];edges=np.unique(np.sort(edges,axis=1),axis=0);i=np.r_[edges[:,0],edges[:,1]];j=np.r_[edges[:,1],edges[:,0]];adj=coo_matrix((np.ones(len(i)),(i,j)),shape=(len(unique),len(unique))).tocsr();degree=np.asarray(adj.sum(1)).ravel();L=coo_matrix((degree,(np.arange(len(unique)),np.arange(len(unique)))),shape=adj.shape).tocsr()-adj;anchorset=set(group[boundary])|set(group[upper]);anchors=np.array(sorted(anchorset));free=np.array([i for i in range(len(unique))if i not in anchorset]);templates={}
 for tag,clothfile in [('base',cp['base_mesh'])]+[(key,cp['shape_targets'][key])for key in part['shape_targets']]:
  clothgeom=np.array(P.read_meshfile(clothfile).find('object')[0].find('mesh').get('p')).reshape(-1,3);delta=np.zeros_like(unique);counts=np.zeros(len(unique))
  for q in boundary:delta[group[q]]+=clothgeom[nearest[q]]-wanted[q];counts[group[q]]+=1
  good=counts>0;delta[good]/=counts[good,None]
  # Source UV duplicates at a boundary must have the same actual source target.
  assert max(np.linalg.norm(delta[group[q]]-(clothgeom[nearest[q]]-wanted[q]))for q in boundary)<1e-3
  if len(free):delta[free]=spsolve(L[free][:,free],-L[free][:,anchors]@delta[anchors])
  geometry=wanted+delta[group];assert np.isfinite(geometry).all();geometry[boundary]=clothgeom[nearest[boundary]];templates[tag]=geometry
 # Boundary copies retain the exact existing coat endpoint's skin transfer;
 # everywhere else uses native Head/Chest/Neck semantic source weights.
 ix[boundary]=ci[nearest[boundary]];weights[boundary]=cw[nearest[boundary]]
 variantreports=[]
 for tag,geometry in templates.items():
  output=copy.deepcopy(tree);on=output.find('object')[0].find('mesh');norm,tangent=normal_tangent(geometry,tri,uv);on.attrib.update(p=geometry.ravel().tolist(),n=norm.ravel().tolist(),ta=tangent.ravel().tolist());on.find('aabb').attrib.update(min=geometry.min(0).tolist(),max=geometry.max(0).tolist());center=(geometry.min(0)+geometry.max(0))/2;on.attrib['boundingsphere']=center.tolist()+[float(np.linalg.norm(geometry-center,axis=1).max())];on.find('skin').attrib.update(ix=ix.ravel().tolist(),w=weights.ravel().tolist())
  dest=M/Path(part['base_mesh']if tag=='base'else part['shape_targets'][tag]).name
  if tag!='base':output.find('object')[0].remove(output.find('object')[0].find('skeleton'));on.remove(on.find('skin'))
  P.write_meshfile(str(dest),output);read=P.read_meshfile(str(dest));rn=read.find('object')[0].find('mesh');assert rn.get('tri')==n.get('tri')and rn.get('u0')==n.get('u0');assert np.max(abs(np.array(rn.get('p')).reshape(-1,3)[boundary]-np.array(P.read_meshfile(cp['base_mesh']if tag=='base'else cp['shape_targets'][tag]).find('object')[0].find('mesh').get('p')).reshape(-1,3)[nearest[boundary]]))<1e-5
  variantreports.append({'key':tag,'candidate':str(dest),'no_skeleton':tag!='base','no_skin':tag!='base','same_triangles_uv':True,'boundary_geometry_cloth_endpoint_max_cm':float(np.max(abs(np.array(rn.get('p')).reshape(-1,3)[boundary]-templates[tag][boundary])))})
 new=P.read_meshfile(str(M/Path(part['base_mesh']).name)).find('object')[0];ND=rigdata(new.find('skeleton'));checks=[];maxgap=0;uppermax=0;skinfinite=True
 for f in range(61):
  posed=deform(new.find('mesh'),ND,shared_pose(ND,B,BW[f]));clothpose=deform(cm,CD,shared_pose(CD,B,BW[f]));gap=np.linalg.norm(posed[boundary]-clothpose[nearest[boundary]],axis=1);expected=localhp@visible[f,:3,:3].T+visible[f,:3,3];uppererror=np.linalg.norm(posed[upper]-expected[upper],axis=1);maxgap=max(maxgap,float(gap.max()));uppermax=max(uppermax,float(uppererror.max()));skinfinite=skinfinite and bool(np.isfinite(posed).all());checks.append({'frame':f,'boundary_max_gap_cm':float(gap.max()),'upper_real_visible_head_error_max_cm':float(uppererror.max())})
 assert maxgap<1e-4 and skinfinite
 # All BS share base skin/header at runtime: verify all six lower endpoints.
 bschecks={}
 for key in part['shape_targets']:
  target=copy.deepcopy(new.find('mesh'));target.attrib['p']=templates[key].ravel().tolist();ctarget=copy.deepcopy(cm);ctarget.attrib['p']=np.array(P.read_meshfile(cp['shape_targets'][key]).find('object')[0].find('mesh').get('p')).tolist();err=0
  for f in range(61):
   hpv=deform(target,ND,shared_pose(ND,B,BW[f]));cpv=deform(ctarget,CD,shared_pose(CD,B,BW[f]));err=max(err,float(np.linalg.norm(hpv[boundary]-cpv[nearest[boundary]],axis=1).max()))
  assert err<1e-4;bschecks[key]=err
 ast=clausewitz(Path(r['asset_path']).read_text(encoding='utf-8-sig'));blocks=[(k,v)for k,v in ast if k in ['pdxmesh','entity']and one(v,'name')in [part['mesh_name'],part['entity']]];asset=M/f'uma_0001_headwear_{family[3:]}_repair.asset';asset.write_text(script_block(blocks)+'\n',encoding='utf-8-sig')
 records={'family':family,'source_snapshot':r['source_snapshot'],'source_points':r['source_points'],'all75_source_points_preserved_exact_original_bodyspace_header':True,'header_bones':len(ND['names']),'core146_header_exact':all(ND['names'][i]==B['names'][i]and np.max(abs(ND['inv'][i]-B['inv'][i]))<1e-5 for i in range(146)),'candidate_base':str(M/Path(part['base_mesh']).name),'candidate_asset':str(asset),'variants':variantreports,'source_maps':part['source_maps'],'triangles_uv_texture_unchanged':True,'upper_original_native_head_geometry_anchors':upper.tolist(),'boundary_vertex_indices':boundary.tolist(),'boundary_source_pairs':[{'hat_source':int(vid[i]),'coat_source':int(coids[nearest[i]]),'source_distance_cm':float(dist[i]*100)}for i in boundary],'native_weights_preserved_except_boundary_cloth_copy':True,'native_head_semantic_bone':'uma_src_Head','boundary_cloth_skin_copy_count':len(boundary),'all61_boundary_max_gap_cm':maxgap,'all61_upper_visible_head_error_max_cm':uppermax,'all61_BS_boundary_gaps_cm':bschecks,'all61_skinning_finite':skinfinite,'frames':checks,'geometry_rule':'Upper original source hood transformed with calibrated visible Head bind; no old Y compression. Uniform harmonic correction over original welded topology transports only transition/lower hood to actual source-coincident existing coat endpoints. Upper anchors stay fixed.','skin_rule':'Native source Head/Neck/Chest/Shoulder semantics map to existing body146 source helpers/core. Exact matching coat endpoint skin is copied only at true source lower boundary. No nearest-body transfer elsewhere.','shared_pose_entity':'torso','node':None,'own_animation_import':None,'own_animation_states':[],'ear':False,'runtime_verified':False,'visual_verified':False}
 results.append(records);print('HAT_SHARED',family,'bones',len(ND['names']),'boundpairs',len(boundary),'gap',maxgap,'uppererr',uppermax,'BS',bschecks,flush=True)
(O/'hat-shared-body.json').write_text(json.dumps({'rigid_candidate_denied_due_to_hood_coat_gap':True,'visible_head_relative_to_body_head_first':relative[0].tolist(),'visible_head_relative_to_body_head_translation_minmax':[relative[:,:3,3].min(0).tolist(),relative[:,:3,3].max(0).tolist()],'relative_matrix_variation_max':float(np.abs(relative-relative[0]).max()),'results':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8-sig')
(O/'hat-shared-contract.txt').write_text('最终候选路线：无own animation的真实Head语义shared body hood。\n保留原152骨header（146 core含12真实源参考点，另6source助手），全部75源点映射保持。正权Head来自真实uma_src_Head而不是旧最近身体权重。\n上帽恢复原source几何且依据实际visible bn_h_head校准；下围依据真实source-coat重合顶点输运，同拓扑harmonic适配，不压整帽到脖子。\n下围复制真实cloth边界skin；6BS的下围逐一匹配对应coat BS。所有base/BS三角、UV和原纹理不变。BS无skeleton/skin。\n挂接：shared_pose_entity=torso，node不设，无自身animation import/state、无ear。这不同于原错误近邻权重路线，头部有真实Head语义骨驱动。\n旧rigid全帽候选保留为已否定，不最终安装。\n',encoding='utf-8-sig')
