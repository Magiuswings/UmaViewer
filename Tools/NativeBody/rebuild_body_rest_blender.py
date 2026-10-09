"""Canonical-density skin union, UMA rest-pose baking, then vanilla CK3 binding.

Run in Blender 4.2. Immutable source snapshots and the installed vanilla body
are the inputs. No subdivision, remeshing, or posed-normal compensation is used.
Every donor barycentric map, fairing coefficient and native skinning matrix is
shared by all supplied profiles, retaining additive, vertex-correspondent keys.
"""
import argparse,copy,importlib.util,json,sys
from collections import defaultdict
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree

BASE=(1,0,2)
FIELDS=('height','shape','bust')
ENDPOINTS={'b0':(1,0,0),'b1':(1,0,1),'b3':(1,0,3),'b4':(1,0,4),
           's1':(1,1,2),'s2':(1,2,2),'h0':(0,0,2),'h2':(2,0,2)}
KEYS={'b0':'bs_body_breast_shape_1','b1':'bs_body_breast_shape_2',
      'b3':'bs_body_breast_shape_3','b4':'bs_body_breast_shape_4',
      's1':'bs_body_gaunt_1','s2':'bs_body_fat_1',
      'h0':'HeightSource_0','h2':'HeightSource_2'}

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def xyz(mesh):return np.array([[v[k] for k in 'xyz'] for v in mesh['vertices']],dtype=float)
def profile(r):return tuple(int(r['profile'][k])for k in FIELDS)

def bary(p,a,b,c):
    u=b-a;v=c-a;q=p-a;aa=u@u;ab=u@v;bb=v@v;den=aa*bb-ab*ab
    if abs(den)<1e-16:return np.array([1.,0.,0.])
    s=(bb*(q@u)-ab*(q@v))/den;t=(aa*(q@v)-ab*(q@u))/den
    result=np.maximum([1-s-t,s,t],0);return result/sum(result)

def affine_error(values):
    basis=values[BASE];worst=0.
    for p,actual in values.items():
        prediction=basis.copy()
        for axis,value in enumerate(p):
            anchor=list(BASE);anchor[axis]=value
            prediction+=values[tuple(anchor)]-basis
        worst=max(worst,float(np.linalg.norm(actual-prediction,axis=-1).max()))
    return worst

def welded_normals(p,faces,inverse):
    a,b,c=p[faces[:,0]],p[faces[:,1]],p[faces[:,2]]
    cross=np.cross(b-a,c-a);n=np.zeros((int(inverse.max())+1,3))
    for slot in range(3):np.add.at(n,inverse[faces[:,slot]],cross)
    n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-15)
    return n[inverse]

def geometry_quality(p,faces,inverse,selected):
    wf=inverse[faces];fn=np.cross(p[faces[:,1]]-p[faces[:,0]],p[faces[:,2]]-p[faces[:,0]])
    area=np.linalg.norm(fn,axis=1);fn/=np.maximum(area[:,None],1e-15)
    owners=defaultdict(list)
    for i,t in enumerate(wf):
        for a,b in zip(t,np.roll(t,-1)):
            if a!=b:owners[tuple(sorted((int(a),int(b))))].append(i)
    angles=[];nonmanifold=0;boundaries=0
    for edge,fs in owners.items():
        if len(fs)>2:nonmanifold+=1
        elif len(fs)==1:boundaries+=1
        elif selected[fs[0]] or selected[fs[1]]:
            angles.append(float(np.degrees(np.arccos(np.clip(fn[fs[0]]@fn[fs[1]],-1,1)))))
    return dict(vertices=len(p),triangles=len(faces),welded_vertices=int(inverse.max())+1,
                nonmanifold_edges=nonmanifold,boundary_edges=boundaries,degenerate_faces=int(sum(area<1e-12)),
                covered_dihedral_degrees_p50=float(np.quantile(angles,.5)),covered_dihedral_degrees_p95=float(np.quantile(angles,.95)))

