import os
import json,sys,numpy as np
from pathlib import Path
from collections import defaultdict
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
R=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));A=np.load(R/'clothing-parts/garment-prepared.npz');d=json.loads((R/'parsed/body.json').read_text());m=d['meshes'][0];bones={b['id']:b for b in d['bones']};p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);used=A['source_ids'];faces=A['faces'];unique,wel=np.unique(np.round(p[used],6),axis=0,return_inverse=True);wf=wel[faces];edges=np.concatenate([wf[:,[0,1]],wf[:,[1,2]],wf[:,[2,0]]]);g=coo_matrix((np.ones(len(edges)*2),(np.r_[edges[:,0],edges[:,1]],np.r_[edges[:,1],edges[:,0]])),shape=(len(unique),len(unique))).tocsr();n,labels=connected_components(g,directed=False);weights=defaultdict(list)
for w in m['weights']:weights[w['vertex']].append((w['bone'],w['weight']))
def lineage(b):
 out=[]
 while b:
  out.append(bones[b]['name']);b=bones[b].get('parent')
 return out
chains={b:lineage(b)for b in bones};reports=[]
for group in range(n):
 fi=np.flatnonzero(labels[wf[:,0]]==group);vs=np.unique(faces[fi]);ids=used[vs];score=defaultdict(float)
 for i in ids:
  for b,w in weights[i]:score[b]+=w/len(ids)
 skirt=sum(w for b,w in score.items()if any('Skirt'in n for n in chains[b]));leg=sum(w for b,w in score.items()if any(n.startswith(('Thigh_','Knee_','Ankle_','Toe_'))for n in chains[b]));low=sum(w for b,w in score.items()if any(n.startswith(('Knee_','Ankle_','Toe_'))for n in chains[b]));ribbon=sum(w for b,w in score.items()if bones[b]['name'].startswith('Sp_Th_Ribbon'));report=dict(component=group,triangles=len(fi),vertices=len(ids),min=p[ids].min(0).tolist(),max=p[ids].max(0).tolist(),centroid=p[ids].mean(0).tolist(),skirt=skirt,leg=leg,lower_leg=low,leg_ribbon=ribbon,top_bones=sorted([(bones[b]['name'],w)for b,w in score.items()],key=lambda q:-q[1])[:4]);reports.append(report)
