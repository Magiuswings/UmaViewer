"""Actual UMA raw local frames, matched source idle; draft assets only."""
import json,sys,re,hashlib,copy
from pathlib import Path
from collections import defaultdict
import xml.etree.ElementTree as ET
import numpy as np,UnityPy
from scipy.spatial.transform import Rotation
sys.path[:0]=['C:/Users/33775/Desktop/网页制作/UmaV6Scripts','C:/Users/33775/Desktop/网页制作/UmaV7Scripts','E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter']
from native_motion import sample_clip,path_hash,transform_paths,vector,ear_local_frames,tail_local_frames
from build_ck3_mod import parser_only
ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/MotionSources');V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/HeadSources');V6=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001');REPO=Path('E:/UmaViewer-Workspace/UmaViewer-source');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');BPATH=Path('E:/UmaViewer-Exports/2026-10-08-Skin-Envelope/snapshots/charashared__body_bdy0004_00_00_1_0_2.uma.json');body=json.loads(BPATH.read_text());locator_env=UnityPy.load(str(V7/'decoded/locator/3d/animator/drivenkeylocator'));locator_hashes=transform_paths(locator_env);report=[];stored={}
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def clipfile(basename):return next(p for p in (ROOT/'bundles'/basename).rglob('*')if p.is_file()and p.name==basename)
def loadclip(path):
    env=UnityPy.load(str(path));obj=next(o for o in env.objects if o.type.name=='AnimationClip');clip=obj.read();times,tracks=sample_clip(clip);return clip,times,tracks,obj.path_id
def rig(data):
    byid={b['id']:b for b in data['bones']};world={b['name']:np.array(b['matrix']).reshape(4,4)for b in data['bones']};parents={b['name']:byid[b['parent']]['name']if b['parent']else None for b in data['bones']};local={n:np.linalg.inv(world[parents[n]])@m if parents[n]else m for n,m in world.items()};hashes={}
    def path(b):return (path(byid[b['parent']])+'/'if b['parent']else '')+b['name']
    for b in data['bones']:
        parts=path(b).split('/')
        for k in range(len(parts)):hashes[path_hash('/'.join(parts[k:]))]=b['name']
    return world,parents,local,hashes
def direct_frames(data,times,tracks):
    world,parents,local,hashes=rig(data);frames={};channels={};mapped=[]
    for n,m in local.items():
        s=np.linalg.norm(m[:3,:3],axis=0);r=m[:3,:3]/s[None,:];channels[n]={'t':np.tile(m[:3,3],(len(times),1)),'q':np.tile(Rotation.from_matrix(r).as_quat(),(len(times),1)),'s':np.tile(s,(len(times),1))}
    for tr in tracks:
        assert tr['hash']in hashes,('unresolved body hash',tr['hash']);name=hashes[tr['hash']];attribute=tr['attribute'];assert attribute in [1,2,3,4]
        if attribute==4:value=Rotation.from_euler('zxy',tr['values'][:,[2,0,1]],degrees=True).as_quat();field='q'
        else:value=tr['values'];field={1:'t',2:'q',3:'s'}[attribute]
        channels[name][field]=value.copy();mapped.append({'crc32':tr['hash'],'attribute':attribute,'bone':name,'dynamic':bool(np.ptp(value,axis=0).max()>1e-7)})
    for n,d in channels.items():
        q=d['q']/np.linalg.norm(d['q'],axis=1)[:,None];matrix=np.tile(np.eye(4),(len(times),1,1));matrix[:,:3,:3]=Rotation.from_quat(q).as_matrix()*d['s'][:,None,:];matrix[:,:3,3]=d['t'];frames[n]=matrix
    return frames,mapped
def write_draft(module,names,frames):
    C=np.diag([-100.,100.,-100.,1.]);CI=np.linalg.inv(C);info=ET.Element('info',{'fps':[30.],'sa':[len(next(iter(frames.values())))],'j':[len(names)]});samples=ET.Element('samples');pieces=defaultdict(list);active={}
    for n in names:
        m=C@frames[n]@CI;s=np.linalg.norm(m[:,:3,:3],axis=1);r=m[:,:3,:3]/s[:,None,:];q=Rotation.from_matrix(r).as_quat()
        for f in range(1,len(q)):
            if q[f]@q[f-1]<0:q[f]*=-1
        d={'t':m[:,:3,3],'q':q,'s':s};cs=''.join(c for c in ['t','q','s']if np.max(np.abs(d[c]-d[c][0]))>1e-7);ET.SubElement(info,n,{'sa':[cs],**{c:d[c][0].tolist()for c in ['t','q','s']}})
        for c in cs:pieces[c].append(d[c])
        if cs:active[n]=cs
    for c,arrays in pieces.items():samples.set(c,np.stack(arrays,axis=1).ravel().tolist())
    file=ET.Element('File',{'pdxasset':[1,0]});file.append(info);file.append(samples);folder=ROOT/'draft'/'animation'/module;folder.mkdir(parents=True,exist_ok=True);path=folder/('uma_'+module+'_native_source_draft.anim');P.write_animfile(str(path),file);parsed=P.read_meshfile(str(path));assert parsed.find('info').get('j')==[len(names)];assert parsed.find('info').get('sa')==info.get('sa');return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bone_keys':names,'animated_keys':active,'draft_only_target_binding_not_applied':True,'draft_axis_and_unit':'Unity native local -> engine diag(-100,+100,-100), no target A-bind adaptation.'}
