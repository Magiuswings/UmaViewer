"""Export a static CK3 preview pose without editing or saving source mesh coordinates."""
import argparse
import json
from pathlib import Path
import sys
import math
import bpy
from mathutils import Matrix

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blend',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pdx-plugin',type=Path,required=True)
    p.add_argument('--pose',choices=('rest','relaxed'),default='relaxed')
    p.add_argument('--frames',type=int,default=30)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.frames<2:p.error('CK3 preview animation requires at least two actual samples')
    assert bpy.app.version[:2]==(4,2)
    sys.path.insert(0,str(args.pdx_plugin.parent))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    io_pdx_mesh.register()
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    assert len(rigs)==1
    rig=rigs[0]
    before={o.name:[tuple(v.co) for v in o.data.vertices] for o in bpy.context.scene.objects if o.type=='MESH'}
    for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    if args.pose=='relaxed':
        for side in ('l','r'):
            bone=rig.pose.bones['bn_'+side+'_shoulder']
            elbow=rig.pose.bones['bn_'+side+'_elbow']
            direction=elbow.head-bone.head
            angle=math.pi/4 if direction.x>0 else -math.pi/4
            pivot=bone.head.copy()
            bone.matrix=Matrix.Translation(pivot)@Matrix.Rotation(angle,4,'Y')@Matrix.Translation(-pivot)@bone.matrix
            bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
    args.output.parent.mkdir(parents=True,exist_ok=True)
    pdx.export_animfile(str(args.output.resolve()),frame_start=1,frame_end=args.frames)
    anim=pdx_data.read_meshfile(str(args.output.resolve()))
    info=anim.find('info');samples=anim.find('samples')
    assert info.attrib['j']==[134] and info.attrib['sa']==[args.frames]
    # IO PDX omits constant animation channels. CK3 needs an actual sample
    # buffer here, so serialize repeated REAL pose offsets, without changing
    # the captured pose or introducing artificial movement.
    bones=list(info)
    for bone in bones:bone.attrib['sa']=['tqs']
    for channel in ('t','q','s'):
        one=[v for bone in bones for v in bone.attrib[channel]]
        samples.attrib[channel]=one*args.frames
    pdx_data.write_animfile(str(args.output.resolve()),anim)
    reread=pdx_data.read_meshfile(str(args.output.resolve()))
    assert len(reread.find('samples').attrib['t'])==args.frames*134*3
    assert all([tuple(v.co) for v in bpy.data.objects[n].data.vertices]==positions for n,positions in before.items())
    args.output.with_suffix('.json').write_text(json.dumps(dict(pose=args.pose,bones=134,frames=args.frames,constant_real_samples=True,source_mesh_coordinates_unchanged=True,source_blend=str(args.blend),limitations='Static preview pose only; original animation translations are not retargeted'),indent=2),encoding='utf8')
    print('MOD_POSE_EXPORTED '+str(args.output),flush=True)

if __name__=='__main__':main()
