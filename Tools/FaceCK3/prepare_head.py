"""Prepare shared face weights, coordinate transport and readable CK3 textures.

Run with the existing HeadlessExporter venv; all scratch/output stays on E:.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt,map_coordinates

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def bake(source,uv,source_uv,faces,size=512):
    """Transfer each source triangle's UV onto the common UV, then pad islands."""
    image=np.asarray(source.convert('RGBA'),dtype=float);out=np.zeros((size,size,4));valid=np.zeros((size,size),bool)
    target=uv*np.array([size-1,-(size-1)])+np.array([0,size-1])
    origin=source_uv*np.array([image.shape[1]-1,-(image.shape[0]-1)])+np.array([0,image.shape[0]-1])
    for tri in faces:
        a,b,c=target[tri];mat=np.column_stack((b-a,c-a));den=np.linalg.det(mat)
        if abs(den)<1e-8:continue
        low=np.maximum(np.floor(np.min(target[tri],axis=0)).astype(int),0);high=np.minimum(np.ceil(np.max(target[tri],axis=0)).astype(int),size-1)
        if np.any(high<low):continue
        xx,yy=np.meshgrid(np.arange(low[0],high[0]+1),np.arange(low[1],high[1]+1));xy=np.column_stack((xx.ravel(),yy.ravel()))
        st=(xy-a)@np.linalg.inv(mat).T;bw=np.column_stack((1-st.sum(1),st));keep=np.min(bw,axis=1)>=-1e-5
        xy=xy[keep];sample=bw[keep]@origin[tri]
        for k in range(4):out[xy[:,1],xy[:,0],k]=map_coordinates(image[:,:,k],[sample[:,1],sample[:,0]],order=1,mode='nearest')
        valid[xy[:,1],xy[:,0]]=True
    assert valid.any()
    nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True);out[~valid]=out[nearest[0][~valid],nearest[1][~valid]]
    # CK3 skin diffuse alpha is a palette mask, not opacity.
    out[:,:,3]=0
    return Image.fromarray(np.clip(np.rint(out),0,255).astype('uint8')),int(valid.sum())

