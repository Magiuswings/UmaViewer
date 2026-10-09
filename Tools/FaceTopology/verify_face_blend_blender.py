"""Reopen the final Blender file and evaluate every identity BS on one network."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np

def main():
    p=argparse.ArgumentParser()
    for name in ('targets','models'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);data=np.load(a.targets/'face-targets.npz');manifest=json.loads((a.models/'blend-manifest.json').read_text());C=np.array([[-1,0,0],[0,0,-1],[0,1,0]])
    file=a.models/'uma_0001_face_base.blend';bpy.ops.wm.open_mainfile(filepath=str(file));obj=bpy.data.objects[manifest['mesh']];faces=np.array([list(f.vertices)for f in obj.data.polygons]);expected=data['faces'][:,::-1];assert np.array_equal(faces,expected)
    assert len(obj.data.vertices)==manifest['vertices'];assert len(obj.data.shape_keys.key_blocks)==len(manifest['keys'])+1
    records=[];intermediate=[]
    for ident,name in manifest['keys'].items():
        for key in obj.data.shape_keys.key_blocks:key.value=0
        key=obj.data.shape_keys.key_blocks[name];key.value=1.;bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        try:
            v=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',v);v=v.reshape(-1,3);assert len(mesh.vertices)==manifest['vertices'];assert np.array_equal(np.array([list(f.vertices)for f in mesh.polygons]),faces)
            error=float(np.max(np.linalg.norm(v-data[ident]@C.T,axis=1)));assert error<1e-7 and np.isfinite(v).all()
            t=v[faces];area=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)*.5;degen=int(sum(area<1e-12));assert degen==0,(ident,degen)
        finally:evaluated.to_mesh_clear()
        records.append(dict(id=ident,evaluated_coordinate_error_m=error,vertices=len(v),triangles=len(faces),degenerate_faces=degen))
        for value in (.25,.5,.75):
            q=(data['Basis']*(1-value)+data[ident]*value)@C.T;t=q[faces];area=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)*.5
            intermediate.append(dict(id=ident,value=value,degenerate_faces=int(sum(area<1e-12))))
    for key in obj.data.shape_keys.key_blocks:key.value=0
    report=dict(passed=True,final_blend_reopened=True,identity_keys=len(records),vertices=manifest['vertices'],triangles=len(faces),every_key_and_evaluated_mesh_same_vertex_count_and_order=True,every_key_and_evaluated_mesh_same_edges_and_oriented_faces=True,endpoint_zero_degenerate_faces=True,
        maximum_coordinate_error_m=max(r['evaluated_coordinate_error_m']for r in records),endpoint_checks=records,intermediate_checks=intermediate,intermediate_degenerate_faces=max(r['degenerate_faces']for r in intermediate),
        blend_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),game_materials_and_expression_rigs_verified=False)
    (a.models/'blender-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('ALL_FACE_BS_REOPEN_VERIFIED',len(records),'keys',len(intermediate),'intermediate samples',flush=True)

if __name__=='__main__':main()
