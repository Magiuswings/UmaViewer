import os
"""Fit all source apparel to complete nude canonical body; retain every source point; write real PDX+BS without Blender."""
import json,sys,os,tempfile,gc,copy,argparse,hashlib
from pathlib import Path
from collections import defaultdict
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'ClothingSources';OUT=ROOT/'ClothingParts';OUT.mkdir(exist_ok=True);CAN=Path(str(Path(os.environ.get('UMA_V7_CANONICAL','E:/UmaViewer-Exports/2026-10-09-Body-Rebuild/canonical-rest-v3'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind,globals_for
PD=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));rigfile=ROOT/'Rigs/body.mesh';rig=PD.read_meshfile(str(rigfile));coreskel=rig.find('object')[0].find('skeleton');core_names=[b.tag for b in coreskel];core_index={n:i for i,n in enumerate(core_names)};corebind=inverse_bind(coreskel);coreworld=np.linalg.inv(corebind);source_map=json.loads((ROOT/'Rigs/body-source-map.json').read_text());native=json.loads((CAN/'native-bone-transforms.json').read_text());nativeT={n:np.array(native['posed'][n])@np.linalg.inv(np.array(native['bind'][n]))for n in native['names']};profiles=np.load(CAN/'fitted-body-profiles.npz');rawprofiles=np.load(CAN/'source-skin-profiles.npz');bodyfile=next(Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'v5')).rglob('uma_0001_body_base.mesh'));body=PD.read_meshfile(str(bodyfile));bn=body.find('object')[0].find('mesh');bodyp=np.array(bn.attrib['p']).reshape(-1,3)*.01;bodybl=bodyp[:,[0,2,1]];bodyix=np.array(bn.find('skin').attrib['ix']).reshape(-1,4);bodyw=np.array(bn.find('skin').attrib['w']).reshape(-1,4);bodyn=np.array(bn.attrib['n']).reshape(-1,3)[:,[0,2,1]];tree=cKDTree(bodybl);canorder=np.array(json.loads((CAN/'pdx-vertex-order.json').read_text())['export_to_source']);baseprofiles=profiles['h1_s0_b2'][canorder];C=np.array([[-1,0,0],[0,0,-1],[0,1,0]],float);D=np.array([[1,0,0],[0,0,1],[0,1,0]],float);C4=np.eye(4);C4[:3,:3]=C;D4=np.eye(4);D4[:3,:3]=D
KEYS={'b0':'bs_body_breast_shape_1','b1':'bs_body_breast_shape_2','b3':'bs_body_breast_shape_3','b4':'bs_body_breast_shape_4','s1':'bs_body_gaunt_1','s2':'bs_body_fat_1'};PROFILE_KEYS={'b0':'h1_s0_b0','b1':'h1_s0_b1','b3':'h1_s0_b3','b4':'h1_s0_b4','s1':'h1_s1_b2','s2':'h1_s2_b2'};PARTIDS={'clothes':1,'shoes':2,'socks':3,'headwear':4};scratch=ROOT/'.temp';scratch.mkdir(exist_ok=True);tempfile.tempdir=str(scratch)
for k in ['TEMP','TMP','TMPDIR']:os.environ[k]=str(scratch)
def point(p,m):return m[:3,:3]@p+m[:3,3]
def to_engine(m):
 out=D4@m@D4;out[:3,3]*=100;return out

def normals_tangents(p,tri,uv):
 normal=np.zeros_like(p);cross=np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]])
 for j in range(3):np.add.at(normal,tri[:,j],cross)
 _,ids=np.unique(np.round(p,5),axis=0,return_inverse=True);total=np.zeros((ids.max()+1,3));np.add.at(total,ids,normal);normal=total[ids];normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12);tan=np.zeros_like(p);e1=uv[tri[:,1]]-uv[tri[:,0]];e2=uv[tri[:,2]]-uv[tri[:,0]];den=e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0];den=np.where(abs(den)<1e-10,1,den);t=((p[tri[:,1]]-p[tri[:,0]])*e2[:,1,None]-(p[tri[:,2]]-p[tri[:,0]])*e1[:,1,None])/den[:,None]
 for j in range(3):np.add.at(tan,tri[:,j],t)
 tan-=normal*np.sum(tan*normal,axis=1)[:,None];tan/=np.maximum(np.linalg.norm(tan,axis=1)[:,None],1e-12);zero=np.linalg.norm(tan,axis=1)<.1;tan[zero]=[1,0,0];return normal,np.column_stack([tan,np.ones(len(p))])
