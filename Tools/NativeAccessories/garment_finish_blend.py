import os
import bpy,numpy as np
from pathlib import Path
R=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001")) / 'clothing-parts';a=np.load(R/'garment-prepared.npz');bpy.ops.wm.open_mainfile(filepath=str(R/'uma_1001_clothing_00.blend'));o=bpy.data.objects['uma_1001_clothing_00'];bpy.context.view_layer.objects.active=o;bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL',lock_active=False);basis=o.shape_key_add(name='Basis')
for tag,key in [('b0','bs_body_breast_shape_1'),('b1','bs_body_breast_shape_2'),('b3','bs_body_breast_shape_3'),('b4','bs_body_breast_shape_4'),('s1','bs_body_gaunt_1'),('s2','bs_body_fat_1')]:
 k=o.shape_key_add(name=key);k.data.foreach_set('co',(a[tag]*100).astype(np.float32).ravel());k.relative_key=basis;k.value=0
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01;bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(R/'uma_1001_clothing_00.blend'));print('GARMENT_EDITABLE_KEYS_SAVED',flush=True)
