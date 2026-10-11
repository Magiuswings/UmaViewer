import sys,os,json,copy
from pathlib import Path
import numpy as np
import bpy
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));OUT=ROOT/'clothing-parts';REPO=Path(os.environ.get("UMA_V6_REPO", "E:/UmaViewer-Workspace/UmaViewer-source"));PLUGIN=Path(os.environ.get("UMA_V6_PLUGIN", "E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh"))
sys.path[:0]=[str(PLUGIN.parent),str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')];import io_pdx_mesh
from io_pdx_mesh import pdx_data
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
from test_vanilla_body_animation_blender import inverse_bind,globals_for
sys.path.insert(0,str(REPO/'Tools/BodyVectors'));from build_vector_body_blender import accelerate_pdx_lookup;accelerate_pdx_lookup(pdx)
io_pdx_mesh.register();a=np.load(OUT/'garment-prepared.npz');report=json.loads((OUT/'garment-preparation.json').read_text());stock=pdx_data.read_meshfile(str(OUT/'uma_0001_body_clothed.mesh'));o=stock.find('object')[0];sk=o.find('skeleton');sn=o.find('mesh');names=[x.tag for x in sk];bind=inverse_bind(sk);world=np.linalg.inv(bind);bpy.ops.wm.read_factory_settings(use_empty=True)
files=[str(OUT/'uma_1001_clothing_00.mesh')]
# Verify poses from exact installed stock animation bytes, direct LBS against exported mesh.
bodyp=np.array(sn.attrib['p']).reshape(-1,3);bodytri=np.array(sn.attrib['tri']).reshape(-1,3);bodyix=np.array(sn.find('skin').attrib['ix']).reshape(-1,4);bodyw=np.array(sn.find('skin').attrib['w']).reshape(-1,4)
read=pdx_data.read_meshfile(files[0]);cn=read.find('object')[0].find('mesh');cp=np.array(cn.attrib['p']).reshape(-1,3);ct=np.array(cn.attrib['tri']).reshape(-1,3);cix=np.array(cn.find('skin').attrib['ix']).reshape(-1,4);cw=np.array(cn.find('skin').attrib['w']).reshape(-1,4)
def posed(points,idx,weight,mats):
 h=np.column_stack([points,np.ones(len(points))]);out=np.zeros_like(points)
 for s in range(4):out+=np.einsum('nij,nj->ni',mats[np.maximum(idx[:,s],0)],h)[:,:3]*weight[:,s,None]
 return out
clips=[('neutral',None),('standing_idle','female_body_idle_1.anim'),('throne_sitting','female_body_throneRoom_ruler1_1.anim')];poses=[];animreports=[];folder=Path(os.environ.get("UMA_V6_GAME", "D:/steam/steamapps/common/Crusader Kings III/game")) / 'gfx/models/portraits/female_body'
for label,clip in clips:
 if clip:
  anim=pdx_data.read_meshfile(str(folder/clip));count=anim.find('info').attrib['sa'][0];frames=sorted({0,count//2,count-1})
 else:frames=[0];count=1
 for frame in frames:
  mats=globals_for(anim.find('info'),anim.find('samples'),frame,sk)@bind if clip else np.repeat(np.eye(4)[None],len(names),axis=0);bp=posed(bodyp,bodyix,bodyw,mats);cl=posed(cp,cix,cw,mats);bvh=BVHTree.FromPolygons([Vector(x)for x in bp],bodytri.tolist(),all_triangles=True);cbvh=BVHTree.FromPolygons([Vector(x)for x in cl],ct.tolist(),all_triangles=True);pairs=bvh.overlap(cbvh);signed=[]
  for v in cl:
   hit,n,fi,di=bvh.find_nearest(Vector(v));signed.append((Vector(v)-hit).dot(n))
  regions={'shoes':cp[ct,1].mean(1)<15,'socks':(cp[ct,1].mean(1)>=15)&(cp[ct,1].mean(1)<62),'skirt_waist':(cp[ct,1].mean(1)>=62)&(cp[ct,1].mean(1)<90),'upper':cp[ct,1].mean(1)>=90};badtri={x[1]for x in pairs};regioncounts={n:int(sum(flag[i]for i in badtri))for n,flag in regions.items()};signed=np.array(signed);edges=ct[:,[0,1]];l=np.linalg.norm(cl[edges[:,0]]-cl[edges[:,1]],axis=1);l0=np.linalg.norm(cp[edges[:,0]]-cp[edges[:,1]],axis=1);valid=l0>.01;ratio=l[valid]/l0[valid];rec=dict(intersections_by_rest_region=regioncounts,label=label,animation=clip,frame=int(frame),frames=int(count),finite=bool(np.isfinite(cl).all()),edge_stretch_p99=float(np.quantile(ratio,.99)),edge_stretch_max=float(ratio.max()),intersecting_triangle_pairs=len(pairs),intersecting_clothing_triangles=len({x[1]for x in pairs}),nearest_surface_signed_min_cm=float(signed.min()),nearest_surface_negative_over_2mm=int(sum(signed<-.2)),nearest_surface_negative_over_10mm=int(sum(signed<-1)),collision_method='Exact BVH triangle overlap; nearest-surface oriented sign is supplementary and ambiguous near open body neck/limbs')
  animreports.append(rec)
  if frame==frames[len(frames)//2]:poses.append((label,bp,cl))
(OUT/'clothing-clothed-animation-collision.json').write_text(json.dumps(animreports,indent=2),encoding='utf8');print('COLLISION',json.dumps(animreports),flush=True)
# Render front/side neutral and seated actual meshes and their native diffuse atlas.
bpy.ops.wm.read_factory_settings(use_empty=True);skinmat=bpy.data.materials.new('Body diagnostic skin');skinmat.diffuse_color=(.87,.64,.47,1);clothmat=bpy.data.materials.new('Clothing source diffuse');clothmat.use_nodes=True;node=clothmat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(OUT/'uma_1001_clothing_00_diffuse.dds'));clothmat.node_tree.links.new(node.outputs['Color'],clothmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color']);clothmat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.8
for row,(label,bp,cl)in enumerate([poses[0],poses[-1]]):
 for col in [0,1]:
  for title,pp,tt,material,iscloth in [('body',bp,bodytri,skinmat,False),('clothing',cl,ct,clothmat,True)]:
   xyz=pp[:,[0,2,1]]*.01
   if col==1:xyz=xyz[:,[1,0,2]];xyz[:,0]*=-1
   xyz[:,0]+=col*2.;xyz[:,2]-=row*2.
   mm=bpy.data.meshes.new(f'{label}_{col}_{title}');mm.from_pydata(xyz.tolist(),[],tt[:,::-1].tolist());mm.update();oo=bpy.data.objects.new(mm.name,mm);bpy.context.collection.objects.link(oo);mm.materials.append(material)
   for poly in mm.polygons:poly.use_smooth=True
   if iscloth:
    u=mm.uv_layers.new(name='UV0');us=np.array(cn.attrib['u0']).reshape(-1,2)
    for loop in mm.loops:u.data[loop.index].uv=(us[loop.vertex_index,0],1-us[loop.vertex_index,1])
  curve=bpy.data.curves.new('label','FONT');curve.body=label+(' front'if col==0 else ' side');curve.size=.08;oo=bpy.data.objects.new('label',curve);bpy.context.collection.objects.link(oo);oo.location=(col*2-.65,-.6,1.55-row*2);oo.rotation_euler=(np.pi/2,0,0)
bpy.ops.object.camera_add(location=(1,-10,-.15));cam=bpy.context.object;cam.rotation_euler=(Vector((1,0,-.15))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=4.1;bpy.context.scene.camera=cam
for pos,power,size in [((0,-4,5),1000,5),((4,2,4),800,4)]:
 bpy.ops.object.light_add(type='AREA',location=pos);l=bpy.context.object;l.data.energy=power;l.data.size=size;l.rotation_euler=(Vector((1,0,-.15))-l.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.world=bpy.data.worlds.new('GarmentWorld');scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1500;scene.render.resolution_y=1500;scene.render.resolution_percentage=100;scene.world.color=(.08,.08,.08);scene.render.image_settings.file_format='PNG';scene.render.filepath=str(OUT/'clothing-clothed-neutral-sitting-front-side.png');scene.view_settings.view_transform='Standard';bpy.ops.render.render(write_still=True)
delivery=dict(files=files,textures=[str(OUT/f'uma_1001_clothing_00_{x}.dds')for x in ['diffuse','normal','properties']],shader='portrait_attachment',body_shared_skeleton_exact=True,bones=134,source=report,animation_collision_reports=animreports,render=str(OUT/'clothing-clothed-neutral-sitting-front-side.png'),blender_source=str(OUT/'uma_1001_clothing_00.blend'),limitations=['Runtime game visual verification not executed','Static skinning does not simulate garment cloth physics','BVH intersections must be reviewed; finite meshes alone do not prove collision-free garments'])
(OUT/'clothing-clothed-delivery.json').write_text(json.dumps(delivery,indent=2),encoding='utf8');print('CLOTHING_DELIVERED',flush=True)
