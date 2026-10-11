"""Export the unretopologized 1001 head and a real triangle head carrier using PDX IO."""
import argparse,copy,json,sys
from collections import defaultdict
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix

def main():
    p=argparse.ArgumentParser()
    for n in ['root','repo','plugin']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert bpy.app.version[:2]==(4,2)
    sys.path[:0]=[str(a.plugin.parent),str(a.repo/'Tools/PDXExporter'),str(a.repo/'Tools/BodyVectors'),str(a.repo/'Tools/NativeBody')]
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from build_vector_body_blender import accelerate_pdx_lookup
    from test_vanilla_body_animation_blender import inverse_bind
    from rigging import _semantic_map
    io_pdx_mesh.register();accelerate_pdx_lookup(pdx);bpy.ops.wm.read_factory_settings(use_empty=True)
    r=a.root;mod=r/'UMA-V6-1001';models=mod/'gfx/models/portraits/uma';character=models/'1001';shared=models/'0001'
    raw=json.loads((r/'parsed/head.json').read_text());policy=json.loads((r/'head-policy.json').read_text());materials={m['element']:m for m in json.loads((r/'head-materials.json').read_text())};ear=json.loads((r/'motion-parts/ear-source-triangles.json').read_text())
    original=pdx_data.read_meshfile(str(r/'v5/gfx/models/portraits/uma/0001/uma_0001_head_empty.mesh'));skeleton=original.find('object')[0].find('skeleton');names=[n.tag for n in skeleton];world=np.linalg.inv(inverse_bind(skeleton));assert len(names)==61
    swap=np.array([[1,0,0],[0,0,1],[0,1,0]]);arm=bpy.data.armatures.new('uma_head_carrier');rig=bpy.data.objects.new('uma_head_carrier',arm);bpy.context.collection.objects.link(rig);rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
    for i,name in enumerate(names):
        matrix=np.eye(4);matrix[:3,:3]=swap@world[i,:3,:3]@swap;matrix[:3,3]=swap@world[i,:3,3];bone=arm.edit_bones.new(name);bone.length=3.;bone.matrix=Matrix(matrix.tolist())
    for node in skeleton:
        if node.attrib.get('pa'):arm.edit_bones[node.tag].parent=arm.edit_bones[names[node.attrib['pa'][0]]]
    bpy.ops.object.mode_set(mode='OBJECT')
    byid={b['id']:b for b in raw['bones']};byname={b['name']:b for b in raw['bones']};semantic=_semantic_map('head')
    def mapped(name):
        while name:
            if name in semantic:return semantic[name]
            node=byname.get(name);name=byid[node['parent']]['name']if node and node.get('parent')else None
        return 'bn_h_head'
    mapping={b['id']:mapped(b['name'])for b in raw['bones']}
    C=np.array(policy['engine_transform']);H=np.array(policy['source_head_world']);origin=np.array(policy['engine_head_anchor'])
    report=[];parts={}
    def build(element,source,triangles):
        triangles=np.asarray(triangles,int).reshape(-1,3);ids=np.unique(triangles);lookup=np.full(len(source['vertices']),-1);lookup[ids]=np.arange(len(ids));faces=lookup[triangles][:,::-1]
        src=np.array([[v['x'],v['y'],v['z']]for v in source['vertices']]);engine=(src[ids]-H)@C.T+origin;points=engine@swap.T
        uv0=next(u['values']for u in source['uvs']if u['channel']==0);uv=np.array([[v['x'],v['y']]for v in uv0])[ids]
        prefix='uma_1001_'+element+'_base';mesh=bpy.data.meshes.new('uma_1001_'+element+'Shape');mesh.from_pydata(points.tolist(),[],faces.tolist());mesh.update();obj=bpy.data.objects.new('uma_1001_'+element,mesh);bpy.context.collection.objects.link(obj)
        for poly in mesh.polygons:poly.use_smooth=True
        layer=mesh.uv_layers.new(name='UV0')
        for loop in mesh.loops:layer.data[loop.index].uv=uv[loop.vertex_index]
        source_normals=np.array([[v['x'],v['y'],v['z']]for v in source['normals']])[ids];normals=source_normals@C.T@swap.T;normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-20);mesh.normals_split_custom_set_from_vertices(normals.tolist())
        weights=[defaultdict(float)for _ in ids]
        for w in source['weights']:
            if lookup[w['vertex']]>=0:weights[lookup[w['vertex']]][mapping[w['bone']]]+=w['weight']
        groups={n:obj.vertex_groups.new(name=n)for n in names};maxerr=0.
        for i,weight in enumerate(weights):
            used=sorted(weight.items(),key=lambda kv:-kv[1])[:4];total=sum(v for _,v in used)
            if total<=0:used=[('bn_h_head',1.)];total=1.
            maxerr=max(maxerr,abs(total-1))
            for n,v in used:
                if v>0:groups[n].add([i],v/total,'REPLACE')
        mat=bpy.data.materials.new(element);mat.use_nodes=True;mat['shader']=materials[element]['shader'];mesh.materials.append(mat);bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.7
        for channel in ['diffuse','normal','properties']:
            tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(character/(prefix+'_'+channel+'.dds')),check_existing=True)
            if channel=='diffuse':tex.image.alpha_mode='NONE'if element in ['face','face_parts','brow']else'STRAIGHT';mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
            elif channel=='normal':tex.image.colorspace_settings.name='Non-Color'
            else:tex.image.colorspace_settings.name='Non-Color'
        obj.parent=rig;obj.modifiers.new('UMA carrier pose','ARMATURE').object=rig;pdx.set_mesh_index(mesh,0)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=obj;file=character/(prefix+'.mesh');pdx.export_meshfile(str(file),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
        data=pdx_data.read_meshfile(str(file));assert len(data.find('object'))==1;node=data.find('object')[0];old=node.find('skeleton');node.remove(old);node.append(copy.deepcopy(skeleton));m=node.find('mesh');m.find('material').attrib={'shader':[materials[element]['shader']],'diff':[prefix+'_diffuse.dds'],'n':[prefix+'_normal.dds'],'spec':[prefix+'_properties.dds']}
        pdx_data.write_meshfile(str(file),data);_,order=pdx.get_mesh_info(obj,0,split_criteria=['id','p','uv'],sort_vertices=True);actual=np.array(m.attrib['p']).reshape(-1,3);error=float(np.max(abs(actual-engine[order])));assert error<1e-4 and len(actual)==len(ids)
        report.append(dict(element=element,file=file.relative_to(mod).as_posix(),vertices=len(ids),triangles=len(faces),shape=node.tag,shader=materials[element]['shader'],prefix=prefix,source_mesh=source['name'],geometry_error_cm=error,weight_source_sum_error=maxerr,unmodified_source_indices=ids.tolist(),shape_keys=0))
        parts[element]=obj;return obj
    for source in raw['meshes']:
        if source['name']=='M_Face':
            for element,category in [('face','face'),('eye','eyes')]:build(element,source,[v for f in source['faces']if f['category']==category for v in f['triangles']])
        elif source['name']=='M_Line00':build('face_parts',source,[v for f in source['faces']for v in f['triangles']])
        elif source['name']=='M_Mayu':build('brow',source,[v for f in source['faces']for v in f['triangles']])
        elif source['name']=='M_Hair':
            alltri=np.array([v for f in source['faces']for v in f['triangles']]).reshape(-1,3)
            remove=ear.get('ear_triangle_ids',ear.get('ear_triangle_indices',ear.get('hair_remove_triangle_ids')))
            if remove is None:
                # The motion worker exports both retained/remove indices; fail
                # loudly if its schema changed instead of guessing an ear split.
                candidates=[v for k,v in ear.items()if 'ear' in k and 'tri' in k and isinstance(v,list)];assert len(candidates)==1,ear.keys();remove=candidates[0]
            keep=np.ones(len(alltri),bool);keep[np.array(remove,int)]=False;build('hair',source,alltri[keep]);assert int(keep.sum())+len(remove)==len(alltri)
    assert set(parts)=={'face','eye','face_parts','brow','hair'}
    # A tiny, valid triangle inside the head. Identical neutral BS geometry
    # ensures every stock head BS declaration has a harmless matching target.
    points=origin+np.array([[0,0,0],[.001,0,0],[0,.001,0]]);tiny=bpy.data.meshes.new('uma_0001_head_carrierShape');tiny.from_pydata((points@swap.T).tolist(),[],[[2,1,0]]);tiny.update();dummy=bpy.data.objects.new('uma_0001_head_carrierTriangle',tiny);bpy.context.collection.objects.link(dummy)
    uv=tiny.uv_layers.new(name='UV0')
    for loop,value in zip(tiny.loops,[(0,1),(1,0),(0,0)]):uv.data[loop.index].uv=value
    groups={name:dummy.vertex_groups.new(name=name)for name in names};groups['bn_h_head'].add([0,1,2],1.,'REPLACE');dummy.modifiers.new('carrier pose','ARMATURE').object=rig;dummy.parent=rig
    mat=bpy.data.materials.new('carrier invisible');mat['shader']='portrait_attachment';mat.use_nodes=True;tiny.materials.append(mat)
    for k,ending in [('diff','diffuse'),('n','normal'),('spec','properties')]:
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(shared/('uma_0001_head_empty_'+ending+'.dds')),check_existing=True)
    pdx.set_mesh_index(tiny,0);bpy.ops.object.select_all(action='DESELECT');dummy.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=dummy;pdx.export_meshfile(str(shared/'uma_0001_head_empty.mesh'),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
    carrier=pdx_data.read_meshfile(str(shared/'uma_0001_head_empty.mesh'));objectnode=carrier.find('object')[0];old=objectnode.find('skeleton');objectnode.remove(old);objectnode.append(copy.deepcopy(skeleton));objectnode.find('mesh').find('material').attrib={'shader':['portrait_attachment'],'diff':['uma_0001_head_empty_diffuse.dds'],'n':['uma_0001_head_empty_normal.dds'],'spec':['uma_0001_head_empty_properties.dds']};assert objectnode.find('mesh').find('aabb')is not None
    pdx_data.write_meshfile(str(shared/'uma_0001_head_empty.mesh'),carrier);pdx_data.write_meshfile(str(shared/'uma_0001_head_none.mesh'),carrier);dummy.hide_render=True
    # Actual plugin reimports establish the exported geometry and skeletons.
    imported=0
    for file in [shared/'uma_0001_head_empty.mesh',*[mod/x['file']for x in report]]:
        before=set(bpy.data.objects);pdx.import_meshfile(str(file),imp_mesh=True,imp_skel=True,imp_locs=False,join_materials=True,bonespace=False);new=[o for o in bpy.data.objects if o not in before];assert any(o.type=='MESH'for o in new)
        imported_rig=next(m.object for o in new if o.type=='MESH'for m in o.modifiers if m.type=='ARMATURE');assert len(imported_rig.data.bones)==61
        for obj in new:bpy.data.objects.remove(obj,do_unlink=True)
        imported+=1
    out={'passed':True,'parts':report,'carrier_bones':len(names),'carrier_vertices':3,'carrier_triangles':1,'pdx_reimports':imported,'source_head_world':H.tolist(),'identity_morph_strategy_removed':True,'original_eyeball_triangles_preserved':True,'excluded_neutral_effects':['M_Cheek','M_Tear_L','M_Tear_R'],'geometry_retopologized':False,'runtime_verified':False}
    (r/'head-export.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;(r/'Models/1001').mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(r/'Models/1001/uma_1001_head_source.blend'));print('ORIGINAL_HEAD_V6_EXPORTED',[(x['element'],x['vertices'])for x in report],flush=True)
if __name__=='__main__':main()
