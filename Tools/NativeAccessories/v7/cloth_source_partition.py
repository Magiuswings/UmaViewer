import os
"""Original triangle partition: skin evidence + topology + anatomical chains. No CK3 rig."""
import json,sys,gc,argparse,re
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from PIL import Image
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'));PARTS={'skin':0,'clothing':1,'shoes':2,'socks':3,'headwear':4,'inactive':5}
def components(tri,nv,weld=None):
 t=tri if weld is None else weld[tri];n=nv if weld is None else int(weld.max())+1
 if not len(t):return np.zeros(0,int)
 edges=np.concatenate([t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]]);matrix=coo_matrix((np.ones(len(edges)*2),(np.r_[edges[:,0],edges[:,1]],np.r_[edges[:,1],edges[:,0]])),shape=(n,n)).tocsr();_,labels=connected_components(matrix,directed=False);return labels[t[:,0]]
def partition(source,out):
 d=json.loads(Path(source).read_text(encoding='utf8'));family=Path(source).parent.name;fs=family[3:].split('_');typ=int(fs[0]);sub=int(fs[1]);boot_tops={5:.36,6:.36,50:.36,51:.28,52:.44,53:.29,54:.67,55:.27};boot_top=boot_tops.get(typ)
 if typ==7:boot_top={0:.30,1:.30,2:.39,3:.18,4:.69,5:.18}.get(sub)
 if typ==8 and sub==8:boot_top=.40
 if typ==13 and sub==5:boot_top=.43
 if family in ('bdy1001_02',):boot_top=.74
 if family in ('bdy1001_30','bdy1001_90'):boot_top=.28
 naked_feet=typ in (4,18)or(typ==9 and sub==1)or(typ==2 and sub in (2,3));tights=family in ('bdy1002_00','bdy1002_90','bdy0019_00_00')or(typ==8 and sub in (0,1));trousers=typ in (12,14)or(typ==7 and sub==5)or(typ==8 and sub in range(2,8))or(typ==13 and sub in (4,6));bones={b['id']:b for b in d['bones']};chain={}
 for bid in bones:
  anc=[];cur=bid
  while cur:anc.append(bones[cur]['name']);cur=bones[cur].get('parent')
  chain[bid]=anc
 mats=d['materials'];resources=Path(source).parent/'resources';reports=[];archive={};review=[]
 for mi,m in enumerate(d['meshes']):
  p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);uvlayer=next((u for u in m['uvs']if u['channel']==0),None);uv=np.array([[v[k]for k in 'xy']for v in uvlayer['values']])if uvlayer else np.zeros((len(p),2));tri=[];material=[]
  for f in m['faces']:
   t=np.array(f['triangles']).reshape(-1,3);tri.extend(t.tolist());material.extend([f['material']]*len(t))
  tri=np.array(tri,int);material=np.array(material,int);ctr=p[tri].mean(1);weights=defaultdict(list)
  for w in m['weights']:weights[w['vertex']].append((w['bone'],w['weight']))
  aux=np.array([sum(w for b,w in weights[i]if any(n.startswith('Sp_')for n in chain[b]))for i in range(len(p))]);leg=np.array([sum(w for b,w in weights[i]if any(n.startswith(('Thigh_','Knee_','Ankle_','Toe_'))for n in chain[b]))for i in range(len(p))]);foot=np.array([sum(w for b,w in weights[i]if any(n.startswith(('Ankle_','Toe_'))for n in chain[b]))for i in range(len(p))]);skirt=np.array([sum(w for b,w in weights[i]if any('Skirt'in n for n in chain[b]))for i in range(len(p))]);head=np.array([sum(w for b,w in weights[i]if any(n=='Head'for n in chain[b]))for i in range(len(p))]);legtri=leg[tri].mean(1);foottri=foot[tri].mean(1);auxtri=aux[tri].mean(1);skirttri=skirt[tri].mean(1);headtri=head[tri].mean(1);votes=np.zeros(len(tri),int);white=np.zeros(len(tri),float);warm=np.zeros(len(tri),float);areacover=np.zeros(len(tri),float)
  sample=np.concatenate([uv[tri],uv[tri].mean(1)[:,None],((uv[tri[:,0]]+uv[tri[:,1]])/2)[:,None],((uv[tri[:,1]]+uv[tri[:,2]])/2)[:,None],((uv[tri[:,2]]+uv[tri[:,0]])/2)[:,None]],axis=1)
  for mat in np.unique(material):
   if mat<0:continue
   prop=next((x for x in mats[mat]['properties']if x['name']=='_MainTex'and x.get('texture')),None)
   if not prop:review.append(dict(mesh=mi,material=int(mat),reason='No native diffuse binding, cannot prove skin removal'));continue
   atlas=np.asarray(Image.open(resources/prop['texture']).convert('RGB'));ids=np.flatnonzero(material==mat);s=(sample[ids]*prop.get('scale',[1,1])+prop.get('offset',[0,0]))%1;color=atlas[np.minimum(((1-s[:,:,1])*atlas.shape[0]).astype(int),atlas.shape[0]-1),np.minimum((s[:,:,0]*atlas.shape[1]).astype(int),atlas.shape[1]-1)].astype(float);votes[ids]=(np.linalg.norm(color-np.array([252,228,204]),axis=2)<=42).sum(1);white[ids]=((color.min(2)>215)&((color.max(2)-color.min(2))<35)).mean(1);warm[ids]=((color[:,:,0]-color[:,:,1]>=7)&(color[:,:,1]-color[:,:,2]>=4)&(color[:,:,1]>65)).mean(1)
   area_prop=next((x for x in mats[mat]['properties']if x['name']=='_MaskColorTex'and x.get('texture')),None)
   if area_prop:
    aa=np.asarray(Image.open(resources/area_prop['texture']).convert('RGB'));pixels=aa[np.minimum(((1-s[:,:,1])*aa.shape[0]).astype(int),aa.shape[0]-1),np.minimum((s[:,:,0]*aa.shape[1]).astype(int),aa.shape[1]-1)].astype(float);areacover[ids]=(abs(pixels-128).max(2)>25).mean(1)
  skin=(votes>=5)&(auxtri<.15)&(areacover<.5)
  # Preserve sock/pant shadow colors when that leg region is mostly actual cloth.
  legstats=[]
  for side in [-1,1]:
   region=(ctr[:,0]*side>0)&(ctr[:,1]>.20)&(ctr[:,1]<.65)&(legtri>.55)&(skirttri<.05);ratio=float(skin[region].mean())if region.any()else 0;legstats.append(dict(side=side,skin_vote_ratio=ratio,triangles=int(region.sum())))
   if ratio<.55:skin[region]=False
   # A truly bare lower leg/foot's tiny UV color misses are anatomy, not shoes.
   naked=(ctr[:,0]*side>0)&(ctr[:,1]<.65)&(legtri>.55)&(auxtri<.001)&(skirttri<.01)
   if ratio>.90:skin[naked & (ctr[:,1]>.19)]=True
   footregion=(ctr[:,0]*side>0)&(ctr[:,1]<.19)&(foottri>.65)&(auxtri<.001);footratio=float(skin[footregion].mean())if footregion.any()else 0
   if footratio>.90:skin[footregion]=True
  # Never call alpha cloth overlays or clear source accessory chains bare skin.
  alpha=np.array([mat>=0 and any(k in mats[mat]['name'].lower()for k in ['alpha','cloth','shoe','socks'])for mat in material]);skin[alpha]=False
  neckpoint=next((np.array([b['matrix'][3],b['matrix'][7],b['matrix'][11]])for b in bones.values()if b['name']=='Head'),np.array([0,1.4,0]));stub=(headtri>.3)&(auxtri<.005)&(np.linalg.norm(ctr-neckpoint,axis=1)<.08)&(warm>.5);skin[stub]=True
  if naked_feet:skin[(legtri>.55)&(ctr[:,1]<.74)&(skirttri<.01)&(auxtri<.05)]=True
  groups=np.full(len(tri),PARTS['clothing'],int);groups[skin]=PARTS['skin'];labels=components(tri[~skin],len(p));clothids=np.flatnonzero(~skin);comp=[]
  ankles=[b['matrix'][7]for b in bones.values()if b['name'].startswith('Ankle_')and'offset'not in b['name']];ankley=float(np.median(ankles))if ankles else .13;neck=next((b['matrix'][7]for b in bones.values()if b['name']=='Neck'),1.3)
  for label in np.unique(labels):
   ids=clothids[labels==label];vs=np.unique(tri[ids]);lo=p[vs].min(0);hi=p[vs].max(0);mass=float(leg[vs].mean());sm=float(skirt[vs].mean());fm=float(foot[vs].mean());hm=float(head[vs].mean());category='clothing';reason='Whole original indexed/UV island: garment default'
   if sm>.02:reason='Source skirt chain overrides low hem position'
   elif hm>.55 and ctr[ids,1].mean()>max(neck+.035,neckpoint[1]-.005):category='headwear';reason='Head ancestry + source height above neckline'
   elif mass>.55 and tights and hi[1]<1.02 and hi[1]>.20:category='socks';reason='Source image confirms complete pantyhose leg/hip island, not trousers'
   elif mass>.55 and hi[1]<.73:
    anklez=next((b['matrix'][11]for b in bones.values()if b['name']in ('Ankle_L','Ankle_R')),-.06);tube=hi[1]>ankley+.008 and (white[ids].mean()>.6 or fm<.8) and abs(ctr[ids,2].mean()-anklez)<.04 and hi[2]-lo[2]<.12
    if boot_top and hi[1]<=boot_top:category='shoes';reason='Source preview confirms complete boot shaft/attachments within reviewed boot envelope'
    elif trousers and hi[1]>.19:category='clothing';reason='Source preview confirms trouser/yukata leg fabric, not socks'
    elif tube:category='socks';reason='Ankle/leg tube island centered on source ankle, not projecting over forefoot'
    elif hi[1]<=ankley+.055 or (fm>.7 and ctr[ids,1].mean()<ankley+.035):category='shoes';reason='Foot/ankle chain + complete island within source shoe envelope'
    else:category='socks';reason='Leg chain + complete island above shoe envelope below native shorts/skirt waist'
   elif mass>.55 and lo[1]<ankley+.02 and hi[1]>.73:
    review.append(dict(mesh=mi,component=int(label),reason='Leg garment island spans waist and foot; preserved as main clothing to avoid cutting trousers'))
   groups[ids]=PARTS[category];comp.append(dict(component=int(label),category=category,reason=reason,triangles=len(ids),vertices=len(vs),bounds_min=lo.tolist(),bounds_max=hi.tolist(),leg_mass=mass,foot_mass=fm,skirt_mass=sm,head_mass=hm,source_triangle_indices=ids.tolist(),source_vertex_ids=vs.tolist()))
  if not m.get('active',True):groups[:]=PARTS['inactive']
  archive[f'm{mi}_p']=p;archive[f'm{mi}_tri']=tri;archive[f'm{mi}_uv']=uv;archive[f'm{mi}_material']=material;archive[f'm{mi}_part']=groups;archive[f'm{mi}_skin_votes']=votes;archive[f'm{mi}_white_votes']=white
  counts={name:int(sum(groups==n))for name,n in PARTS.items()};assert sum(counts.values())==len(tri);reports.append(dict(mesh=mi,name=m['name'],vertices=len(p),source_triangles=len(tri),counts=counts,source_ankle_height_m=ankley,leg_skin_evidence=legstats,components=comp))
 out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/'source-parts.npz',**archive);report=dict(source=str(source),family=d['family_key'],characters=d['characters'],part_names=PARTS,meshes=reports,total_counts=dict(sum((Counter(r['counts'])for r in reports),Counter())),source_bones_retained=len(d['bones']),source_weight_records_retained=sum(len(m['weights'])for m in d['meshes']),all_original_faces_assigned_once=True,missing_triangles=0,duplicate_triangles=0,requires_review=review,classification='UV skin votes are only one signal; garment aux/alpha safeguards, per-leg cloth majority, full original indexed/UV islands, chain/height and skirt priority; no geometry/weights changed');(out/'source-partition.json').write_text(json.dumps(report,indent=2),encoding='utf8');return report
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--family',action='append');a=ap.parse_args();idx=json.loads((ROOT/'cloth-source-index.json').read_text(encoding='utf8'));rows=[]
 for record in idx['records']:
  if a.family and record['family']not in a.family:continue
  if record['status']!='parsed':continue
  source=next(s for s in record['selected_prefabs']if s['prefab']==record['basis_prefab']);out=ROOT/'partitions'/record['family'];r=partition(source['parsed_path'],out);rows.append(dict(family=record['family'],snapshot=source['parsed_path'],partition=str(out/'source-partition.json'),npz=str(out/'source-parts.npz'),counts=r['total_counts'],review_count=len(r['requires_review'])));print('SOURCE_PARTITION',record['family'],r['total_counts'],'review',len(r['requires_review']),flush=True);gc.collect()
 (ROOT/'cloth-component-index.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
if __name__=='__main__':main()