def reconstruct(config,out):
    bodies={profile(r):r for r in config['records']if r['profile']['costume_id']=='0004'}
    donors={sub:{profile(r):r for r in config['records']if r['profile']['costume_id']=='0009' and r['profile']['body_type_sub']==sub}for sub in ('00','01')}
    source_data={};source={};donor_points={};donor_data={}
    for p,r in bodies.items():
        data=json.loads(Path(r['snapshot']).read_text(encoding='utf8'));mesh=next(m for m in data['meshes']if m['name']=='M_Body')
        source_data[p]=data;source[p]=xyz(mesh)
    basis_data=source_data[BASE];mesh=next(m for m in basis_data['meshes']if m['name']=='M_Body');basis=source[BASE]
    faces=np.array([t[:3]for t in bodies[BASE]['triangles']],dtype=int)
    assert len(basis)==3510 and len(faces)==5472
    canonical=set(tuple(sorted(t))for t in faces)
    for p,r in bodies.items():assert set(tuple(sorted(t[:3]))for t in r['triangles'])==canonical
    unique,inverse=np.unique(np.round(basis,6),axis=0,return_inverse=True);count=np.bincount(inverse);nw=len(unique)
    def weld(v):
        q=np.zeros((nw,3));np.add.at(q,inverse,v);return q/count[:,None]
    welded={p:weld(v)for p,v in source.items()}
    duplicates_max=max(float(np.linalg.norm(v-welded[p][inverse],axis=1).max())for p,v in source.items())
    assert duplicates_max<2e-6,duplicates_max
    # A UV split is not another geometric sample. Fair across all canonical
    # position duplicates, leaving the original indices/UV atlas untouched.
    wf=inverse[faces];edges=np.array(sorted(set(tuple(sorted((int(a),int(b))))for t in wf for a,b in zip(t,np.roll(t,-1))if a!=b)))
    a=np.r_[edges[:,0],edges[:,1]];b=np.r_[edges[:,1],edges[:,0]]
    lengths=np.linalg.norm(welded[BASE][a]-welded[BASE][b],axis=1);ew=1/np.maximum(lengths,.002)
    denom=np.bincount(a,weights=ew,minlength=nw)
    wrapped=np.zeros(len(faces),bool)
    for p,r in bodies.items():
        flags={tuple(sorted(t[:3])):flag for t,flag in zip(r['triangles'],r['wrapped'])}
        wrapped|=np.array([flags[tuple(sorted(t))]for t in faces])
    wrapped_v=np.zeros(nw,bool);wrapped_v[wf[wrapped].reshape(-1)]=True
    distance=np.full(nw,100,dtype=int);distance[wrapped_v]=0
    for ring in range(1,5):
        near=np.zeros(nw,bool);near[b[distance[a]<ring]]=True
        distance[near & (distance>ring)]=ring
    fair=np.choose(np.minimum(distance,4),[1.,.75,.40,.15,0.])
    n=weld(welded_normals(basis,faces,inverse));n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
    refs={}
    for sub,group in donors.items():
        donor_points[sub]={}
        for p,r in group.items():
            d=json.loads(Path(r['snapshot']).read_text(encoding='utf8'));dm=next(m for m in d['meshes']if m['name']=='M_Body')
            donor_points[sub][p]=xyz(dm)
            if p==BASE:donor_data[sub]=d
        skin=[t[:3]for t,flag in zip(group[BASE]['triangles'],group[BASE]['skin'])if flag]
        refs[sub]=(skin,BVHTree.FromPolygons([Vector(x)for x in donor_points[sub][BASE]],skin,all_triangles=True))
        assert affine_error(donor_points[sub])<1e-5
    maps={};rejected=0
    for i in np.flatnonzero(wrapped_v):
        choices=[]
        for sub,(skin,bvh)in refs.items():
            hit,hn,fi,d=bvh.find_nearest(Vector(welded[BASE][i]),.025)
            if fi is None or hn.dot(Vector(n[i]))<.65:continue
            q=np.array(hit);depth=(welded[BASE][i]-q)@n[i]
            if depth<-.00015:continue
            tri=skin[fi];w=bary(q,*donor_points[sub][BASE][tri]);valid=True
            for p in source:
                qp=w@donor_points[sub][p][tri]
                if (qp-welded[p][i])@n[i]>.00015:valid=False;break
            if valid:choices.append((float(d),sub,tri,w))
            else:rejected+=1
        if choices:
            d,sub,tri,w=min(choices,key=lambda x:x[0]);maps[int(i)]=(sub,tri,w)
    profiles=sorted(source);stack=np.array([welded[p]for p in profiles]);targets=stack.copy()
    for i,(sub,tri,w)in maps.items():
        for pi,p in enumerate(profiles):targets[pi,i]=w@donor_points[sub][p][tri]
    # Low-pass the full surface, including the original cloth ridges. A fixed
    # Taubin filter removes high-frequency creases with much less volume loss
    # than repeated ordinary Laplacian smoothing. No vertices/faces are added.
    result=targets.copy()
    for cycle in range(24):
        for coefficient in (.45,-.47):
            average=np.zeros_like(result)
            for pi in range(len(profiles)):np.add.at(average[pi],a,result[pi,b]*ew[:,None])
            average/=denom[None,:,None]
            result+=coefficient*fair[None,:,None]*(average-result)
    corrected={p:result[i][inverse]for i,p in enumerate(profiles)}
    error=affine_error(corrected);assert error<1e-5,error
    before=geometry_quality(basis,faces,inverse,wrapped);after=geometry_quality(corrected[BASE],faces,inverse,wrapped)
    assert after['covered_dihedral_degrees_p95']<before['covered_dihedral_degrees_p95']
    report=dict(source_profiles=len(source),source_common_families=['0004','0009_00','0009_01'],
                original_vertices=len(basis),output_vertices=len(basis),original_triangles=len(faces),output_triangles=len(faces),
                vertex_indices_and_triangles_unchanged=True,subdivisions=0,vertex_count_multiplier=1.,
                original_regional_sample_counts_preserved=True,
                original_uv_splits=nw!=len(basis),duplicate_position_error_m=duplicates_max,
                donor_samples=len(maps),covered_geometric_vertices=int(sum(wrapped_v)),outside_donor_maps_rejected=rejected,
                fixed_filter_cycles=24,source_additivity_error_m=affine_error(source),reconstructed_additivity_error_m=error,
                quality_before=before,quality_after=after,
                geometry_changed=True,uses_posed_normal_calibration=False,
                policy='Original 0004 topology; actual 0009 skin sampled inward; smooth whole covered surface and transitions with a common fixed linear filter; no densification')
    write(out/'skin-reconstruction.json',report)
    write(out/'donor-correspondence.json',dict(welded_source_ids=inverse.tolist(),wrapped_faces=wrapped.tolist(),fairing_weights=fair.tolist(),mappings={str(i):dict(family=s,triangle=t,weights=w.tolist())for i,(s,t,w)in maps.items()}))
    np.savez_compressed(out/'source-skin-profiles.npz',**{'h%d_s%d_b%d'%p:v for p,v in corrected.items()},faces=faces,source_basis=basis,inverse=inverse)
    print('CANONICAL_SKIN_REBUILT',report,flush=True)
    return basis_data,mesh,source,corrected,faces,inverse