def bake_native(mat,res):
 prop=next((p for p in mat['properties']if p['name']=='_MainTex'and p.get('texture')),None)
 if not prop:return Image.new('RGBA',(4,4),(255,255,255,255)),dict(method='missing texture diagnostic white')
 im=Image.open(res/prop['texture']).convert('RGBA');area=next((p for p in mat['properties']if p['name']=='_MaskColorTex'and p.get('texture')),None);palette=mat.get('native_default_mask_colors');method='Native diffuse copied'
 if area and palette:
  a=np.asarray(Image.open(res/area['texture']).convert('RGB').resize(im.size,Image.Resampling.NEAREST),float);s=np.clip((a-128)/127,-1,1);s[abs(s)<.055]=0;weights=np.concatenate([np.maximum(s,0),np.maximum(-s,0)],axis=2);colors=[]
  for suffix in ['r1','g1','b1','r2','g2','b2']:
   h=palette['color_'+suffix].lstrip('#');colors.append(np.array([int(h[i:i+2],16)for i in (0,2,4)])/255)
  total=weights.sum(2);weights/=np.maximum(total,1)[:,:,None];mix=np.maximum(1-total,0)[:,:,None]+np.einsum('hwk,kc->hwc',weights,np.array(colors));rgba=np.asarray(im).copy();rgba[:,:,:3]=np.clip(rgba[:,:,:3]*mix,0,255).astype(np.uint8);im=Image.fromarray(rgba);method='Source signed area-mask neutral128 and native primary/secondary palette multiplication; deterministic conversion, Unity shader pixel parity not claimed'
 return im,dict(method=method,source=str(res/prop['texture']),palette_id=palette.get('id')if palette else None)
def make_skeleton(data):
 bones={b['id']:b for b in data['bones']};trans={};bound={};mapping={};sk=copy.deepcopy(coreskel);report=[]
 def t_for(bid):
  if bid in trans:return trans[bid]
  b=bones[bid];name=b['name'];pa=b.get('parent')
  if name in nativeT:trans[bid]=nativeT[name]
  elif pa:trans[bid]=t_for(pa)
  else:trans[bid]=np.diag([.991494545]*3+[1])
  return trans[bid]
 def target(name):
  if name in source_map:return source_map[name]
  if name.startswith('pfb_bdy'):return 'uma_src_body_origin'
  return None
 def visit(bid):
  if bid in mapping:return mapping[bid]
  b=bones[bid];pa=b.get('parent');parent=visit(pa)if pa else None;t=t_for(bid);B=C4@np.array(b['matrix']).reshape(4,4)@np.linalg.inv(C4);fitted=t@B;eng=to_engine(fitted);mapped=target(b['name'])
  point_matches_core=mapped in core_index and np.linalg.norm(coreworld[core_index[mapped],:3,3]-eng[:3,3])<=.001
  if point_matches_core:index=core_index[mapped];engine_name=mapped
  else:
   engine_name='uma_src_'+b['name'];used={n.tag for n in sk};suffix=1
   while engine_name in used:engine_name='uma_src_'+b['name']+'_'+str(suffix);suffix+=1
   index=len(sk);inv=np.linalg.inv(eng);node=ET.SubElement(sk,engine_name);node.attrib['ix']=[index];node.attrib['tx']=inv[:3,:].T.ravel().tolist()
   if parent is not None:node.attrib['pa']=[parent]
  mapping[bid]=index;bound[bid]=eng;report.append(dict(source_id=bid,source_name=b['name'],source_parent=pa,engine_name=engine_name,index=index,semantic_core_name=mapped,source_hierarchy_only=b.get('source_hierarchy_only',False),original_unity_point=[b['matrix'][3],b['matrix'][7],b['matrix'][11]],fitted_source_point_cm=eng[:3,3].tolist(),retained=True,core_mapping=index<len(coreskel)));return index
 for bid in bones:visit(bid)
 assert list(sk)[:len(coreskel)]and all(sk[i].attrib==coreskel[i].attrib and sk[i].tag==coreskel[i].tag for i in range(len(coreskel)));return sk,trans,mapping,report,bones

