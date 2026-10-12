"""Four real-source clips, every joint of each exact final reference skeleton."""
import json,sys,hashlib,copy
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import defaultdict
import re
import numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter')
from build_ck3_mod import parser_only
ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');OUT=ROOT/'MotionSources';RIGS=ROOT/'Rigs';V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');contract=json.loads((RIGS/'rig-contract.json').read_text());independent=json.loads((RIGS/'ear-tail-rig-contract.json').read_text());raw=np.load(OUT/'native-source-local-frames.npz');index=json.loads((OUT/'native-source-local-index.json').read_text());records={r['key']:r for r in index['records']};N=json.loads(Path('E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3/native-bone-transforms.json').read_text());sourcebody=json.loads(Path(records['body_home_idle']['source_bind_snapshot']).read_text());headcontract=json.loads((V7/'rig-contract.json').read_text());HC=np.eye(4);HC[:3,:3]=np.array(headcontract['head_source_to_engine']);HCI=np.linalg.inv(HC);UC=np.diag([-100.,100.,-100.,1.]);UCI=np.linalg.inv(UC);S=np.eye(4);S[:3,:3]=np.array([[1.,0,0],[0,0,1],[0,1,0]])*100;SI=np.linalg.inv(S);BP={n:S@np.array(w)@SI for n,w in N['posed'].items()};BT={n:S@np.array(w)@SI for n,w in N['bind'].items()};deliveries=[]
def polar(m):
    u,s,v=np.linalg.svd(m[:3,:3]);r=u@v
    if np.linalg.det(r)<0:u[:,-1]*=-1;r=u@v
    return r
def typed(path):return json.loads(Path(path).read_text())
def source_rig(data):
    byid={b['id']:b['name']for b in data['bones']};world={b['name']:np.array(b['matrix']).reshape(4,4)for b in data['bones']};parents={b['name']:byid.get(b['parent'])for b in data['bones']};return world,parents
def compose_names(local,parents,left=None):
    world={}
    def one(n):
        if n in world:return world[n]
        p=parents[n];m=one(p)@local[n]if p else local[n]
        if not p and left is not None:m=left@m
        world[n]=m;return m
    for n in local:one(n)
    return world
def compose_typed(local,rig):
    world=[None]*len(rig['names'])
    def one(i):
        if world[i]is not None:return world[i]
        p=rig['parents'][i];world[i]=one(p)@local[:,i]if p is not None else local[:,i];return world[i]
    for i in range(len(world)):one(i)
    return np.stack(world,axis=1)
def local_from_desired(rig,desired,count):
    bind=np.array(rig['bind_local']);world=[None]*len(rig['names']);local=[None]*len(world)
    def one(i):
        if world[i]is not None:return world[i]
        n=rig['names'][i];p=rig['parents'][i];pm=one(p)if p is not None else np.tile(np.eye(4),(count,1,1))
        if n in desired:world[i]=desired[n];local[i]=np.linalg.inv(pm)@world[i]
        else:local[i]=np.tile(bind[i],(count,1,1));world[i]=pm@local[i]
        return world[i]
    for i in range(len(world)):one(i)
    return np.stack(local,axis=1),np.stack(world,axis=1)
