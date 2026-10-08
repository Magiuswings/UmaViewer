"""Render the actual stock animation samples, not an invented demonstration pose."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import bpy
from mathutils import Vector

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--fixed',type=Path,required=True);p.add_argument('--working',type=Path,required=True);p.add_argument('--before',type=Path,required=True);p.add_argument('--output-name',default='native-animation-comparison');p.add_argument('--before-label',default='Union: old bind');p.add_argument('--fixed-label',default='Union: corrected bind')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b
    sys.path.insert(0,str(Path(__file__).parent));from test_vanilla_body_animation_blender import mesh_info,globals_for
    pdx=b.parser_only(a.plugin);folder=a.game/'gfx/models/portraits/female_body';sk,_,_=mesh_info(pdx.read_meshfile(str(folder/'female_body.mesh')))
    inputs=[a.working,a.before,a.fixed]
    clips=['female_body_idle_1.anim','female_body_throneRoom_ruler1_1.anim','female_body_jockey_walk.anim'];labels=['Working sample (uma_3d.zip)',a.before_label,a.fixed_label];records=[]
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mat=bpy.data.materials.new('DiagnosticClay');mat.diffuse_color=(.61,.71,.79,1)
    for row,clip in enumerate(clips):
        data=pdx.read_meshfile(str(folder/clip));count=data.find('info').attrib['sa'][0];frame=count//2;world=globals_for(data.find('info'),data.find('samples'),frame,sk)
        maxz=-float('inf')
        for col,source in enumerate(inputs):
            tree=pdx.read_meshfile(str(source));_,parts,bind=mesh_info(tree);p,ix,w,_=parts[0];points=np.column_stack((p,np.ones(len(p))));out=np.zeros((len(p),3));matrices=world@bind
            for slot in range(4):out+=np.einsum('nij,nj->ni',matrices[np.maximum(ix[:,slot],0)],points)[:,:3]*w[:,slot,None]
            # PDX Y-up -> Blender Z-up, centimeters -> meters.
            xyz=out[:,[0,2,1]]*.01;xyz[:,0]+=col*2.15;xyz[:,2]-=row*2.1
            maxz=max(maxz,float(xyz[:,2].max()));source_node=tree.find('object')[0].find('mesh');tris=np.asarray(source_node.attrib['tri']).reshape(-1,3)[:,::-1]
            mesh=bpy.data.meshes.new(f'{row}_{col}');mesh.from_pydata(xyz.tolist(),[],tris.tolist());mesh.update();obj=bpy.data.objects.new(labels[col],mesh);bpy.context.scene.collection.objects.link(obj);mesh.materials.append(mat)
            for poly in mesh.polygons:poly.use_smooth=True
            normal=np.asarray(source_node.attrib['n']).reshape(-1,3);skinned=np.zeros_like(normal)
            for slot in range(4):skinned+=np.einsum('nij,nj->ni',matrices[np.maximum(ix[:,slot],0),:3,:3],normal)*w[:,slot,None]
            skinned/=np.maximum(np.linalg.norm(skinned,axis=1)[:,None],1e-12);mesh.normals_split_custom_set_from_vertices(skinned[:,[0,2,1]].tolist())
        records.append(dict(animation=clip,frame=frame,frames=count))
        rowlabel=['Standing idle','Throne seated','Riding (jockey_walk)'][row];curve=bpy.data.curves.new(rowlabel,'FONT');curve.body=rowlabel;curve.size=.085;obj=bpy.data.objects.new(rowlabel,curve);bpy.context.scene.collection.objects.link(obj);obj.location=(-.8,-.4,maxz+.09);obj.rotation_euler=(1.570796,0,0)
    for col,label in enumerate(labels):
        curve=bpy.data.curves.new(label,'FONT');curve.body=label;curve.align_x='CENTER';curve.size=.12
        obj=bpy.data.objects.new(label,curve);bpy.context.scene.collection.objects.link(obj);obj.location=(col*2.15,-.4,1.65);obj.rotation_euler=(1.570796,0,0)
    bpy.ops.object.camera_add(location=(2.15,-12,-.8));camera=bpy.context.object;camera.rotation_euler=(Vector((2.15,0,-.85))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=6.6;bpy.context.scene.camera=camera
    for position,power,size in [((0,-4,5),1100,5),((5,2,4),800,4)]:
        bpy.ops.object.light_add(type='AREA',location=position);light=bpy.context.object;light.data.energy=power;light.data.shape='DISK';light.data.size=size;light.rotation_euler=(Vector((2.15,0,-.85))-light.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1500;scene.render.resolution_y=1500;scene.render.resolution_percentage=100;scene.world.color=(.15,.15,.15);scene.render.image_settings.file_format='PNG';scene.render.filepath=str(a.root/(a.output_name+'.png'));scene.view_settings.view_transform='Standard'
    bpy.ops.render.render(write_still=True);(a.root/(a.output_name+'.json')).write_text(json.dumps(dict(columns=labels,rows=records,method='Direct evaluation of unmodified stock animation samples'),indent=2),encoding='utf8');print('ANIMATION_RENDER_COMPLETE',flush=True)

if __name__=='__main__':main()
