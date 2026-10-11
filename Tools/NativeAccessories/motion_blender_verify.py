"""Read genuine PDX binary accessories/animations with IO PDX Mesh in Blender 4.2."""
import os
import sys,json,traceback
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Quaternion
sys.path.insert(0,'E:/UmaViewer-Workspace/PDX-vendor')
import io_pdx_mesh
from io_pdx_mesh.pdx_blender import blender_import_export as IO
from io_pdx_mesh import pdx_data as P
OUT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001")) / 'motion-parts';ROUND=OUT/'pdx-io-roundtrip';ROUND.mkdir(exist_ok=True)
delivery=json.loads((OUT/'motion-delivery.json').read_text());results=[]
def expected_pose(path,rigdata,frame):
    tree=P.read_meshfile(str(path));info=tree.find('info');samples=tree.find('samples');count=info.get('sa')[0];locals=[]
    for ch,width in [('t',3),('q',4),('s',3)]:
        active=[i for i,b in enumerate(info)if ch in b.get('sa')[0]]
        packed=np.array(samples.get(ch)or[]).reshape(count,len(active),width)if active else None
        for i,b in enumerate(info):
            if ch=='t':locals.append({})
            locals[i][ch]=packed[frame,active.index(i)]if i in active else b.get(ch)
    world=[]
    for i,d in enumerate(locals):
        t=Matrix.Translation(d['t']);q=d['q'];r=Quaternion((q[3],q[0],q[1],q[2])).to_matrix().to_4x4();s=Matrix.Diagonal([*d['s'],1.]);local=np.array(t@r@s);pa=rigdata['parents'][i];world.append(world[pa]@local if pa is not None else local)
    mats=np.array(world)@np.linalg.inv(np.array(rigdata['world_bind']));v=np.array(rigdata['geometry']);ix=np.array(rigdata['skinix']);w=np.array(rigdata['skinw']);posed=np.zeros_like(v)
    for j in range(4):
        good=ix[:,j]>=0;M=mats[ix[good,j]];posed[good]+=w[good,j,None]*(np.einsum('vij,vj->vi',M[:,:3,:3],v[good])+M[:,:3,3])
    return posed[:,[0,2,1]]
for part in delivery['parts']:
    kind=part['kind'];prepared=json.loads((OUT/f'{kind}-rig-prepared.json').read_text())
    for rec in part['animations']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        IO.import_meshfile(str(OUT/part['mesh']),imp_locs=False,join_materials=False)
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
        bpy.context.view_layer.objects.active=rig
        IO.import_animfile(str(OUT/rec['file']))
        samples=[]
        for frame in [0,rec['peak_frame_zero_based'],rec['frames']-1]:
            bpy.context.scene.frame_set(frame+1);bpy.context.view_layer.update();obj=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());evaluated=obj.to_mesh();actual=np.array([list(obj.matrix_world@v.co)for v in evaluated.vertices]);obj.to_mesh_clear();expected=expected_pose(OUT/rec['file'],prepared,frame)
            assert actual.shape==expected.shape
            error=float(np.linalg.norm(actual-expected,axis=1).max());assert np.isfinite(actual).all()
            samples.append({'frame_zero_based':frame,'source_pose_error_cm':error,'aabb_min':actual.min(0).tolist(),'aabb_max':actual.max(0).tolist()})
        bpy.context.view_layer.objects.active=rig
        animout=ROUND/Path(rec['file']).name
        IO.export_animfile(str(animout),frame_start=1,frame_end=rec['frames'],uniform_scale=False)
        rr=P.read_meshfile(str(animout));assert rr.find('info').get('sa')==[rec['frames']]
        # Export neutral mesh without baking animation into vertices.
        rig.animation_data_clear()
        for bone in rig.pose.bones:bone.matrix_basis=Matrix()
        bpy.context.view_layer.update()
        meshout=ROUND/f'uma_1001_{kind}_{rec["state"]}_roundtrip.mesh'
        IO.export_meshfile(str(meshout),exp_locs=False,sort_verts='~')
        mr=P.read_meshfile(str(meshout));assert mr.find('object') is not None
        result={'kind':kind,'state':rec['state'],'imported_bones':len(rig.data.bones),'imported_vertices':len(mesh.data.vertices),'evaluated_poses':samples,'max_source_pose_error_cm':max(s['source_pose_error_cm']for s in samples),'pdx_export_anim':str(animout.relative_to(OUT)),'pdx_export_mesh':str(meshout.relative_to(OUT)),'pdx_export_reimport_parser':True}
        results.append(result);print('BLENDER_PDX_IO_VERIFIED',kind,rec['state'],result['max_source_pose_error_cm'],flush=True)
report={'blender_version':bpy.app.version_string,'plugin':'IO PDX Mesh original importer/exporter','results':results,'all_evaluated_pose_errors_below_0_001_cm':all(x['max_source_pose_error_cm']<.001 for x in results)}
(OUT/'blender-pdx-io-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
delivery['blender_pdx_io_verification']=report
(OUT/'motion-delivery.json').write_text(json.dumps(delivery,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
assert report['all_evaluated_pose_errors_below_0_001_cm'], 'Original plugin pose sampling differs from mathematical PDX skinning; see report.'
print('BLENDER_MOTION_IO_COMPLETE',flush=True)