def write(module,rig,local,source_keys,extra):
    names=rig['names'];count=len(local);info=ET.Element('info',{'fps':[30.],'sa':[count],'j':[len(names)]});samples=ET.Element('samples');parts=defaultdict(list);decomposed=[];active={};shear=[]
    for i,n in enumerate(names):
        m=local[:,i];r=np.array([polar(x)for x in m]);stretch=np.transpose(r,(0,2,1))@m[:,:3,:3];scale=np.diagonal(stretch,axis1=1,axis2=2).copy();assert np.min(scale)>0,(module,n,scale.min());q=Rotation.from_matrix(r).as_quat()
        for f in range(1,count):
            if q[f]@q[f-1]<0:q[f]*=-1
        data={'t':m[:,:3,3],'q':q,'s':scale};cs=''.join(c for c in ['t','q','s']if np.max(np.abs(data[c]-data[c][0]))>1e-7)
        if module=='head'and n=='head_root':assert not cs and np.max(np.abs(data['t']-contract['head_direct_root']['head_root_offset_cm']))<1e-6
        decomposed.append(data)
        error=float(np.max(np.abs(stretch-scale[:,None,:]*np.eye(3)[None,:,:])))
        if error>1e-5:shear.append({'bone':n,'local_affine_off_diagonal_residual':error,'source_reference_contains_affine_shear':True})
    expected=compose_typed(local,rig);projected=np.tile(np.eye(4),(count,len(names),1,1));world_projected=[None]*len(names);fixes=[]
    for i,d in enumerate(decomposed):projected[:,i,:3,:3]=Rotation.from_quat(d['q']).as_matrix()*d['s'][:,None,:]
    def fix_point(i):
        if world_projected[i]is not None:return world_projected[i]
        p=rig['parents'][i];pm=fix_point(p)if p is not None else np.tile(np.eye(4),(count,1,1));t=(np.linalg.inv(pm[:,:3,:3])@(expected[:,i,:3,3]-pm[:,:3,3])[:,:,None])[:,:,0];error=float(np.max(np.linalg.norm(t-decomposed[i]['t'],axis=1)));projected[:,i,:3,3]=t;decomposed[i]['t']=t;world_projected[i]=pm@projected[:,i]
        if error>1e-5:fixes.append({'bone':names[i],'parent_affine_to_TRS_translation_compensation_max_cm':error,'actual_target_world_point_preserved':True})
        return world_projected[i]
    for i in range(len(names)):fix_point(i)
    for i,(n,d)in enumerate(zip(names,decomposed)):
        cs=''.join(c for c in ['t','q','s']if np.max(np.abs(d[c]-d[c][0]))>1e-7);ET.SubElement(info,n,{'sa':[cs],**{c:d[c][0].tolist()for c in ['t','q','s']}})
        for c in cs:parts[c].append(d[c])
        if cs:active[n]=cs
    for c,arrays in parts.items():samples.set(c,np.stack(arrays,axis=1).ravel().tolist())
    file=ET.Element('File',{'pdxasset':[1,0]});file.append(info);file.append(samples);folder=OUT/'Final'/'animation'/module;folder.mkdir(parents=True,exist_ok=True);path=folder/('uma_'+module+'_native_idle.anim');P.write_animfile(str(path),file);read=P.read_meshfile(str(path));ri=read.find('info');rs=read.find('samples');assert ri.get('j')==[len(names)]and ri.get('sa')==[count];assert [b.tag for b in ri]==names
    parsed=np.tile(np.eye(4),(count,len(names),1,1));maxerr=0.;maxrelative=0.;largest_parameter=None
    for c,width in [('t',3),('q',4),('s',3)]:
        ids=[i for i,n in enumerate(names)if c in active.get(n,'')];array=np.array(rs.get(c)or[]).reshape(count,len(ids),width)if ids else None
        for i,d in enumerate(decomposed):
            value=array[:,ids.index(i)]if i in ids else np.tile(ri[i].get(c),(count,1));error=float(np.max(np.abs(value-d[c])));relative=error/max(1.,float(np.max(np.abs(d[c]))));maxrelative=max(maxrelative,relative)
            if error>maxerr:maxerr=error;largest_parameter={'bone':names[i],'channel':c,'absolute_error':error,'relative_error':relative,'largest_parameter_abs_value':float(np.max(np.abs(d[c])))}
            if c=='t':parsed[:,i,:3,3]=value
            elif c=='q':parsed[:,i,:3,:3]=Rotation.from_quat(value).as_matrix()
            else:parsed[:,i,:3,:3]*=value[:,None,:]
    assert maxrelative<5e-7,(module,largest_parameter);actual=compose_typed(parsed,rig);point_errors=np.linalg.norm(actual[:,:,:3,3]-expected[:,:,:3,3],axis=2)
    diagnostics={'module':module,'largest_parameter':largest_parameter,'maximum_world_point_error_cm':float(point_errors.max()),'worst_point_bone':names[int(np.unravel_index(point_errors.argmax(),point_errors.shape)[1])],'per_bone_world_point_errors_cm':{n:float(point_errors[:,i].max())for i,n in enumerate(names)}};(OUT/(module+'-roundtrip-diagnostic.json')).write_text(json.dumps(diagnostics,indent=2)+'\n',encoding='utf8')
    assert np.max(point_errors)<.01,(module,point_errors.max(),diagnostics['worst_point_bone']);record={'module':module,'file':str(path),'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_record_keys':source_keys,'frames':count,'fps':30,'j':len(names),'reference_skeleton_json':str(RIGS/(module+'carrier.json'))if module in ['head','ear','tail']else str(RIGS/'body.json'),'bone_keys_exact_same_order_as_reference':True,'constant_helpers_included':len(names)-len(active),'animated_bone_channels':active,'binary_sample_roundtrip_error':maxerr,'binary_sample_relative_roundtrip_error':maxrelative,'largest_parameter_roundtrip_record':largest_parameter,'float32_parameter_roundtrip_policy':'relative error for large helper-local parameters, plus absolute world-point error <.01 cm after hierarchy evaluation; full per-bone measured errors disclosed','all_frame_world_bonepoint_roundtrip_error_cm':float(point_errors.max()),'affine_shear_loss_records':shear,'affine_helper_worldpoint_compensations':fixes,'root_channels':dict(ri.find('head_root').attrib)if module=='head'else None,'source_provenance':[records[k]for k in source_keys],**extra};deliveries.append(record);np.savez_compressed(OUT/(module+'-final-pose-evidence.npz'),local=parsed,world=actual);print('FINAL_NATIVE_CLIP',module,len(names),count,len(active),point_errors.max(),flush=True);return parsed,actual
