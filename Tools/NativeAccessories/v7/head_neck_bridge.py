import os
"""Six-to-ten endpoint bridge, original body/head meshes and rigs untouched."""
import json,sys,copy,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
from head_pdx_tools import skeleton,make_mesh
from head_assembly_math import rigdata,compose,readlocals,deform,shared_pose
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'HeadSources';OUT=SRC/'NeckBridge';OUT.mkdir(exist_ok=True);MOD=ROOT/'UMA-V7';BASE=MOD/'gfx/models/portraits/uma/0001';P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))));GAP=json.loads((SRC/'AssemblyQA/neck-surface-gap.json').read_text());REG=json.loads((ROOT/'Reports/head-registration.json').read_text())
def node(path):return P.read_meshfile(str(path)).find('object')[0]
def sample(arr,uv):
    h,w=arr.shape[:2];x=min(w-1,max(0,round(float(uv[0])*(w-1))));y=min(h-1,max(0,round(float(uv[1])*(h-1))));return arr[y,x]
bt=node(BASE/'uma_0001_body_base.mesh');BM=bt.find('mesh');B=rigdata(bt.find('skeleton'));TH=B['bind'][B['names'].index('bn_sp_thoracic')];THI=np.linalg.inv(TH);bp=np.array(BM.get('p')).reshape(-1,3);bn=np.array(BM.get('n')).reshape(-1,3);buv=np.array(BM.get('u0')).reshape(-1,2);bodyids=[r['final_body_vertex_id']for r in GAP['body_open_neck_ring']];lowerworld=bp[bodyids];lower=(THI[:3,:3]@lowerworld.T).T+THI[:3,3];ln=bn[bodyids]@TH[:3,:3];ln/=np.linalg.norm(ln,axis=1)[:,None];bodydiff=Image.open(BASE/BM.find('material').get('diff')[0]).convert('RGBA');bodypixels=np.array(bodydiff);lowcolor=np.array([sample(bodypixels,buv[i])for i in bodyids]);carrier=rigdata(node(BASE/'uma_0001_head_female.mesh').find('skeleton'));A0=readlocals(P,ROOT/'Rigs/uma_1002_head_points.anim',0);A1=readlocals(P,ROOT/'Rigs/uma_1002_head_points.anim',1);DELTA={n:A1[n][:3,3]-v[:3,3]for n,v in A0.items()if np.abs(A1[n][:3,3]-v[:3,3]).max()>1e-8};contract=json.loads((ROOT/'rig-contract.json').read_text());C=np.array(contract['head_source_to_engine']);anchor=np.array(contract['head_anchor']);deliveries=[]
for actor in['1001','1002']:
    case=next(a for a in GAP['actors']if a['actor']==actor);upper=np.array([v['head_local_position_cm']for v in case['ring_vertices']]);raw=json.loads((SRC/f'parsed/chr{actor}_80/head.json').read_text());models={m['name']:m for m in raw['meshes']};fr=next(r for r in REG if r['actor']==actor and r['variant']=='80'and r['element']=='face');hr=next(r for r in REG if r['actor']==actor and r['variant']=='80'and r['element']=='hair');face=node(fr['mesh']);hair=node(hr['mesh']);fm=face.find('mesh');hm=hair.find('mesh');F=rigdata(face.find('skeleton'));names=F['names'];parents=F['parents'];bind=F['bind'].copy();bind[names.index('head_root')]=np.eye(4)
    for bodyname,headname in [('bn_l_clavicle','bn_h_l_clavicle'),('bn_r_clavicle','bn_h_r_clavicle')]:bind[names.index(headname)]=THI@B['bind'][B['names'].index(bodyname)]
    uppern=[];upperw=[];colors=[];skinpatch=[]
    facepts=np.array(fm.get('p')).reshape(-1,3);faceuv=np.array(fm.get('u0')).reshape(-1,2);facepix=np.array(Image.open(Path(fr['mesh']).parent/fm.find('material').get('diff')[0]).convert('RGBA'));hairpts=np.array(hm.get('p')).reshape(-1,3);hairuv=np.array(hm.get('u0')).reshape(-1,2);hairpix=np.array(Image.open(Path(hr['mesh']).parent/hm.find('material').get('diff')[0]).convert('RGBA'));hairnormal=np.array(Image.open(Path(hr['mesh']).parent/hm.find('material').get('n')[0]).convert('RGBA'));srcbone={b['name']:b['id']for b in raw['bones']}
    for i,entry in enumerate(case['ring_vertices']):
        ref=next((r for r in entry['source_refs']if r['source_mesh']=='M_Face'),entry['source_refs'][0]);m=models[ref['source_mesh']];v=ref['source_vertex_id'];n=np.array([m['normals'][v][k]for k in'xyz'])@C.T;n/=np.linalg.norm(n);uppern.append(n);weights={names.index('bn_h_head'):next(w['weight']for w in ref['weights']if w['bone']=='Head'),names.index('bn_h_neck_1'):next(w['weight']for w in ref['weights']if w['bone']=='Neck')};upperw.append(weights)
        if ref['source_mesh']=='M_Face':j=int(np.argmin(np.linalg.norm(facepts-upper[i],axis=1)));colors.append(sample(facepix,faceuv[j]))
        else:
            patchrow=next(r for r in REG if r['actor']==actor and r['variant']=='80'and r['element']=='neck_patch');patchmesh=node(patchrow['mesh']).find('mesh');puv=np.array(patchmesh.get('u0')).reshape(-1,2);own=json.loads((SRC/'NeckPatch/neck-patch-delivery.json').read_text());ownrow=next(r for r in own['rows']if r['actor']==actor and r['variant']=='80');ids=ownrow['source_vertex_mapping'][0]['source_vertex_ids'];j=ids.index(v);pix=np.array(Image.open(Path(patchrow['mesh']).parent/patchmesh.find('material').get('diff')[0]).convert('RGBA'));original=sample(pix,puv[j]);colors.append(original);skinpatch.append({'source_vertex_id':v,'current_component':'neck_patch','current_shader':'portrait_skin_face','current_palette_blue_mask':0,'hair_tint_disabled':True,'source_diffuse_rgba':original.tolist(),'actual_final_neck_patch_mesh':patchrow['mesh']})
    lowerw=[];merged=[]
    for record in GAP['body_open_neck_ring']:
        ws={};tiny=0.
        for w in record['weights']:
            mapped={'bn_sp_thoracic':'head_root','bn_l_clavicle':'bn_h_l_clavicle','bn_r_clavicle':'bn_h_r_clavicle'}.get(w['bone'],'head_root')
            if w['bone']not in['bn_sp_thoracic','bn_l_clavicle','bn_r_clavicle']:tiny+=w['weight']
            j=names.index(mapped);ws[j]=ws.get(j,0)+w['weight']
        total=sum(ws.values());lowerw.append({j:w/total for j,w in ws.items()});merged.append(tiny)
    # Angular zipper in actual assembled surface space: exactly 6+10 triangles.
    lc=lowerworld[:,[0,2]].mean(0);uw=np.array([r['position_world_cm']for r in case['ring_vertices']]);uc=uw[:,[0,2]].mean(0);la=np.mod(np.arctan2(lowerworld[:,2]-lc[1],lowerworld[:,0]-lc[0]),2*np.pi);ua=np.mod(np.arctan2(uw[:,2]-uc[1],uw[:,0]-uc[0]),2*np.pi);li=np.argsort(la);ui=np.argsort(ua);langle=la[li];uangle=ua[ui];i=j=0;tris=[]
    while i<6 or j<10:
        nl=langle[(i+1)%6]+(2*np.pi if i+1>=6 else 0);nu=uangle[(j+1)%10]+(2*np.pi if j+1>=10 else 0)
        if i<6 and(j>=10 or nl<=nu):tris.append([int(li[i%6]),int(li[(i+1)%6]),6+int(ui[j%10])]);i+=1
        else:tris.append([int(li[i%6]),6+int(ui[(j+1)%10]),6+int(ui[j%10])]);j+=1
    tris=np.array(tris);posed=np.vstack([lowerworld,uw])
    for t in tris:
        normal=np.cross(posed[t[1]]-posed[t[0]],posed[t[2]]-posed[t[0]]);radial=posed[t].mean(0)[[0,2]]-((lc+uc)/2)
        if np.dot(normal[[0,2]],radial)<0:t[1],t[2]=t[2],t[1]
    assert len(tris)==16;points=np.vstack([lower,upper]);normals=np.vstack([ln,np.array(uppern)]);uv=np.column_stack([np.r_[la/(2*np.pi),ua/(2*np.pi)],np.r_[np.ones(6),np.zeros(10)]]);ix=np.full((16,4),-1,int);weights=np.zeros((16,4))
    for v,ws in enumerate([*lowerw,*upperw]):
        for slot,(bone,w)in enumerate(ws.items()):ix[v,slot]=bone;weights[v,slot]=w
    prefix='uma_'+actor+'_neck_base';path=OUT/(prefix+'.mesh');meta=make_mesh(P,path,prefix+'Shape',points,normals,uv,tris,ix,weights,skeleton(names,parents,bind),'portrait_skin_face',prefix)
    # 256x64 angular skin-color ramp; exact sampled endpoint pigments retained.
    image=np.zeros((64,256,4),np.uint8)
    def cyclic(colors,angles,x):
        ids=np.argsort(angles);aa=angles[ids];cc=np.array(colors)[ids];aa=np.r_[aa[-1]-2*np.pi,aa,aa[0]+2*np.pi];cc=np.vstack([cc[-1],cc,cc[0]]);return np.array([np.interp(x,aa,cc[:,k])for k in range(3)])
    for x in range(256):
        theta=x/255*2*np.pi;a=cyclic(np.array(colors),ua,theta);b=cyclic(lowcolor,la,theta)
        for y in range(64):image[y,x,:3]=np.rint(a*(1-y/63)+b*(y/63));image[y,x,3]=255
    for ending,arr in [('diffuse',image),('normal',np.tile([0,128,0,128],(32,32,1))),('properties',np.tile([0,38,0,180],(32,32,1))),('ssao',np.tile([255,255,255,96],(32,32,1)))]:Image.fromarray(np.asarray(arr,np.uint8),'RGBA').save(OUT/(prefix+'_'+ending+'.dds'),pixel_format='DXT5')
    bridge=node(path).find('mesh');BR=rigdata(node(path).find('skeleton'));checks=[]
    for label,bodyclip,headclip in [('idle',Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body/female_body_idle_1.anim')),MOD/'gfx/models/portraits/uma/animation/uma_female_head_idle_1.anim'),('court',Path(str(Path(os.environ.get('UMA_V7_GAME','D:/steam/steamapps/common/Crusader Kings III/game')) / 'gfx/models/portraits/female_body/female_body_throneRoom_ruler3_1.anim')),MOD/'gfx/models/portraits/uma/animation/uma_female_head_throneRoom_ruler3_1.anim')]:
        count=P.read_meshfile(str(bodyclip)).find('info').get('sa')[0];hc=P.read_meshfile(str(headclip)).find('info').get('sa')[0];maxlow=maxup=0.
        for frame in range(count):
            bw=compose(B,readlocals(P,bodyclip,frame));cw=compose(carrier,readlocals(P,headclip,min(frame,hc-1)),DELTA if actor=='1002'else{});external=bw[B['names'].index('bn_sp_thoracic')]@np.linalg.inv(cw[carrier['names'].index('head_root')])
            for bb,hb in [('bn_l_clavicle','bn_h_l_clavicle'),('bn_r_clavicle','bn_h_r_clavicle')]:cw[carrier['names'].index(hb)]=np.linalg.inv(external)@bw[B['names'].index(bb)]
            posedbridge=deform(bridge,BR,shared_pose(BR,carrier,cw));posedbridge=(external[:3,:3]@posedbridge.T).T+external[:3,3];bodygoal=deform(BM,B,bw)[bodyids];maxlow=max(maxlow,float(np.linalg.norm(posedbridge[:6]-bodygoal,axis=1).max()));faceworld=shared_pose(F,carrier,cw);uppergoal=np.zeros((10,3))
            for h in range(10):
                for bone,w in upperw[h].items():uppergoal[h]+=((faceworld[bone]@F['inv'][bone])@np.r_[upper[h],1])[:3]*w
            uppergoal=(external[:3,:3]@uppergoal.T).T+external[:3,3];maxup=max(maxup,float(np.linalg.norm(posedbridge[6:]-uppergoal,axis=1).max()))
        assert maxlow<.005,(actor,label,maxlow);assert maxup<.0001,(actor,label,maxup);checks.append({'context':label,'all_body_frames_sampled':count,'lower_edge_max_error_cm':maxlow,'upper_edge_max_error_cm':maxup})
    row={'actor':actor,'element':'neck','variant':'base','prefix':prefix,'gene':'uma_neck','shared_pose':'head','node':None,'mesh':str(path),'shader':'portrait_skin_face','vertices':16,'triangles':16,'textures':[str(OUT/(prefix+'_'+ending+'.dds'))for ending in['diffuse','normal','properties','ssao']],**meta};deliveries.append({'row':row,'lower_ring_body_vertex_ids':bodyids,'upper_ring_source_records':case['ring_vertices'],'lower_positions_head_thoracic_local_cm':lower.tolist(),'upper_positions_head_local_cm':upper.tolist(),'copied_lower_normals':ln.tolist(),'copied_upper_normals':np.array(uppern).tolist(),'merged_non_thoracic_clavicle_weight_max':max(merged),'body_face_vertices_or_core_rigs_modified':False,'bridge_inverse_bind_policy':'head_root=I; clavicles=inv(bodyThoracicBind)*bodyClavBind; other actor face/head inverse binds exact. All three current joint attachments required.','all_frame_lbs_validation':checks,'rear_neck_skin_patch_current_status':skinpatch,'rear_skin_patch_shader_note':'Actual final source neck patch isolated with portrait_skin_face; bridge upper endpoint pigments sampled from its normalized DDS, lower from normalized body DDS. CPU selected palette must be applied for visual preview.'})
    print('NECK_BRIDGE_BUILT',actor,checks,max(merged),flush=True)
report={'passed_numeric_lbs':True,'blender_visual_validation_pending_slot':True,'rows':[d['row']for d in deliveries],'actors':deliveries,'density':'16 actual endpoints /16 connecting triangles, no extra tessellation','root_registration':'gene uma_neck; actor-specific shared head accessory; no node translation','no_body_or_source_face_geometry_edit':True};(OUT/'neck-delivery.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
