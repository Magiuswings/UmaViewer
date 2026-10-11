import os
"""One serialized Blender batch: native skirt weights A/B/C, full nude BVH + actual idle/throne views."""
import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind,globals_for
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));abdir=R/'ClothingParts/AB-bdy1002_00';ab=json.loads((abdir/'ab-candidates.json').read_text());reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());fam=next(x for x in reg['families']if x['family']=='bdy1002_00');origdir=Path(fam['directory']);bodydir=next(Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'v5')).rglob('uma_0001_body_base.mesh')).parent
def readbody(tag):return pd.read_meshfile(str(bodydir/('uma_0001_body_'+tag+'.mesh'))).find('object')[0].find('mesh')
bn=readbody('base');bp=np.array(bn.attrib['p']).reshape(-1,3);bp=bp+(np.array(readbody('b0').attrib['p']).reshape(-1,3)-bp)+(np.array(readbody('s1').attrib['p']).reshape(-1,3)-bp);bt=np.array(bn.attrib['tri']).reshape(-1,3);bix=np.array(bn.find('skin').attrib['ix']).reshape(-1,4);bw=np.array(bn.find('skin').attrib['w']).reshape(-1,4);bnames=[n.tag for n in pd.read_meshfile(str(bodydir/'uma_0001_body_base.mesh')).find('object')[0].find('skeleton')];bodylabels=[]
for face in bt:
 masses={}
 for v in face:
  for bi,w in zip(bix[v],bw[v]):
   if w>0:masses[bnames[bi]]=masses.get(bnames[bi],0)+w
 dominant=max(masses,key=masses.get);bodylabels.append('hands'if any(s in dominant.lower()for s in ['hand','wrist','finger','thumb','index','middle','ring','pinky'])else 'legs'if any(s in dominant.lower()for s in ['hip','knee','ankle','toe'])else 'torso_or_other')
def deform(p,ix,w,mat):
 h=np.column_stack([p,np.ones(len(p))]);o=np.zeros_like(p)
 for j in range(4):o+=np.einsum('nij,nj->ni',mat[np.maximum(ix[:,j],0)],h)[:,:3]*w[:,j,None]
 return o
def material(path):
 name=Path(path).stem
 if name in bpy.data.materials:return bpy.data.materials[name]
 m=bpy.data.materials.new(name);m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.8;tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=bpy.data.images.load(str(path),check_existing=True);m.node_tree.links.new(tx.outputs['Color'],bs.inputs['Base Color']);m.node_tree.links.new(tx.outputs['Alpha'],bs.inputs['Alpha']);return m
def draw(name,p,t,uv,mat,col,row):
 xyz=p[:,[0,2,1]]*.01
 if col:xyz=xyz[:,[1,0,2]];xyz[:,0]*=-1
 xyz[:,0]+=col*2;xyz[:,2]-=row*1.8;me=bpy.data.meshes.new(name);me.from_pydata(xyz.tolist(),[],t[:,::-1].tolist());me.update();ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob);me.materials.append(mat)
 for poly in me.polygons:poly.use_smooth=True
 if uv is not None:
  layer=me.uv_layers.new(name='UV0')
  for loop in me.loops:layer.data[loop.index].uv=(uv[loop.vertex_index,0],1-uv[loop.vertex_index,1])