# Body: world rotations are absolute source orientation, rebased against fitted
# A only for axes. Real local translation displacement keeps new bind lengths.
bodyrig=typed(RIGS/'body.json');bw=np.array(bodyrig['world']);bl=np.array(bodyrig['bind_local']);sourceW,sourceparents=source_rig(sourcebody);sourceLocal={n:raw['body_home_idle__'+n]for n in sourceW};count=len(next(iter(sourceLocal.values())));sourceworld=compose_names(sourceLocal,sourceparents);sourceworldE={n:UC@m@UCI for n,m in sourceworld.items()};mapold=json.loads((V7/'Rigs/body-source-map.json').read_text());prune=contract['body']['prune']['old_to_new_name'];mapping={n:prune[t]for n,t in mapold.items()if t in prune and n in sourceworldE};source_for_target={t:n for n,t in mapping.items()};rgoal={t:np.array([polar(m)for m in sourceworldE[n]])@polar(BP[n]).T@polar(bw[bodyrig['index_by_name'][t]])for n,t in mapping.items()};rotworld=[None]*len(bw)
foot_rest=[];effective_sourceR={n:np.array([polar(m)for m in sourceworldE[n]])for n in mapping};foot_geom=P.read_meshfile(str(ROOT/'UMA-V8/gfx/models/portraits/uma/0001/uma_0001_body_base.mesh')).find('object')[0].find('mesh');foot_points=np.array(foot_geom.get('p')).reshape(-1,3);foot_contact={}
for side in ['L','R']:
    ai=bodyrig['index_by_name'][mapping['Ankle_'+side]];ti=bodyrig['index_by_name'][mapping['Toe_'+side]];mask=(foot_points[:,0]>0 if side=='L'else foot_points[:,0]<0)&(foot_points[:,1]<3);fore=np.flatnonzero(mask&(np.abs(foot_points[:,2]-bw[ti,2,3])<2.5));heel=np.flatnonzero(mask&(foot_points[:,2]>=bw[ai,2,3]-.5));assert len(fore)>4 and len(heel)>4;fore=fore[foot_points[fore,1]<=foot_points[fore,1].min()+.15];heel=heel[foot_points[heel,1]<=foot_points[heel,1].min()+.15];fc=foot_points[fore].mean(0);hc=foot_points[heel].mean(0);horizontal=fc-hc;horizontal[1]=0;lateral=np.cross(horizontal,[0.,1.,0.]);lateral/=np.linalg.norm(lateral);angle=np.arctan2(hc[1]-fc[1],np.linalg.norm(horizontal));correction=Rotation.from_rotvec(lateral*angle).as_matrix();foot_contact[side]={'forefoot_vertex_ids':fore.tolist(),'heel_vertex_ids':heel.tolist(),'rest_forefoot_center_cm':fc.tolist(),'rest_heel_center_cm':hc.tolist(),'geometry_derived_constant_foot_pitch_degrees':float(np.rad2deg(angle)),'pitch_world_axis':lateral.tolist(),'rest_correction_rotation_matrix':correction.tolist(),'contact_definition':'Low .15cm surface layer within metatarsal/ftBall Z±2.5cm and heel Z>=AnkleZ-.5cm, per side.'}
    for part in ['Ankle','Ankle_offset','Toe','Toe_offset']:
        src=part+'_'+side;target=mapping[src];ti=bodyrig['index_by_name'][target];sr=effective_sourceR[src];variation=sr@sr[0].T;rgoal[target]=variation@correction@polar(bw[ti]);effective_sourceR[src]=rgoal[target]@polar(bw[ti]).T@polar(BP[src]);foot_rest.append({'source':src,'target':target,'reference':'actual source absolute world orientation at frame0, rebased to target bind plus actual heel/forefoot contact-plane correction','true_source_world_rotation_variation_max_deg':float(np.rad2deg(Rotation.from_matrix(variation).magnitude()).max()),'firstframe_target_world_rotation_matches_geometry_contact_rest':True})
