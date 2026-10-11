"""Native 1001 ear/tail accessories. Source Unity clips only, no motion synthesis."""
import os
import json,sys,hashlib
from pathlib import Path
import xml.etree.ElementTree as X
import numpy as np
from scipy.spatial.transform import Rotation
from PIL import Image,ImageDraw
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter')
from build_ck3_mod import parser_only
ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"));OUT=ROOT/'motion-parts'
OUT.mkdir(exist_ok=True)
P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')
C=np.diag([-97.6403989,97.6403989,-97.6403989,1.]);CI=np.linalg.inv(C)
head=json.loads((ROOT/'parsed/head.json').read_text());tail=json.loads((ROOT/'parsed/tail.json').read_text())
index={c['key']:c for c in json.loads((ROOT/'native-motion-index.json').read_text())};source=np.load(ROOT/'native-motion-frames.npz')
def dump(path,v):path.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')
def xyz(values):return np.array([[v[k]for k in 'xyz']for v in values])
def transform(m,v):return (m[:3,:3]@v.T).T+m[:3,3]
def decompose(m):
    s=np.linalg.norm(m[:,:3,:3],axis=1);r=m[:,:3,:3]/s[:,None,:]
    assert np.max(np.abs(np.linalg.det(r)-1))<2e-5
    q=Rotation.from_matrix(r).as_quat()
    for i in range(1,len(q)):
        if np.dot(q[i-1],q[i])<0:q[i]*=-1
    return {'t':m[:,:3,3], 'q':q,'s':s}
def triangles(m):return np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in m['faces']])
hair=next(m for m in head['meshes']if m['name']=='M_Hair');tri=triangles(hair);bmap={b['id']:b for b in head['bones']}
ear_vertices={w['vertex']for w in hair['weights']if 'Ear' in bmap[w['bone']]['name']}
uf=list(range(len(hair['vertices'])))
def find(i):
    while uf[i]!=i:uf[i]=uf[uf[i]];i=uf[i]
    return i
for row in tri:
    for i in row[1:]:uf[find(int(i))]=find(int(row[0]))
component_ids={find(i)for i in ear_vertices};retained_vertices=[i for i in range(len(uf))if find(i)in component_ids]
ear_ids=np.flatnonzero(np.isin(tri,retained_vertices).all(axis=1));ear_tri=tri[ear_ids]
remaining_ids=np.flatnonzero(~np.isin(np.arange(len(tri)),ear_ids))
boundary=set(ear_tri.ravel())&set(tri[remaining_ids].ravel())
split={'source_mesh':'M_Hair','source_triangle_numbering':'zero based within faces[0].triangles, three successive indices per triangle','source_triangle_ids':ear_ids.tolist(),'retained_source_vertex_ids':retained_vertices,'hair_remove_triangle_ids':ear_ids.tolist(),'hair_retained_triangle_ids':remaining_ids.tolist(),'retained_triangles':len(ear_ids),'retained_vertices':len(retained_vertices),'source_triangles':len(tri),'connected_components':len(component_ids),'shared_vertex_boundary_with_hair':sorted(boundary),'root_vertices_without_ear_influence':sorted(set(retained_vertices)-ear_vertices),'reason':'Keep every disconnected component carrying native Ear skin weights, including its Head-weighted base. No geometric cuts across components.'}
assert not boundary
dump(OUT/'ear-source-triangles.json',split)
print('EAR_SPLIT_READY',len(retained_vertices),len(ear_ids),flush=True)
def oldworld(filename,name):
    tree=P.read_meshfile(str(ROOT/'v5/gfx/models/portraits/uma/0001'/filename));skel=tree.find('object')[0].find('skeleton');b=next(b for b in skel if b.tag==name)
    inv=np.eye(4);inv[:3]=np.array(b.get('tx')).reshape(4,3).T
    return np.linalg.inv(inv)
