import os
"""Update only existing 1002 editable project's main-clothes geometry/BS/weights from final PDX."""
import json,sys
from pathlib import Path
import bpy,numpy as np
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));sys.path[:0]=[str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter')];from build_ck3_mod import parser_only
pd=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());fam=next(f for f in reg['families']if f['family']=='bdy1002_00');part=fam['parts']['clothes'];dest=Path(fam['directory'])/Path(fam['asset_path']).with_suffix('.blend').name;bpy.ops.wm.open_mainfile(filepath=str(dest));base=pd.read_meshfile(part['base_mesh']);targets={key:pd.read_meshfile(file)for key,file in part['shape_targets'].items()};updated=[]
for oi,obj in enumerate(base.find('object')):
 names=[b.tag for b in obj.find('skeleton')]
 for mi,node in enumerate(obj.findall('mesh')):
  object=bpy.data.objects[obj.tag+f'_slot{mi}'];mesh=object.data;p=np.array(node.attrib['p']).reshape(-1,3)[:,[0,2,1]];mesh.vertices.foreach_set('co',p.astype(np.float32).ravel());mesh.shape_keys.key_blocks['Basis'].data.foreach_set('co',p.astype(np.float32).ravel())
  for key,tree in targets.items():points=np.array(tree.find('object')[oi].findall('mesh')[mi].attrib['p']).reshape(-1,3)[:,[0,2,1]];mesh.shape_keys.key_blocks[key].data.foreach_set('co',points.astype(np.float32).ravel())
  object.vertex_groups.clear();ix=np.array(node.find('skin').attrib['ix']).reshape(-1,4);w=np.array(node.find('skin').attrib['w']).reshape(-1,4)
  for bid in np.unique(ix[w>0]):
   group=object.vertex_groups.new(name=names[int(bid)]);ids,slots=np.where((ix==bid)&(w>0));bins={}
   for i,j in zip(ids,slots):bins.setdefault(round(float(w[i,j]),3),[]).append(int(i))
   for weight,ids in bins.items():group.add(ids,weight,'REPLACE')
  bpy.context.view_layer.objects.active=object;bpy.ops.object.select_all(action='DESELECT');object.select_set(True);bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL',lock_active=False);mesh.normals_split_custom_set_from_vertices(np.array(node.attrib['n']).reshape(-1,3)[:,[0,2,1]].tolist());mesh.update();object['skirt_pose_refinement']=json.dumps(fam['skirt_pose_refinement']);updated.append(object.name)
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(dest));deliveryfile=R/'ClothingParts/AB-bdy1002_00/selected-delivery.json';delivery=json.loads(deliveryfile.read_text());delivery.update(editable_pending=False,editable_updated=True,editable_file=str(dest),editable_objects=updated);deliveryfile.write_text(json.dumps(delivery,indent=2),encoding='utf8');print('SKIRT_EDITABLE_UPDATED',str(dest),updated,flush=True)