def body_rot(i):
    if rotworld[i]is not None:return rotworld[i]
    n=bodyrig['names'][i];p=bodyrig['parents'][i];rotworld[i]=rgoal[n]if n in rgoal else (body_rot(p)@polar(bl[i])if p is not None else np.tile(polar(bl[i]),(count,1,1)));return rotworld[i]
for i in range(len(bw)):body_rot(i)
bodylocal=np.tile(bl,(count,1,1,1));delta_checks=[]
for i,n in enumerate(bodyrig['names']):
    p=bodyrig['parents'][i];pr=body_rot(p)if p is not None else np.tile(np.eye(3),(count,1,1));localR=np.transpose(pr,(0,2,1))@body_rot(i);stretch=polar(bl[i]).T@bl[i,:3,:3];bodylocal[:,i,:3,:3]=localR@stretch
    if n in source_for_target:
        src=source_for_target[n];sp=sourceparents[src];bindlocal=np.linalg.inv(BT[sp])@BT[src]if sp else BT[src];cl=UC@sourceLocal[src]@UCI;delta=cl[:,:3,3]-bindlocal[:3,3];sr=np.array([polar(m)for m in sourceworldE[sp]])if sp else np.tile(np.eye(3),(count,1,1));offset=(np.transpose(pr,(0,2,1))@sr@delta[:,:,None])[:,:,0];bodylocal[:,i,:3,3]=bl[i,:3,3]+offset;delta_checks.append({'source':src,'target':n,'delta_cm_min':delta.min(0).tolist(),'delta_cm_max':delta.max(0).tolist()})