def prepare_mesh(m,rawprofile,trans,bones):
 src=np.array([[v[k]for k in 'xyz']for v in m['vertices']],float);wsrc=defaultdict(list)
 for w in m['weights']:wsrc[w['vertex']].append((w['bone'],w['weight']))
 neutral=src.copy();neutral_report=dict(source_profile=rawprofile,neutral_profile='h1_s0_b2')
 if rawprofile!='h1_s0_b2'and rawprofile in rawprofiles:
  rawtree=cKDTree(rawprofiles[rawprofile]);dist,near=rawtree.query(src,k=4);coef=1/np.maximum(dist,.003)**2;coef/=coef.sum(1)[:,None];delta=rawprofiles['h1_s0_b2']-rawprofiles[rawprofile];neutral+=np.sum(delta[near]*coef[:,:,None],axis=1);neutral_report['neutral_delta_max_m']=float(np.linalg.norm(neutral-src,axis=1).max())
 h=np.column_stack([neutral@C.T,np.ones(len(src))]);fit=np.zeros_like(src)
 for i,ws in wsrc.items():
  for bid,w in ws:fit[i]+=(trans[bid]@h[i])[:3]*w
 dist,near=tree.query(fit,k=4);coef=1/np.maximum(dist,.002)**2;coef/=coef.sum(1)[:,None];ix=np.full((len(src),4),-1,int);weight=np.zeros((len(src),4));source_names={bid:b['name']for bid,b in bones.items()}
 def core_target(bid):
  while bid:
   name=source_names[bid];target=source_map.get(name)
   if target in core_index and core_index[target]<134:return core_index[target]
   bid=bones[bid].get('parent')
  return core_index['body_root']
 skirt=np.zeros(len(src),float)
 for i,ws in wsrc.items():
  values=defaultdict(float);is_skirt=any('Skirt'in source_names[bid]and w>.01 for bid,w in ws);skirt[i]=is_skirt
  if is_skirt:
   z=fit[i,2];rootweight=np.clip((z-.64)/.20,0,1);kneeweight=np.clip((.53-z)/.22,0,1)*(1-rootweight);thighweight=1-rootweight-kneeweight;left=.5+.5*np.tanh(fit[i,0]/.14);candidates={core_index['body_root']:rootweight,core_index['bn_l_hip']:thighweight*left,core_index['bn_r_hip']:thighweight*(1-left),core_index['bn_l_knee']:kneeweight*left,core_index['bn_r_knee']:kneeweight*(1-left)};values.update(candidates)
  else:
   # Native ancestor skinning protects loose coat/cape pieces from nearest-hand capture.
   aux=sum(w for bid,w in ws if source_names[bid].startswith('Sp_'))
   if aux>.4:
    for bid,w in ws:values[core_target(bid)]+=w
   else:
    for bv,c in zip(near[i],coef[i]):
     for bi,bw in zip(bodyix[bv],bodyw[bv]):
      if bw>0:values[int(bi)]+=float(c*bw)
  best=sorted([(a,b)for a,b in values.items()if b>1e-9],key=lambda x:-x[1])[:4];total=sum(w for bid,w in best)
  for j,(bid,w)in enumerate(best):ix[i,j]=bid;weight[i,j]=w/total
 # Source foot transforms receive a small flat-sole transport, not a global body shrink.
 foot=np.array([sum(w for bid,w in ws if any(source_names[bid].startswith(k)for k in ['Ankle','Toe']))for ws in [wsrc[i]for i in range(len(src))]])
 close=(dist[:,0]<.035);signed=np.sum((fit-bodybl[near[:,0]])*bodyn[near[:,0]],axis=1);push=np.clip(.0035-signed,0,.018);fit[close]+=bodyn[near[close,0]]*push[close,None]
 shape={'base':fit}
 for tag,key in PROFILE_KEYS.items():shape[tag]=fit+np.sum((profiles[key][canorder]-baseprofiles)[near]*coef[:,:,None],axis=1)
 return shape,ix,weight,neutral_report,skirt

