import os
"""1002 local native skirt-chain weight candidates. Never modify production or body."""
import sys,json,copy,os
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')))); REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text()); fam=next(f for f in reg['families']if f['family']=='bdy1002_00');part=fam['parts']['clothes'];src=json.loads(Path(fam['source_snapshot']).read_text());bones={b['id']:b for b in src['bones']};dest=R/'ClothingParts/AB-bdy1002_00';dest.mkdir(exist_ok=True)
base=pd.read_meshfile(part['base_mesh']);sk=base.find('object')[0].find('skeleton');names=[b.tag for b in sk];bi={n:i for i,n in enumerate(names)};bind=inverse_bind(sk)
source=[]
for mi,m in enumerate(src['meshes']):
 p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);mass=np.zeros(len(p));front=np.zeros(len(p));chains=defaultdict(set)
 for row in m['weights']:
  name=bones[row['bone']]['name']
  if 'MSkirt' not in name:continue
  v=row['vertex'];w=row['weight'];direction=name.split('_')[-2]; factor={'F':1,'FL':1,'FR':1,'FLL':.8,'FRR':.8,'L':.35,'R':.35,'BL':.04,'BR':.04,'B':0}[direction];mass[v]+=w;front[v]+=w*factor;chains[v].add(direction)
 front/=np.maximum(mass,1e-10);source.append((p,mass,front,chains))
bodydir=next(Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'v5')).rglob('uma_0001_body_base.mesh')).parent
def bodyp(tag):return np.array(pd.read_meshfile(str(bodydir/('uma_0001_body_'+tag+'.mesh'))).find('object')[0].find('mesh').attrib['p']).reshape(-1,3)
bodytree=pd.read_meshfile(str(bodydir/'uma_0001_body_base.mesh'));bn=bodytree.find('object')[0].find('mesh');bp=bodyp('base');bp=bp+(bodyp('b0')-bp)+(bodyp('s1')-bp);bt=np.array(bn.attrib['tri']).reshape(-1,3);bix=np.array(bn.find('skin').attrib['ix']).reshape(-1,4);bw=np.array(bn.find('skin').attrib['w']).reshape(-1,4)
def deform(p,ix,w,mat):
 h=np.column_stack([p,np.ones(len(p))]);out=np.zeros_like(p)
 for j in range(4):out+=np.einsum('nij,nj->ni',mat[np.maximum(ix[:,j],0)],h)[:,:3]*w[:,j,None]
 return out