ground_cm=0.;sourcepoint={};desired_body={}
def point_native(src):
    if src in sourcepoint:return sourcepoint[src]
    target=mapping[src];ti=bodyrig['index_by_name'][target];sp=sourceparents[src];cl=UC@sourceLocal[src]@UCI;bindlocal=np.linalg.inv(BT[sp])@BT[src]if sp else BT[src];delta=cl[:,:3,3]-bindlocal[:3,3]
    if sp is not None:
        pi=bodyrig['index_by_name'][mapping[sp]];sr=effective_sourceR[sp];ref=bw[ti,:3,3]-bw[pi,:3,3];offset=(sr@polar(BP[sp]).T@ref[:,None])[:,:,0]+(sr@delta[:,:,None])[:,:,0];point=point_native(sp)+offset
    else:point=bw[ti,:3,3]+delta
    if src=='Hip':point=point.copy();point[:,1]+=ground_cm
    sourcepoint[src]=point;return point
for src,target in mapping.items():
    ti=bodyrig['index_by_name'][target];m=np.tile(np.eye(4),(count,1,1));stretch=polar(bw[ti]).T@bw[ti,:3,:3];m[:,:3,:3]=rgoal[target]@stretch;m[:,:3,3]=point_native(src);desired_body[target]=m
bodylocal,body_goal=local_from_desired(bodyrig,desired_body,count)
bodymesh=P.read_meshfile(str(ROOT/'UMA-V8/gfx/models/portraits/uma/0001/uma_0001_body_base.mesh')).find('object')[0].find('mesh');p=np.array(bodymesh.get('p')).reshape(-1,3);skin=bodymesh.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);weights=np.array(skin.get('w')).reshape(-1,4);inverse=np.array(bodyrig['inverse_bind']);hp=np.column_stack([p,np.ones(len(p))]);footids=np.flatnonzero(p[:,1]<12);floor_before=[]
for f in range(count):
    q=np.zeros_like(p);mat=body_goal[f]@inverse
    for slot in range(4):q+=np.einsum('nij,nj->ni',mat[np.maximum(ix[:,slot],0)],hp)[:,:3]*weights[:,slot,None]
    floor_before.append(float(q[footids,1].min()))
ground_cm=-min(floor_before)
for src,target in mapping.items():
    if src not in [sourcebody['bones'][0]['name'],'Position']:desired_body[target][:,1,3]+=ground_cm
