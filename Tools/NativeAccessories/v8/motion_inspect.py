import json,sys,hashlib
from pathlib import Path
import numpy as np,UnityPy
sys.path.insert(0,'C:/Users/33775/Desktop/网页制作/UmaV6Scripts')
from native_motion import sample_clip,transform_paths,path_hash
ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/MotionSources');BODY=Path('E:/UmaViewer-Exports/2026-10-08-Skin-Envelope/snapshots/charashared__body_bdy0004_00_00_1_1_0.uma.json');data=json.loads(BODY.read_text());byid={b['id']:b for b in data['bones']};hashes={}
def path(b):return (path(byid[b['parent']])+'/'if b['parent']else '')+b['name']
for b in data['bones']:
    parts=path(b).split('/')
    for k in range(len(parts)):
        suffix='/'.join(parts[k:]);hashes[path_hash(suffix)]=b['name']
nativebody=UnityPy.load('E:/UmaViewer-Exports/2026-10-08-Vector-Body/named-common-v2/3d/chara/body/bdy0004_00/pfb_bdy0004_00_00_1_1_0')
for crc,suffix in transform_paths(nativebody).items():hashes[crc]=suffix.rsplit('/',1)[-1]
locator=UnityPy.load('E:/UmaViewer-Exports/2026-10-11-UMA-V7/HeadSources/decoded/locator/3d/animator/drivenkeylocator');loc=transform_paths(locator);reports=[]
for folder in sorted((ROOT/'bundles').iterdir()):
    for file in folder.rglob('*'):
        if not file.is_file():continue
        env=UnityPy.load(str(file));objects={}
        for o in env.objects:objects[o.type.name]=objects.get(o.type.name,0)+1
        for o in env.objects:
            if o.type.name!='AnimationClip':continue
            clip=o.read();times,tracks=sample_clip(clip);rows=[];bindings=clip.m_ClipBindingConstant.genericBindings
            for tr,b in zip(tracks,bindings):
                name=hashes.get(tr['hash']);locator=loc.get(tr['hash']);rows.append({'path_crc32':tr['hash'],'attribute':tr['attribute'],'class_id':b.typeID,'custom_type':b.customType,'source_bone':name,'locator':locator,'value_components':tr['values'].shape[1],'range_max':float(np.ptp(tr['values'],axis=0).max()),'first':tr['values'][0].tolist()})
            record={'bundle':str(file),'bundle_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'objects':objects,'clip_name':clip.m_Name,'clip_path_id':o.path_id,'is_humanoid':getattr(clip,'m_HumanMotion',None),'seconds':float(times[-1]-times[0]),'sampled_frames':len(times),'native_sample_rate':clip.m_SampleRate,'tracks':rows,'track_count':len(rows),'unresolved_count':sum(not(t['source_bone']or t['locator'])and t['path_crc32']!=0 for t in rows)};reports.append(record);print(json.dumps({'clip':record['clip_name'],'seconds':record['seconds'],'frames':len(times),'tracks':len(rows),'humanoid':record['is_humanoid'],'unresolved':record['unresolved_count'],'preview':rows[:8]},indent=2),flush=True)
(ROOT/'native-clip-inspection.json').write_text(json.dumps({'source_body_skeleton':str(BODY),'clips':reports},indent=2)+'\n',encoding='utf8')