anims={}
folder=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body'))
for label,file in [('idle','female_body_idle_1.anim'),('throne','female_body_throneRoom_ruler1_1.anim')]:
 a=pd.read_meshfile(str(folder/file));nf=a.find('info').attrib['sa'][0];anims[label]=[(frame,globals_for(a.find('info'),a.find('samples'),frame,sk)@bind)for frame in sorted({0,nf//2,nf-1})]
targets={k:pd.read_meshfile(f)for k,f in part['shape_targets'].items()};nodes=[(oi,ni,n)for oi,o in enumerate(base.find('object'))for ni,n in enumerate(o.findall('mesh'))];manifest=[]
for case,strength,width in [('baseline',None,None),('A',.88,.09),('B',1.0,.065),('C',1.0,.035),('D',1.0,.065),('E',1.0,.045)]:
 tree=copy.deepcopy(base);changed=0;records=[];weight_arrays=[]
 for (_,_,n),sm in zip(nodes,part['source_maps']):
  ids=np.array(sm['source_vertex_ids']);p,mass,front,chains=source[sm['mesh']];ix=np.array(n.find('skin').attrib['ix']).reshape(-1,4);w=np.array(n.find('skin').attrib['w']).reshape(-1,4);ni=ix.copy();nw=w.copy();active=(mass[ids]>.01)&(p[ids,1]<.985)
  if strength is not None:
   for j in np.flatnonzero(active):
    sid=ids[j];ramp=np.clip((.985-p[sid,1])/(.085 if case=='D'else .055 if case=='E'else .205),0,1);ramp=ramp*ramp*(3-2*ramp);sector=np.clip(front[sid]*1.35,0,1)if case in ['D','E']else front[sid];thigh=ramp*(.06+(strength-.06)*sector);left=.5+.5*np.tanh(-p[sid,0]/width);values={bi['body_root']:1-thigh,bi['bn_l_hip']:thigh*left,bi['bn_r_hip']:thigh*(1-left)};best=sorted(values.items(),key=lambda x:-x[1]);ni[j]=-1;nw[j]=0
    for k,(bid,weight)in enumerate(best):ni[j,k]=bid;nw[j,k]=weight
   changed+=int(np.sum(np.any(ni!=ix,axis=1)|np.any(abs(nw-w)>1e-8,axis=1)))
  weight_arrays.append((ni,nw));records.append(dict(mesh=sm['mesh'],material=sm['material'],affected_source_vertex_ids=ids[active].tolist(),front_source_vertex_ids=ids[active&(front[ids]>.6)].tolist(),back_source_vertex_ids=ids[active&(front[ids]<.2)].tolist(),source_native_skirt_influence=True))
 cdir=dest/case;cdir.mkdir(exist_ok=True);files={}
 for tag,file in [('base',part['base_mesh']),*[(Path(f).stem.rsplit('_',1)[-1],f)for f in part['shape_targets'].values()]]:
  target=pd.read_meshfile(file)
  for node,(ni,nw)in zip([n for o in target.find('object')for n in o.findall('mesh')],weight_arrays):node.find('skin').attrib['ix']=ni.ravel().tolist();node.find('skin').attrib['w']=nw.ravel().tolist()
  output=cdir/Path(file).name;pd.write_meshfile(str(output),target);back=pd.read_meshfile(str(output));
  for old,new in zip([n for o in pd.read_meshfile(file).find('object')for n in o.findall('mesh')],[n for o in back.find('object')for n in o.findall('mesh')]):
   assert old.attrib==new.attrib;assert np.allclose(np.array(new.find('skin').attrib['w']).reshape(-1,4).sum(1),1);assert np.array_equal(inverse_bind(back.find('object')[0].find('skeleton')),bind)
  files[tag]=str(output)
 stats=[]
 for label,samples in anims.items():
  for frame,mat in samples:
   body=deform(bp,bix,bw,mat);normal=np.zeros_like(body);cross=np.cross(body[bt[:,1]]-body[bt[:,0]],body[bt[:,2]]-body[bt[:,0]])
   for k in range(3):np.add.at(normal,bt[:,k],cross)
   normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-10);btr=cKDTree(body)
   for (oi,mi,node),sm,(ix,w)in zip(nodes,part['source_maps'],weight_arrays):
    p=np.array(node.attrib['p']).reshape(-1,3)
    for key in ['bs_body_breast_shape_1','bs_body_gaunt_1']:p+=np.array(targets[key].find('object')[oi].findall('mesh')[mi].attrib['p']).reshape(-1,3)-np.array(node.attrib['p']).reshape(-1,3)
    out=deform(p,ix,w,mat);dist,near=btr.query(out);signed=np.sum((out-body[near])*normal[near],axis=1);ids=np.array(sm['source_vertex_ids']);raw,mass,front,_=source[sm['mesh']];mask=(mass[ids]>.01)&(raw[ids,1]<.985);frontmask=mask&(front[ids]>.6);t=np.array(node.attrib['tri']).reshape(-1,3);e=np.concatenate([t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]]);lo=np.linalg.norm(p[e[:,0]]-p[e[:,1]],axis=1);lp=np.linalg.norm(out[e[:,0]]-out[e[:,1]],axis=1);ratio=lp[lo>.1]/lo[lo>.1];stats.append(dict(label=label,frame=frame,skirt_inside_2mm_vertex_proxy=int(sum(signed[mask]<-.2)),front_inside_2mm_vertex_proxy=int(sum(signed[frontmask]<-.2)),front_signed_min_cm=float(signed[frontmask].min()),edge_p99=float(np.quantile(ratio,.99)),edge_max=float(ratio.max()),finite=bool(np.isfinite(out).all())))
 entry=dict(case=case,files=files,strength=strength,side_width_m=width,changed_export_vertices=changed,geometry_unchanged=True,body_unchanged=True,binding_unchanged=True,all_six_bs_same_weights=True,classification=records,CPU=stats);manifest.append(entry);print('SKIRT_AB',case,changed,[(s['label'],s['frame'],s['front_inside_2mm_vertex_proxy'],round(s['edge_p99'],3),round(s['edge_max'],3))for s in stats],flush=True)
(dest/'ab-candidates.json').write_text(json.dumps(dict(family='bdy1002_00',source_registration=str(R/'ClothingParts/clothing-registration.json'),source_snapshot=fam['source_snapshot'],policy='Independent candidates only. Native MSkirt chain directions plus original height determine weights; geometry, body and bind untouched. Nearest-vertex sign proxy is not collision/visual approval.',candidates=manifest),indent=2),encoding='utf8')
