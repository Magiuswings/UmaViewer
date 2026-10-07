"""Render the delivered bodies and measured union coverage; never save source blends."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

COLORS={'0004_skin':(.83,.58,.39,1),'0009_skin':(.12,.8,.34,1),'0004_fill':(.62,.14,.74,1)}

def render(objects,path,back=False):
    scene=bpy.context.scene
    points=[obj.matrix_world@v.co for obj in objects for v in obj.data.vertices]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center=(lo+hi)/2
    cam=bpy.data.objects.new('Skin validation camera',bpy.data.cameras.new('Skin validation camera'));scene.collection.objects.link(cam)
    scene.camera=cam;cam.location=center+Vector((0,4 if back else -4,.05));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=max(hi.z-lo.z,(hi.x-lo.x)*1.5)*1.12
    for pos,energy in (((3,-4,4),140),((-3,-2,2),90),((0,4,3),140)):
        d=bpy.data.lights.new('Skin validation light','AREA');d.energy=energy;d.size=4
        obj=bpy.data.objects.new(d.name,d);scene.collection.objects.link(obj);obj.location=center+Vector(pos);obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('Skin validation world');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.22,.22,.22,1)
    scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=480;scene.render.resolution_y=720;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard';scene.render.film_transparent=False
    scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)

def main():
    config=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8'))
    assert bpy.app.version[:2]==(4,2)
    out=Path(config['output']);source=Path(config['source_manifest']).parent
    dest=out/'previews';dest.mkdir(exist_ok=True)
    delivered=json.loads((out/'export-manifest.json').read_text(encoding='utf8'))
    detail=json.loads((source/'coverage-detail.json').read_text(encoding='utf8'))
    coverage_config=json.loads((source/'coverage-config.json').read_text(encoding='utf8'))
    for item in delivered['components']:
        if item['category']!='body_base':continue
        for mode in ('skin','coverage'):
            for side in ('front','back'):
                bpy.ops.wm.open_mainfile(filepath=str(out/item['blend']))
                objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
                if mode=='coverage':
                    entry=next(e for e in coverage_config['bodies'] if e['name']==item['job'])
                    data=json.loads(Path(entry['snapshot_path']).read_text(encoding='utf8'))
                    for obj in objects:
                        mi=next(i for i,m in enumerate(data['meshes']) if m['name']==obj['uma_source_renderer'])
                        original=data['meshes'][mi]
                        record=next(r for r in detail['records'] if r['job']==item['job'] and r['mesh_index']==mi)
                        triangles=[f['triangles'][i:i+3] for f in original['faces'] for i in range(0,len(f['triangles']),3)]
                        labels={tuple(sorted(tri)):label for tri,label in zip(triangles,record['labels'])}
                        ids=[x.value for x in obj.data.attributes['uma_source_vertex'].data]
                        obj.data.materials.clear()
                        names=list(COLORS)
                        for name,color in COLORS.items():
                            mat=bpy.data.materials.new(name);mat.use_nodes=True
                            bsdf=mat.node_tree.nodes['Principled BSDF'];bsdf.inputs['Base Color'].default_value=color;bsdf.inputs['Roughness'].default_value=.8
                            obj.data.materials.append(mat)
                        for poly in obj.data.polygons:poly.material_index=names.index(labels[tuple(sorted(ids[v] for v in poly.vertices))])
                path=dest/(item['job']+'__'+mode+'__'+side+'.png')
                render(objects,path,side=='back')
                print('SKIN_PREVIEW',path.name,flush=True)
    print('SKIN_PREVIEWS_COMPLETE',flush=True)

if __name__=='__main__':main()