def retain(record,frames):
    for n,m in frames.items():assert np.isfinite(m).all();stored[record['key']+'__'+n]=m
    record['bone_keys']=list(frames);record['native_local_frame_count']=len(next(iter(frames.values())));record['dynamic_matrix_bones']=[n for n,m in frames.items()if np.max(np.abs(m-m[0]))>1e-7];report.append(record)
    print('REAL_SOURCE_FRAMES',record['key'],record['native_local_frame_count'],len(frames),len(record['dynamic_matrix_bones']),flush=True)
bodyfile=clipfile('anm_hom_type01_000_001_loop');bclip,bt,btracks,bid=loadclip(bodyfile);bodyframes,bmapped=direct_frames(body,bt,btracks);retained={n:m for n,m in bodyframes.items()if not re.search(r'(^|_)(ear|tail)(_|$|[0-9])',n,re.I)};record={'key':'body_home_idle','module':'body','source_bundle':str(bodyfile),'source_sha256':hashlib.sha256(bodyfile.read_bytes()).hexdigest(),'source_clip_name':bclip.m_Name,'source_clip_path_id':bid,'fps':30,'seconds':float(bt[-1]-bt[0]),'source_bind_snapshot':str(BPATH),'track_bindings':bmapped,'source_track_count':len(btracks),'unresolved_track_count':0,'excluded_separate_module_bones':[n for n in bodyframes if n not in retained]};record['draft']=write_draft('body',list(retained),retained);retain(record,retained)
facefile=clipfile('anm_hom_type01_000_001_loop_face');fclip,ft,ftracks,fid=loadclip(facefile);assert np.array_equal(bt,ft);enumtext=(REPO/'Assets/Scripts/umamusume/Gallop/Live/Cutt/LiveTimelineDefine.cs').read_text();enums={}
for t in ftracks:stored['facial_source_track__'+str(t['hash'])+'_'+str(t['attribute'])]=t['values']
for family,etype in [('eye','FacialEyeId'),('eyebrow','FacialEyebrowId'),('mouth','FacialMouthId')]:
    block=re.search(r'enum\s+'+etype+r'\s*\{([^}]+)',enumtext,re.S).group(1);enums[family]={name:int(value)for name,value in re.findall(r'(\w+)\s*=\s*(\d+)',block)}
for actor in ['1001','1002']:
    sourcepath=V7/f'parsed/chr{actor}_80/head.json';head=json.loads(sourcepath.read_text());world,parents,local,_=rig(head);frames={n:np.tile(m,(len(ft),1,1))for n,m in local.items()};targets=json.loads((sourcepath.parent/'driven-targets.json').read_text());target=next(x['data']for x in targets if 'facial_target'in x['data'].get('m_Name',''));table={family:target['_'+family+'Target']for family in ['eye','eyebrow','mouth']};fields={};used=[];ignored=[]
    for family,entries in table.items():
        for group in entries[0]['_faceGroupInfo']:
            for item in group['_trsArray']:
                n=item['_path'];fields[n]={'t':np.tile(vector(item['_position']),(len(ft),1)),'s':np.tile(vector(item['_scale']),(len(ft),1)),'euler':np.tile(vector(item['_rotation']),(len(ft),1))}
    assert all(t['hash']in locator_hashes for t in ftracks);loc={locator_hashes[t['hash']]:t['values']for t in ftracks if t['attribute']==1}
    def add(family,index,side,weight,path):
        for item in table[family][index]['_faceGroupInfo'][side]['_trsArray']:
            n=item['_path'];assert n in fields
            for k,source in [('t','_position'),('s','_scale'),('euler','_rotation')]:fields[n][k]+=weight[:,None]*vector(item[source])
        used.append({'locator':path,'family':family,'index':index,'side':side,'weight_min':float(weight.min()),'weight_max':float(weight.max())})
    for path,value in loc.items():
        family='eyebrow'if 'Eyebrow_'in path else 'eye'if 'Eye_'in path else 'mouth'if 'Mouth_Base'in path else None
        if family is None:
            if not path.startswith('Eyeball_'):ignored.append({'locator':path,'reason':'non-skeletal shader/cheek/tear controller, source values retained in tracks'} )
            continue
        tag=path.rsplit('__',1)[-1];assert tag in enums[family],path;side=1 if '_L_'in path else 0;w=value[:,0]*-100
        if family=='mouth':w=np.abs(w);side=0
        add(family,enums[family][tag],side,w,path)
    all_eye=loc.get('Eyeball_all_Ctrl',np.zeros((len(ft),3)))
    for side,letter in [(1,'L'),(0,'R')]:
        value=loc.get('Eyeball_'+letter+'_Ctrl',np.zeros((len(ft),3)));add('eye',20,side,(value[:,0]+all_eye[:,0])*100,'Eyeball_'+letter+'_Ctrl/XRange');add('eye',21,side,(value[:,1]+all_eye[:,1])*(100 if side else -100),'Eyeball_'+letter+'_Ctrl/YRange')
    for n,d in fields.items():
        assert n in frames;frames[n][:,:3,:3]=Rotation.from_euler('xyz',d['euler'],degrees=True).as_matrix()*d['s'][:,None,:];frames[n][:,:3,3]=d['t']
    # Same real body clip supplies head/neck motion. Head prefab's true local
    # translation lengths stay intact, and no synthetic blink is introduced.
    for n in ['Neck','Head']:
        s=np.linalg.norm(frames[n][:,:3,:3],axis=1);br=bodyframes[n][:,:3,:3];bs=np.linalg.norm(br,axis=1);frames[n][:,:3,:3]=br/bs[:,None,:]*s[:,None,:]
    frames={n:m for n,m in frames.items()if not re.search(r'(^|_)(ear|tail)(_|$|[0-9])',n,re.I)};record={'key':'head_'+actor+'_home_idle','module':'head','actor':actor,'source_bundle':str(facefile),'source_sha256':hashlib.sha256(facefile.read_bytes()).hexdigest(),'source_clip_name':fclip.m_Name,'source_clip_path_id':fid,'head_neck_motion_source':str(bodyfile),'head_neck_body_track_keys':['Neck','Head'],'fps':30,'seconds':2.,'source_bind_snapshot':str(sourcepath),'source_target_table':str(sourcepath.parent/'driven-targets.json'),'source_locator_tracks':len(ftracks),'locator_hashes_resolved':len(ftracks),'locator_position_paths':len(loc),'actual_skeletal_locators_used':used,'non_skeletal_controllers':ignored,'facial_loop_is_constant_pose_not_blink':True,'facial_native_points_set':list(fields),'source_track_npz_prefix':'facial_source_track__'}
    if actor=='1001':record['draft']=write_draft('head',list(frames),frames)
    retain(record,frames)