reports=[]
selected=sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else []
for candidate in ab['candidates']:
 if selected and candidate['case']not in selected:continue
 bpy.ops.wm.read_factory_settings(use_empty=True);skinmat=bpy.data.materials.new('Complete unchanged nude h1_s1_b0');skinmat.diffuse_color=(.87,.66,.49,1);loaded={};sk=None
 for category,part in fam['parts'].items():
  if category=='headwear':continue
  file=candidate['files']['base']if category=='clothes'else part['base_mesh'];tree=pd.read_meshfile(file);sk=tree.find('object')[0].find('skeleton');targets={k:pd.read_meshfile(candidate['files'][tag]if category=='clothes'else part['shape_targets'][k])for tag,k in [('b0','bs_body_breast_shape_1'),('s1','bs_body_gaunt_1')]};nodes=[];mapidx=0
  for oi,obj in enumerate(tree.find('object')):
   for ni,node in enumerate(obj.findall('mesh')):
    p0=np.array(node.attrib['p']).reshape(-1,3);p=p0.copy()
    for target in targets.values():p+=np.array(target.find('object')[oi].findall('mesh')[ni].attrib['p']).reshape(-1,3)-p0
    t=np.array(node.attrib['tri']).reshape(-1,3);mask=np.zeros(len(p),bool)
    if category=='clothes':ids=part['source_maps'][mapidx]['source_vertex_ids'];affected=set(candidate['classification'][mapidx]['affected_source_vertex_ids']);mask=np.array([v in affected for v in ids])
    nodes.append((p,t,np.array(node.attrib['u0']).reshape(-1,2),np.array(node.find('skin').attrib['ix']).reshape(-1,4),np.array(node.find('skin').attrib['w']).reshape(-1,4),origdir/node.find('material').attrib['diff'][0],mask));mapidx+=1
  loaded[category]=nodes
 bind=inverse_bind(sk);tests=[]
 for row,(label,clip)in enumerate([('neutral',None),('idle','female_body_idle_1.anim'),('throne','female_body_throneRoom_ruler1_1.anim')]):
  if clip:a=pd.read_meshfile(str(Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body'))/clip));nf=a.find('info').attrib['sa'][0];frames=sorted({0,nf//2,nf-1})
  else:frames=[0]
  for frame in frames:
   mat=globals_for(a.find('info'),a.find('samples'),frame,sk)@bind if clip else np.repeat(np.eye(4)[None],len(sk),axis=0);body=deform(bp,bix,bw,mat);bv=BVHTree.FromPolygons([Vector(x)for x in body],bt.tolist(),all_triangles=True);parts={};posed={}
   sockbvhs=[BVHTree.FromPolygons([Vector(x)for x in deform(p,ix,w,mat)],t.tolist(),all_triangles=True)for p,t,uv,ix,w,tx,mask in loaded.get('socks',[])]
   for category,nodes in loaded.items():
    rows=[];posed[category]=[]
    for p,t,uv,ix,w,tx,mask in nodes:
     out=deform(p,ix,w,mat);clothbvh=BVHTree.FromPolygons([Vector(x)for x in out],t.tolist(),all_triangles=True);pairs=bv.overlap(clothbvh);sets={region:set()for region in ['hands','legs','torso_or_other']};skirtsets={region:set()for region in sets};tri_mask=np.any(mask[t],axis=1);sockpairs=[pair for sockbvh in sockbvhs for pair in sockbvh.overlap(clothbvh)]if category=='clothes'else []
     for bodyface,clothesface in pairs:
      region=bodylabels[bodyface];sets[region].add(clothesface)
      if tri_mask[clothesface]:skirtsets[region].add(clothesface)
     e=np.concatenate([t[tri_mask][:,[0,1]],t[tri_mask][:,[1,2]],t[tri_mask][:,[2,0]]])if tri_mask.any()else np.concatenate([t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]]);lo=np.linalg.norm(p[e[:,0]]-p[e[:,1]],axis=1);lp=np.linalg.norm(out[e[:,0]]-out[e[:,1]],axis=1);ratio=lp[lo>.1]/lo[lo>.1];rows.append(dict(all_intersecting_clothing_triangles=len({c for b,c in pairs}),intersection_regions={r:len(v)for r,v in sets.items()},native_skirt_intersection_regions={r:len(v)for r,v in skirtsets.items()},native_skirt_sock_intersecting_triangles=len({c for s,c in sockpairs if tri_mask[c]}),skirt_edge_p99=float(np.quantile(ratio,.99)),skirt_edge_max=float(ratio.max()),finite=bool(np.isfinite(out).all())));posed[category].append((out,t,uv,tx))
    parts[category]=rows
   tests.append(dict(label=label,clip=clip,frame=frame,parts=parts))
   if frame==frames[len(frames)//2]:
    for col in [0,1]:
     draw(label+'body',body,bt,None,skinmat,col,row)
     for category,nodes in posed.items():
      for i,(out,t,uv,tx)in enumerate(nodes):draw(label+category+str(i),out,t,uv,material(tx),col,row)
     curve=bpy.data.curves.new('label','FONT');curve.body=candidate['case']+' '+label+(' front'if col==0 else ' side');curve.size=.075;ob=bpy.data.objects.new('label',curve);bpy.context.collection.objects.link(ob);ob.location=(col*2-.7,-.65,1.5-row*1.8);ob.rotation_euler=(np.pi/2,0,0)
 bpy.ops.object.camera_add(location=(1,-12,-1));cam=bpy.context.object;cam.rotation_euler=(Vector((1,0,-1))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=5.6;bpy.context.scene.camera=cam
 for pos,energy,size in [((0,-4,5),800,5),((4,2,4),650,4)]:
  bpy.ops.object.light_add(type='AREA',location=pos);li=bpy.context.object;li.data.energy=energy;li.data.size=size;li.rotation_euler=(Vector((1,0,-1))-li.location).to_track_quat('-Z','Y').to_euler()
 scene=bpy.context.scene;scene.world=bpy.data.worlds.new('WardrobeWorld');scene.world.color=(.09,.09,.09);scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1400;scene.render.resolution_y=1800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';image=abdir/('ab-'+candidate['case']+'-neutral-idle-throne.png');scene.render.filepath=str(image);scene.view_settings.view_transform='Standard';bpy.ops.render.render(write_still=True)
 # Separate material ownership evidence: native purple horse motifs must not be mistaken for purple sock penetration.
 for ob in bpy.data.objects:
  if ob.type!='MESH':continue
  color=(.95,.95,.95,1)if 'clothes'in ob.name else (.08,.16,1,1)if 'socks'in ob.name else (.4,.4,.4,1)if 'shoes'in ob.name else (1,.18,.12,1)
  for slot in ob.material_slots:
   mat=slot.material.copy();slot.material=mat
   if mat.use_nodes:
    bs=mat.node_tree.nodes.get('Principled BSDF')
    for link in list(bs.inputs['Base Color'].links):mat.node_tree.links.remove(link)
    bs.inputs['Base Color'].default_value=color
   else:mat.diffuse_color=color
 idimage=abdir/('ab-'+candidate['case']+'-material-ownership.png');scene.render.filepath=str(idimage);bpy.ops.render.render(write_still=True);report=dict(case=candidate['case'],body_profile='h1_s1_b0',body_unchanged=True,geometry_unchanged=candidate['geometry_unchanged'],hand_contacts_separate=True,method='Exact complete barebody triangle BVH under actual exported-mesh LBS with unchanged native stock clip. Source chain mask determines skirt region. Regions use dominant original body skin bone.',tests=tests,image=str(image),material_ownership_image=str(idimage),material_ownership_colors=dict(clothes='white preserving source alpha',socks='blue',barebody='red',shoes='gray'));reports.append(report);(abdir/('ab-'+candidate['case']+'-collision.json')).write_text(json.dumps(report,indent=2),encoding='utf8');print('SKIRT_AB_RENDER',candidate['case'],[(t['label'],t['frame'],t['parts']['clothes'][0]['native_skirt_intersection_regions'])for t in tests],flush=True)
indexfile=abdir/'ab-render-index.json';previous=json.loads(indexfile.read_text())if indexfile.exists()else [];cases={r['case']for r in reports};indexfile.write_text(json.dumps([r for r in previous if r['case']not in cases]+reports,indent=2),encoding='utf8');print('SKIRT_AB_RENDER_COMPLETE',flush=True)
