import os,sys,json,hashlib
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from PIL import Image,ImageDraw,ImageFont
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only,clausewitz,one,values
from head_assembly_math import rigdata,shared_pose,deform
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9');O=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V10/HeelPose');P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');r=json.loads((O/'heel-validation.json').read_text(encoding='utf-8-sig'));q=np.load(O/'heel-body-poses.npz');names=q['bone_names'].tolist();NW=q['world'];BW=q['source_world'];family=next(x for x in json.loads((V/'Reports/clothing-registration.json').read_text())['families']if x['family']=='bdy1001_00')
so=P.read_meshfile(r['source_mesh']).find('object')[0];S=rigdata(so.find('skeleton'));B={'names':names};nodes=so.findall('mesh');skin=lambda w:np.vstack([deform(n,S,shared_pose(S,B,w))for n in nodes]);n0=skin(NW[0]);b0=skin(BW[0]);offset=0;tris=[]
for m in nodes:tris.extend((np.array(m.get('tri')).reshape(-1,3)+offset).tolist());offset+=len(m.get('p'))//3
tris=np.array(tris);snapshot=json.loads(Path(r['source_snapshot']).read_text());rawall=[];rawtris=[];offset=0
for mapping in family['parts']['shoes']['source_maps']:
 m=snapshot['meshes'][mapping['mesh']];ids=mapping['source_vertex_ids'];raw=np.array([[m['vertices'][i][c]for c in 'xyz']for i in ids])*100;rawall.extend(raw.tolist());source_tri=np.array(next(f for f in m['faces']if f['material']==mapping['material'])['triangles']).reshape(-1,3)
 # Source triangles are mapped to retained vertices; source indices may be dictionaries.
 source_index={i:j for j,i in enumerate(ids)}
 for ti in mapping['source_triangle_indices']:
  face=source_tri[ti]
  if isinstance(face,dict):face=[face[c]for c in ['x','y','z']]
  if all(i in source_index for i in face):rawtris.append([source_index[i]+offset for i in face])
 offset+=len(raw)
raw=np.array(rawall);rawtris=np.array(rawtris)
direction=[]
for f in range(61):
 rec={'frame_zero_based':f}
 for side in ['l','r']:
  i,j,k=[names.index(f'bn_{side}_{v}')for v in ['ankle','ftBall','ftToe']]
  for label,w in [('native',BW),('heel',NW)]:
   ankleball=w[f,j,:3,3]-w[f,i,:3,3];balltoe=w[f,k,:3,3]-w[f,j,:3,3];a=ankleball/np.linalg.norm(ankleball);b=balltoe/np.linalg.norm(balltoe)
   rec[f'{side}_{label}']={'ankle_to_ball_direction':a.tolist(),'ankle_to_ball_downward_degrees':float(np.rad2deg(np.arctan2(-a[1],np.linalg.norm(a[[0,2]])))),'ball_to_toe_direction':b.tolist(),'ball_to_toe_downward_degrees':float(np.rad2deg(np.arctan2(-b[1],np.linalg.norm(b[[0,2]]))))}
 direction.append(rec)
