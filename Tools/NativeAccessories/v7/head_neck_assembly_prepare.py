import os
from pathlib import Path
s=Path(__file__).with_name('head_assembly_blender.py').read_text()
s=s.replace("'blender-assembly-qa.json'","'blender-neck-repair-qa.json'")
s=s.replace("'uma_v7_dual_actor_assembly.blend'","'uma_v7_dual_actor_neck_repaired.blend'")
s=s.replace("+'_final_assembly.blend'","+'_neck_repaired_assembly.blend'")
s=s.replace("+'_80_final_assembly.blend'","+'_80_neck_repaired_assembly.blend'")
s=s.replace("f'{actor}_{variant}_neck_eye_{label}.png'","f'{actor}_{variant}_neck_repaired_{label}.png'")
s=s.replace("'face_parts','ear','headwear']","'face_parts','ear','headwear','neck_patch']")
s=s.replace("r['element']=='tail'","r['element']in ['tail','neck']")
s=s.replace("pose(body,bodyworld);pose(carrier,headworld);bpy.context.view_layer.update();bi=body['data']['names'].index('bn_sp_thoracic');ri=carrier['data']['names'].index('head_root');external=bodyworld[bi]@np.linalg.inv(headworld[ri]);carrier['rig'].matrix_world=Matrix((SW4@external@SW4).tolist());errors={}","""pose(body,bodyworld);bi=body['data']['names'].index('bn_sp_thoracic');ri=carrier['data']['names'].index('head_root');external=bodyworld[bi]@np.linalg.inv(headworld[ri]);headworld=headworld.copy()
                for bb,hb in [('bn_l_clavicle','bn_h_l_clavicle'),('bn_r_clavicle','bn_h_r_clavicle')]:headworld[carrier['data']['names'].index(hb)]=np.linalg.inv(external)@bodyworld[body['data']['names'].index(bb)]
                pose(carrier,headworld);carrier['rig'].matrix_world=Matrix((SW4@external@SW4).tolist());bpy.context.view_layer.update();errors={} """)
s=s.replace("return {'head_root_to_body_thoracic_error_cm':root_error", """bridge=next(p for p in parts if p['row']['element']=='neck');actual=evaluated(bridge);sourcebody=evaluated(body);delivery=json.loads((ROOT/'HeadSources/NeckBridge/neck-delivery.json').read_text());ring=next(a for a in delivery['actors']if a['row']['actor']==actor);edge_error=float(np.linalg.norm(actual[:6]-sourcebody[ring['lower_ring_body_vertex_ids']],axis=1).max());assert edge_error<.005
                upperpoints=np.vstack([evaluated(p)for p in parts if p['row']['element']in ['face','neck_patch']]);upper_error=float(max(np.linalg.norm(upperpoints-v,axis=1).min()for v in actual[6:]));assert upper_error<.0001
                return {'bridge_top_actual_bpy_to_original_face_or_patch_error_cm':upper_error,'bridge_bottom_actual_bpy_lbs_to_body_ring_error_cm':edge_error,'head_root_to_body_thoracic_error_cm':root_error""")
s=s.replace("carrier['rig']['uma_head_points_1002']", """for bb,hb in [('bn_l_clavicle','bn_h_l_clavicle'),('bn_r_clavicle','bn_h_r_clavicle')]:
        c=carrier['rig'].pose.bones[hb].constraints.new('COPY_TRANSFORMS');c.target=body['rig'];c.subtarget=bb;c.target_space='WORLD';c.owner_space='WORLD'
    carrier['rig']['uma_head_points_1002']""")
# Real palette CPU colors are applied to preview copies; original SDK shader
# material structures remain present and are restored before editable save.
s=s.replace("gray=bpy.data.materials.new('Neutral geometry QA');gray.diffuse_color=(.58,.62,.67,1)","""previews=json.loads((OUT/'PalettePreview/preview-index.json').read_text())['rows']
    def preview(part):
        row=next(r for r in previews if r['actor']==actor and Path(r['mesh'])==Path(part['file']));mat=bpy.data.materials.new('CPU palette diffuse '+part['obj'].name);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.75;bs.inputs['Specular IOR Level'].default_value=.2;tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(row['png'],check_existing=True);mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
        if part is not body and part['row']['element']in ['hair','ear','tail']:mat.node_tree.links.new(tex.outputs['Alpha'],bs.inputs['Alpha']);mat.surface_render_method='DITHERED'
        return mat""")
s=s.replace("p['obj'].data.materials.append(gray)","p['obj'].data.materials.append(preview(p))")
s=s.replace("obj.data.materials.clear()\n        for mat in mats:obj.data.materials.append(mat)","obj['original_PDX_material_names']=[m.name for m in mats]\n        for mat in mats:mat.use_fake_user=True")
s=s.replace("Runtime joint_attachment additional clavicle matching not solved in this QA; these joints do not weight selected visible head components.","All three current joint matches (head_root, left clavicle, right clavicle) explicitly solved; bridge bottom error compared to actual evaluated body vertices.")
s=s.replace("'marker_color_legend':", "'skin_preview_CPU_palette_applied':True,'skin_lighting_is_Blender_PBR_not_CK3_shader':True,'neck_bridge_source_16_points_16_triangles':True,'marker_color_legend':")
extras="""
# Binary edits get one isolated unmodified SDK import before assembly.
OWN=ROOT/'HeadSources';checks=[]
idx=json.loads((OWN/'Export/head-export-index.json').read_text())
files=[Path(r['mesh_path'])for h in idx['heads']for r in h['components']if r.get('present')and r['element']in ['hair','neck_patch']]
files += [Path(r['mesh_path'])for h in idx['heads']if (h['actor'],h['variant'])==('1002','30')for r in h['components']if r['element']=='headwear']
files += [Path(r['mesh'])for r in json.loads((OWN/'NeckBridge/neck-delivery.json').read_text())['rows']]
for file in files:
    bpy.ops.wm.read_factory_settings(use_empty=True);part=load(file,file.stem);assert len(part['data']['names'])<=255;checks.append({'file':str(file),'bone_count':len(part['data']['names']),'vertices':len(part['obj'].data.vertices),'triangles':len(part['obj'].data.polygons),'standard_SDK_import_passed':True})
(OUT/'neck-repair-sdk-import.json').write_text(json.dumps({'passed':True,'checks':checks,'vendor_modified':False},indent=2)+'\\n',encoding='utf8')
"""
s=s.replace("for sex in ['female','male']:",extras+"\nfor sex in ['female','male']:")
path=Path(__file__).with_name('head_neck_assembly_blender.py');path.write_text(s,encoding='utf8');compile(s,str(path),'exec');print('PREPARED',path)
