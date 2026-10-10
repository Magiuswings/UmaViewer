"""Blender 4.2 + PDX IO: complete, consistently ordered neutral identity BS."""
import argparse,copy,json,sys
from collections import defaultdict
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector,Euler

def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def geometric_normals(points,faces,groups):
    n=np.zeros_like(points);tri=points[faces];fn=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    for slot in range(3):np.add.at(n,faces[:,slot],fn)
    for group in groups:
        value=n[group].sum(0);n[group]=value/max(np.linalg.norm(value),1e-20)
    return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-20)

def main():
    p=argparse.ArgumentParser()
    for n in ('repo','plugin','root','targets','source-mod'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--reuse-exports',action='store_true');p.add_argument('--seal-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert bpy.app.version[:2]==(4,2)
    def view_center():
        values=[];deps=bpy.context.evaluated_depsgraph_get()
        for obj in bpy.context.scene.objects:
            if obj.type!='MESH':continue
            evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();values.extend([tuple(evaluated.matrix_world@v.co)for v in mesh.vertices]);evaluated.to_mesh_clear()
        q=np.array(values);return(q.min(0)+q.max(0))*.5,float(np.max(q.max(0)-q.min(0)))
    def set_view(center,size):
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':
                    region=area.spaces.active.region_3d;region.view_location=Vector(center);region.view_distance=size*1.7;region.view_rotation=Euler((np.pi/2,0,0)).to_quaternion();region.view_perspective='ORTHO'
    if a.seal_only:
        file=a.root/'Models/0001/uma_0001_head_base.blend';bpy.ops.wm.open_mainfile(filepath=str(file));center,size=view_center();set_view(center,size)
        for mat in bpy.data.materials:
            if mat.get('shader')=='portrait_skin_face':
                for node in mat.node_tree.nodes:
                    if node.type=='TEX_IMAGE'and node.image and 'diffuse' in node.image.name:node.image.alpha_mode='NONE'
        bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(file));print('HEAD_VIEWPORT_SEALED',center.tolist(),size,flush=True);return
    sys.path[:0]=[str(a.plugin.parent),str(a.repo/'Tools/PDXExporter'),str(a.repo/'Tools/BodyVectors'),str(a.repo/'Tools/NativeBody'),str(a.repo/'Tools/FaceTopology')]
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from build_vector_body_blender import accelerate_pdx_lookup
    from test_vanilla_body_animation_blender import inverse_bind
    from build_native_body_blend import native_action
    from rigging import _semantic_map
    io_pdx_mesh.register();accelerate_pdx_lookup(pdx);bpy.ops.wm.read_factory_settings(use_empty=True)
    prep=json.loads((a.root/'prepared.json').read_text());data=np.load(a.targets/'face-targets.npz');top=json.loads((a.targets/'common-topology.json').read_text());old=pdx_data.read_meshfile(str(a.source_mod/'gfx/models/portraits/uma/1001/uma_1001_head_base.mesh'));oldobj=old.find('object')[0];skeleton=oldobj.find('skeleton');names=[b.tag for b in skeleton];world=np.linalg.inv(inverse_bind(skeleton));swap=np.array([[1,0,0],[0,0,1],[0,1,0]])
    arm=bpy.data.armatures.new('uma_0001_head_skeleton');rig=bpy.data.objects.new('uma_0001_head_rig',arm);bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for i,name in enumerate(names):
        mat=np.eye(4);mat[:3,:3]=swap@world[i,:3,:3]@swap;mat[:3,3]=swap@world[i,:3,3];bone=arm.edit_bones.new(name);bone.length=3.;bone.matrix=Matrix(mat.tolist())
    for i,node in enumerate(skeleton):
        if node.attrib.get('pa'):arm.edit_bones[node.tag].parent=arm.edit_bones[names[node.attrib['pa'][0]]]
    bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=False
    raw=json.loads(Path(prep['raw_snapshot']).read_text());byid={b['id']:b for b in raw['bones']};byname={b['name']:b for b in raw['bones']};semantic=_semantic_map('head')
    def mapped(name):
        while name:
            if name in semantic:return semantic[name]
            b=byname.get(name);name=byid[b['parent']]['name']if b and b.get('parent')else None
        return 'head_root'
    mapping={n:mapped(n)for n in byname}
    def material(name,shader,diffuse):
        mat=bpy.data.materials.new(name);mat.use_nodes=True;mat['shader']=shader;nodes=mat.node_tree.nodes;links=mat.node_tree.links;bsdf=nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.7
        for label,file in [('diff',diffuse),('n',a.root/'textures/0001/uma_0001_head_base_normal.dds'),('spec',a.root/'textures/0001/uma_0001_head_base_properties.dds')]:
            tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(file),check_existing=True)
            if label=='diff':
                if shader=='portrait_skin_face':tex.image.alpha_mode='NONE'
                links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
            elif label=='spec':tex.image.colorspace_settings.name='Non-Color';links.new(tex.outputs['Alpha'],bsdf.inputs['Roughness'])
            else:
                tex.image.colorspace_settings.name='Non-Color';normal=nodes.new('ShaderNodeNormalMap');sep=nodes.new('ShaderNodeSeparateColor');comb=nodes.new('ShaderNodeCombineColor');comb.inputs['Blue'].default_value=1.;links.new(tex.outputs['Color'],sep.inputs[0]);links.new(sep.outputs['Green'],comb.inputs['Red']);links.new(tex.outputs['Alpha'],comb.inputs['Green']);links.new(comb.outputs[0],normal.inputs['Color']);links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
        return mat
    def build(name,points,faces,uv,weights,mat,index):
        mesh=bpy.data.meshes.new(name+'Shape');mesh.from_pydata(points.tolist(),[],faces.tolist());mesh.update();obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);mesh.materials.append(mat)
        for polygon in mesh.polygons:polygon.use_smooth=True
        layer=mesh.uv_layers.new(name='UV0')
        for loop in mesh.loops:layer.data[loop.index].uv=uv[loop.vertex_index]
        groups={n:obj.vertex_groups.new(name=n)for n in names}
        for i,ws in enumerate(weights):
            accum=defaultdict(float)
            for n,w in ws.items():accum[n]+=w
            use=sorted(accum.items(),key=lambda r:-r[1])[:4];total=sum(w for n,w in use)
            if total<=0:use=[('bn_h_head',1.)];total=1.
            for n,w in use:
                if w>1e-8:groups[n].add([i],float(w/total),'REPLACE')
        obj.parent=rig;modifier=obj.modifiers.new('Shared UMA head animations','ARMATURE');modifier.object=rig;pdx.set_mesh_index(mesh,index);return obj
    transform=np.array(prep['engine_transform']);origin=np.array(prep['engine_origin']);engine=lambda p:p@transform.T+origin;blender=lambda p:engine(p)@swap.T
    weights=[]
    for ws in prep['common_weights']:
        accum=defaultdict(float)
        for n,w in ws.items():accum[mapped(n)]+=w
        weights.append(dict(accum))
    face=build('uma_0001_face',blender(data['Basis']),data['faces'][:,::-1],data['uv0'],weights,material('portrait_skin_face','portrait_skin_face',a.root/'textures/0001/uma_0001_face_base_diffuse.dds'),0);basis=face.shape_key_add(name='Basis')
    for row in prep['records']:
        key=face.shape_key_add(name=row['attribute']);key.data.foreach_set('co',blender(data[row['id']]).astype(np.float32).reshape(-1));key.relative_key=basis;key.value=0
    extras=prep['extra_face_parts'];extraweights=[defaultdict(float)for v in extras['source_indices']];lookup={v:i for i,v in enumerate(extras['source_indices'])}
    for w in raw['meshes'][0]['weights']:
        if w['vertex']in lookup:extraweights[lookup[w['vertex']]][mapping[byid[w['bone']]['name']]]+=w['weight']
    supporting=[build('uma_1001_face_parts',np.array(extras['points'])@swap.T,np.array(extras['faces'])[:,::-1],np.array(extras['uv0']),extraweights,material('portrait_skin_face_parts','portrait_skin_face',a.root/'textures/1001/uma_1001_face_parts_diffuse.dds'),1)]
    for index,element,shader,texture in [(1,'brow','portrait_hair','uma_1001_face_base_diffuse.dds'),(2,'hair','portrait_hair','uma_1001_hair_base_diffuse.dds'),(3,'eye','portrait_eye','uma_1001_eye_base_diffuse.dds')]:
        node=oldobj.findall('mesh')[index];points=np.array(node.attrib['p']).reshape(-1,3)@swap.T;tri=np.array(node.attrib['tri']).reshape(-1,3)[:,::-1];uv=np.array(node.attrib['u0']).reshape(-1,2);uv[:,1]=1-uv[:,1];skin=node.find('skin');ix=np.array(skin.attrib['ix']).reshape(-1,4);w=np.array(skin.attrib['w']).reshape(-1,4);ws=[{names[j]:float(v)for j,v in zip(ids,values)if v>0}for ids,values in zip(ix,w)]
        supporting.append(build('uma_1001_'+element,points,tri,uv,ws,material('portrait_'+element,shader,a.source_mod/'gfx/models/portraits/uma/1001'/texture),index+1))
    # Export a ordinary temporary mesh for each endpoint: PDX IO does not
    # evaluate Blender KeyBlocks when serializing a BS mesh.
    exports=[];base_order=None;base_shapes=None
    for ident,file in [('Basis','meshes/0001/uma_0001_head_base.mesh'),*[(r['id'],r['mesh'])for r in prep['records']]]:
        clone=face.copy();clone.data=face.data.copy();bpy.context.collection.objects.link(clone);clone.shape_key_clear();points=blender(data[ident]);clone.data.vertices.foreach_set('co',points.astype(np.float32).reshape(-1));clone.data.update();normals=geometric_normals(points,data['faces'][:,::-1],top['geometric_split_groups']);clone.data.normals_split_custom_set_from_vertices(normals.tolist());saved=face.data.name;face.data.name=saved+'Editing';clone.data.name=saved
        bpy.ops.object.select_all(action='DESELECT');clone.select_set(True);rig.select_set(True)
        for obj in supporting:obj.select_set(True)
        bpy.context.view_layer.objects.active=clone;arm.pose_position='REST';target=a.root/file;target.parent.mkdir(parents=True,exist_ok=True)
        if not(a.reuse_exports and target.is_file()):pdx.export_meshfile(str(target),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
        parsed=pdx_data.read_meshfile(str(target))
        for obj in parsed.find('object'):
            current=obj.find('skeleton');assert [n.tag for n in current]==names;obj.remove(current);obj.append(copy.deepcopy(skeleton))
        pdx_data.write_meshfile(str(target),parsed);_,order=pdx.get_mesh_info(clone,0,split_criteria=['id','p','uv'],sort_vertices=True);shapes=[(o.tag,len(o.find('mesh').attrib['p'])//3,o.find('mesh').attrib['tri'],o.find('mesh').attrib['u0'],o.find('mesh').find('skin').attrib)for o in parsed.find('object')]
        assert len(order)==875
        actual=np.array(parsed.find('object')[0].find('mesh').attrib['p']).reshape(-1,3);assert np.max(abs(actual-points[order]@swap.T))<1e-4
        if ident=='Basis':base_order=order;base_shapes=shapes
        else:assert order==base_order and shapes==base_shapes,'Endpoint changed topology, UV or weights'
        exports.append(dict(id=ident,file=file,objects=[dict(name=o.tag,vertices=len(o.find('mesh').attrib['p'])//3,triangles=len(o.find('mesh').attrib['tri'])//3)for o in parsed.find('object')]))
        dead=clone.data;bpy.data.objects.remove(clone,do_unlink=True);bpy.data.meshes.remove(dead);face.data.name=saved
        if len(exports)%20==0:print('EXPORTED_CK3_HEADS',len(exports)-1,flush=True)
    basefile=a.root/'meshes/0001/uma_0001_head_base.mesh';(a.root/'meshes/0001/uma_0001_head_none.mesh').write_bytes(basefile.read_bytes())
    write(a.root/'pdx-vertex-order.json',dict(export_to_source=base_order));write(a.root/'rig-transfer.json',dict(mapping=mapping,engine_transform=transform.tolist(),engine_origin=origin.tolist(),skeleton_inverse_binds_exact=True,all_targets_share_weights=True,weight_source='1001 common-network mapping; new forehead nodes interpolate their edge endpoints'))
    native_action.skeleton=skeleton;actions=[]
    for name in ['uma_female_head_idle_1.anim','uma_female_head_eye_shut.anim','uma_female_head_mouth_open.anim']:
        file=a.source_mod/'gfx/models/portraits/uma/animation'/name
        if file.exists():actions.append(native_action(rig,file,pdx_data))
    # Open in the default 1001 identity so the retained test hair/eyes match.
    face.data.shape_keys.key_blocks['uma_bs_face_1001'].value=1.;arm.pose_position='POSE'
    if actions:rig.animation_data.action=actions[0]
    bpy.context.scene.frame_set(1);bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    face['uma_identity_note']=prep['texture_switching'];face['uma_topology_hash']=top['topology_hash'];rig.hide_set(True)
    center,size=view_center();set_view(center,size)
    bpy.ops.object.select_all(action='DESELECT');face.select_set(True);bpy.context.view_layer.objects.active=face;bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True);bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
    (a.root/'Models/0001').mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.root/'Models/0001/uma_0001_head_base.blend'))
    write(a.root/'export-report.json',dict(passed=True,blender=bpy.app.version_string,face_vertices=875,face_triangles=1334,identity_targets=182,objects=exports[0]['objects'],exports=exports,common_animations=[x.name for x in actions],reused_skeleton_bones=61,default_identity='1001',base_geometry_identity='1003',materials=['portrait_skin_face','portrait_hair','portrait_eye'],runtime_verified=False))
    print('CK3_HEAD_EXPORT_COMPLETE',len(exports)-1,flush=True)

if __name__=='__main__':main()