rootlift=(NW-BW)[:,:,1,3];nonankle=[i for i,n in enumerate(names)if n!='ground_joint'and not any(s in n for s in ['ankle','ftBall','ftToe','Ankle_offset','Toe_offset'])]
r.update(foot_direction_all_frames=direction,source_geometry_cm={'raw_unity_shoe_retained_vertices':len(raw),'triangles':len(rawtris),'aabb':[raw.min(0).tolist(),raw.max(0).tolist()],'rule':'original Unity source vertices selected by V9 shoe source_maps; no fabricated shoe geometry'},new_body_pose_outside_feet_world_deltaY_min_cm=float(rootlift[:,nonankle].min()),new_body_pose_outside_feet_world_deltaY_max_cm=float(rootlift[:,nonankle].max()),private_body_mesh_skeletal_set_import_verified=True,candidate_mesh_path_needs_resolution='Private wrapper is in UMA/0001 alongside reused V9 resources; integrate there without changing original mesh/BS/shaders. Original uma_body_mesh remains reference_skeleton.',test_asset_relative='gfx/models/portraits/uma/0001/uma_heel_1001_body_test.asset')
asset=one(clausewitz((O/r['test_asset_relative']).read_text(encoding='utf-8-sig')),'pdxmesh');assert one(one(asset,'import'),'name')=='uma_heel_1001_body';assert one(asset,'file')=='uma_0001_body_base.mesh'
r['output_clip_sha256']=hashlib.sha256((O/'gfx/models/portraits/uma/animation/body/uma_heel_1001_idle.anim').read_bytes()).hexdigest()
(O/'heel-validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8-sig')
# Numerical mesh silhouette proof, intentionally separate from rendered artistic acceptance.
im=Image.new('RGB',(1560,1040),(20,24,32));dr=ImageDraw.Draw(im);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
dr.text((24,20),'1001 original high-heel mesh / numerical stance evidence (cm)',font=font,fill=(240,240,240));dr.text((24,53),'Real shoe triangles, unchanged skin; frame 0. Not a CK3 shader or runtime screenshot.',font=small,fill=(180,185,195))
for idx,(title,p,t,axes,color)in enumerate([('Raw original Unity shoe geometry',raw,rawtris,(2,1),(96,177,237)),('Native barefoot idle + original heels',b0,tris,(2,1),(234,137,77)),('Heel-adapted native idle + same heels',n0,tris,(2,1),(106,222,170)),('Heel stance: front / same mesh',n0,tris,(0,1),(106,222,170))]):
 x=(idx%2)*780;y=100+(idx//2)*450;dr.text((x+30,y),title,font=font,fill=color)
 pp=p[:,axes];lo=pp.min(0);hi=pp.max(0);lo[1]=min(lo[1],-7);hi[1]=max(hi[1],21);scale=min(680/(hi[0]-lo[0]),330/(hi[1]-lo[1]));proj=(pp-(lo+hi)/2)*[scale,-scale]+[x+390,y+225]
 ground=y+225+((lo[1]+hi[1])/2)*scale;dr.line([(x+35,ground),(x+745,ground)],fill=(194,198,210),width=2);dr.text((x+35,ground+6),'ground Y = 0',font=small,fill=(194,198,210))
 for tri in t:
  points=[tuple(proj[i])for i in tri];dr.line(points+[points[0]],fill=color,width=1)
 dr.text((x+30,y+396),f'vertices {len(p)} | Y min {p[:,1].min():.6f} | Y max {p[:,1].max():.3f}',font=small,fill=(214,214,214))
im.save(O/'heel-mesh-ground-evidence.png')
(O/'heel-integration.txt').write_text('高跟鞋站姿测试候选：bdy1001_00 / 1001默认鞋\n\nBody clip: gfx/models/portraits/uma/animation/body/uma_heel_1001_idle.anim\nSkeletal set: uma_heel_1001_body (706个普通key全复用V9)\nPrivate pdxmesh: uma_heel_1001_body_mesh (import实际验证为uma_heel_1001_body)\nExplicit test entity: uma_heel_1001_body_entity\nAsset path: gfx/models/portraits/uma/0001/uma_heel_1001_body_test.asset\n\n全部61帧PDX回读：鞋底最低Y='+str(r['whole_shoe_min_y_cm'])+'cm；前掌/后跟最大离地='+str(r['max_selected_support_clearance_cm'])+'cm；腿链长度误差='+str(max(r['leg_chain_length_max_error_cm'].values()))+'cm。\n原idle SHA256: '+r['source_clip_sha256_before_after']+'\n原146骨名/序/父链保留，原mesh/BS/着色器不改，只改左右ankle q与body_root t。\n\n集成：将私有wrapper与现有V9 0001资源并放，测试portrait type明确选用此entity，鞋明确选bdy1001_00。动态按鞋gene/user_data自动切换set尚未实现，不虚构语法。\n头部：heel-body-poses.npz world[f]必须交给与裸足相同的新245骨head seam helper映射，重新求head root/颈桥/颈环对应pose；不要重复叠加root lift。参考skeleton仍是原uma_body_mesh。\n\nheel-mesh-ground-evidence.png为原始鞋网格/原idle/新pose的数值线框证据，并非美术render。未做Blender或CK3运行验证，不声明所有高跟通用或全鞋零穿模。\n',encoding='utf-8-sig')
print('HEEL_EVIDENCE',len(raw),len(rawtris),'directions',direction[0],'rootY',r['new_body_pose_outside_feet_world_deltaY_min_cm'],r['new_body_pose_outside_feet_world_deltaY_max_cm'],flush=True)