bodylocal,body_goal=local_from_desired(bodyrig,desired_body,count)
bodyparsed,bodypose=write('body',bodyrig,bodylocal,['body_home_idle'],{'retarget_method':'Absolute orientation against native fitted A; calibrated A joint vectors transported along ORIGINAL NATIVE parents, then converted to destination parents; real source local translation minus Nbind. Avoids stock/native parent mismatch at Shoulder/volume joints.','source_bone_to_target':mapping,'translation_displacements':delta_checks,'Ear_Tail_keys_absent':True,'canonical_rotation_proof':str(OUT/'retarget-formula-numerical-proof.json'),'ground_calibration_cm':ground_cm,'ground_calibration_is_constant_clip_placement_not_mesh_or_bind_edit':True,'foot_rest_reference_corrections':foot_rest,'actual_heel_forefoot_geometry_contact_calibration':foot_contact,'ground_calibration_measured_after_flatfoot_correction_allframes':True,'floor_before_calibration_minmax_cm':[min(floor_before),max(floor_before)]})
# Header: exact visible head bind centers, never body Head attachment-marker
# positions. Body Neck/Head orientation is transported relative to body socket.
headrig=typed(RIGS/'headcarrier.json');hb=np.array(headrig['world']);hcount=count;desired={};rootindex=headrig['index_by_name']['head_root'];rootbind=hb[rootindex];socketindex=bodyrig['index_by_name']['bn_sp_thoracic'];neckindex=bodyrig['index_by_name']['bn_sp_cervical'];ext=bodypose[:,socketindex]@np.linalg.inv(rootbind);extbind=bw[socketindex]@np.linalg.inv(rootbind);extR=np.array([polar(m)for m in ext]);faceproof=[];source_head_bodyR=np.array([polar(m)for m in sourceworldE['Head']]);body_neckR=np.array([polar(m)for m in bodypose[:,neckindex]])
for actor in ['1001','1002']:
    hrec=records['head_'+actor+'_home_idle'];data=json.loads(Path(hrec['source_bind_snapshot']).read_text());sourcebind,sparents=source_rig(data);sm=json.loads((RIGS/('head_'+actor+'-source-map.json')).read_text());src_to_dst={b['name']:sm.get(b['id'])for b in data['bones']};nativebind={n:HC@m@HCI for n,m in sourcebind.items()};Hsource=sourcebind['Head'][:3,3];hname=src_to_dst['Head'];nname=src_to_dst['Neck'];hi=headrig['index_by_name'][hname];ni=headrig['index_by_name'][nname];K=np.eye(4);K[:3,3]=hb[hi,:3,3]-HC[:3,:3]@Hsource;nativebind={n:K@m for n,m in nativebind.items()};loc={}
    for n in sourcebind:
        if hrec['key']+'__'+n in raw:m=raw[hrec['key']+'__'+n]
        else:m=np.tile(np.linalg.inv(sourcebind[sparents[n]])@sourcebind[n]if sparents[n]else sourcebind[n],(hcount,1,1))
        loc[n]=HC@m@HCI
    globalNeckBind=extbind@hb[ni];globalHeadBind=extbind@hb[hi];goalNeckR=body_neckR@polar(bw[neckindex]).T@polar(globalNeckBind);goalHeadR=source_head_bodyR@polar(BP['Head']).T@polar(globalHeadBind);targetNeckObjectR=np.transpose(extR,(0,2,1))@goalNeckR;targetHeadObjectR=np.transpose(extR,(0,2,1))@goalHeadR;sourceNeckObjectR=targetNeckObjectR@polar(hb[ni]).T@polar(nativebind['Neck']);sourceHeadObjectR=targetHeadObjectR@polar(hb[hi]).T@polar(nativebind['Head']);loc['Neck'][:,:3,:3]=sourceNeckObjectR;loc['Head'][:,:3,:3]=np.transpose(sourceNeckObjectR,(0,2,1))@sourceHeadObjectR;pose=compose_names(loc,sparents,K);mapped=[]
    skipped_shader_info=[]
    for src,target in src_to_dst.items():
        if target not in headrig['index_by_name']or src not in pose or target=='head_root':continue
        if actor=='1002'and not target.startswith('uma_1002_'):continue
        if '_info'in src.lower():skipped_shader_info.append({'source':src,'target':target,'reason':'Unity shader parameter helper, no positive skin weights; retain reference local constant following parent, not encoded parameter xyz as CK3 joint movement'});continue
        goal=pose[src]@np.linalg.inv(nativebind[src])@hb[headrig['index_by_name'][target]];desired[target]=goal;mapped.append({'source':src,'target':target})
    neck_bind_under_socket=(np.linalg.inv(extbind)@bw[neckindex])[:3,3];bind_offset=hb[ni,:3,3]-neck_bind_under_socket;neck_current_object=(np.linalg.inv(ext)@bodypose[:,neckindex])[:,:3,3]+bind_offset;shift=neck_current_object-desired[nname][:,:3,3]
    for item in mapped:desired[item['target']][:,:3,3]+=shift
    faceproof.append({'actor':actor,'mapped_skeletal_bones':mapped,'shader_parameter_info_helpers_retained_static':skipped_shader_info,'native_head_center_preserved_as_header_bind_not_body_marker':True,'same_body_Neck_Head_motion_source':records['body_home_idle']['source_bundle'],'constant_facial_locator_source':hrec['source_bundle'],'actor2_uses_own_bind_namespaces':actor=='1002','global_visible_head_bind_center_cm':globalHeadBind[:3,3].tolist(),'body_current_cervical_point_transport_applied_to_whole_actor_head':True,'original_actor_neck_bind_offset_under_socket_cm':bind_offset.tolist(),'whole_head_transport_shift_minmax_cm':[shift.min(0).tolist(),shift.max(0).tolist()]})
