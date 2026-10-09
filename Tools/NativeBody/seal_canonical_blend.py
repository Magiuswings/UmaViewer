"""Set a useful opening view and decode packed PDX normals for Blender preview."""
import argparse,json,sys
from pathlib import Path
import bpy
from mathutils import Euler

def main():
    p=argparse.ArgumentParser()
    for name in ('repo','root','textures'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'))
    from blender_pipeline import geometry_signature
    file=a.root/'uma_0001_body.blend';bpy.ops.wm.open_mainfile(filepath=str(file));body=bpy.data.objects['uma_0001_body'];rig=bpy.data.objects['uma_0001_body_vanillaRig'];before=geometry_signature(body)
    mat=body.data.materials[0];nodes=mat.node_tree.nodes;links=mat.node_tree.links
    bsdf=nodes.get('Principled BSDF')
    tex=next(n for n in nodes if n.type=='TEX_IMAGE' and n.image.name.endswith('_normal.dds'))
    normal=next(n for n in nodes if n.type=='NORMAL_MAP')
    for link in list(normal.inputs['Color'].links):links.remove(link)
    separate=nodes.new('ShaderNodeSeparateColor');combine=nodes.new('ShaderNodeCombineColor');combine.inputs['Blue'].default_value=1.
    links.new(tex.outputs['Color'],separate.inputs[0]);links.new(separate.outputs['Green'],combine.inputs['Red']);links.new(tex.outputs['Alpha'],combine.inputs['Green']);links.new(combine.outputs[0],normal.inputs['Color'])
    diffuse=next(n for n in nodes if n.type=='TEX_IMAGE' and '_diffuse.dds'in n.image.name)
    diffuse.image=bpy.data.images.load(str(a.textures/'uma_0001_body_skin1_diffuse.dds'),check_existing=True)
    rig.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;space.region_3d.view_distance=210.;space.region_3d.view_location=(0,0,73);space.region_3d.view_rotation=Euler((1.57079632679,0,0)).to_quaternion();space.region_3d.view_perspective='ORTHO';space.shading.type='SOLID';space.shading.color_type='MATERIAL'
    bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
    assert geometry_signature(body)==before
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True);bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(file))
    (a.root/'editor-preview.json').write_text(json.dumps(dict(opening_view='Front orthographic / real stock idle',hide_rig_overlay_by_default=True,packed_pdx_normal_G_alpha_decoded=True,default_skin_index=1,geometry_keys_uv_and_object_transforms_unchanged=True),indent=2),encoding='utf8')

if __name__=='__main__':main()
