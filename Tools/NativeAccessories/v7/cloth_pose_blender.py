import os
"""Actual complete nude body + current clothes under unchanged stock idle/throne, BVH and front/side images."""
import sys,json,copy
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')];from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());bodydir=next(Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'v5')).rglob('uma_0001_body_base.mesh')).parent;bodytree=pd.read_meshfile(str(bodydir/'uma_0001_body_base.mesh'));bn=bodytree.find('object')[0].find('mesh');bp=np.array(bn.attrib['p']).reshape(-1,3);bt=np.array(bn.attrib['tri']).reshape(-1,3);bix=np.array(bn.find('skin').attrib['ix']).reshape(-1,4);bw=np.array(bn.find('skin').attrib['w']).reshape(-1,4);bbody=np.array(pd.read_meshfile(str(bodydir/'uma_0001_body_b0.mesh')).find('object')[0].find('mesh').attrib['p']).reshape(-1,3);sbody=np.array(pd.read_meshfile(str(bodydir/'uma_0001_body_s1.mesh')).find('object')[0].find('mesh').attrib['p']).reshape(-1,3);folder=Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body'));reports=[];skinmat=None

def deform(points,ix,w,mat):
 hp=np.column_stack([points,np.ones(len(points))]);out=np.zeros_like(points)
 for j in range(4):out+=np.einsum('nij,nj->ni',mat[np.maximum(ix[:,j],0)],hp)[:,:3]*w[:,j,None]
 return out

def material(path):
 name=Path(path).stem
 if name in bpy.data.materials:return bpy.data.materials[name]
 mat=bpy.data.materials.new(name);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.8;node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(path,check_existing=True);mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color']);mat.node_tree.links.new(node.outputs['Alpha'],bs.inputs['Alpha']);return mat

def drawgeom(name,p,t,uv,mat,col,row):
 xyz=p[:,[0,2,1]]*.01
 if col:xyz=xyz[:,[1,0,2]];xyz[:,0]*=-1
 xyz[:,0]+=col*2;xyz[:,2]-=row*1.8
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(xyz.tolist(),[],t[:,::-1].tolist());mesh.update();obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);mesh.materials.append(mat)
 for poly in mesh.polygons:poly.use_smooth=True
 if uv is not None:
  layer=mesh.uv_layers.new(name='UV0')
  for loop in mesh.loops:layer.data[loop.index].uv=(uv[loop.vertex_index,0],1-uv[loop.vertex_index,1])
 return obj

