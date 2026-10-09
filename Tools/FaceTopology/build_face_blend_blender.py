"""Create the editable common face and all neutral identity shape keys in Blender 4.2."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Euler,Vector

def main():
    p=argparse.ArgumentParser()
    for name in ('targets','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.output.mkdir(parents=True,exist_ok=False)
    data=np.load(a.targets/'face-targets.npz');topology=json.loads((a.targets/'common-topology.json').read_text(encoding='utf8'));report=json.loads((a.targets/'targets-report.json').read_text(encoding='utf8'));C=np.array([[-1,0,0],[0,0,-1],[0,1,0]])
    faces=data['faces'][:,::-1];points=data['Basis']@C.T;bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
    mat=bpy.data.materials.new('portrait_skin_face');mat.use_nodes=True;mat['shader']='portrait_skin_face';mat.diffuse_color=(.63,.65,.68,1);shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=mat.diffuse_color;shader.inputs['Roughness'].default_value=.75
    def mesh_object(name,points,faces,collection):
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(points.tolist(),[],faces.tolist());mesh.update();obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj);mesh.materials.append(mat)
        for poly in mesh.polygons:poly.use_smooth=True
        return obj
    body=mesh_object('uma_0001_face_base',points,faces,scene.collection);uv=body.data.uv_layers.new(name='UV0')
    for loop in body.data.loops:uv.data[loop.index].uv=data['uv0'][loop.vertex_index]
    body.shape_key_add(name='Basis');keys={}
    for row in report['per_model']:
        ident=row['id'];name='uma_0001_face_'+ident if ident.startswith('npc_')else'uma_'+ident+'_face';key=body.shape_key_add(name=name);key.data.foreach_set('co',(data[ident]@C.T).astype(np.float32).reshape(-1));key.value=0;keys[ident]=key.name
    body['uma_network_objective']=topology['objective'];body['uma_topology_hash']=topology['topology_hash'];body['uma_basis_source']=topology['source_medoid'];body['uma_identity_shape_keys']=json.dumps(keys);body['uma_scope']='Geometrically connected facial skin shell; source eye/oral/eyelid parts retained separately';body['uma_material_work_pending']='Character textures require transfer/rebake to common UV; expression rigs are not verified'
    refs=bpy.data.collections.new('SOURCE_REFERENCES_DO_NOT_EXPORT');scene.collection.children.link(refs);refs.hide_render=True
    chosen=['1001','1003','1071','1105','9003','9007','npc_000','npc_009']
    for ident in chosen:
        if 'original_'+ident+'_p'not in data.files:continue
        mesh_object('source_'+ident+'_face',data['original_'+ident+'_p']@C.T,data['original_'+ident+'_faces'][:,::-1],refs)
    mesh_object('arithmetic_mean_geometry_reference',data['MeanReference']@C.T,faces,refs);refs.hide_viewport=True
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.;center=(points.min(0)+points.max(0))*.5
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;space.region_3d.view_location=Vector(center);space.region_3d.view_distance=.43;space.region_3d.view_rotation=Euler((np.pi/2,0,0)).to_quaternion();space.region_3d.view_perspective='ORTHO';space.shading.type='SOLID';space.shading.color_type='MATERIAL'
    bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body;bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'uma_0001_face_base.blend'))
    for row in report['per_model']:
        ident=row['id'];directory=a.output/('0001'if ident.startswith('npc_')else ident);directory.mkdir(exist_ok=True);name='uma_0001_face_'+ident if ident.startswith('npc_')else'uma_'+ident+'_face_base';p=data[ident]@C.T
        text=['# Common facial network / neutral identity target']+['v %.9g %.9g %.9g'%tuple(v)for v in p]+['vt %.9g %.9g'%tuple(v)for v in data['uv0']]+['f '+' '.join(str(int(v)+1)+'/'+str(int(v)+1)for v in face)for face in faces]
        (directory/(name+'.obj')).write_text('\n'.join(text)+'\n',encoding='utf8')
    (a.output/'blend-manifest.json').write_text(json.dumps(dict(blender=bpy.app.version_string,mesh='uma_0001_face_base',vertices=len(points),triangles=len(faces),identity_keys=len(keys),keys=keys,topology_hash=topology['topology_hash'],source_reference_objects=chosen,source_files_unchanged=True,ck3_export_and_expression_animations_verified=False),indent=2),encoding='utf8');print('COMMON_FACE_BLEND_CREATED',len(keys),'keys',len(points),'vertices',flush=True)

if __name__=='__main__':main()
