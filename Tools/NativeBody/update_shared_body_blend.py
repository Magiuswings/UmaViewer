"""Update the editable body normals and names, keeping vertices and shape keys exact."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import bpy

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--blend',type=Path,required=True);p.add_argument('--mod',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b;pdx=b.parser_only(a.plugin);bpy.ops.wm.open_mainfile(filepath=str(a.blend));body=bpy.data.objects['1001_body'];rig=bpy.data.objects['1001_body_vanilla_rig'];data=pdx.read_meshfile(str(a.mod/'gfx/models/portraits/uma/0001/uma_0001_body_base.mesh'));mesh=data.find('object')[0].find('mesh');points=np.asarray(mesh.attrib['p']).reshape(-1,3);current=np.asarray([v.co[:]for v in body.data.vertices])[:,[0,2,1]];assert np.array_equal(current,points)
    signatures={k.name:np.asarray([v.co[:]for v in k.data])for k in body.data.shape_keys.key_blocks};normals=np.asarray(mesh.attrib['n']).reshape(-1,3);body.data.normals_split_custom_set_from_vertices(normals[:,[0,2,1]].tolist());body.name='uma_0001_body';body.data.name='M_Body_body';rig.name='uma_0001_body_rig';body['normal_policy']='Native idle geometric skin normals, inverted through preserved skin matrices';body['shared_model_id']='0001'
    for image in bpy.data.images:
        if image.name.startswith('1001_body_'):image.name='uma_0001_body_'+image.name.removeprefix('1001_body_')
    for key,expected in signatures.items():assert np.array_equal(np.asarray([v.co[:]for v in body.data.shape_keys.key_blocks[key].data]),expected)
    a.output.parent.mkdir(parents=True,exist_ok=True);bpy.context.preferences.filepaths.save_version=0;bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(a.output));report=dict(passed=True,positions_and_all_shape_keys_exact=True,bones=134,body_name=body.name,rig_name=rig.name,normal_policy=body['normal_policy'],ck3_visual_runtime_verified=False);a.output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('SHARED_BODY_BLEND_UPDATED',flush=True)

if __name__=='__main__':main()