earindex=json.loads((V6/'native-motion-index.json').read_text());e=next(r for r in earindex if r['key']=='ear_03');earfile=V6/'more-native'/e['source'];eclip,et,etracks,eid=loadclip(earfile);partindex=json.loads((V7/'head-parts-index.json').read_text())
for rec in partindex['records']:
    if rec['kind']!='head':continue
    actor=rec['character_id'];variant=rec['variant'];targets=json.loads(Path(rec['driven_targets_json']).read_text());target=next(x['data']for x in targets if 'ear_target'in x['data'].get('m_Name',''));frames,used=ear_local_frames(et,etracks,locator_hashes,target);record={'key':'ear_'+actor+'_'+variant,'module':'ear','actor':actor,'variant':variant,'source_bundle':str(earfile),'source_sha256':hashlib.sha256(earfile.read_bytes()).hexdigest(),'source_clip_name':eclip.m_Name,'source_clip_path_id':eid,'fps':30,'seconds':float(et[-1]-et[0]),'source_target_table':rec['driven_targets_json'],'source_locator_tracks':len(etracks),'resolved_locator_paths':used,'same_previously_verified_source_clip_key':'ear_03'}
    if actor=='1001'and variant=='80':record['draft']=write_draft('ear',list(frames),frames)
    retain(record,frames)
t=next(r for r in earindex if r['key']=='tail_10');tailfile=V6/'named-native'/t['source'];tclip,tt,ttracks,tid=loadclip(tailfile);taildata=json.loads((V7/'parsed/tail_1001/tail.json').read_text());frames,parents,mapped=tail_local_frames(tt,ttracks,taildata);record={'key':'tail_shared_native_idle','module':'tail','source_bundle':str(tailfile),'source_sha256':hashlib.sha256(tailfile.read_bytes()).hexdigest(),'source_clip_name':tclip.m_Name,'source_clip_path_id':tid,'fps':30,'seconds':float(tt[-1]-tt[0]),'source_bind_snapshot':str(V7/'parsed/tail_1001/tail.json'),'source_transform_tracks':len(ttracks),'resolved_source_keys':mapped,'same_previously_verified_source_clip_key':'tail_10'};record['draft']=write_draft('tail',list(frames),frames);retain(record,frames)
np.savez_compressed(ROOT/'native-source-local-frames.npz',**stored);dump(ROOT/'native-source-local-index.json',{'chosen_body':'body_home_idle','chosen_head':'head_1001_home_idle plus head_1002_home_idle target-table variant','source_absolute_Unity_LOCAL_frames':True,'source_motion_not_synthesized_or_amplified':True,'one_source_per_module_final_target_contract_pending':True,'head_body_ear_tail_separated':True,'records':report,'draft_animation_files':[r['draft']['path']for r in report if 'draft'in r],'static_facial_pose_disclosed':True,'CK3_clip_not_used_for_motion_source':True});print('RAW_MOTION_DELIVERY_COMPLETE',len(report),len(stored),flush=True)