def native_pose(data,mesh,values,stock,pdx,out):
    from rigging import _semantic_map
    from test_vanilla_body_animation_blender import inverse_bind
    # UMA -> Blender is handedness reflection plus Y-up -> Z-up; PDX stock
    # already has its own axis conversion. Never interpret Blender Y as height.
    C=np.array([[-1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]],float)
    # Use the true inverse; this handedness/axis conversion is not involutory.
    B={b['name']:C@np.array(b['matrix']).reshape(4,4)@np.linalg.inv(C)for b in data['bones']}
    byid={b['id']:b['name']for b in data['bones']};parents={b['name']:byid.get(b.get('parent'))for b in data['bones']}
    skeleton=stock.find('object')[0].find('skeleton');world=np.linalg.inv(inverse_bind(skeleton))
    stock_blender={b.tag:np.array(pdx.swap_coord_space(Matrix(world[i].tolist())))for i,b in enumerate(skeleton)}
    for m in stock_blender.values():m[:3,3]*=.01
    semantic={s:t for s,t in _semantic_map('body').items()if s in B}
    heads={s:stock_blender[t][:3,3].copy()for s,t in semantic.items()}
    base=values[BASE]@C[:3,:3].T
    stock_points=np.array(stock.find('object')[0].find('mesh').attrib['p']).reshape(-1,3)*.01
    size=(stock_points[:,1].max()-stock_points[:,1].min())/(base[:,2].max()-base[:,2].min())
    chains={'Hip':'Waist','Waist':'Spine','Spine':'Neck','Neck':'Head'}
    for side in ('L','R'):
        chains.update({f'Shoulder_{side}':f'Arm_{side}',f'Arm_{side}':f'Elbow_{side}',f'ShoulderRoll_{side}':f'Elbow_{side}',f'Elbow_{side}':f'Wrist_{side}',f'ArmRoll_{side}':f'Wrist_{side}',f'Wrist_{side}':f'Middle_01_{side}',f'Thigh_{side}':f'Knee_{side}',f'Knee_{side}':f'Ankle_{side}',f'Ankle_{side}':f'Toe_{side}'})
        for finger in ('Thumb','Index','Middle','Ring','Pinky'):
            for j in (1,2):chains[f'{finger}_{j:02}_{side}']=f'{finger}_{j+1:02}_{side}'
    # The native neck sleeve is taller than the stock neck sleeve. Preserve the
    # stock cervical bind point while fitting its exposed upper edge as well.
    neck=B['Neck'][:3,3];head=B['Head'][:3,3]
    scale_neck=(stock_points[:,1].max()-heads['Neck'][2])/(base[:,2].max()-neck[2])
    heads['Head']=heads['Neck']+(head-neck)*max(.2,min(1.5,scale_neck))
    matrices={};audit=[]
    def visit(name):
        if name in matrices:return
        parent=parents[name]
        if parent:visit(parent)
        old=B[name];child=chains.get(name)
        if name in heads:
            transform=np.eye(4);linear=np.eye(3)*size;angle=0.;stretch=size
            if child in B and child in heads:
                u=B[child][:3,3]-old[:3,3];v=heads[child]-heads[name]
                if np.linalg.norm(u)>1e-6 and np.linalg.norm(v)>1e-6:
                    q=Vector(u).rotation_difference(Vector(v));R=np.array(q.to_matrix());unit=u/np.linalg.norm(u);stretch=np.linalg.norm(v)/np.linalg.norm(u)
                    linear=R@(size*np.eye(3)+(stretch-size)*np.outer(unit,unit));angle=float(np.degrees(q.angle))
            elif parent:
                linear=matrices[parent][:3,:3]@np.linalg.inv(B[parent][:3,:3])
            transform[:3,:3]=linear;transform[:3,3]=heads[name]-linear@old[:3,3]
            matrices[name]=transform@old
            audit.append(dict(uma=name,ck3=semantic.get(name),rotation_degrees=angle,axial_scale=stretch,native_rest_head_m=old[:3,3].tolist(),fitted_head_m=heads[name].tolist()))
        elif parent:matrices[name]=matrices[parent]@np.linalg.inv(B[parent])@old
        else:
            m=old.copy();m[:3,:3]*=size;m[:3,3]*=size;matrices[name]=m
    for name in B:visit(name)
    names=list(B);indices={n:i for i,n in enumerate(names)}
    transforms=np.array([matrices[n]@np.linalg.inv(B[n])for n in names])
    ix=np.zeros((len(base),4),int);weights=np.zeros((len(base),4));slots=np.zeros(len(base),int)
    for w in mesh['weights']:
        i=w['vertex'];slot=slots[i];assert slot<4
        ix[i,slot]=indices[byid[w['bone']]];weights[i,slot]=w['weight'];slots[i]+=1
    weights/=weights.sum(1)[:,None]
    result={}
    for p,points in values.items():
        h=np.column_stack((points@C[:3,:3].T,np.ones(len(points))));v=np.zeros_like(points)
        for slot in range(4):v+=np.einsum('nij,nj->ni',transforms[ix[:,slot]],h)[:,:3]*weights[:,slot,None]
        result[p]=v
    # Native skin transport changes the entire pose, not just inverse binds.
    # Inspect actual sole contact rather than inferring it from ankle origins.
    feet=[]
    for side in ('L','R'):
        foot_bones={indices[n]for n in (f'Ankle_{side}',f'Ankle_offset_{side}',f'Toe_{side}',f'Toe_offset_{side}')if n in indices}
        mass=sum(weights[:,slot]*np.isin(ix[:,slot],list(foot_bones))for slot in range(4))
        ids=np.flatnonzero(mass>.95);p=result[BASE][ids]
        feet.append(dict(side=side,vertices=ids.tolist(),minimum_z_m=float(p[:,2].min()),maximum_z_m=float(p[:,2].max()),forward_bounds_m=[float(p[:,1].min()),float(p[:,1].max())]))
    # Flat soles: use the source ankle/foot groups, independently per foot.
    # Fit bottom samples at heel and forefoot to the same plane; blend the
    # corrective affine transform through native weights, for all profiles.
    foot_corrections=[]
    for record in feet:
        side=record['side'];ids=np.array(record['vertices']);p=result[BASE][ids];lo,hi=np.quantile(p[:,1],[.15,.85])
        heel=p[p[:,1]>=hi];front=p[p[:,1]<=lo]
        zheel=float(np.quantile(heel[:,2],.05));zfront=float(np.quantile(front[:,2],.05))
        yheel=float(np.median(heel[:,1]));yfront=float(np.median(front[:,1]));slope=(zheel-zfront)/max(yheel-yfront,1e-6)
        # This local shear places heel and forefoot on one horizontal plane
        # without changing vertex count, toe length, UVs or morph additivity.
        foot_bones={indices[n]for n in (f'Ankle_{side}',f'Ankle_offset_{side}',f'Toe_{side}',f'Toe_offset_{side}')if n in indices}
        mass=sum(weights[:,slot]*np.isin(ix[:,slot],list(foot_bones))for slot in range(4))
        z0=float(np.min(p[:,2]-slope*(p[:,1]-yfront)))
        for value in result.values():value[:,2]-=mass*(slope*(value[:,1]-yfront)+z0)
        foot_corrections.append(dict(side=side,native_ankle_weight_mask=True,heel_pitch_slope=slope,ground_shift_m=z0))
    error=affine_error(result);assert error<1e-5,error
    report=dict(native_source_bones=len(names),vanilla_bones=len(skeleton),source_geometry_pose='T',output_geometry_pose='fitted A',
                original_uma_skeleton_used_before_ck3=True,native_transforms_baked_into_all_profiles=True,overall_scale=size,
                source_minimum_height_m=float(base[:,2].min()),final_minimum_height_m=float(result[BASE][:,2].min()),
                foot_corrections=foot_corrections,additive_error_after_pose_m=error,joints=audit,
                ck3_reference_inverse_binds_copied_only_after_geometry_pose_baking=True)
    write(out/'rest-pose-fitting.json',report)
    np.savez_compressed(out/'fitted-body-profiles.npz',**{'h%d_s%d_b%d'%p:v for p,v in result.items()})
    write(out/'native-bone-transforms.json',dict(names=names,bind={n:B[n].tolist()for n in names},posed={n:matrices[n].tolist()for n in names},parents=parents))
    print('NATIVE_T_TO_A_BAKED',size,'minimum_z',report['final_minimum_height_m'],flush=True)
    return result,semantic,B,matrices,parents,byid,stock_blender