for familyname,actor in [('bdy1001_00',1001),('bdy1002_00',1002),('bdy0020_00_00',1001),('bdy0013_01_00',1001)]:
 family=next(x for x in reg['families']if x['family']==familyname);bpy.ops.wm.read_factory_settings(use_empty=True);skinmat=bpy.data.materials.new('Complete Nude Body');skinmat.diffuse_color=(.87,.66,.49,1);bodyprofile=bp if actor==1001 else bp+(bbody-bp)+(sbody-bp);loaded={};rigsk=None
 for category,part in family['parts'].items():
  if category=='headwear':continue
  tree=pd.read_meshfile(part['base_mesh']);rigsk=tree.find('object')[0].find('skeleton');nodes=[]
  targets={k:pd.read_meshfile(f)for k,f in part['shape_targets'].items()}
  for oi,obj in enumerate(tree.find('object')):
   for mi,node in enumerate(obj.findall('mesh')):
    p=np.array(node.attrib['p']).reshape(-1,3)
    if actor==1002:
     for key in ['bs_body_breast_shape_1','bs_body_gaunt_1']:
      target=targets[key].find('object')[oi].findall('mesh')[mi];p+=np.array(target.attrib['p']).reshape(-1,3)-np.array(node.attrib['p']).reshape(-1,3)
    nodes.append((p,np.array(node.attrib['tri']).reshape(-1,3),np.array(node.attrib['u0']).reshape(-1,2),np.array(node.find('skin').attrib['ix']).reshape(-1,4),np.array(node.find('skin').attrib['w']).reshape(-1,4),Path(part['base_mesh']).parent/node.find('material').attrib['diff'][0]))
  loaded[category]=nodes
 binds=inverse_bind(rigsk);images=[];case=[]
 for row,(label,clip)in enumerate([('neutral',None),('standing_idle','female_body_idle_1.anim'),('throne_sitting','female_body_throneRoom_ruler1_1.anim')]):
  if clip:
   a=pd.read_meshfile(str(folder/clip));count=a.find('info').attrib['sa'][0];frames=sorted({0,count//2,count-1})
  else:frames=[0]
  for frame in frames:
   mat=globals_for(a.find('info'),a.find('samples'),frame,rigsk)@binds if clip else np.repeat(np.eye(4)[None],len(rigsk),axis=0);body=deform(bodyprofile,bix,bw,mat);bvh=BVHTree.FromPolygons([Vector(x)for x in body],bt.tolist(),all_triangles=True);partreports={};posednodes={}
   for category,nodes in loaded.items():
    records=[];posed=[]
    for p,t,uv,ix,w,tex in nodes:
     out=deform(p,ix,w,mat);assert np.isfinite(out).all();clothbvh=BVHTree.FromPolygons([Vector(x)for x in out],t.tolist(),all_triangles=True);pairs=bvh.overlap(clothbvh);signed=[]
     for v in out:
      hit,n,fi,di=bvh.find_nearest(Vector(v));signed.append((Vector(v)-hit).dot(n))
     signed=np.array(signed);edges=np.concatenate([t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]]);lo=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1);lp=np.linalg.norm(out[edges[:,0]]-out[edges[:,1]],axis=1);valid=lo>.1;ratio=lp[valid]/lo[valid];records.append(dict(vertices=len(p),triangles=len(t),finite=True,intersecting_triangle_pairs=len(pairs),intersecting_clothing_triangles=len({x[1]for x in pairs}),signed_min_cm=float(signed.min()),negative_over_2mm=int(sum(signed<-.2)),edge_stretch_p99=float(np.quantile(ratio,.99)),edge_stretch_max=float(ratio.max())));posed.append((out,t,uv,tex))
    partreports[category]=records;posednodes[category]=posed
   record=dict(label=label,animation=clip,frame=int(frame),body_actor=actor,body_profile='h1_s0_b2'if actor==1001 else 'h1_s1_b0',body_clothed=False,body_vertices=len(body),body_triangles=len(bt),parts=partreports);case.append(record)
   if frame==frames[len(frames)//2]:
    for col in [0,1]:
     drawgeom(label+' body',body,bt,None,skinmat,col,row)
     for category,nodes in posednodes.items():
      for ni,(out,t,uv,tex)in enumerate(nodes):drawgeom(label+' '+category+str(ni),out,t,uv,material(str(tex)),col,row)
     curve=bpy.data.curves.new('label','FONT');curve.body=label+(' front'if col==0 else ' side');curve.size=.075;ob=bpy.data.objects.new('label',curve);bpy.context.collection.objects.link(ob);ob.location=(col*2-.7,-.65,1.5-row*1.8);ob.rotation_euler=(np.pi/2,0,0)
 bpy.ops.object.camera_add(location=(1,-12,-1.0));cam=bpy.context.object;cam.rotation_euler=(Vector((1,0,-1))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=5.6;bpy.context.scene.camera=cam
 for pos,energy,size in [((0,-4,5),800,5),((4,2,4),650,4)]:
  bpy.ops.object.light_add(type='AREA',location=pos);li=bpy.context.object;li.data.energy=energy;li.data.size=size;li.rotation_euler=(Vector((1,0,-1))-li.location).to_track_quat('-Z','Y').to_euler()
 scene=bpy.context.scene;scene.world=bpy.data.worlds.new('WardrobeWorld');scene.world.color=(.09,.09,.09);scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1400;scene.render.resolution_y=1800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';dest=R/'Reports'/('wardrobe-'+familyname+'-nude-standing-sitting.png');scene.render.filepath=str(dest);scene.view_settings.view_transform='Standard';bpy.ops.render.render(write_still=True);casefile=R/'Reports'/('wardrobe-'+familyname+'-pose-collision.json');casefile.write_text(json.dumps(dict(family=familyname,actor=actor,complete_nude_body=True,body_clothed=False,game_visual_verified=False,method='Actual exported part mesh+shared stock animation local t/q/s direct LBS; BVH all complete barebody triangles; source textures; nearest oriented sign is supplementary',tests=case,image=str(dest)),indent=2),encoding='utf8');reports.append(dict(family=familyname,actor=actor,report=str(casefile),image=str(dest)));print('WARDROBE_BVH_RENDERED',familyname,[(r['label'],sum(x['intersecting_clothing_triangles']for n in r['parts'].values()for x in n))for r in case],flush=True)
(R/'Reports/clothing-live-pose-index.json').write_text(json.dumps(reports,indent=2),encoding='utf8');print('WARDROBE_ACTUAL_POSE_COMPLETE',flush=True)

