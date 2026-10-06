"""Blender 4.2: preserve UMA geometry, adapt CK3 rigs and export PDX morph meshes."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from rigging import adapt_rig
from morphs import topology_mapping

SHADERS = {'body_skin':'portrait_skin','body_clothing_mixed':'portrait_attachment',
           'face':'portrait_skin_face','face_effects':'portrait_skin_face',
           'hair':'portrait_hair','tail':'portrait_hair','eyebrows':'portrait_hair',
           'eyes':'portrait_eye','clothing':'portrait_attachment',
           'headwear':'portrait_attachment','footwear':'portrait_attachment'}

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')

def geometry_signature(obj):
    values = dict(vertices=[list(v.co) for v in obj.data.vertices],
                  world=[list(row) for row in obj.matrix_world],
                  faces=[list(p.vertices) for p in obj.data.polygons],
                  uv=[[list(u.uv) for u in layer.data] for layer in obj.data.uv_layers],
                  keys={k.name:[list(v.co) for v in k.data] for k in obj.data.shape_keys.key_blocks} if obj.data.shape_keys else {})
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

def material(entry,shader,config):
    mat=bpy.data.materials.new(entry['name']+'__'+shader)
    mat.use_nodes=True;mat['shader']=shader
    mat['uma_original_material']=json.dumps(entry,ensure_ascii=False)
    mat['pdx_texture_note']='Source diffuse; generated neutral PDX normal/properties. Unity shader not reproduced.'
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    bsdf=nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value=.7
    props={p['name']:p for p in entry['properties']}
    diffuse_prop=props.get('_MainTex',{})
    diffuse=diffuse_prop.get('texture')
    if diffuse:
        texture_key=json.dumps([diffuse,diffuse_prop.get('scale',[1,1]),diffuse_prop.get('offset',[0,0])],separators=(',',':'))
        path=Path(config['output'])/'textures'/config['diffuse'][texture_key]['dds']
        tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(path),check_existing=True)
        links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
        links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
    else:
        bsdf.inputs['Base Color'].default_value=tuple(props.get('_Color',{}).get('value',[1,1,1,1]))
    tex=nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(Path(config['output'])/'textures/neutral_properties.dds'),check_existing=True)
    tex.image.colorspace_settings.name='Non-Color'
    links.new(tex.outputs['Alpha'],bsdf.inputs['Roughness'])
    tex=nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(Path(config['output'])/'textures/neutral_normal.dds'),check_existing=True)
    tex.image.colorspace_settings.name='Non-Color'
    normal=nodes.new('ShaderNodeNormalMap')
    # Flat preview normal; DDS packed channels exported intact for CK3.
    normal.inputs['Color'].default_value=(.5,.5,1,1)
    separate=nodes.new('ShaderNodeSeparateColor');links.new(tex.outputs['Color'],separate.inputs[0])
    combine=nodes.new('ShaderNodeCombineColor');combine.inputs['Blue'].default_value=1
    links.new(separate.outputs['Red'],combine.inputs['Red']);links.new(tex.outputs['Alpha'],combine.inputs['Green'])
    links.new(combine.outputs[0],normal.inputs['Color']);links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
    return mat

def build(data,category,config,core):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig,names=core.make_rig(data)
    collection=bpy.data.collections.new(category);bpy.context.scene.collection.children.link(collection)
    objects=[];materials={};pairs={}
    for original in data['meshes']:
        mesh=dict(original);sections=[]
        for f in original['faces']:
            if not f['triangles'] or (category!='body_base' and f['category']!=category):continue
            shader=SHADERS[f['category']]
            pair=(f['material'],shader)
            if pair not in pairs:
                idx=len(pairs);pairs[pair]=idx
                entry=data['materials'][f['material']] if f['material']>=0 else dict(name='missing',properties=[])
                materials[idx]=material(entry,shader,config)
            sections.append(dict(f,part='body',material=pairs[pair]))
        if not sections:continue
        mesh['faces']=sections
        obj=core.make_mesh(mesh,'body',collection,rig,names,materials)
        obj['uma_category']=category;obj['uma_character_id']=data['character_id']
        obj['uma_variant']=data['variant'];obj['uma_source_renderer']=original['name']
        obj['uma_source_mesh_id']=str(original['unity_mesh_id'])
        used=sorted({v for f in sections for v in f['triangles']})
        attr=obj.data.attributes.new('uma_source_vertex',type='INT',domain='POINT')
        for a,v in zip(attr.data,used):a.value=v
        obj['uma_source_section_categories']=json.dumps([dict(category=f['category'],triangles=len(f['triangles'])//3) for f in sections])
        obj.hide_render=not original['active']
        objects.append(obj)
    return rig,objects

def select_export(objects,rig):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]

def binary_checks(path,pdx_data,objects,pdx):
    root=pdx_data.read_meshfile(str(path));counts=[]
    assert len(root.find('object'))==len(objects),'PDX export omitted a source renderer'
    for node,obj in zip(root.find('object'),objects):
        assert node.tag==obj.data.name,(node.tag,obj.data.name)
        skel=node.find('skeleton');names=[b.tag for b in skel]
        assert len(node.findall('mesh'))==len(obj.data.materials),'PDX export omitted a material slot'
        for slot,m in enumerate(node.findall('mesh')):
            if not m.attrib.get('p'):continue
            p=m.attrib['p'];n=len(p)//3;tri=m.attrib['tri']
            assert all(math.isfinite(v) for v in p)
            assert len(tri)%3==0 and all(0<=i<n for i in tri)
            assert m.find('material').attrib['shader'][0] in set(SHADERS.values())
            skin=m.find('skin');weights=skin.attrib['w'];indices=skin.attrib['ix']
            assert len(weights)==len(indices)==4*n
            assert all(abs(sum(weights[i:i+4])-1)<1e-5 for i in range(0,len(weights),4))
            assert all(-1<=i<len(names) for i in indices)
            # Plugin exports world coordinates in its defined coordinate system.
            info,ids=pdx.get_mesh_info(obj,slot,split_criteria=['id','p','uv'],sort_vertices=True)
            assert tri==info['tri']
            expected_triangles=sum(len(poly.vertices)-2 for poly in obj.data.polygons if poly.material_index==slot)
            assert len(tri)//3==expected_triangles
            assert len(p)==len(info['p'])
            assert max((abs(a-b) for a,b in zip(p,info['p'])),default=0)<1e-5
            counts.append(dict(object=node.tag,slot=slot,vertices=n,triangles=len(tri)//3,shader=m.find('material').attrib['shader'][0],bones=len(names)))
    return counts

def main():
    config=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8'))
    assert bpy.app.version[:2]==(4,2), 'PDX conversion requires Blender 4.2'
    out=Path(config['output']);src=Path(config['manifest'])
    sys.path.insert(0,str(Path(config['plugin']).parent))
    import io_pdx_mesh
    from io_pdx_mesh import pdx_data
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    io_pdx_mesh.register()
    core_path=HERE/'uma_blender_import.py'
    if not core_path.exists():core_path=HERE.parents[1]/'Assets/StreamingAssets/Blender/uma_blender_import.py'
    spec=importlib.util.spec_from_file_location('uma_core',core_path);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    manifest=json.loads(src.read_text(encoding='utf8'));results=[]
    if config.get('morphs_only'):
        previous=json.loads((out/'export-manifest.json').read_text(encoding='utf8'))
        build_morph_groups(config,previous['components'],pdx,pdx_data)
        return
    for job in manifest['jobs']:
        if config['jobs'] and job['name'] not in config['jobs']:continue
        data=json.loads((src.parent/job['snapshot']).read_text(encoding='utf8'))
        categories=list(job['categories'])
        if any(j['name']==job['name'] for j in manifest.get('body_bases',[])):categories.append('body_base')
        for category in categories:
            if config['only'] and category not in config['only']:continue
            start=time.monotonic();rig,objects=build(data,category,config,core)
            if not objects:continue
            before={o.name:geometry_signature(o) for o in objects}
            reference=config['head_reference'] if job['kind']=='head' else config['body_reference']
            report=adapt_rig(rig,objects,reference,pdx,pdx_data,job['kind'])
            rig=bpy.data.objects[report['rig_name']]
            assert all(geometry_signature(o)==before[o.name] for o in objects),'Retargeting moved geometry'
            for i,o in enumerate(objects):pdx.set_mesh_index(o.data,i)
            stem=job['name']+'__'+category
            directory=out/'components'/('chara'+data['character_id']);directory.mkdir(parents=True,exist_ok=True)
            for obj in objects:
                for mat in obj.data.materials:
                    for texture in pdx.get_material_textures(mat).values():
                        texture=Path(texture);adjacent=directory/texture.name
                        if not adjacent.exists():os.link(texture,adjacent)
            blend=directory/(stem+'.blend');mesh=directory/(stem+'.mesh')
            select_export(objects,rig)
            pdx.export_meshfile(str(mesh),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
            checks=binary_checks(mesh,pdx_data,objects,pdx)
            bpy.context.scene['uma_mesh_policy']=config['mesh_policy']
            bpy.context.scene['uma_source_snapshot']=str(src.parent/job['snapshot'])
            bpy.context.scene['uma_category']=category
            bpy.context.scene['uma_reference_skeleton']=reference
            bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
            bpy.ops.wm.save_as_mainfile(filepath=str(blend))
            write(directory/(stem+'.rig.json'),report)
            item=dict(name=stem,job=job['name'],character_id=data['character_id'],variant=data['variant'],kind=job['kind'],category=category,
                      blend=blend.relative_to(out).as_posix(),mesh=mesh.relative_to(out).as_posix(),
                      source_snapshot=job['snapshot'],objects=[dict(name=o.name,renderer=o['uma_source_renderer'],geometry_sha256=before[o.name],vertices=len(o.data.vertices),triangles=len(o.data.polygons)) for o in objects],
                      binary_checks=checks,rig_report=(directory/(stem+'.rig.json')).relative_to(out).as_posix(),seconds=round(time.monotonic()-start,3))
            results.append(item);write(out/'export-manifest.json',dict(blender=bpy.app.version_string,plugin_version=io_pdx_mesh.IO_PDX_INFO['version'],mesh_policy=config['mesh_policy'],components=results,morph_groups=[]))
            print('PDX_COMPONENT '+stem,flush=True)
    # Apparel grouping is driven by verified connectivity/UVs; never force a
    # different silhouette or costume onto an unrelated vertex topology.
    build_morph_groups(config,results,pdx,pdx_data)

def build_morph_groups(config,results,pdx,pdx_data):
    out=Path(config['output'])
    from morphs import add_shape_key,make_blendshape_object
    index=json.loads((out/'apparel-index.json').read_text(encoding='utf8'))
    records={r['id']:r for r in index['records']}
    lookup={(item['job'],item['category']):item for item in results}
    groups=[];rejected=[]
    def component(record):
        category='body_base' if record['category']=='whole_mesh' else record['category']
        item=lookup.get((record['job'],category))
        if item is None:return None,None
        obj=next((o for o in item['objects'] if o['renderer']==record['mesh_name']),None)
        return item,obj
    def load_object(item,description):
        with bpy.data.libraries.load(str(out/item['blend']),link=False) as (original,loaded):
            if description['name'] not in original.objects:raise ValueError('Missing source object')
            loaded.objects=[description['name']]
        return loaded.objects[0]
    source_root=Path(config['manifest']).parent
    def source_partitions(item,description):
        data=json.loads((source_root/item['source_snapshot']).read_text(encoding='utf8'))
        mesh=next(m for m in data['meshes'] if m['name']==description['renderer'])
        return {tuple(sorted(f['triangles'][i:i+3])):f['category'] for f in mesh['faces'] for i in range(0,len(f['triangles']),3)}
    for indexed in index['compatible_groups']:
        base_record=records[indexed['base']]
        if base_record.get('virtual_subset'):continue
        base_item,base_desc=component(base_record)
        if base_item is None or base_desc is None:continue
        targets=[]
        for target_id in indexed['targets']:
            r=records[target_id];item,desc=component(r)
            if item and desc:targets.append((r,item,desc))
        if not targets:continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        base=load_object(base_item,base_desc)
        rig=next(m.object for m in base.modifiers if m.type=='ARMATURE')
        bpy.context.scene.collection.objects.link(rig)
        bpy.context.scene.collection.objects.link(base)
        # An individual Renderer can form a morph even when another object
        # in the broad category has different topology. Keep that scope explicit.
        group_name=base_item['name']+'__'+base_record['mesh_name']+'__morphs'
        directory=out/'morphs'/group_name;directory.mkdir(parents=True,exist_ok=True)
        shape_name=base.data.name
        pdx.set_mesh_index(base.data,0)
        for mat in base.data.materials:
            for texture in pdx.get_material_textures(mat).values():
                texture=Path(texture);adjacent=directory/texture.name
                if not adjacent.exists():os.link(texture,adjacent)
        base_path=directory/'base.mesh'
        select_export([base],rig)
        pdx.export_meshfile(str(base_path),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
        base_data=pdx_data.read_meshfile(str(base_path))
        base_meshes=base_data.find('object')[0].findall('mesh')
        target_reports=[]
        if base.data.shape_keys:raise ValueError('Existing source Shape Keys need an explicit morph merge policy')
        basis_hash=geometry_signature(base)
        for record,item,description in targets:
            target=load_object(item,description)
            mapping,reason=topology_mapping(base,target)
            if mapping is None:
                rejected.append(dict(base=base_record['id'],target=record['id'],reason=reason));continue
            key_name='chara'+record['character_id']+'__'+item['variant']+'__'+record['mesh_name']
            if base.data.shape_keys and key_name in base.data.shape_keys.key_blocks:
                key_name+='__'+str(len(target_reports))
            key=add_shape_key(base,target,key_name)
            clone=make_blendshape_object(base,target,'PDX morph temporary')
            # Per-vertex source normals are retained separately from coordinates.
            target_normals=[None]*len(target.data.vertices)
            for loop in target.data.loops:target_normals[loop.vertex_index]=target.data.corner_normals[loop.index].vector.copy()
            if all(n is not None for n in target_normals):
                clone.data.normals_split_custom_set_from_vertices([target_normals[i] for i in mapping])
            bpy.context.scene.collection.objects.link(clone)
            base.data.name=shape_name+'__working'
            clone.data.name=shape_name
            target_path=directory/(key_name+'.mesh')
            select_export([clone],rig)
            pdx.export_meshfile(str(target_path),exp_mesh=True,exp_skel=True,exp_locs=False,exp_selected=True,as_blendshape=True,sort_verts='+')
            binary=pdx_data.read_meshfile(str(target_path))
            assert binary.find('object')[0].tag==base_data.find('object')[0].tag
            meshes=binary.find('object')[0].findall('mesh')
            assert len(base_meshes)==len(meshes)
            for a,b in zip(base_meshes,meshes):
                assert len(a.attrib['p'])==len(b.attrib['p']) and a.attrib['tri']==b.attrib['tri']
                for uv in ('u0','u1','u2','u3'):assert a.attrib.get(uv)==b.attrib.get(uv)
            delta=max(((base.data.vertices[i].co-target.data.vertices[j].co).length for i,j in enumerate(mapping)),default=0)
            base_partition=source_partitions(base_item,base_desc)
            target_partition=source_partitions(item,description)
            base_ids=[i.value for i in base.data.attributes['uma_source_vertex'].data]
            target_ids=[i.value for i in target.data.attributes['uma_source_vertex'].data]
            changes=[]
            for polygon in base.data.polygons:
                bkey=tuple(sorted(base_ids[i] for i in polygon.vertices))
                tkey=tuple(sorted(target_ids[mapping[i]] for i in polygon.vertices))
                bcategory=base_partition[bkey];tcategory=target_partition[tkey]
                if bcategory!=tcategory:changes.append(dict(base_source_triangle=list(bkey),target_source_triangle=list(tkey),base_category=bcategory,target_category=tcategory))
            target_reports.append(dict(key=key.name,source_job=item['job'],source_component=item['blend'],source_renderer=record['mesh_name'],
                                       mesh=target_path.relative_to(out).as_posix(),mapping_reason=reason,max_delta=delta,
                                       shape_preserves_source_coordinates=True,weights='Base rig/weights reused; target original weights remain in its component file',
                                       materials='Base material slots/textures retained; morph is geometry only',
                                       source_partition_changes=dict(count=len(changes),faces=changes,policy='Base shader classification retained; target original classification preserved in target component')))
            clone_data=clone.data;bpy.data.objects.remove(clone,do_unlink=True);bpy.data.meshes.remove(clone_data)
            base.data.name=shape_name
        if not target_reports:continue
        assert all(tuple(a.co)==tuple(b.co) for a,b in zip(base.data.vertices,base.data.shape_keys.key_blocks[0].data))
        base['uma_morph_scope']='Whole source body' if base_record['category']=='whole_mesh' else 'One original Renderer in '+base_record['category']
        base['uma_morph_base_source']=base_record['id']
        base['uma_morph_basis_geometry_signature']=basis_hash
        bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=0
        blend=directory/'editable.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        lines=['# PDX mesh asset fragment; integrate names/genes in your own CK3 mod.','pdxmesh = {',
               '    name = "'+group_name+'"','    file = "base.mesh"']
        for t in target_reports:lines.append('    blend_shape = { id = "'+t['key']+'" type = "'+Path(t['mesh']).name+'" }')
        lines.append('}')
        (directory/'morph.asset').write_text('\n'.join(lines)+'\n',encoding='utf8')
        groups.append(dict(name=group_name,category=base_record['category'],renderer=base_record['mesh_name'],
                           base_job=base_record['job'],base_record=base_record['id'],base_selection='First deterministic source in compatible family',
                           blend=blend.relative_to(out).as_posix(),base_mesh=base_path.relative_to(out).as_posix(),targets=target_reports,
                           scope=base['uma_morph_scope'],source_coordinates_unchanged=True))
        print('PDX_MORPH_GROUP '+group_name+' targets='+str(len(target_reports)),flush=True)
    report=json.loads((out/'export-manifest.json').read_text(encoding='utf8'))
    report['morph_groups']=groups;report['morph_rejections']=rejected
    report['cross_character_morph_policy']='Require verified directed connectivity and all UV layers; base geometry never warped'
    write(out/'export-manifest.json',report)

if __name__=='__main__':main()
