"""Independent reopened Blender/PDX, morph composition, and full-clip audit."""
import argparse,json,sys
from pathlib import Path
import bpy
import numpy as np

def clip_world(data,skeleton):
    """Evaluate every native frame with one cached vanilla bind-local table."""
    from test_vanilla_body_animation_blender import inverse_bind
    bindworld=np.linalg.inv(inverse_bind(skeleton));names=[n.tag for n in skeleton];lookup={n:i for i,n in enumerate(names)}
    parents=[n.attrib.get('pa',[None])[0]for n in skeleton];info=data.find('info');samples=data.find('samples');frames=info.attrib['sa'][0]
    local=np.tile(bindworld[None],(frames,1,1,1))
    for i,parent in enumerate(parents):
        if parent is not None:local[:,i]=np.linalg.inv(bindworld[parent])@bindworld[i]
    flags={b.tag:''.join(b.attrib.get('sa',[]))for b in info};counts={c:sum(c in v for v in flags.values())for c in 'tqs'};offset={c:0 for c in 'tqs'}
    streams={c:np.array(samples.attrib[c]).reshape(frames,counts[c],-1)for c in 'tqs'if counts[c]}
    for b in info:
        name=b.tag.rsplit(':',1)[-1]
        values={}
        for c in 'tqs':
            if c in flags[b.tag]:values[c]=streams[c][:,offset[c]];offset[c]+=1
            else:values[c]=np.tile(b.attrib[c],(frames,1))
        if name not in lookup:continue
        x,y,z,w=values['q'].T;R=np.zeros((frames,3,3))
        R[:,0,0]=1-2*(y*y+z*z);R[:,0,1]=2*(x*y-z*w);R[:,0,2]=2*(x*z+y*w)
        R[:,1,0]=2*(x*y+z*w);R[:,1,1]=1-2*(x*x+z*z);R[:,1,2]=2*(y*z-x*w)
        R[:,2,0]=2*(x*z-y*w);R[:,2,1]=2*(y*z+x*w);R[:,2,2]=1-2*(x*x+y*y)
        s=values['s'];s=np.repeat(s,3,axis=1)if s.shape[1]==1 else s
        i=lookup[name];local[:,i,:3,:3]=R*s[:,None,:];local[:,i,:3,3]=values['t']
    world=np.zeros_like(local);done=set()
    def visit(i):
        if i in done:return
        parent=parents[i]
        if parent is None:world[:,i]=local[:,i]
        else:visit(parent);world[:,i]=world[:,parent]@local[:,i]
        done.add(i)
    for i in range(len(names)):visit(i)
    return world

def skin(p,ix,w,T):
    h=np.column_stack((p,np.ones(len(p))));out=np.zeros((len(T),len(p),3))
    for slot in range(4):out+=np.einsum('fnij,nj->fni',T[:,np.maximum(ix[:,slot],0)],h)[...,:3]*w[None,:,slot,None]
    return out

