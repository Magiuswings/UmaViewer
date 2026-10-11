import os
"""Sample genuine 1002 ear clips through the actual 1002 driven target table."""
import json,sys
from pathlib import Path
import numpy as np,UnityPy
from scipy.spatial.transform import Rotation
sys.path.insert(0,'C:/Users/33775/Desktop/网页制作/UmaV6Scripts')
from native_motion import sample_clip,transform_paths,ear_local_frames
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'HeadSources'));OUT=ROOT/'motions';OUT.mkdir(exist_ok=True);targets=json.loads((ROOT/'parsed/chr1002_80/driven-targets.json').read_text(encoding='utf8'));target=next(t['data']for t in targets if 'ear_target'in t['data'].get('m_Name',''));locator=UnityPy.load(str(ROOT/'decoded/locator/3d/animator/drivenkeylocator'));hashes=transform_paths(locator);catalog=json.loads((ROOT/'head-source-catalog.json').read_text(encoding='utf8'));clips=[e for e in catalog['ear_clips']if e['character_id']=='1002'and e['character_match']and e['present']];saved={};records=[]
for number,e in enumerate(clips):
    env=UnityPy.load(str(ROOT/'decoded/ear-motion-1002'/e['name']));clip=next(o.read()for o in env.objects if o.type.name=='AnimationClip');times,tracks=sample_clip(clip);frames,used=ear_local_frames(times,tracks,hashes,target);amplitude=0.;endpoint=0.;finite=True
    for name,values in frames.items():
        rot=values[:,:3,:3];s=np.linalg.norm(rot,axis=1);r=Rotation.from_matrix(rot/np.maximum(s[:,None,:],1e-20));amplitude=max(amplitude,float(np.rad2deg((r[0].inv()*r).magnitude()).max()));endpoint=max(endpoint,float(np.rad2deg((r[0].inv()*r[-1]).magnitude())));finite&=bool(np.isfinite(values).all())
    assert finite
    key='ear1002_'+str(number).zfill(2);records.append({'kind':'ear','character_id':'1002','key':key,'source':e['name'],'clip_name':clip.m_Name,'frames':len(times),'seconds':float(times[-1]-times[0]),'fps':30,'amplitude_degrees':amplitude,'endpoint_max_bone_angle_degrees':endpoint,'bones':list(frames),'source_bindings_mapped':used,'target_table':'1002 native ast_chr1002_80_ear_target','sample_semantics':'Unity source local animated TRS, no retarget/amplitude scaling. Parent uses source bind parent chain.'})
    for name,v in frames.items():saved[key+'__'+name]=v
    print('SOURCE_1002_EAR',number,len(times),round(amplitude,3),round(endpoint,4),e['name'],flush=True)
np.savez_compressed(OUT/'native-ear-1002-frames.npz',**saved);(OUT/'native-ear-1002-index.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
base=json.loads((ROOT/'head-parts-index.json').read_text(encoding='utf8'));base['native_motion']={'1001':{'reuse_verified_mesh_anims_root':str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'motion-parts'),'unity_local_frames':str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'native-motion-frames.npz'),'clip_index':str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'native-motion-index.json')},'1002':{'unity_local_frames':str(OUT/'native-ear-1002-frames.npz'),'clip_index':str(OUT/'native-ear-1002-index.json'),'source_target_table':str(ROOT/'parsed/chr1002_80/driven-targets.json'),'clips':len(records)},'tail':{'shared_native_model_id':1,'shared_mesh_source_equal':True,'reuse_verified_clips':str(Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'motion-parts/animation/tail'))),'material_diffuse_character_specific':'Use parsed/tail_1001 or tail_1002 source material texture paths, not shared 1001 texture.'}}
(ROOT/'head-parts-index.json').write_text(json.dumps(base,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('NATIVE_1002_SAMPLING_COMPLETE',len(records),flush=True)
