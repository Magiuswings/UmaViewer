"""Explicit generic UMA body dimensions; never infer bust from a costume suffix."""
from collections import defaultdict
from pathlib import PurePosixPath
import re

def body_profile(source,kind='body'):
    if kind!='body':return None
    name=PurePosixPath(str(source).replace('\\','/')).name
    match=re.fullmatch(r'pfb_bdy(\d{4})_(\d+)_(\d+)_(\d+)_(\d+)_(\d+)',name)
    if not match or int(match[1])>=1000:return None
    costume,sub,setting,height,shape,bust=match.groups()
    identity=f'bdy{costume}_{sub}_{setting}'
    return dict(costume_id=costume,body_type_sub=sub,body_setting=setting,
                height=height,shape=shape,bust=bust,
                geometry_key=f'{identity}__height_{height}__shape_{shape}__bust_{bust}',
                provenance='Generic prefab: costume, subtype, setting, height, shape, bust')

def profiles_compatible(base,target):
    if base is None and target is None:return True
    if base is None or target is None:return False
    return base['geometry_key']==target['geometry_key']

def select_body_bases(jobs,load_snapshot,variant='auto'):
    if variant=='none':return []
    groups=defaultdict(list)
    for job in jobs:
        if job['kind']!='body':continue
        data=load_snapshot(job)
        profile=body_profile(job['source'])
        bust=profile['bust'] if profile else 'unknown'
        total=sum(len(f['triangles'])//3 for m in data['meshes'] for f in m['faces'])
        skin=sum(len(f['triangles'])//3 for m in data['meshes'] for f in m['faces'] if f['category']=='body_skin')
        if variant=='auto' and skin:score=skin/max(total,1)
        elif variant==data['variant']:score=1.
        else:continue
        groups[(job['character_id'],bust)].append((score,job,profile))
    results=[]
    for (owner,bust),items in sorted(groups.items()):
        score,job,profile=max(items,key=lambda value:(value[0],value[1]['name']))
        results.append(dict(name=job['name'],source=job['source'],character_id=owner,
                            selection=variant,bust=bust,body_profile=profile,
                            base_group=f'chara{owner}__bust_{bust}',
                            skin_triangle_ratio=score if variant=='auto' else None,
                            note='Complete source outfit per owner/bust; unknown bust never inferred; no missing surfaces reconstructed'))
    return results