def main():
    parser=argparse.ArgumentParser()
    for name in ('repo','plugin','root','stock'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--reopen-only',action='store_true',help='Verify editor-only changes without repeating unchanged full native clip scans')
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));sys.path.insert(0,str(a.repo/'Tools/BodyVectors'));sys.path.insert(0,str(a.plugin.parent));sys.path.insert(0,str(Path(__file__).parent))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from build_vector_body_blender import accelerate_pdx_lookup
    from rebuild_body_rest_blender import ENDPOINTS,BASE,KEYS,affine_error
    from test_vanilla_body_animation_blender import mesh_info,globals_for,inverse_bind
    from build_ck3_mod import clausewitz,one,values
    io_pdx_mesh.register();accelerate_pdx_lookup(pdx)
    stock=pdx_data.read_meshfile(str(a.stock));sk,sparts,sbind=mesh_info(stock);names=[n.tag for n in sk]
    meshes={v:pdx_data.read_meshfile(str(a.root/'meshes'/('uma_0001_body_'+v+'.mesh')))for v in ('base','none',*ENDPOINTS)}
    base=meshes['base'].find('object')[0].find('mesh');parts=mesh_info(meshes['base'])[1];p0,ix,w,_=parts[0];positions={}
    for variant,data in meshes.items():
        node=data.find('object')[0].find('mesh');positions[variant]=np.array(node.attrib['p']).reshape(-1,3)
        assert node.attrib['tri']==base.attrib['tri'] and node.attrib['u0']==base.attrib['u0'] and node.find('skin').attrib==base.find('skin').attrib
        assert np.array_equal(inverse_bind(data.find('object')[0].find('skeleton')),sbind)
        assert all(abs(sum(row)-1)<1e-6 for row in w)
    source=np.load(a.root/'fitted-body-profiles.npz');profiles={tuple(int(p[1:])for p in k.split('_')):source[k]for k in source.files}
    # PDX IO sorts the three corners of each encountered triangle, not the
    # entire global vertex table. Retain its explicit export/source mapping.
    faces=np.load(a.root/'source-skin-profiles.npz')['faces'];order=np.array(list(dict.fromkeys(v for face in faces for v in sorted(face))),int);assert len(order)==3510
    rows=[]
    for profile,expected in profiles.items():
        composed=p0.copy()
        for variant,p in ENDPOINTS.items():
            axis=next(i for i,(v,b)in enumerate(zip(p,BASE))if v!=b)
            if profile[axis]==p[axis]:composed+=positions[variant]-p0
        target=expected[order][:,[0,2,1]]*100;error=float(np.linalg.norm(composed-target,axis=1).max());assert error<.0001,(profile,error)
        rows.append(dict(profile=profile,composition_error_cm=error))
    bpy.ops.wm.open_mainfile(filepath=str(a.root/'uma_0001_body.blend'));body=bpy.data.objects['uma_0001_body'];rig=bpy.data.objects['uma_0001_body_vanillaRig']
    _,plugin_order=pdx.get_mesh_info(body,0,split_criteria=['id','p','uv'],sort_vertices=True);assert plugin_order==order.tolist()
    (a.root/'pdx-vertex-order.json').write_text(json.dumps(dict(export_to_source=plugin_order,source_indices_preserved_in_blend=True)),encoding='utf8')
    assert len(body.data.vertices)==3510 and len(body.data.polygons)==5472 and len(rig.data.bones)==134
    reopened=[]
    for clip in ('female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim','female_body_jockey_walk.anim'):
        data=pdx_data.read_meshfile(str(a.stock.parent/clip));frames=data.find('info').attrib['sa'][0];rig.animation_data.action=bpy.data.actions[Path(clip).stem];rig.data.pose_position='POSE'
        for frame in sorted({0,frames//2,frames-1}):
            T=globals_for(data.find('info'),data.find('samples'),frame,sk)@sbind;bpy.context.scene.frame_set(frame+1)
            for variant in ('base',*ENDPOINTS):
                for key in body.data.shape_keys.key_blocks:key.value=0
                if variant!='base':body.data.shape_keys.key_blocks[KEYS[variant]].value=1
                bpy.context.view_layer.update();evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get());m=evaluated.to_mesh()
                try:
                    co=np.empty(len(m.vertices)*3,dtype=np.float32);m.vertices.foreach_get('co',co);actual=co.reshape(-1,3)[order][:,[0,2,1]]
                finally:evaluated.to_mesh_clear()
                expected=skin(positions[variant],ix,w,T[None])[0];error=float(np.linalg.norm(actual-expected,axis=1).max());assert error<.005,(clip,frame,variant,error)
                reopened.append(dict(clip=clip,frame=frame,variant=variant,error_cm=error))
    # PDX IO roundtrip explicitly materializes every endpoint with its normals.
    rig.data.pose_position='REST';roundtrip=a.root/'roundtrip';roundtrip.mkdir(exist_ok=True);rt=[]
    for variant in ('base',*ENDPOINTS):
        clone=body.copy();clone.data=body.data.copy();bpy.context.collection.objects.link(clone);clone.shape_key_clear();coords=np.zeros_like(positions[variant]);coords[order]=positions[variant][:,[0,2,1]];clone.data.vertices.foreach_set('co',coords.astype(np.float32).reshape(-1));clone.data.update()
        node=meshes[variant].find('object')[0].find('mesh');normals=np.zeros_like(coords);normals[order]=np.array(node.attrib['n']).reshape(-1,3)[:,[0,2,1]];clone.data.normals_split_custom_set_from_vertices(normals.tolist())
        saved=body.data.name;body.data.name=saved+'__editing';clone.data.name=saved;pdx.set_mesh_index(clone.data,0);bpy.ops.object.select_all(action='DESELECT');clone.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=clone
        f=roundtrip/('uma_0001_body_'+variant+'.mesh');pdx.export_meshfile(str(f),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
        n=pdx_data.read_meshfile(str(f)).find('object')[0].find('mesh');error=float(np.linalg.norm(np.array(n.attrib['p']).reshape(-1,3)-positions[variant],axis=1).max());assert error<.0001
        assert n.attrib['tri']==base.attrib['tri'] and n.attrib['u0']==base.attrib['u0'] and n.find('skin').attrib==base.find('skin').attrib
        rt.append(dict(variant=variant,position_error_cm=error));m=clone.data;bpy.data.objects.remove(clone,do_unlink=True);bpy.data.meshes.remove(m);body.data.name=saved
    images=[dict(name=x.name,packed=x.packed_file is not None)for x in bpy.data.images if x.type=='IMAGE'];assert all(x['packed']for x in images)
    if a.reopen_only:
        report=dict(passed=True,final_editor_file_reopened=True,evaluated_samples=len(reopened),max_evaluated_error_cm=max(x['error_cm']for x in reopened),pdx_roundtrips=rt,packed_images=images,geometry_topology_uv_skin_keys_unchanged=True)
        (a.root/'editor-reopen-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('SEALED_EDITOR_REOPENED',len(reopened),'evaluations',flush=True);return
    # Every frame of every stock declaration: quantify strain, not just finite
    # coordinates. Additive tracks are audited separately as native data;
    # standalone application is not a claim about engine additive blending.
    tree=clausewitz(a.stock.with_suffix('.asset').read_text(encoding='utf-8-sig'));asset=one(tree,'pdxmesh');clips=[('animation',v)for v in values(asset,'animation')]+[('additive_animation',v)for v in values(asset,'additive_animation')]
    def edge_table(p,tri):
        f=np.array(tri).reshape(-1,3);edges=np.unique(np.sort(np.concatenate((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]])),axis=1),axis=0);length=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1);keep=length>.05;return edges[keep],length[keep]
    edges,l0=edge_table(p0,base.attrib['tri']);snode=stock.find('object')[0].find('mesh');ps,six,sw,_=sparts[0];sedges,sl0=edge_table(ps,snode.attrib['tri']);reports=[];total=0
    for number,(kind,entry)in enumerate(clips):
        file=a.stock.parent/one(entry,'type');data=pdx_data.read_meshfile(str(file));world=clip_world(data,sk);T=world@sbind;frames=len(world);total+=frames;max99=0.;stock99=0.;worst=0.;stockworst=0.
        # Bound memory even for long clips.
        for start in range(0,frames,32):
            batch=T[start:start+32];new=skin(p0,ix,w,batch);reference=skin(ps,six,sw,batch);assert np.isfinite(new).all()
            ratio=np.linalg.norm(new[:,edges[:,0]]-new[:,edges[:,1]],axis=2)/l0[None];sr=np.linalg.norm(reference[:,sedges[:,0]]-reference[:,sedges[:,1]],axis=2)/sl0[None]
            max99=max(max99,float(np.quantile(ratio,.99)));stock99=max(stock99,float(np.quantile(sr,.99)));worst=max(worst,float(ratio.max()));stockworst=max(stockworst,float(sr.max()))
        reports.append(dict(id=one(entry,'id'),kind=kind,frames=frames,edge_stretch_p99=max99,vanilla_edge_stretch_p99=stock99,edge_stretch_max=worst,vanilla_edge_stretch_max=stockworst))
        if (number+1)%25==0:print('FULL_NATIVE_CLIPS',number+1,'frames',total,flush=True)
    report=dict(passed=True,vertices=3510,triangles=5472,all_endpoints_share_topology_uv_weights_and_stock_bind=True,
                profiles_verified=len(rows),composition_checks=rows,max_composition_error_cm=max(x['composition_error_cm']for x in rows),
                blend_reopened=True,reopened_evaluated_samples=len(reopened),max_reopened_skinning_error_cm=max(x['error_cm']for x in reopened),
                pdx_roundtrips=rt,packed_images=images,all_native_declarations=len(reports),all_native_frames=total,clips=reports,
                native_animation_bytes_unmodified=True,ck3_visual_runtime_verified=False)
    (a.root/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('CANONICAL_REST_VERIFIED',len(rows),'profiles',total,'native frames',flush=True)

if __name__=='__main__':main()