def main():
    p=argparse.ArgumentParser()
    for n in ('repo','targets','research','source-mod','plugin','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--resume',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=a.resume)
    sys.path[:0]=[str(a.repo/'Tools/PDXExporter'),str(a.repo/'Tools/NativeBody')]
    from build_ck3_mod import parser_only
    from test_vanilla_body_animation_blender import inverse_bind
    import UnityPy
    pdx=parser_only(a.plugin);old=pdx.read_meshfile(str(a.source_mod/'gfx/models/portraits/uma/1001/uma_1001_head_base.mesh'));skeleton=old.find('object')[0].find('skeleton');world=np.linalg.inv(inverse_bind(skeleton));names=[b.tag for b in skeleton]
    raw=json.loads((a.research/'face-inputs/snapshots/uma_1001_face_80.json').read_text(encoding='utf8'));byid={b['id']:b for b in raw['bones']};byname={b['name']:b for b in raw['bones']}
    head=np.array(byname['Head']['matrix']).reshape(4,4);neck=np.array(byname['Neck']['matrix']).reshape(4,4)
    # Anchor to the already validated UMA head skeleton, preserving its bytes.
    origin=world[names.index('bn_h_head'),:3,3];scale=np.linalg.norm(origin-world[names.index('bn_h_neck_1'),:3,3])/np.linalg.norm(head[:3,3]-neck[:3,3])
    transform=np.diag([-scale,scale,-scale]);z=np.load(a.targets/'face-targets.npz');top=json.loads((a.targets/'common-topology.json').read_text(encoding='utf8'));records=[]
    mappings={json.loads(f.read_text(encoding='utf8'))['id']:json.loads(f.read_text(encoding='utf8'))for f in (a.targets/'targets').glob('*.json')}
    jobs={j['id']:j for j in json.loads((a.research/'face-inputs/manifest.json').read_text(encoding='utf8'))['jobs']}
    texture_cache={}
    def image_for(reference):
        if reference not in texture_cache:
            bundle,name=reference.rsplit('/',1);file=a.research/'named-assets'/bundle
            env=UnityPy.load(str(file));obj=next(o.read()for o in env.objects if o.type.name=='Texture2D'and o.read().m_Name==name)
            texture_cache[reference]=obj.image.copy()
        return texture_cache[reference]
    def location(ident,variant):
        return ('0001', 'npc'+ident.rsplit('_',1)[-1])if ident.startswith('npc_')else(ident,variant)
    report=json.loads((a.targets/'targets-report.json').read_text(encoding='utf8'))
    for row in report['per_model']:
        ident=row['id'];job=jobs[ident];mapping=mappings[ident];snapshot=a.research/'face-inputs'/job['snapshot'];data=json.loads(snapshot.read_text(encoding='utf8'))
        reference=next((p.get('texture')for p in data['materials'][0]['properties']if p['name']=='_MainTex'),None);fallback=reference is None
        if fallback:
            assert ident.startswith('npc_'),'Missing named-character diffuse: '+ident
            reference=next(p['texture']for p in raw['materials'][0]['properties']if p['name']=='_MainTex')
        character,variant=location(ident,str(job['variant']))
        prefix='uma_'+character+'_face_'+variant;texture=a.output/'textures'/character/(prefix+'_diffuse.dds');texture.parent.mkdir(parents=True,exist_ok=True)
        if not(a.resume and texture.exists()):
            source_uv=np.array(mappings['1001']['source_uv0_on_common_vertices']if fallback else mapping['source_uv0_on_common_vertices'])
            baked,coverage=bake(image_for(reference),z['uv0'],source_uv,z['faces']);baked.save(texture,pixel_format='DXT5')
        else:coverage=None
        records.append(dict(id=ident,character_id=character,variant=variant,mesh='meshes/'+character+'/uma_'+character+'_head_'+variant+'.mesh',diffuse=texture.relative_to(a.output).as_posix(),attribute='uma_bs_face_'+ident,template='uma_face_'+ident,index=len(records),source=str(job['source']),texture_source=reference,texture_coverage_pixels=coverage,npc_runtime_texture_unavailable=fallback))
        if len(records)%20==0:print('PREPARED_FACE_TEXTURES',len(records),flush=True)
    extras=a.output/'textures/0001';extras.mkdir(exist_ok=True)
    base=next(r for r in records if r['id']=='1001');Image.open(a.output/base['diffuse']).save(extras/'uma_0001_face_base_diffuse.dds',pixel_format='DXT5')
    Image.new('RGBA',(32,32),(0,128,0,128)).save(extras/'uma_0001_head_base_normal.dds',pixel_format='DXT5');Image.new('RGBA',(32,32),(0,0,0,180)).save(extras/'uma_0001_head_base_properties.dds',pixel_format='DXT5');Image.new('RGBA',(32,32),(255,255,255,255)).save(extras/'uma_0001_head_base_ssao.dds',pixel_format='DXT5')
    mesh=raw['meshes'][0];used=set(mappings['1001']['canonical_to_original_vertex'][:855]);extra_faces=[t for s in mesh['faces']if s['category']=='face'for t in np.array(s['triangles']).reshape(-1,3).tolist()if not all(v in used for v in t)]
    extra_used=sorted({v for t in extra_faces for v in t});remap={v:i for i,v in enumerate(extra_used)};rawpoints=np.array([[mesh['vertices'][v][k]for k in 'xyz']+[1]for v in extra_used]);local=(rawpoints@np.linalg.inv(head).T)[:,:3]
    original_image=image_for(next(p['texture']for p in raw['materials'][0]['properties']if p['name']=='_MainTex')).convert('RGBA');original_image.putalpha(0);original_image.save(a.output/'textures/1001/uma_1001_face_parts_diffuse.dds',pixel_format='DXT5')
    extras_data=dict(points=(local@transform.T+origin).tolist(),faces=[[remap[v]for v in t]for t in extra_faces],uv0=[[mesh['uvs'][0]['values'][v][k]for k in 'xy']for v in extra_used],source_indices=extra_used)
    write(a.output/'prepared.json',dict(records=records,basis_identity='1003',default_identity='1001',vertices=875,triangles=1334,engine_transform=transform.tolist(),engine_origin=origin.tolist(),engine_units='centimeters',source_anchor='1001 Head local frame',reused_skeleton_bones=61,extra_face_parts=extras_data,raw_snapshot=str(a.research/'face-inputs/snapshots/uma_1001_face_80.json'),common_weights=mappings['1001']['source_bone_weights_on_common_vertices'],body_mod_source=str(a.source_mod),texture_switching='Morph genes change geometry only; per-identity rebaked diffuse files are separately indexed, default uses 1001. Hair/iris/eyebrows and oral parts remain the existing 1001 test components.'))
    print('HEAD_PREPARATION_COMPLETE',len(records),'scale_cm_per_m',scale,flush=True)

if __name__=='__main__':main()