def build_outputs(a,data,source_mesh,original,skin,fitted,faces,inverse,semantic,B,G,parents,byid,stock,stock_blender,pdx,pdx_data):
    from build_vector_body_blender import accelerate_pdx_lookup
    from test_vanilla_body_animation_blender import inverse_bind
    from build_native_body_blend import native_action
    accelerate_pdx_lookup(pdx);bpy.ops.wm.read_factory_settings(use_empty=True)
    out=a.output;directory=out/'meshes';directory.mkdir()
    mat=bpy.data.materials.new('portrait_skin');mat.use_nodes=True;mat['shader']='portrait_skin'
    mat.diffuse_color=(.8,.64,.5,1);bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.7
    for label,name in [('diff','uma_0001_body_skin1_diffuse.dds'),('n','uma_0001_body_base_normal.dds'),('spec','uma_0001_body_base_properties.dds')]:
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(a.textures/name),check_existing=True)
        if label=='diff':mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
        else:tex.image.colorspace_settings.name='Non-Color'
    # PDX material textures are read using the plugin's node conventions.
    for tex in mat.node_tree.nodes:
        if tex.type=='TEX_IMAGE':
            if tex.image.name.endswith('_normal.dds'):
                normal=mat.node_tree.nodes.new('ShaderNodeNormalMap');separate=mat.node_tree.nodes.new('ShaderNodeSeparateColor');combine=mat.node_tree.nodes.new('ShaderNodeCombineColor');combine.inputs['Blue'].default_value=1
                mat.node_tree.links.new(tex.outputs['Color'],separate.inputs[0]);mat.node_tree.links.new(separate.outputs['Green'],combine.inputs['Red']);mat.node_tree.links.new(tex.outputs['Alpha'],combine.inputs['Green']);mat.node_tree.links.new(combine.outputs[0],normal.inputs['Color']);mat.node_tree.links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
            elif tex.image.name.endswith('_properties.dds'):mat.node_tree.links.new(tex.outputs['Alpha'],bsdf.inputs['Roughness'])
    mesh=bpy.data.meshes.new('uma_0001_bodyShape');mesh.from_pydata(fitted[BASE].tolist(),[],faces[:,::-1].tolist());mesh.update()
    body=bpy.data.objects.new('uma_0001_body',mesh);bpy.context.collection.objects.link(body);mesh.materials.append(mat)
    for face in mesh.polygons:face.use_smooth=True
    # Existing source UV splits are retained. Only UV0 is needed by this skin
    # shader, preventing the previous zero-area unused UV2 tangent warnings.
    layer=next(x for x in source_mesh['uvs']if x['channel']==0);uv=mesh.uv_layers.new(name='UV0')
    for loop in mesh.loops:
        v=layer['values'][loop.vertex_index];uv.data[loop.index].uv=(v['x'],v['y'])
    groups={n:body.vertex_groups.new(name=n)for n in stock_blender}
    def target(name):
        while name:
            if name in semantic:return semantic[name]
            if name=='Chest':return 'bn_sp_thoracic'
            if name=='Head':return 'bn_sp_cervical'
            name=parents[name]
        return 'body_root'
    mapping={n:target(n)for n in B};combined=defaultdict(lambda:defaultdict(float))
    for w in source_mesh['weights']:combined[w['vertex']][mapping[byid[w['bone']]]]+=w['weight']
    # Compressing UMA's long neck into the vanilla neck span also compresses
    # its old cervical/thoracic weight gradient. Re-sample the actual stock
    # surface weights here; otherwise a 1 mm rest edge can become 14 mm when
    # the head turns. The same fixed basis-space map is used for every BS.
    snode=stock.find('object')[0].find('mesh');sp=np.array(snode.attrib['p']).reshape(-1,3)[:,[0,2,1]]*.01
    stri=np.array(snode.attrib['tri']).reshape(-1,3)
    necktri=[t.tolist()for t in stri if np.min(sp[t,2])>1.17 and np.max(np.abs(sp[t,0]))<.12]
    neckbvh=BVHTree.FromPolygons([Vector(p)for p in sp],necktri,all_triangles=True)
    sskin=snode.find('skin');six=np.array(sskin.attrib['ix']).reshape(-1,4);sw=np.array(sskin.attrib['w']).reshape(-1,4);stocknames=[n.tag for n in stock.find('object')[0].find('skeleton')];neck_maps=[]
    for i,point in enumerate(fitted[BASE]):
        if point[2]<1.24 or abs(point[0])>.075 or combined[i].get('bn_sp_cervical',0)<.01:continue
        hit,hn,fi,distance=neckbvh.find_nearest(Vector(point),.09)
        if fi is None:raise ValueError('No vanilla neck surface for '+str(i))
        tri=necktri[fi];bw=bary(np.array(hit),*sp[tri]);ws=defaultdict(float)
        for j,coef in zip(tri,bw):
            for slot in range(4):
                if sw[j,slot]>0:ws[stocknames[six[j,slot]]]+=coef*sw[j,slot]
        combined[i]=ws;neck_maps.append(dict(vertex=i,triangle=tri,barycentric=bw.tolist(),distance_m=float(distance),weights=dict(ws)))
    write(out/'neck-weight-adaptation.json',dict(policy='Common basis-space barycentric transfer of vanilla cervical surface weights after neck-rest fitting',vertices=len(neck_maps),mappings=neck_maps))
    for i,influences in combined.items():
        ws=sorted(influences.items(),key=lambda x:-x[1])[:4];total=sum(w for n,w in ws)
        for n,w in ws:groups[n].add([i],w/total,'REPLACE')
    arm=bpy.data.armatures.new('uma_0001_body_vanillaSkeleton');rig=bpy.data.objects.new('uma_0001_body_vanillaRig',arm);bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    skeleton=stock.find('object')[0].find('skeleton');names=[b.tag for b in skeleton]
    # Save centimeter coordinates consistently with native body animation t.
    for n in names:
        b=arm.edit_bones.new(n);b.length=.03;b.matrix=Matrix(stock_blender[n].tolist());b.align_roll(b.matrix.to_3x3()@Vector((0,0,1)))
    for i,node in enumerate(skeleton):
        if node.attrib.get('pa'):arm.edit_bones[node.tag].parent=arm.edit_bones[names[node.attrib['pa'][0]]]
    bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True
    modifier=body.modifiers.new('Vanilla body animation','ARMATURE');modifier.object=rig;body.parent=rig
    basis=body.shape_key_add(name='Basis')
    for variant,p in ENDPOINTS.items():
        key=body.shape_key_add(name=KEYS[variant]);key.data.foreach_set('co',fitted[p].astype(np.float32).reshape(-1));key.value=0;key.relative_key=basis
    # Canonical meter-space editable rest stage before conversion to engine cm.
    body['body_rebuild_policy']='Canonical 3510 vertices; true donor skin + surface fairing; source UMA T-to-A pose baked before vanilla binding'
    body['basis_profile']='height=1, shape=0, bust=2';body['native_reference']='rest-pose-fitting.json';body['shape_height_policy']='Source references only; in-game height uses stock additive animations'
    # Scale data and bone translations together, not an asset scale multiplier.
    for key in body.data.shape_keys.key_blocks:
        for v in key.data:v.co*=100
    mesh.vertices.foreach_set('co',(fitted[BASE]*100).astype(np.float32).reshape(-1))
    mesh.update();mesh.normals_split_custom_set_from_vertices(welded_normals(fitted[BASE],faces[:,::-1],inverse).tolist())
    bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
    for n in names:
        b=arm.edit_bones[n];b.head*=100;b.tail*=100
    bpy.ops.object.mode_set(mode='OBJECT');bpy.context.view_layer.update()
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    # Keep the original and reconstructed T poses as hidden editable references.
    refs=bpy.data.collections.new('SOURCE_REFERENCES_DO_NOT_EXPORT');bpy.context.scene.collection.children.link(refs);refs.hide_render=True;refs.hide_viewport=True
    C=np.array([[-1,0,0],[0,0,-1],[0,1,0]])
    for label,points in [('Original_0004_T',original[BASE]),('Reconstructed_skin_T',skin[BASE])]:
        m=bpy.data.meshes.new(label);m.from_pydata((points@C.T*100).tolist(),[],faces[:,::-1].tolist());m.update();o=bpy.data.objects.new(label,m);refs.objects.link(o)
        for f in m.polygons:f.use_smooth=True
    # Source native rig after the baked fitting, kept separately for inspection.
    arm_native=bpy.data.armatures.new('UMA_native_fitted_rest');native=bpy.data.objects.new('UMA_native_fitted_rest',arm_native);refs.objects.link(native)
    refs.hide_viewport=False;bpy.context.view_layer.objects.active=native;native.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for name,m in G.items():
        b=arm_native.edit_bones.new(name);b.length=3.;frame=Matrix(m.tolist());q=frame.to_quaternion().to_matrix().to_4x4();q.translation=frame.translation*100;b.matrix=q
    for name,parent in parents.items():
        if parent:arm_native.edit_bones[name].parent=arm_native.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT');refs.hide_viewport=True
    pdx.set_mesh_index(mesh,0);records=[]
    for variant,p in [('base',BASE),*ENDPOINTS.items(),('none',BASE)]:
        clone=body.copy();clone.data=mesh.copy();bpy.context.collection.objects.link(clone);clone.shape_key_clear();clone.data.vertices.foreach_set('co',(fitted[p]*100).astype(np.float32).reshape(-1));clone.data.update()
        # Recompute normal from the final geometry, never compensate against
        # one particular animation. Weld UV-duplicate positions geometrically.
        normals=welded_normals(fitted[p],faces[:,::-1],inverse)
        clone.data.normals_split_custom_set_from_vertices(normals.tolist())
        saved=mesh.name;mesh.name=saved+'__editing';clone.data.name=saved
        bpy.ops.object.select_all(action='DESELECT');clone.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=clone;arm.pose_position='REST'
        file=directory/('uma_0001_body_'+variant+'.mesh');pdx.export_meshfile(str(file),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
        parsed=pdx_data.read_meshfile(str(file));obj=parsed.find('object')[0];old=obj.find('skeleton');assert [b.tag for b in old]==names
        # Restore the exact native inverse-bind float values after Blender's
        # unavoidable edit-bone frame decomposition; geometry is already posed.
        obj.remove(old);obj.append(copy.deepcopy(skeleton));pdx_data.write_meshfile(str(file),parsed)
        node=obj.find('mesh');assert len(node.attrib['p'])//3==3510
        _,export_order=pdx.get_mesh_info(clone,0,split_criteria=['id','p','uv'],sort_vertices=True)
        if variant=='base':write(out/'pdx-vertex-order.json',dict(export_to_source=export_order,source_indices_preserved_in_blend=True))
        else:assert export_order==json.loads((out/'pdx-vertex-order.json').read_text(encoding='utf8'))['export_to_source']
        if records:assert node.attrib['tri']==records[0]['tri'] and node.attrib['u0']==records[0]['u0']
        records.append(dict(variant=variant,profile=p,vertices=len(node.attrib['p'])//3,triangles=len(node.attrib['tri'])//3,tri=node.attrib['tri'],u0=node.attrib['u0']))
        dead=clone.data;bpy.data.objects.remove(clone,do_unlink=True);bpy.data.meshes.remove(dead);mesh.name=saved
        print('EXPORTED_CANONICAL_REST_ENDPOINT',variant,flush=True)
    # Inspectable real vanilla Actions and additive tracks; these are not
    # rewritten .anim assets and do not replace the mod's stock relative paths.
    native_action.skeleton=skeleton;actions=[];folder=a.stock.parent
    for name in ['female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim','female_body_jockey_walk.anim','female_body_height.anim','female_body_body_shape_apple.anim','female_body_body_shape_hourglass.anim','female_body_body_shape_pear.anim','female_body_body_shape_rectangle.anim','female_body_body_shape_triangle.anim']:
        file=folder/name
        if not file.is_file():continue
        action=native_action(rig,file,pdx_data);actions.append(action);print('IMPORTED_NATIVE_ACTION',name,flush=True)
    arm.pose_position='POSE';rig.animation_data.action=actions[0];bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True);bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'uma_0001_body.blend'))
    for r in records:r.pop('tri');r.pop('u0')
    write(out/'export-report.json',dict(blender=bpy.app.version_string,vertices=3510,triangles=5472,vanilla_skeleton_bones=134,
        stock_inverse_binds_exact=True,source_pose_baked_before_rebind=True,endpoints=records,keys=KEYS,actions=[x.name for x in actions],
        copied_game_assets_in_source_repository=False,source_profiles_tested=28,missing_source_parameter_combinations=17,per_character_body_keys=0,
        runtime_visual_verified=False))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','plugin','config','stock','textures','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert bpy.app.version[:2]==(4,2)
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));sys.path.insert(0,str(a.repo/'Tools/BodyVectors'));sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(a.plugin.parent))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    io_pdx_mesh.register();stock=pdx_data.read_meshfile(str(a.stock));config=json.loads(a.config.read_text(encoding='utf8'))
    data,mesh,source,skin,faces,inverse=reconstruct(config,a.output)
    fitted,semantic,B,G,parents,byid,stock_blender=native_pose(data,mesh,skin,stock,pdx,a.output)
    build_outputs(a,data,mesh,source,skin,fitted,faces,inverse,semantic,B,G,parents,byid,stock,stock_blender,pdx,pdx_data)
    print('CANONICAL_BODY_REST_REBUILD_COMPLETE',flush=True)

if __name__=='__main__':main()
