import os
import json,sys
from pathlib import Path
import UnityPy,numpy as np
from scipy.spatial.transform import Rotation
from native_motion import sample_clip,transform_paths,ear_local_frames,tail_local_frames
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));s=json.loads((ROOT/'resource-selection.json').read_text());locator=UnityPy.load(str(ROOT/'locator-native/3d/animator/drivenkeylocator'));hashes=transform_paths(locator);target=json.loads((ROOT/'parsed/ear-driven-targets.json').read_text())[0];tail=json.loads((ROOT/'parsed/tail.json').read_text());records=[];saved={}
for kind,paths,folder in [('ear',s['ear_candidates'],'more-native'),('tail',s['tail_candidates'],'named-native')]:
    for number,path in enumerate(paths):
        env=UnityPy.load(str(ROOT/folder/path));clip=next(o.read()for o in env.objects if o.type.name=='AnimationClip');times,tracks=sample_clip(clip)
        if not tracks:continue
        if kind=='ear':frames,used=ear_local_frames(times,tracks,hashes,target)
        else:frames,parents,used=tail_local_frames(times,tracks,tail)
        amplitude=0
        for name,values in frames.items():
            rot=values[:,:3,:3];scale=np.linalg.norm(rot,axis=1);r=Rotation.from_matrix(rot/np.maximum(scale[:,None,:],1e-20));diff=r[0].inv()*r;amplitude=max(amplitude,float(np.rad2deg(diff.magnitude()).max()))
        key=kind+'_'+str(number).zfill(2);records.append(dict(kind=kind,key=key,source=path,frames=len(times),seconds=float(times[-1]-times[0]),fps=30,amplitude_degrees=amplitude,bones=list(frames),source_bindings_mapped=used))
        for name,v in frames.items():saved[key+'__'+name]=v
        print('SAMPLED_NATIVE_MOTION',kind,number,len(times),round(amplitude,2),flush=True)
np.savez_compressed(ROOT/'native-motion-frames.npz',**saved);(ROOT/'native-motion-index.json').write_text(json.dumps(records,indent=2),encoding='utf8')
print('NATIVE_MOTION_SAMPLING_COMPLETE',len(records),flush=True)