def make_part(data,archive,category,pid,sk,prepared,dir,stem,textures):
 template=copy.deepcopy(rig);objects=template.find('object');objects.clear();settings=[];sourceids=[];report=[];part_node_data=[]
 for mi,m in enumerate(data['meshes']):
  tri=archive[f'm{mi}_tri'];part=archive[f'm{mi}_part'];matids=archive[f'm{mi}_material'];uv=archive[f'm{mi}_uv'];selected=np.flatnonzero(part==pid)
  if not len(selected):continue
  obj=ET.SubElement(objects,stem+f'_m{mi:02d}Shape');obj.append(copy.deepcopy(sk))
  for slot,mat in enumerate(np.unique(matids[selected])):
   fi=selected[matids[selected]==mat];verts=np.unique(tri[fi]);local=np.full(len(m['vertices']),-1,int);local[verts]=np.arange(len(verts));lt=local[tri[fi]];node=ET.SubElement(obj,'mesh');node.attrib['tri']=lt.ravel().tolist();node.attrib['u0']=np.column_stack([uv[verts,0],1-uv[verts,1]]).ravel().tolist();skin=ET.SubElement(node,'skin');skin.attrib['bones']=[4];skin.attrib['ix']=prepared[mi][1][verts].ravel().tolist();skin.attrib['w']=prepared[mi][2][verts].ravel().tolist();material=ET.SubElement(node,'material');tx=textures[int(mat)];material.attrib.update(shader=['portrait_attachment'],diff=[Path(tx['diffuse']).name],n=[Path(tx['normal']).name],spec=[Path(tx['properties']).name]);ET.SubElement(node,'aabb');part_node_data.append((node,mi,verts,lt));settings.append(dict(shape=obj.tag,index=slot,shader='portrait_attachment',diffuse=tx['diffuse'],normal=tx['normal'],properties=tx['properties'],source_material=int(mat)));sourceids.append(dict(mesh=mi,material=int(mat),source_vertex_ids=verts.tolist(),source_triangle_indices=fi.tolist()));report.append(dict(mesh=mi,material=int(mat),vertices=len(verts),triangles=len(fi)))
 if not part_node_data:return None
 variants={};checks=[]
 for tag in ['base',*KEYS]:
  for node,mi,verts,tri in part_node_data:
   p=prepared[mi][0][tag][verts]@D.T*100;uv=np.array(node.attrib['u0']).reshape(-1,2);n,tan=normals_tangents(p,tri,uv);node.attrib['p']=p.ravel().tolist();node.attrib['n']=n.ravel().tolist();node.attrib['ta']=tan.ravel().tolist();node.find('aabb').attrib.update(min=p.min(0).tolist(),max=p.max(0).tolist());center=(p.min(0)+p.max(0))/2;node.attrib['boundingsphere']=center.tolist()+[float(np.linalg.norm(p-center,axis=1).max())]
  file=dir/(stem+'_'+tag+'.mesh');PD.write_meshfile(str(file),template);read=PD.read_meshfile(str(file));count=0;tri_count=0
  for obj in read.find('object'):
   assert np.array_equal(inverse_bind(obj.find('skeleton'))[:len(coreskel)],corebind);assert len(obj.find('skeleton'))==len(sk)
   for node in obj.findall('mesh'):
    xyz=np.array(node.attrib['p']).reshape(-1,3);w=np.array(node.find('skin').attrib['w']).reshape(-1,4);assert np.isfinite(xyz).all()and np.isfinite(w).all();assert abs(w.sum(1)-1).max()<2e-7;count+=len(xyz);tri_count+=len(node.attrib['tri'])//3
  variants[tag]=str(file);checks.append(dict(variant=tag,vertices=count,triangles=tri_count,source_points=len(sk),core_bind_exact=True,weights_normalized=True,pdx_readback=True))
 return dict(mesh_name=stem+'_mesh',entity=stem+'_entity',base_mesh=variants['base'],shape_targets={key:variants[tag]for tag,key in KEYS.items()},meshsettings=settings,vertices=sum(x['vertices']for x in report),triangles=sum(x['triangles']for x in report),source_maps=sourceids,validation=checks,actor_variants=[])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--family',action='append');a=ap.parse_args();index=json.loads((SRC/'cloth-source-index.json').read_text(encoding='utf8'));registrationfile=OUT/'clothing-registration.json';registration=json.loads(registrationfile.read_text())if registrationfile.exists()else dict(version=1,families=[],shape_contract=KEYS,body_rig=str(rigfile),body_clothed_fixed=False,shared_asset_once=True)
 for record in index['records']:
  if a.family and record['family']not in a.family:continue
  source=next(p for p in record['selected_prefabs']if p['prefab']==record['basis_prefab']);data=json.loads(Path(source['parsed_path']).read_text(encoding='utf8'));archive=np.load(SRC/'partitions'/record['family']/'source-parts.npz');owner=record['output_character_directory'];diff=record['family'][3:];diff=diff if record['generic']else diff.split('_',1)[1];dir=OUT/owner/record['family'];dir.mkdir(parents=True,exist_ok=True);sk,trans,mapping,points,bones=make_skeleton(data);prof=source.get('profile');actor=next(x for x in index['characters']if x['id']==record['characters'][0]);rawprofile=f"h{prof['height']}_s{prof['shape']}_b{prof['bust']}"if prof else f"h{actor['height']}_s{actor['shape']}_b{actor['bust']}";prepared={};neutral_reports=[]
  for mi,m in enumerate(data['meshes']):prepared[mi]=prepare_mesh(m,rawprofile,trans,bones);neutral_reports.append(prepared[mi][3])
  textures={}
  for mat,material in enumerate(data['materials']):
   stem=f'uma_{owner}_clothing_{diff}_m{mat:02d}';im,note=bake_native(material,Path(source['parsed_path']).parent/'resources');diffuse=dir/(stem+'_diffuse.dds');im.save(diffuse,pixel_format='DXT5');normal=dir/(stem+'_normal.dds');Image.new('RGBA',im.size,(0,128,0,128)).save(normal,pixel_format='DXT5');props=dir/(stem+'_properties.dds');Image.new('RGBA',im.size,(30,180,0,210)).save(props,pixel_format='DXT5');textures[mat]=dict(diffuse=str(diffuse),normal=str(normal),properties=str(props),source_material=material,note=note)
  parts={}
  for category,pid in PARTIDS.items():
   element='clothing'if category=='clothes'else category;stem=f'uma_{owner}_{element}_{diff}';part=make_part(data,archive,category,pid,sk,prepared,dir,stem,textures)
   if part:parts[category]=part
  sourcepointfile=dir/'native-source-points.json';sourcepointfile.write_text(json.dumps(dict(source=source['parsed_path'],source_bones=len(data['bones']),total_bones=len(sk),core_body_bones=len(coreskel),points=points,missing_source_points=0,source_weights=[dict(mesh=i,name=m['name'],weights=m['weights'])for i,m in enumerate(data['meshes'])],neutralization=neutral_reports,policy='All source bones and hierarchy points retained; runtime weights use stock core134. No shared body shrink/no fixed clothed.'),indent=2),encoding='utf8');sourcepart=json.loads((SRC/'partitions'/record['family']/'source-partition.json').read_text());output=dict(family=record['family'],key=record['key'],characters=record['characters'],directory=str(dir),asset_path=str(dir/f'uma_{owner}_wardrobe_{diff}.asset'),shared_asset_once=record['generic'],parts=parts,source_snapshot=source['parsed_path'],source_points=str(sourcepointfile),source_partition=str(SRC/'partitions'/record['family']/'source-partition.json'),source_counts=sourcepart['total_counts'],headwear_source=str(SRC/'partitions'/record['family']/'source-parts.npz')if sourcepart['total_counts'].get('headwear')else None,bones=len(sk),no_body_mesh_changes=True,body_clothed_fixed=False,material_provenance=textures,runtime_game_verified=False,classification_reviews=sourcepart['requires_review'])
  registration['families']=[r for r in registration['families']if r['family']!=record['family']]+[output];registration['families'].sort(key=lambda r:r['family']);temp=registrationfile.with_suffix('.tmp');temp.write_text(json.dumps(registration,indent=2),encoding='utf8');temp.replace(registrationfile);print('WARDROBE_PDX',record['family'],'parts',[(k,p['vertices'],p['triangles'])for k,p in parts.items()],'bones',len(sk),flush=True);del data,prepared,archive;gc.collect()
 print('CLOTHING_REGISTRATION',len(registration['families']),str(registrationfile),flush=True)
if __name__=='__main__':main()