headlocal,headgoal=local_from_desired(headrig,desired,hcount);headlocal[:,rootindex]=np.array(headrig['bind_local'])[rootindex];headparsed,headpose=write('head',headrig,headlocal,['head_1001_home_idle','head_1002_home_idle','body_home_idle'],{'head_root_static_direct_minus_d':True,'no_uma_head_base_or_point_additives':True,'head_body_Ear_Tail_keys_absent':True,'actor_semantic_coverage':faceproof,'body_source_marker_translation_not_used':True,'body_socket_current_root_inverse_attachment':True})
# Independent ear/headwear namespaces preserve original native local axes and
# attachment-local inverse binds; no shared head pose inside their skeleton.
earrig=typed(RIGS/'earcarrier.json');el=np.tile(np.array(earrig['bind_local']),(460,1,1,1));variantmaps=json.loads((RIGS/'ear-variant-remap.json').read_text());earkeys=[]
for row in variantmaps:
    key='ear_'+row['actor']+'_'+row['variant'];earkeys.append(key);rec=records[key]
    for src in rec['bone_keys']:
        target=row['old_name_to_union_name'][src];i=earrig['index_by_name'][target];el[:,i]=HC@raw[key+'__'+src]@HCI
earparsed,earpose=write('ear',earrig,el,earkeys,{'single_actual_source_clip':records[earkeys[0]]['source_bundle'],'variant_native_driver_tables_preserved':True,'all_namespaced_ancestry_and_static_Ear_refs_included':True,'attachment_current_head_node_only_once':True})
tailrig=typed(RIGS/'tailcarrier.json');tl=np.tile(np.array(tailrig['bind_local']),(65,1,1,1));trec=records['tail_shared_native_idle'];source_tail=json.loads(Path(trec['source_bind_snapshot']).read_text());tw,tp=source_rig(source_tail);tbody=bw[bodyrig['index_by_name']['body_root']];tdesired=np.eye(4);tdesired[:3,3]=tbody[:3,3];TK=np.linalg.inv(tbody)@tdesired
for src,target in independent['tail']['source_name_to_target'].items():
    i=tailrig['index_by_name'][target];m=HC@raw[trec['key']+'__'+src]@HCI
    if tp[src]is None:m=TK@m
    tl[:,i]=m
tailparsed,tailpose=write('tail',tailrig,tl,[trec['key']],{'single_actual_source_clip':trec['source_bundle'],'tail_body_root_current_attachment_only_once':True,'original_inverse_body_root_bind_axis_compensation_preserved':True})
from v8_rigs import is_ear_tail
assert [d['j']for d in deliveries]==[146,242,169,9];assert not any(is_ear_tail(n)for n in headrig['names']+bodyrig['names']);rootattrs=next(d for d in deliveries if d['module']=='head')['root_channels'];assert rootattrs['sa']==[''];result={'passed_exact_reference_joint_counts_and_binary_roundtrip':True,'modules':deliveries,'one_file_per_module':True,'filenames_expected_by_private_macros':{d['module']:d['file']for d in deliveries},'no_stock_CK3_motion_used':True,'no_synthetic_sine_or_amplification':True,'original_V7_and_final_V8_models_configs_not_modified':True,'SDK_Blender_import_and_game_execution_not_claimed':True};(OUT/'native-animation-delivery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('FOUR_NATIVE_EXACT_TARGET_ANIMATIONS_READY',flush=True)
