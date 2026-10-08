"""Render before/after full body and abdomen in texture and pure geometry modes."""
import argparse,importlib.util,json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--old',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.root/'previews';out.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('qa_core',args.repo/'Assets/StreamingAssets/Blender/uma_blender_import.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    for version,folder in (('before',args.old),('after',args.root)):
        m=json.loads((folder/'manifest.json').read_text(encoding='utf8'));job=next(j for j in m['jobs'] if j['name'].endswith('_1_0_2'));data=json.loads((folder/job['snapshot']).read_text(encoding='utf8'))
        for mode in ('texture','gray'):
            bpy.ops.wm.read_factory_settings(use_empty=True);rig,names=core.make_rig(data);rig.hide_render=True
            collection=bpy.data.collections.new('QA');bpy.context.scene.collection.children.link(collection)
            mat=bpy.data.materials.new('QA material');mat.use_nodes=True;bsdf=mat.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.8;bsdf.inputs['Base Color'].default_value=(.5,.5,.5,1)
            if mode=='texture':
                prop=next(x for x in data['materials'][0]['properties'] if x['name']=='_MainTex');tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(folder/m['resources']/prop['texture']));mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
            obj=core.make_mesh(data['meshes'][0],'body',collection,rig,names,{0:mat});scene=bpy.context.scene
            scene.render.engine='BLENDER_EEVEE_NEXT';scene.eevee.taa_render_samples=32;scene.view_settings.view_transform='Standard'
            scene.world=bpy.data.worlds.new('QA World');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.16,.16,1)
            for pos,power in (((-2,-3,3),150),((2,-2,2),70),((0,3,3),80)):
                light=bpy.data.lights.new('QA light','AREA');light.energy=power;light.size=3;lo=bpy.data.objects.new(light.name,light);scene.collection.objects.link(lo);lo.location=pos;lo.rotation_euler=(Vector((0,0,.8))-lo.location).to_track_quat('-Z','Y').to_euler()
            cam=bpy.data.objects.new('QA camera',bpy.data.cameras.new('QA camera'));scene.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO'
            for view,target,scale,position,size in (
                ('front',(0,0,.72),1.8,(0,-4,.72),(800,1000)),
                ('back',(0,0,.72),1.8,(0,4,.72),(800,1000)),
                ('abdomen',(0,-.04,1.015),.25,(0,-3,1.015),(640,640)),
                ('neck',(0,0,1.30),.22,(0,-3,1.30),(640,640)),
                ('thigh',(0,0,.77),.35,(0,-3,.77),(640,640))):
                cam.location=position;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
                scene.render.resolution_x,scene.render.resolution_y=size;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.filepath=str(out/(version+'__'+mode+'__'+view+'.png'));bpy.ops.render.render(write_still=True)
            print('ENVELOPE_QA_RENDERED',version,mode,flush=True)

if __name__=='__main__':main()
