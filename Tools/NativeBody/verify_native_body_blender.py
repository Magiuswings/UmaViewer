"""Reopen the delivered blend and compare real evaluated animation/BS against PDX skinning."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import bpy

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--mod',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--blend',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--character-id',default='1001');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b
    from test_vanilla_body_animation_blender import mesh_info,globals_for
    prefix=a.character_id+'_body_';pdx=b.parser_only(a.plugin);bpy.ops.wm.open_mainfile(filepath=str(a.blend));body=bpy.data.objects[a.character_id+'_body'];rig=bpy.data.objects[a.character_id+'_body_vanilla_rig'];folder=a.mod/'gfx/models/portraits/uma'/a.character_id;sk,parts,bind=mesh_info(pdx.read_meshfile(str(folder/(prefix+'base.mesh'))));p0,ix,w,_=parts[0]
    rig.data.pose_position='POSE';records=[];keys={'b0':'bs_body_breast_shape_1','b1':'bs_body_breast_shape_2','b3':'bs_body_breast_shape_3','b4':'bs_body_breast_shape_4','s1':'bs_body_gaunt_1','s2':'bs_body_fat_1','h0':'HeightSource_0','h2':'HeightSource_2'}
    for clip in ['female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim','female_body_jockey_walk.anim']:
        data=pdx.read_meshfile(str(a.game/'gfx/models/portraits/female_body'/clip));duration=data.find('info').attrib['sa'][0];rig.animation_data.action=bpy.data.actions[Path(clip).stem]
        for frame in sorted({0,duration//2,duration-1}):
            world=globals_for(data.find('info'),data.find('samples'),frame,sk);matrices=world@bind;bpy.context.scene.frame_set(frame+1)
            for variant in ['base',*keys]:
                for key in body.data.shape_keys.key_blocks:key.value=0
                if variant!='base':body.data.shape_keys.key_blocks[keys[variant]].value=1.
                bpy.context.view_layer.update();source=np.asarray(pdx.read_meshfile(str(folder/(prefix+variant+'.mesh'))).find('object')[0].find('mesh').attrib['p']).reshape(-1,3);points=np.column_stack((source,np.ones(len(source))));expected=np.zeros((len(points),3))
                for slot in range(4):expected+=np.einsum('nij,nj->ni',matrices[np.maximum(ix[:,slot],0)],points)[:,:3]*w[:,slot,None]
                evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
                try:
                    positions=np.zeros(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',positions);positions=positions.reshape(-1,3)[:,[0,2,1]];error=np.linalg.norm(positions-expected,axis=1)
                finally:evaluated.to_mesh_clear()
                worst=float(error.max());assert worst<.005,(clip,frame,variant,worst)
                records.append(dict(clip=clip,frame=frame,variant=variant,max_evaluated_error_cm=worst,rms_error_cm=float(np.sqrt(np.mean(error**2)))))
    for key in body.data.shape_keys.key_blocks:key.value=0
    rig.animation_data.action=bpy.data.actions['female_body_idle_1'];bpy.context.scene.frame_set(1)
    images=[dict(name=x.name,packed=x.packed_file is not None)for x in bpy.data.images if x.type=='IMAGE'];assert all(x['packed']for x in images)
    report=dict(passed=True,reopened_blend=str(a.blend),evaluated_checks=len(records),max_evaluated_error_cm=max(x['max_evaluated_error_cm']for x in records),records=records,packed_images=images,vertices=len(body.data.vertices),triangles=len(body.data.polygons),bones=len(rig.data.bones),actual_stock_animation_samples=True,ck3_runtime_verified=False)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('REOPEN_NATIVE_BLEND_VERIFIED',len(records),'checks',report['max_evaluated_error_cm'],flush=True)

if __name__=='__main__':main()
