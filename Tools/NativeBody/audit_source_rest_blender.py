"""Inspect unmodified common topology and both real rest skeletons (Blender 4.2)."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from mathutils import Matrix

p=argparse.ArgumentParser()
for name in ('repo','plugin','config','stock','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);repo=a.repo
sys.path.insert(0,str(repo/'Tools/PDXExporter'))
sys.path.insert(0,str(a.plugin.parent))
from io_pdx_mesh import pdx_data
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
from rigging import _semantic_map
c=json.loads(a.config.read_text(encoding='utf8'))
r=next(r for r in c['records'] if r['profile']['costume_id']=='0004' and tuple(int(r['profile'][k]) for k in ('height','shape','bust'))==(1,0,2))
d=json.loads(Path(r['snapshot']).read_text(encoding='utf8'));m=next(m for m in d['meshes'] if m['name']=='M_Body')
p=np.array([[v[k] for k in 'xyz'] for v in m['vertices']]);f=np.array([t[:3] for t in r['triangles']]);unique,wi=np.unique(np.round(p,6),axis=0,return_inverse=True)
edges=set(tuple(sorted((wi[a],wi[b]))) for t in f for a,b in zip(t,np.roll(t,-1)) if wi[a]!=wi[b])
stock=pdx_data.read_meshfile(str(a.stock));obj=stock.find('object')[0];skel=obj.find('skeleton')
target={}
for b in skel:
    t=b.attrib['tx'];inv=Matrix(((t[0],t[3],t[6],t[9]),(t[1],t[4],t[7],t[10]),(t[2],t[5],t[8],t[11]),(0,0,0,1)))
    target[b.tag]=np.array(inv.inverted().translation)
source={b['name']:np.array(b['matrix']).reshape(4,4)[:3,3] for b in d['bones']}
report=dict(source_bounds=[p.min(0).tolist(),p.max(0).tolist()],stock_bounds=[np.array(obj.find('mesh').attrib['p']).reshape(-1,3).min(0).tolist(),np.array(obj.find('mesh').attrib['p']).reshape(-1,3).max(0).tolist()],source_vertices=len(p),welded_vertices=len(unique),triangles=len(f),edges=len(edges),joints=[dict(uma=a,ck3=b,source_m=source[a].tolist(),stock_cm=target[b].tolist()) for a,b in _semantic_map('body').items() if a in source and b in target],source_bones=list(source))
out=a.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({**report,'joints':report['joints'][:5]+[x for x in report['joints'] if x['uma'].endswith('_L') and not any(f in x['uma'] for f in ('Thumb','Index','Middle','Ring','Pinky'))]},indent=2))