ear_attach=oldworld('uma_0001_head_empty.mesh','bn_h_head');tail_attach=oldworld('uma_0001_body_base.mesh','body_root')
def build(kind,data,m,ids,vids,A):
    byid={b['id']:b for b in data['bones']};needed={w['bone']for w in m['weights']if w['vertex']in vids}
    if kind=='ear':needed|={b['id']for b in data['bones']if 'Ear'in b['name']}
    else:needed={b['id']for b in data['bones']}
    for i in list(needed):
        parent=byid[i]['parent']
        while parent:needed.add(parent);parent=byid[parent]['parent']
    bones=[b for b in data['bones']if b['id']in needed];boneix={b['id']:i for i,b in enumerate(bones)};names=[b['name']for b in bones]
    sourceworld=np.array([np.array(b['matrix']).reshape(4,4)for b in bones])
    # Desired neutral world = converted source geometry plus carrier translation;
    # neutral source renderer is identity. Carrier rotation removed exactly once.
    desired=np.eye(4);desired[:3,3]=A[:3,3]
    origin=np.eye(4)
    if kind=='ear':origin[:3,3]=-np.array(next(b for b in data['bones']if b['name']=='Head')['matrix']).reshape(4,4)[:3,3]
    K=np.linalg.inv(A)@desired@C@origin@CI
    bw=np.array([K@C@w@CI for w in sourceworld])
    geom=transform(K@C,xyz(m['vertices'])[vids]);norm=xyz(m['normals'])[vids]@(K@C)[:3,:3].T;norm/=np.linalg.norm(norm,axis=1)[:,None]
    remap={int(v):i for i,v in enumerate(vids)};faces=np.array([[remap[int(v)]for v in row]for row in triangles(m)[ids]])
    uv=np.array([[v['x'],1-v['y']]for v in m['uvs'][0]['values']])[vids]
    tangent=np.zeros_like(geom)
    for row in faces:
        dp=geom[row[1:]]-geom[row[0]];du=uv[row[1:]]-uv[row[0]];det=np.linalg.det(du)
        if abs(det)>1e-10:
            t=(dp[0]*du[1,1]-dp[1]*du[0,1])/det
            tangent[row]+=t
    tangent-=norm*np.sum(norm*tangent,axis=1)[:,None];length=np.linalg.norm(tangent,axis=1);bad=length<1e-8
    tangent[bad]=np.cross(norm[bad],np.array([0.,1.,0.]));length=np.linalg.norm(tangent,axis=1);assert np.min(length)>1e-10;tangent/=length[:,None]
    skinix=np.full((len(vids),4),-1,int);skinw=np.zeros((len(vids),4));byv={i:[]for i in vids}
    for w in m['weights']:
        if w['vertex']in byv:byv[w['vertex']].append((boneix[w['bone']],float(w['weight'])))
    for v,ws in byv.items():
        assert len(ws)<=4
        total=sum(w for i,w in ws);assert total>0
        for j,(ix,w)in enumerate(ws):skinix[remap[v],j]=ix;skinw[remap[v],j]=w/total
    tree=X.Element('File',{'pdxasset':[1,0]});obj=X.SubElement(tree,'object');shape=X.SubElement(obj,'uma_1001_'+kind,{'lod':[0]});mesh=X.SubElement(shape,'mesh')
    for name,val in [('p',geom),('n',norm),('ta',np.column_stack([tangent,np.ones(len(geom))])),('u0',uv),('tri',faces)]:mesh.set(name,val.ravel().tolist())
    midpoint=(geom.min(0)+geom.max(0))/2;mesh.set('boundingsphere',np.r_[midpoint,np.linalg.norm(geom-midpoint,axis=1).max()].tolist())
    X.SubElement(mesh,'aabb',{'min':geom.min(0).tolist(),'max':geom.max(0).tolist()})
    tex='hair'if kind=='ear'else'tail'
    mat={'shader':['portrait_hair'],'diff':['uma_1001_'+tex+'_diff.dds'],'n':['uma_1001_'+tex+'_normal.dds'],'spec':['uma_1001_'+tex+'_properties.dds']}
    X.SubElement(mesh,'material',mat);X.SubElement(mesh,'skin',{'bones':[4],'ix':skinix.ravel().tolist(),'w':skinw.ravel().tolist()});skel=X.SubElement(shape,'skeleton')
    parents=[]
    for i,b in enumerate(bones):
        parent=boneix[b['parent']]if b['parent']in boneix else None;parents.append(parent)
        props={'ix':[i],'tx':np.linalg.inv(bw[i])[:3].T.ravel().tolist()}
        if parent is not None:props['pa']=[parent]
        X.SubElement(skel,b['name'],props)
    path=OUT/f'uma_1001_{kind}_base.mesh';P.write_meshfile(str(path),tree);r=P.read_meshfile(str(path));readgeom=np.array(r.find('object')[0].find('mesh').get('p')).reshape(-1,3)
    sourcepoints=xyz(m['vertices'])[vids];expected=transform(desired@C@origin,sourcepoints);actual=transform(A,readgeom)
    neutralerror=np.linalg.norm(expected-actual,axis=1).max();assert neutralerror<1e-4
    binderror=max(np.max(np.abs(np.linalg.inv(bw[i])@bw[i]-np.eye(4)))for i in range(len(bones)))
    assert np.isfinite(geom).all()and np.isfinite(bw).all()and np.isfinite(skinw).all()
    artifact={'kind':kind,'mesh':path.name,'mesh_vertices':len(geom),'mesh_triangles':len(faces),'bones':names,'bone_count':len(names),'attachment_node':'bn_h_head'if kind=='ear'else'body_root','attachment_bind_world':A.tolist(),'source_origin_offset_matrix':origin.tolist(),'accessory_convert_matrix':(K@C).tolist(),'geometry_rule':'local=inv(carrierBindWorld) @ Translation(carrierBindOrigin) @ UnityAxisScale @ sourceOriginOffset @ sourceVertex','bone_rule':'localWorld=inv(carrierBindWorld) @ Translation(carrierBindOrigin) @ UnityAxisScale @ sourceOriginOffset @ sourceBoneWorld @ inverse(UnityAxisScale)','material':mat,'neutral_attachment_world_error_cm':float(neutralerror),'inverse_bind_identity_error':float(binderror),'weight_sum_max_error':float(np.abs(skinw.sum(1)-1).max()),'animations':[]}
    fullposes={};frame_data={};folder=OUT/'animation'/kind;folder.mkdir(parents=True,exist_ok=True)
    keys=['ear_04','ear_03','ear_05']if kind=='ear'else['tail_04','tail_10','tail_16']
    for ck,state in zip(keys,['idle_entry','idle','frontEnd_middle_entry']):
        count=index[ck]['frames'];local=[]
        for i,b in enumerate(bones):
            sw=sourceworld[i];pa=parents[i];sl=np.linalg.inv(sourceworld[pa])@sw if pa is not None else sw
            track=source[ck+'__'+b['name']]if ck+'__'+b['name']in source else np.tile(sl,(count,1,1))
            frames=C@track@CI
            if pa is None:frames=K@frames
            local.append(frames)
        world=[]
        for i,frames in enumerate(local):world.append(world[parents[i]]@frames if parents[i]is not None else frames)
        world=np.stack(world,axis=1);skinmat=world@np.linalg.inv(bw)[None,:,:,:];posed=np.zeros((count,len(geom),3))
        for j in range(4):
            good=skinix[:,j]>=0;idx=skinix[good,j];M=skinmat[:,idx];posed[:,good]+=skinw[good,j][None,:,None]*(np.einsum('fvij,vj->fvi',M[:,:,:3,:3],geom[good])+M[:,:,:3,3])
        assert np.isfinite(posed).all()
        decomposed=[decompose(frames)for frames in local];anim=X.Element('File',{'pdxasset':[1,0]});info=X.SubElement(anim,'info',{'fps':[30.],'sa':[count],'j':[len(bones)]})
        channels=[]
        for name,d in zip(names,decomposed):
            active=''.join(ch for ch in ['t','q','s']if np.abs(d[ch]-d[ch][0]).max()>1e-7);channels.append(active)
            X.SubElement(info,name,{'sa':[active],**{ch:d[ch][0].tolist()for ch in ['t','q','s']}})
        samples=X.SubElement(anim,'samples')
        for ch in ['t','q','s']:
            arr=[d[ch]for d,cs in zip(decomposed,channels)if ch in cs]
            if arr:samples.set(ch,np.stack(arr,axis=1).ravel().tolist())
        animpath=folder/f'uma_1001_{kind}_{state}.anim';P.write_animfile(str(animpath),anim);r=P.read_meshfile(str(animpath));ri=r.find('info');rs=r.find('samples');assert ri.get('sa')==[count]and ri.get('j')==[len(bones)]
        # Reconstruct PDX file samples, prove every written sample equals Unity transform conversion.
        reconstructed={};cursor={ch:0 for ch in ['t','q','s']};maximum=0
        for ch,width in [('t',3),('q',4),('s',3)]:
            animated=[i for i,cs in enumerate(channels)if ch in cs];packed=np.array(rs.get(ch)or[]).reshape(count,len(animated),width)if animated else None
            for i,d in enumerate(decomposed):
                written=packed[:,animated.index(i)]if i in animated else np.tile(np.array(ri[i].get(ch)),(count,1));maximum=max(maximum,float(np.abs(written-d[ch]).max()))
        assert maximum<2e-5
        displacement=np.linalg.norm(posed-posed[0],axis=2);peakframe=int(np.argmax(displacement.max(axis=1)));rootdrift=np.linalg.norm(world[:,0,:3,3]-world[0,0,:3,3],axis=1).max();assert rootdrift<1e-5
        motions=[np.rad2deg((Rotation.from_quat(d['q'][0]).inv()*Rotation.from_quat(d['q'])).magnitude()).max()for d in decomposed]
        error=abs(max(motions)-index[ck]['amplitude_degrees']);assert error<.001
        rec={'state':state,'file':str(animpath.relative_to(OUT)).replace('\\','/'),'source_key':ck,**index[ck],'max_vertex_displacement_from_first_frame_cm':float(displacement.max()),'peak_frame_zero_based':peakframe,'root_translation_drift_cm':float(rootdrift),'pdx_sample_reconstruction_max_error':maximum,'converted_amplitude_degrees':float(max(motions)),'pose_aabb_min':posed.min((0,1)).tolist(),'pose_aabb_max':posed.max((0,1)).tolist(),'animated_channels':dict(zip(names,channels))}
        artifact['animations'].append(rec);fullposes[state]=posed;frame_data[state]=rec
        print('NATIVE_ANIM_WRITTEN',kind,state,count,round(displacement.max(),2),flush=True)
    # Orthographic evidence: exact bind (grey), first frame (cyan), strongest frame (gold).
    canvas=Image.new('RGB',(1500,1100),(18,22,30));draw=ImageDraw.Draw(canvas)
    for col,(state,poses)in enumerate(fullposes.items()):
        peak=frame_data[state]['peak_frame_zero_based'];layers=[geom,poses[0],poses[peak]]
        for row,axes in enumerate([(0,1),(2,1)]):
            points=np.concatenate([v[:,axes]for v in layers]);lo=points.min(0);hi=points.max(0);scale=min(440/max(hi[0]-lo[0],1),440/max(hi[1]-lo[1],1));center=(lo+hi)/2
            for v,color in zip(layers,[(85,93,112),(26,215,224),(255,196,68)]):
                pp=(v[:,axes]-center)*[scale,-scale]+[col*500+250,row*500+265]
                for f in faces:draw.line([tuple(pp[i])for i in [*f,f[0]]],fill=color,width=1)
            draw.text((col*500+18,row*500+20),f'{kind} {state}: bind / first / peak {peak}',fill=(235,240,250))
    evidence=OUT/f'{kind}-native-pose-proof.png';canvas.save(evidence);artifact['pose_evidence']=evidence.name
    dump(OUT/f'{kind}-rig-prepared.json',{'mesh':path.name,'bones':names,'parents':parents,'world_bind':bw.tolist(),'source_world':sourceworld.tolist(),'geometry':geom.tolist(),'faces':faces.tolist(),'skinix':skinix.tolist(),'skinw':skinw.tolist(),'animation_paths':[x['file']for x in artifact['animations']]})
    return artifact
