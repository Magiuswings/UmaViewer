import json,sys,copy,hashlib,os,tempfile
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));OUT=ROOT/'clothing-parts';CAN=Path(os.environ.get("UMA_V6_CANONICAL", "E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3"));REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"));OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
import build_ck3_mod as b
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pdx=b.parser_only(Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh")))
d=json.loads((ROOT/'parsed/body.json').read_text());m=d['meshes'][0];bones={x['id']:x for x in d['bones']};byname={x['name']:x for x in d['bones']};p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);uv=np.array([[v[k]for k in 'xy']for v in m['uvs'][0]['values']]);tri=np.array(m['faces'][0]['triangles']).reshape(-1,3)
tex=Image.open(ROOT/'parsed/resources/textures/tex_bdy1001_00_diff__3e2e906bee.png').convert('RGBA');pixels=np.asarray(tex);palette=np.array([252,228,204]);samples=np.concatenate([uv[tri],(uv[tri[:,0]]+uv[tri[:,1]])[:,None]/2,(uv[tri[:,1]]+uv[tri[:,2]])[:,None]/2,(uv[tri[:,2]]+uv[tri[:,0]])[:,None]/2,uv[tri].mean(1)[:,None]],axis=1);samples%=1
colors=pixels[np.minimum((1-samples[:,:,1])*tex.height,tex.height-1).astype(int),np.minimum(samples[:,:,0]*tex.width,tex.width-1).astype(int),:3].astype(float);votes=(np.linalg.norm(colors-palette,axis=-1)<=42).sum(1);skin=votes>=5
# Use source garment chains as affirmative cloth evidence even if a gold trim resembles skin.
sourceweights=defaultdict(list)
for w in m['weights']:sourceweights[w['vertex']].append((bones[w['bone']]['name'],w['weight']))
aux=np.array([sum(w for n,w in sourceweights[i]if n.startswith('Sp_'))for i in range(len(p))]);skin&=aux[tri].mean(1)<.15
# Head/neck tiny anatomical stub does not belong in accessory.
headmass=np.array([sum(w for n,w in sourceweights[i]if n=='Head')for i in range(len(p))]);skin|=(headmass[tri].mean(1)>.5)&(p[tri][:,:,1].mean(1)>1.30)
skin &= p[tri][:,:,1].mean(1)>.65
keep=~skin;faces=tri[keep];used=np.unique(faces);remap=np.full(len(p),-1,int);remap[used]=np.arange(len(used));faces=remap[faces]
C=np.array([[-1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]],float);N=json.loads((CAN/'native-bone-transforms.json').read_text());B={n:C@np.array(x['matrix']).reshape(4,4)@np.linalg.inv(C)for n,x in byname.items()};T={}
def transport(n):
 if n in T:return T[n]
 if n in N['posed']:T[n]=np.array(N['posed'][n])@np.linalg.inv(np.array(N['bind'][n]))
 else:
  pa=bones.get(byname[n]['parent']);T[n]=transport(pa['name'])if pa else np.diag([.991494545]*3+[1])
 return T[n]
for n in B:transport(n)
h=np.column_stack([p@C[:3,:3].T,np.ones(len(p))]);fit=np.zeros((len(p),3))
for i,ws in sourceweights.items():
 for n,w in ws:fit[i]+=(T[n]@h[i])[:3]*w
# Native fitted soles share source-body foot shear; apply same affine coefficients.
fitreport=json.loads((CAN/'rest-pose-fitting.json').read_text())
for corr in fitreport['foot_corrections']:
 side=corr['side'];ids=np.array([sum(w for n,w in sourceweights[i]if n.startswith(('Ankle','Toe'))and n.endswith(side))for i in range(len(p))]);slope=corr['heel_pitch_slope'];body=np.load(CAN/'fitted-body-profiles.npz')['h1_s0_b2'];source=np.load(CAN/'source-skin-profiles.npz')['h1_s0_b2'];# source actual fitted shifts only millimeters; keep source shoes ground minimum separately
 foot=ids>.95
 if foot.any():fit[foot,2]-=fit[foot,2].min()
stockfile=next((ROOT/'v5').rglob('uma_0001_body_base.mesh'));stock=pdx.read_meshfile(str(stockfile));obj=stock.find('object')[0];sk=obj.find('skeleton');sn=obj.find('mesh');names=[x.tag for x in sk];lookup={n:i for i,n in enumerate(names)};bodyp=np.array(sn.attrib['p']).reshape(-1,3)[:,[0,2,1]]*.01;bodyix=np.array(sn.find('skin').attrib['ix']).reshape(-1,4);bodyw=np.array(sn.find('skin').attrib['w']).reshape(-1,4);tree=cKDTree(bodyp)
# Semantic assignment preserves source limb chains. Extra skirt bones are spatially transferred to the canonical skin.
semantic={'Position':'ground_joint','Hip':'body_root','Waist':'bn_sp_lumbar','Spine':'bn_sp_thoracic','Chest':'bn_sp_thoracic','Neck':'bn_sp_cervical','Head':'bn_sp_cervical'}
for side in ['L','R']:
 s=side.lower()
 for old,new in [('Shoulder','clavicle'),('Arm','shoulder'),('Elbow','elbow'),('ArmRoll','forearm'),('Wrist','wrist'),('ShoulderRoll','deltoid'),('Hand_Attach','prop'),('Thigh','hip'),('Knee','knee'),('Ankle','ankle'),('Toe','ftBall')]:semantic[f'{old}_{side}']=f'bn_{s}_{new}'
 for old,new in [('Thumb','thumb'),('Index','index'),('Middle','mid'),('Ring','ring'),('Pinky','pinky')]:
  for j in range(1,4):semantic[f'{old}_{j:02}_{side}']=f'bn_{s}_fi_{new}{j}'
