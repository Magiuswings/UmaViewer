"""Ready component trees, standard external attachment names, static headwear."""
import sys,json,copy,re,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,deform,shared_pose
V8=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');OUT=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9/RigRepair');BASE=V8/'UMA-V8/gfx/models/portraits/uma';P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');full=OUT/'Head245/full_root';template=P.read_meshfile(str(full/'headcarrier_seam.mesh'));S=template.find('object')[0].find('skeleton');D=rigdata(S);reg=json.loads((V8/'Reports/head-registration.json').read_text());rows=[];wearrows=[]
folder=OUT/'Components245';folder.mkdir(parents=True,exist_ok=True)
for sex in ['female','male']:P.write_meshfile(str(folder/('uma_0001_head_'+sex+'.mesh')),copy.deepcopy(template))
for row in reg:
 if row.get('shared_pose')!='head' or row.get('independent_native_pose'):continue
 actor=row['actor'];dest=folder/actor/Path(row['mesh']).name;dest.parent.mkdir(parents=True,exist_ok=True)
 if row['element']=='neck':
  source=full/f'uma_{actor}_neck_unified.mesh';dest.write_bytes(source.read_bytes());rows.append({**row,'source_mesh':row['mesh'],'mesh':str(dest),'bones':245,'bridge_bind_unified':True});continue
 tree=P.read_meshfile(row['mesh']);rawpoints={};maximum=0.;aabb=[]
 for o in tree.find('object'):
  old=rigdata(o.find('skeleton'));rawpoints[o.tag]={'names':old['names'],'original_world_bind':old['bind'].tolist()}
  for m in o.findall('mesh'):
   skin=m.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);w=np.array(skin.get('w')).reshape(-1,4);new=ix.copy()
   for i in np.unique(ix[w>0]):
    n=old['names'][i];assert n in D['names'],(row['prefix'],n);j=D['names'].index(n);maximum=max(maximum,float(abs(old['bind'][i]-D['bind'][j]).max()));new[ix==i]=j
   # Invalid zero-weight indices are explicit -1, not silently inherited.
   new[w==0]=-1;assert maximum<.0002,(row['prefix'],maximum);skin.set('ix',new.ravel().tolist());p=np.array(m.get('p')).reshape(-1,3);assert np.isfinite(p).all();aabb.append([p.min(0).tolist(),p.max(0).tolist()])
  o.remove(o.find('skeleton'));o.append(copy.deepcopy(S))
 P.write_meshfile(str(dest),tree);read=P.read_meshfile(str(dest));orig=P.read_meshfile(row['mesh'])
 for a,b in zip(orig.find('object'),read.find('object')):
  for x,y in zip(a.findall('mesh'),b.findall('mesh')):
   for k in ['p','n','ta','u0','u1','uv0','uv1','tri']:assert x.get(k)==y.get(k),(row['prefix'],k)
   assert x.find('skin').get('w')==y.find('skin').get('w')
 (dest.with_suffix('.source-points.json')).write_text(json.dumps(rawpoints,indent=2)+'\n',encoding='utf8');rows.append({**row,'source_mesh':row['mesh'],'mesh':str(dest),'bones':245,'weighted_bind_delta_max':maximum,'source_geometry_normals_uv_tri_weights_exact':True,'bounds_header_cm':aabb,'source_reference_points_report':str(dest.with_suffix('.source-points.json'))})