import copy,hashlib,shutil
REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')];import build_ck3_mod as b
from test_vanilla_body_animation_blender import inverse_bind,globals_for
PD=b.parser_only(Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh")));FULL=R/'clothing-parts';OUT=FULL/'split-parts';OUT.mkdir(exist_ok=True);order=np.array(json.loads((FULL/'clothing-pdx-vertex-order.json').read_text())['export_to_prepared']);source_ids=used[order];class_by_group={};component_reports=[]
for q in reports:
 footwear=q['skirt']<.01 and q['leg']>.55 and q['max'][1]<.71
 category='footwear' if footwear else 'clothing';class_by_group[q['component']]=category;component_reports.append(dict(q,category=category,policy='Whole welded-source component; skirt-chain priority; footwear requires leg-chain mass >0.55 and source maximum height <0.71m'))
prepared_category=np.array([class_by_group[int(labels[t[0]])]for t in wf]);base=PD.read_meshfile(str(FULL/'uma_1001_clothing_00.mesh'));baseo=base.find('object')[0];basem=baseo.find('mesh');basetri=np.array(basem.attrib['tri']).reshape(-1,3);inverse=np.empty(len(order),int);inverse[order]=np.arange(len(order));assert np.array_equal(basetri,np.roll(inverse[faces],1,axis=1));assert np.array_equal(order[basetri],np.roll(faces,1,axis=1));allids={};sections={};contracts={'b0':'bs_body_breast_shape_1','b1':'bs_body_breast_shape_2','b3':'bs_body_breast_shape_3','b4':'bs_body_breast_shape_4','s1':'bs_body_gaunt_1','s2':'bs_body_fat_1'}
for category in ['clothing','footwear']:
 fi=np.flatnonzero(prepared_category==category);fullverts=np.unique(basetri[fi]);local=np.full(len(order),-1,int);local[fullverts]=np.arange(len(fullverts));localtri=local[basetri[fi]];allids[category]=fi;records=[]
 for tag in ['base',*contracts]:
  inputfile=FULL/('uma_1001_clothing_00'+(''if tag=='base'else '_'+tag)+'.mesh');tree=PD.read_meshfile(str(inputfile));obj=tree.find('object')[0];obj.tag=f'uma_1001_{category}_00Shape';node=obj.find('mesh');assert node.attrib['tri']==basem.attrib['tri'];assert node.attrib['u0']==basem.attrib['u0']
  for attr,width in [('p',3),('n',3),('ta',4),('u0',2),('u1',2),('u2',2),('u3',2)]:
   if attr in node.attrib:node.attrib[attr]=np.array(node.attrib[attr]).reshape(-1,width)[fullverts].ravel().tolist()
  node.attrib['tri']=localtri.ravel().tolist();skin=node.find('skin')
  for attr in ['ix','w']:skin.attrib[attr]=np.array(skin.attrib[attr]).reshape(-1,4)[fullverts].ravel().tolist()
  p=np.array(node.attrib['p']).reshape(-1,3);node.find('aabb').attrib.update(min=p.min(0).tolist(),max=p.max(0).tolist());c=(p.min(0)+p.max(0))/2;node.attrib['boundingsphere']=c.tolist()+[float(np.linalg.norm(p-c,axis=1).max())];filename=OUT/(f'uma_1001_{category}_00'+(''if tag=='base'else '_'+tag)+'.mesh');PD.write_meshfile(str(filename),tree);read=PD.read_meshfile(str(filename));readobj=read.find('object')[0];rm=readobj.find('mesh');original=PD.read_meshfile(str(inputfile)).find('object')[0].find('mesh');assert np.array_equal(inverse_bind(readobj.find('skeleton')),inverse_bind(baseo.find('skeleton')))
  for attr,width in [('p',3),('n',3),('ta',4),('u0',2)]:assert np.array_equal(np.array(rm.attrib[attr]).reshape(-1,width),np.array(original.attrib[attr]).reshape(-1,width)[fullverts])
  for attr in ['ix','w']:assert np.array_equal(np.array(rm.find('skin').attrib[attr]).reshape(-1,4),np.array(original.find('skin').attrib[attr]).reshape(-1,4)[fullverts])
  assert np.array_equal(fullverts[np.array(rm.attrib['tri']).reshape(-1,3)],basetri[fi]);records.append(dict(variant=tag,key=contracts.get(tag),file=str(filename),vertices=len(fullverts),triangles=len(fi),material=rm.find('material').attrib,pdx_readback=True,fullkit_vertex_attributes_exact=True,fullkit_skeleton_exact=True,sha256=hashlib.sha256(filename.read_bytes()).hexdigest()))
 sections[category]=dict(base_mesh=records[0]['file'],mesh_shape=f'uma_1001_{category}_00Shape',vertices=len(fullverts),triangles=len(fi),variants=records,source_vertex_ids=source_ids[fullverts].tolist(),fullkit_vertex_indices=fullverts.tolist(),fullkit_triangle_indices=fi.tolist(),component_ids=[q['component']for q in component_reports if q['category']==category]);print('BROAD_SPLIT',category,len(fullverts),len(fi),flush=True)
joined=np.concatenate(list(allids.values()));assert len(joined)==len(basetri)and len(np.unique(joined))==len(basetri)and np.array_equal(np.sort(joined),np.arange(len(basetri)))
for suffix in ['diffuse','normal','properties']:shutil.copy2(FULL/f'uma_1001_clothing_00_{suffix}.dds',OUT/f'uma_1001_clothing_00_{suffix}.dds')
# Read actual split meshes, evaluate exact same idle/throne matrices and compare restored fullkit vertex positions.
sk=baseo.find('skeleton');bind=inverse_bind(sk);fullp=np.array(basem.attrib['p']).reshape(-1,3);fullix=np.array(basem.find('skin').attrib['ix']).reshape(-1,4);fullw=np.array(basem.find('skin').attrib['w']).reshape(-1,4)
def deform(p,ix,w,m):
 hp=np.column_stack([p,np.ones(len(p))]);out=np.zeros_like(p)
 for j in range(4):out+=np.einsum('nij,nj->ni',m[np.maximum(ix[:,j],0)],hp)[:,:3]*w[:,j,None]
 return out
folder=Path(os.environ.get("UMA_V6_GAME", "D:/steam/steamapps/common/Crusader Kings III/game")) / 'gfx/models/portraits/female_body';animation_reports=[]
for clip in [None,'female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim']:
 if clip:
  data=PD.read_meshfile(str(folder/clip));frames=sorted({0,data.find('info').attrib['sa'][0]//2,data.find('info').attrib['sa'][0]-1})
 else:frames=[0]
 for frame in frames:
  mat=globals_for(data.find('info'),data.find('samples'),frame,sk)@bind if clip else np.repeat(np.eye(4)[None],len(sk),axis=0);expected=deform(fullp,fullix,fullw,mat);errors={}
  for category,section in sections.items():
   node=PD.read_meshfile(section['base_mesh']).find('object')[0].find('mesh');actual=deform(np.array(node.attrib['p']).reshape(-1,3),np.array(node.find('skin').attrib['ix']).reshape(-1,4),np.array(node.find('skin').attrib['w']).reshape(-1,4),mat);error=float(abs(actual-expected[section['fullkit_vertex_indices']]).max());assert error==0;errors[category]=error
  animation_reports.append(dict(animation=clip,frame=int(frame),max_split_vs_fullkit_error_cm=errors))
delivery=dict(version=1,output=str(OUT),fullkit_reference=str(FULL/'uma_1001_clothing_00.mesh'),fullkit_unchanged=True,source=str(R/'parsed/body.json'),source_vertex_ids_preserved=True,sections=sections,components=component_reports,partition=dict(fullkit_triangles=len(basetri),clothing_triangles=len(allids['clothing']),footwear_triangles=len(allids['footwear']),all_faces_assigned_once=True,missing_faces=0,duplicate_faces=0),shared_texture_atlas=[str(OUT/f'uma_1001_clothing_00_{suffix}.dds')for suffix in ['diffuse','normal','properties']],shape_contracts=contracts,animation_partition_equivalence=animation_reports,body_clothed_key='bs_body_clothed',body_clothed_unchanged=str(FULL/'uma_0001_body_clothed.mesh'),limitations='Pure partition does not repair or add collisions; all fullkit animation, fit and runtime limitations carry over')
(OUT/'split-delivery.json').write_text(json.dumps(delivery,indent=2),encoding='utf8');(FULL/'split-delivery.json').write_text(json.dumps(delivery,indent=2),encoding='utf8');print('SPLIT_DELIVERY_COMPLETE',len(component_reports),len(animation_reports),flush=True)