def target(n):
 if n in semantic:return semantic[n]
 pa=bones.get(byname[n]['parent']);return target(pa['name'])if pa else 'body_root'
# Smooth fixed proximity map shared by clothing endpoints.
dist,near=tree.query(fit[used],k=4);coeff=1/np.maximum(dist,.002)**2;coeff/=coeff.sum(1)[:,None];transfer=[];ix=np.full((len(used),4),-1,int);weights=np.zeros((len(used),4));skirtmask=[]
for j,i in enumerate(used):
 ws=defaultdict(float);skirt=any('Skirt' in n and w>.01 for n,w in sourceweights[i]);skirtmask.append(skirt)
 if True:
  for bv,c in zip(near[j],coeff[j]):
   for bi,bw in zip(bodyix[bv],bodyw[bv]):
    if bw>0:ws[int(bi)]+=c*bw
  transfer.append(j)
 else:
  for n,w in sourceweights[i]:ws[lookup[target(n)]]+=w
 if skirt:
  t=np.clip((.84-fit[i,2])/.21,0,1);left=.5+.5*np.tanh(fit[i,0]/.14);ws={lookup['body_root']:1-t,lookup['bn_l_hip']:t*left,lookup['bn_r_hip']:t*(1-left)}
 top=sorted(ws.items(),key=lambda z:-z[1])[:4];total=sum(w for n,w in top)
 for slot,(n,w)in enumerate(top):ix[j,slot]=n;weights[j,slot]=w/total
# Move fitted cloth only out of reconstructed skin where it intersects at rest; preserve native cloth silhouette elsewhere.
cp=fit[used].copy();normals=np.asarray(sn.attrib['n']).reshape(-1,3)[:,[0,2,1]];normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12);nn=near[:,0];signed=np.sum((cp-bodyp[nn])*normals[nn],axis=1);initialsigned=signed.copy();close=(dist[:,0]<.06)&(signed<.004);push=np.clip(.004-signed,0,.04);cp[close]+=normals[nn[close]]*push[close,None]
footmask=np.array([sum(w for n,w in sourceweights[i]if n.startswith(('Ankle','Toe'))and n.endswith(('L','R')))>.5 for i in used]);cp[footmask,2]-=.005+.027*np.clip((.035-cp[footmask,1])/.14,0,1)
cp[footmask,2]=.085+(cp[footmask,2]-.085)*1.35;cp[footmask,1]*=1.12
for side in [-1,1]:
 sel=footmask & (cp[:,0]*side>0);center=.128*side;cp[sel,0]=center+(cp[sel,0]-center)*1.10
# Clothing keys carry same canonical body deltas via fixed nearest skin correspondence.
order=np.array(json.loads((CAN/'pdx-vertex-order.json').read_text())['export_to_source']);profiles=np.load(CAN/'fitted-body-profiles.npz');base=profiles['h1_s0_b2'][order];shapes={}
for tag,key in [('b0','h1_s0_b0'),('b1','h1_s0_b1'),('b3','h1_s0_b3'),('b4','h1_s0_b4'),('s1','h1_s1_b2'),('s2','h1_s2_b2')]:
 delta=profiles[key][order]-base;shapes[tag]=cp+np.sum(delta[near]*coeff[:,:,None],axis=1)
np.savez_compressed(OUT/'garment-prepared.npz',p=cp,faces=faces,uv=uv[used],ix=ix,w=weights,source_ids=used,skirt=np.array(skirtmask),near=near,coeff=coeff,**shapes)
tex.save(OUT/'uma_1001_clothing_00_diffuse.dds');Image.new('RGBA',tex.size,(0,128,0,128)).save(OUT/'uma_1001_clothing_00_normal.dds');Image.new('RGBA',tex.size,(30,180,0,210)).save(OUT/'uma_1001_clothing_00_properties.dds')
report=dict(source=str(d['source']),source_mesh_vertices=len(p),source_triangles=len(tri),clothing_vertices=len(used),clothing_triangles=len(faces),removed_skin_triangles=int(skin.sum()),palette=palette.tolist(),vote_counts=dict(Counter(votes.tolist())),classification='Source face skin palette seven UV samples; >=5 votes; source garment-bone safeguard; anatomical Head stub removed; lower-leg palette matches retained after source full-suit rendering',source_bones=len(B),output_bones=len(sk),semantic_mapping={n:target(n)for n in B},weight_transfer_vertices=len(transfer),skirt_vertices=int(sum(skirtmask)),weight_sum_max_error=float(abs(weights.sum(1)-1).max()),maximum_weight=float(weights.max()),rest_adjusted_vertices=int(close.sum()),rest_push_max_m=float(push[close].max())if close.any()else 0,stock_body=str(stockfile),source_material=d['materials'][0],shape_keys=list(shapes),texture_note='Native diffuse copied as DDS; flat CK3 packed normal; conservative rough nonmetal properties because source Unity masks are not CK3 channels',animation_method='Runtime body shared skeleton; no rigid clothing root')
(OUT/'garment-preparation.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items()if k not in ['source_material','semantic_mapping']},indent=2))