ear=build('ear',head,hair,ear_ids,retained_vertices,ear_attach)
tm=tail['meshes'][0];tailpiece=build('tail',tail,tm,np.arange(len(triangles(tm))),list(range(len(tm['vertices']))),tail_attach)
delivery={'source':'Actual Unity 1001 ear driven-key locator converted local TRS and real tail AnimationClip local TRS. No synthetic motion, no amplitude scaling.','independent_entity_required':True,'shared_pose_entity':False,'source_head_renderer_world':np.eye(4).tolist(),'ear_split':split,'parts':[ear,tailpiece],'stock_animation_mapping_contract':'Map stock idle_entry to idle_entry; frontEnd_middle_entry to frontEnd_middle_entry; all idle loop keys to idle. Long original ear_03 is preserved at 30 fps. Source clips not edited to force seam closure.','risks':['CK3 in-game entity attachment and animation dispatch require runtime validation.','Original cutin/result motions may not have identical first/last frames; looping seam kept honest.','Native ear source uses Ear-driven bones plus Head-weighted root vertices; preserving all connected component vertices prevents dropped bases.','Ear and tail materials reference portrait_hair; root must supply diffuse/normal/properties maps and material palette masks.','Direct PDX writer binary round-trip completed; Blender PDX import/export validation is recorded separately.']}
dump(OUT/'motion-delivery.json',delivery)
print('MOTION_BUILD_COMPLETE',flush=True)
