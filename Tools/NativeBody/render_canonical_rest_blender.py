"""Matched clay views of real source topology, rebuilt skin, and native poses."""
import argparse,json,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

def main():
    p=argparse.ArgumentParser()
    for name in ('repo','plugin','root','stock'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));sys.path.insert(0,str(Path(__file__).parent))
    from build_ck3_mod import parser_only
    from test_vanilla_body_animation_blender import mesh_info,globals_for
    from rebuild_body_rest_blender import welded_normals
    pdx=parser_only(a.plugin);stock=pdx.read_meshfile(str(a.stock));sk,_,_=mesh_info(stock)
    inputs=np.load(a.root/'source-skin-profiles.npz');faces=inputs['faces'];inverse=inputs['inverse'];C=np.array([[-1,0,0],[0,0,-1],[0,1,0]])
    old=inputs['source_basis']@C.T;skin=inputs['h1_s0_b2']@C.T
    fixed=pdx.read_meshfile(str(a.root/'meshes/uma_0001_body_base.mesh'));node=fixed.find('object')[0].find('mesh');fp=np.array(node.attrib['p']).reshape(-1,3)[:,[0,2,1]]*.01;ff=np.array(node.attrib['tri']).reshape(-1,3)[:,::-1]
    sn=stock.find('object')[0].find('mesh');sp=np.array(sn.attrib['p']).reshape(-1,3)[:,[0,2,1]]*.01;sf=np.array(sn.attrib['tri']).reshape(-1,3)[:,::-1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat=bpy.data.materials.new('NeutralClay');mat.diffuse_color=(.63,.64,.66,1);mat.use_nodes=True
    b=mat.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(.63,.64,.66,1);b.inputs['Roughness'].default_value=.8
    def object_at(label,p,f,location):
        mesh=bpy.data.meshes.new(label);mesh.from_pydata(p.tolist(),[],f.tolist());mesh.update();obj=bpy.data.objects.new(label,mesh);bpy.context.collection.objects.link(obj);obj.location=location;mesh.materials.append(mat)
        for poly in mesh.polygons:poly.use_smooth=True
        _,weld=np.unique(np.round(p,6),axis=0,return_inverse=True)
        mesh.normals_split_custom_set_from_vertices(welded_normals(p,f,weld).tolist())
        return obj
    def text(label,location,size=.10):
        c=bpy.data.curves.new(label,'FONT');c.body=label;c.size=size;c.align_x='CENTER';o=bpy.data.objects.new(label,c);bpy.context.collection.objects.link(o);o.location=location;o.rotation_euler=(np.pi/2,0,0)
    columns=[('Original 0004 / 3,510',old,faces[:,::-1]),('Rebuilt skin / 3,510',skin,faces[:,::-1]),('Baked A rest / 3,510',fp,ff),('Vanilla female rest',sp,sf)]
    for i,(label,p,f)in enumerate(columns):object_at(label,p,f,(i*1.6,0,0));text(label,(i*1.6,-.35,1.56),.075)
    # Native animations use the exact exported inverse binds and stock t/q/s.
    rows=[]
    for row,clip in enumerate(('female_body_idle_1.anim','female_body_praying_standing.anim','female_body_throneRoom_ruler1_1.anim','female_body_jockey_walk.anim'),1):
        file=a.stock.parent/clip
        if not file.is_file():continue
        anim=pdx.read_meshfile(str(file));frame=anim.find('info').attrib['sa'][0]//2;world=globals_for(anim.find('info'),anim.find('samples'),frame,sk)
        outputs=[]
        for col,data in enumerate((stock,fixed)):
            _,parts,bind=mesh_info(data);p,ix,w,_=parts[0];h=np.column_stack((p,np.ones(len(p))));out=np.zeros_like(p);T=world@bind
            for slot in range(4):out+=np.einsum('nij,nj->ni',T[np.maximum(ix[:,slot],0)],h)[:,:3]*w[:,slot,None]
            ns=data.find('object')[0].find('mesh');tris=np.array(ns.attrib['tri']).reshape(-1,3)[:,::-1]
            outputs.append((col,out[:,[0,2,1]]*.01,tris))
        center=float((outputs[0][1][:,2].min()+outputs[0][1][:,2].max())/2)
        for col,points,tris in outputs:
            offset=-row*1.75+.7-center
            object_at(clip+str(col),points,tris,(col*1.6+1.6,0,offset));text(('Vanilla'if col==0 else'Rebuilt')+' : '+clip.replace('female_body_','').replace('.anim',''),(col*1.6+1.6,-.35,-row*1.75+1.55),.065)
        rows.append(dict(clip=clip,frame=frame))
    scene=bpy.context.scene;scene.world=bpy.data.worlds.new('DiagnosticWorld');scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1800;scene.render.resolution_y=1900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world.color=(.12,.12,.12);scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    bpy.ops.object.camera_add(location=(2.4,-15,-2.3));camera=bpy.context.object;camera.rotation_euler=(Vector((2.4,0,-2.3))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=8.7;scene.camera=camera
    for pos,energy,size in [((0,-5,4),500,5),((6,-1,2),150,5),((2,4,0),350,5)]:
        bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=energy;o.data.size=size;o.rotation_euler=(Vector((2.4,0,-1.5))-o.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(a.root/'rest-and-native-animation.png');bpy.ops.render.render(write_still=True)
    # Close-up of the actual skin surface under raking light, with no diffuse
    # texture that could hide or simulate a clothing seam.
    for o in list(bpy.data.objects):
        if o.type in ('MESH','FONT'):bpy.data.objects.remove(o,do_unlink=True)
    for i,(label,p)in enumerate([('Original 0004',old),('Rebuilt skin',skin)]):
        object_at(label,p,faces[:,::-1],(i*.8,0,0));text(label,(i*.8,-.15,1.61),.075)
    camera.location=(.4,-4,1.05);camera.rotation_euler=(Vector((.4,0,1.05))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=1.60
    scene.render.resolution_x=1700;scene.render.resolution_y=1100;scene.render.filepath=str(a.root/'skin-surface-comparison.png');bpy.ops.render.render(write_still=True)
    # Original-density wireframe and the actual feet in fitted A rest.
    for o in list(bpy.data.objects):
        if o.type in ('MESH','FONT'):bpy.data.objects.remove(o,do_unlink=True)
    wire=bpy.data.materials.new('DiagnosticWire');wire.diffuse_color=(.02,.025,.03,1)
    for i,(label,points,f)in enumerate(columns[:3]):
        o=object_at(label,points,f,(i*1.5,0,0));o.data.materials.append(wire);m=o.modifiers.new('Original density edges','WIREFRAME');m.thickness=.0005;m.use_replace=False;m.material_offset=1;text(label,(i*1.5,-.15,1.62),.075)
    camera.location=(1.5,-8,.72);camera.rotation_euler=(Vector((1.5,0,.72))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=4.65
    scene.render.resolution_x=1800;scene.render.resolution_y=850;scene.render.filepath=str(a.root/'canonical-density-wireframe.png');bpy.ops.render.render(write_still=True)
    for o in list(bpy.data.objects):
        if o.type in ('MESH','FONT'):bpy.data.objects.remove(o,do_unlink=True)
    for i,(label,points,f)in enumerate(columns[2:]):
        o=object_at(label,points,f,(i*1.6,0,0));text(label,(i*1.6,-.15,1.61),.075)
    camera.location=(.8,-8,.75);camera.rotation_euler=(Vector((.8,0,.75))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=3.1
    scene.render.resolution_x=1500;scene.render.resolution_y=950;scene.render.filepath=str(a.root/'fitted-a-rest-front.png');bpy.ops.render.render(write_still=True)
    for o in list(bpy.data.objects):
        if o.type=='MESH':o.rotation_euler[2]=np.pi/2
        elif o.type=='FONT':bpy.data.objects.remove(o,do_unlink=True)
    camera.location=(.8,-5,.09);camera.rotation_euler=(Vector((.8,0,.09))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=2.1
    scene.render.resolution_x=1700;scene.render.resolution_y=450;scene.render.filepath=str(a.root/'rest-feet-side.png');bpy.ops.render.render(write_still=True)
    write=dict(rest_columns=[x[0]for x in columns],animations=rows,clay_texture_disabled=True,geometric_normals=True,same_camera_and_lighting=True)
    (a.root/'render-report.json').write_text(json.dumps(write,indent=2),encoding='utf8')

if __name__=='__main__':main()