print('STAGED_HEAD_COMPONENTS',len(rows),flush=True)
earremap=json.loads((V8/'Rigs/ear-variant-remap.json').read_text());H=np.load(V8/'MotionSources/head-final-pose-evidence.npz')['world'];hdata=json.loads((V8/'Rigs/headcarrier.json').read_text());headindex=hdata['index_by_name']['bn_h_head']
for row in reg:
 if row['element']!='headwear':continue
 actor=row['actor'];variant=row['variant'];tree=P.read_meshfile(row['mesh']);o=tree.find('object')[0];old=rigdata(o.find('skeleton'));mapping=next(r for r in earremap if r['actor']==actor and r['variant']==variant)['old_name_to_union_name'];own=set(mapping.values());keep=[n for n in old['names']if n in own and not re.search(r'(^|_)(Ear|ear)(_|[0-9]|$)',n.split('__',1)[-1])];skeleton=ET.Element('skeleton');ET.SubElement(skeleton,'head_root',{'ix':[0],'tx':np.eye(4)[:3].T.ravel().tolist()});ET.SubElement(skeleton,'bn_h_head',{'ix':[1],'pa':[0],'tx':np.eye(4)[:3].T.ravel().tolist()});indices={n:i+2 for i,n in enumerate(keep)};original_refs={}
 for n in keep:
  i=old['names'].index(n);pa=old['parents'][i]
  while pa is not None and old['names'][pa]not in indices:pa=old['parents'][pa]
  parent=indices[old['names'][pa]]if pa is not None else 1;tx=np.linalg.inv(old['bind'][i]);ET.SubElement(skeleton,n.replace('uma_ear_','uma_wear_',1),{'ix':[indices[n]],'pa':[parent],'tx':tx[:3].T.ravel().tolist()});original_refs[n]=old['bind'][i].tolist()
 originalweights=[]
 for m in o.findall('mesh'):
  skin=m.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);w=np.array(skin.get('w')).reshape(-1,4);originalweights.append({'bone_names':old['names'],'ix':ix.tolist(),'w':w.tolist()});new=np.full_like(ix,-1);new[:,0]=1;ww=np.zeros_like(w);ww[:,0]=1;skin.set('ix',new.ravel().tolist());skin.set('w',ww.ravel().tolist())
 o.remove(o.find('skeleton'));o.append(skeleton);dest=OUT/'StaticHeadwear'/actor/Path(row['mesh']).name;dest.parent.mkdir(parents=True,exist_ok=True);P.write_meshfile(str(dest),tree);ro=P.read_meshfile(str(dest)).find('object')[0];RD=rigdata(ro.find('skeleton'));maxerror=0.
 for f in [0,30,60]:
  for m in ro.findall('mesh'):
   posed=deform(m,RD,shared_pose(RD,D,np.concatenate([H[f],np.array(D['bind'])[242:]])));p=np.array(m.get('p')).reshape(-1,3);expected=p@H[f,headindex,:3,:3].T+H[f,headindex,:3,3];maxerror=max(maxerror,float(np.linalg.norm(posed-expected,axis=1).max()))
 assert maxerror<.0001;src=P.read_meshfile(row['mesh']).find('object')[0]
 for a,b in zip(src.findall('mesh'),ro.findall('mesh')):
  for k in ['p','n','ta','u0','u1','uv0','tri']:assert a.get(k)==b.get(k)
 meta={'source_mesh':row['mesh'],'mesh':str(dest),'actor':actor,'variant':variant,'bones':len(skeleton),'shared_pose':'head','external_node':None,'animation_import':None,'entity_states':[],'rigid_positive_skin_bone':'bn_h_head','rigid_geometry_attachment_local_bind_is_identity':True,'no_ear_bones_or_union_animation':True,'original_p_n_uv_tri_exact':True,'original_native_reference_points':original_refs,'original_native_weights':originalweights,'source_pose_follow_public_head_max_error_cm':maxerror,'source_world_geometry_invariant':'V8 old node bn_h_head*neutral accessory-local p equals V9 shared head bone world*I_inversebind*p; component public-head bind I is required while preserving original local p.'};dest.with_suffix('.rebind.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8');wearrows.append(meta);print('STATIC_HEADWEAR',actor,variant,len(skeleton),maxerror,flush=True)
report={'head_components':rows,'headwear_components':wearrows,'standard_public_ear_node':'bn_h_head','standard_tail_node':'body_root','actor_1001_1002_public_Head_bind_identical':True,'ears_and_tail_original_source_motion_unmodified':True,'common245_carriers':[str(folder/('uma_0001_head_'+s+'.mesh'))for s in ['female','male']],'head_clip':str(full/'uma_head_native_idle_seam.anim'),'independent_neck_entity_must_be_removed':True,'game_runtime_test_pending':True};(OUT/'ready-components-index.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
