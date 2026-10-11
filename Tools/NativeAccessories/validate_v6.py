"""Read-only reference, encoding, skeleton, texture-mask and gaze checks."""
import argparse,hashlib,json,posixpath,re,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image

def main():
    p=argparse.ArgumentParser()
    for n in ['root','repo','plugin','game']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();r=a.root;mod=r/'UMA-V6-1001';sys.path[:0]=[str(a.repo/'Tools/PDXExporter'),str(a.repo/'Tools/NativeBody')]
    from build_ck3_mod import parser_only,clausewitz,one,values
    from test_vanilla_body_animation_blender import inverse_bind
    pdx=parser_only(a.plugin);resources=[];entities={};meshdefs={};basenames=defaultdict(list);assets=[]
    def visit(node,file):
        for k,v in node:
            if isinstance(v,list):visit(v,file)
            elif isinstance(v,str)and v.lower().endswith(('.mesh','.anim','.dds','.shader')):
                rel=v if v.startswith('gfx/')else posixpath.normpath(file.parent.relative_to(mod).as_posix()+'/'+v)
                assert (mod/rel).is_file()or(a.game/rel).is_file(),(file,v,rel);resources.append(rel)
    for file in (mod/'gfx').rglob('*'):
        if file.is_file():basenames[file.name.casefold()].append(file)
        if file.suffix=='.asset':
            tree=clausewitz(file.read_text(encoding='utf-8-sig'));assets.append(file);visit(tree,file)
            for key,target in [('entity',entities),('pdxmesh',meshdefs)]:
                for value in values(tree,key):name=one(value,'name');assert name not in target;target[name]=value
    assert all(len(v)==1 for v in basenames.values());paths=[str(f)for f in mod.rglob('*')if f.is_file()];assert max(map(len,paths))<256
    for f in mod.rglob('*.txt'):
        assert f.read_bytes().startswith(b'\xef\xbb\xbf');tree=clausewitz(f.read_text(encoding='utf-8-sig'));assert 'gene_uma_face_identity'not in f.read_text(encoding='utf-8-sig');visit(tree,f)
        assert not re.search(r'\bmin\s*=\s*0(?:\.0+)?\s+max\s*=\s*0(?:\.0+)?\b',f.read_text(encoding='utf-8-sig'))
    group=one(clausewitz((mod/'common/portrait_types/uma_portrait_types.txt').read_text(encoding='utf-8-sig')),'uma')
    for kind,key in [('male','minimum_age'),('female','minimum_age'),('boy','maximum_age'),('girl','maximum_age')]:assert one(one(group,'uma_'+kind),key)=='18'
    carrierfile=mod/'gfx/models/portraits/uma/0001/uma_0001_head_empty.mesh';carrier=pdx.read_meshfile(str(carrierfile)).find('object')[0];skel=carrier.find('skeleton');mesh=carrier.find('mesh');assert len(skel)==61 and len(mesh.attrib['p'])==9 and len(mesh.attrib['tri'])==3
    blank=pdx.read_meshfile(str(carrierfile.with_name('uma_0001_head_none.mesh'))).find('object')[0];assert mesh.attrib==blank.find('mesh').attrib and mesh.find('skin').attrib==blank.find('mesh').find('skin').attrib
    original=one(clausewitz((a.game/'gfx/models/portraits/female_head/female_head.asset').read_text(encoding='utf-8-sig')),'pdxmesh');new=meshdefs['uma_0001_head_carrier_mesh'];assert {one(v,'id')for v in values(original,'blend_shape')}=={one(v,'id')for v in values(new,'blend_shape')}
    assert all(one(v,'type')=='uma_0001_head_none.mesh'for v in values(new,'blend_shape'))
    plan=json.loads((r/'integration.json').read_text());partchecks=[]
    for row in plan['parts']:
        data=pdx.read_meshfile(str(mod/row['file']));obj=data.find('object')[0];m=obj.find('mesh');s=obj.find('skeleton');skin=m.find('skin');w=np.array(skin.attrib['w']).reshape(-1,4);ix=np.array(skin.attrib['ix']).reshape(-1,4);assert np.isfinite(w).all()and np.max(abs(w.sum(1)-1))<1e-5;assert ((ix>=0)|(w==0)).all();assert max(ix.reshape(-1))<len(s)
        for k in ['diff','n','spec']:
            ref=m.find('material').attrib[k][0];assert (mod/row['file']).parent.joinpath(ref).is_file();assert 'female_head_'not in ref
        if row['element']not in ['ear','tail','clothing','footwear']:assert [(b.tag,b.attrib)for b in s]==[(b.tag,b.attrib)for b in skel]
        if row['element'] in ['ear','tail','hair','brow']:
            mask=np.array(Image.open((mod/row['file']).parent/m.find('material').attrib['n'][0]).convert('RGBA'))[:,:,2];assert mask.max()>240
        if row['element']=='face':assert not values(meshdefs[row['prefix']+'_mesh'],'blend_shape')
        entity=entities[row['entity']];userdata=one(one(entity,'game_data'),'portrait_entity_user_data');assert not values(userdata,'portrait_decal')
        partchecks.append(dict(element=row['element'],vertices=len(m.attrib['p'])//3,triangles=len(m.attrib['tri'])//3,bones=len(s),maximum_weight_sum_error=float(np.max(abs(w.sum(1)-1)))))
    accessories=clausewitz((mod/'gfx/portraits/accessories/uma_1001_accessories.txt').read_text(encoding='utf-8-sig'))
    for name,body in accessories:
        e=one(body,'entity');assert one(e,'entity')in entities
        if name.endswith(('_ear','_tail')):assert not values(e,'shared_pose_entity')and one(e,'node')in ['bn_h_head','body_root']
        if name.endswith(('_clothing','_footwear')):assert one(e,'shared_pose_entity')=='torso'
    assert mesh.find('aabb')is not None and len(mesh.find('aabb').attrib['min'])==3
    stock=pdx.read_meshfile(str(a.game/'gfx/models/portraits/female_head/female_head.mesh')).find('object')[0].find('skeleton');stockworld=np.linalg.inv(inverse_bind(stock));world=np.linalg.inv(inverse_bind(skel));names=[b.tag for b in skel];stocknames=[b.tag for b in stock];eye=pdx.read_meshfile(str(mod/'gfx/models/portraits/uma/1001/uma_1001_eye_base.mesh')).find('object')[0].find('mesh');q=np.array(eye.attrib['p']).reshape(-1,3);weights=np.array(eye.find('skin').attrib['w']).reshape(-1,4);indices=np.array(eye.find('skin').attrib['ix']).reshape(-1,4);gaze=[]
    from scipy.spatial.transform import Rotation
    for side in ['l','r']:
        name='bn_h_eye_'+side+'_rotate';active=np.any((indices==names.index(name))&(weights>0),axis=1);center=q[active].mean(0);pivot=world[names.index(name),:3,3];old=stockworld[stocknames.index(name),:3,3]
        for axis in ['x','y']:
            for angle in [-15,15]:
                rot=Rotation.from_euler(axis,angle,degrees=True).as_matrix();fixed=pivot+rot@(center-pivot);wrong=old+rot@(center-old);gaze.append(dict(side=side,axis=axis,angle=angle,matched_displacement_cm=float(np.linalg.norm(fixed-center)),stock_pivot_displacement_cm=float(np.linalg.norm(wrong-center))))
    assert max(v['matched_displacement_cm']for v in gaze)<.1
    shader=(mod/'gfx/FX/uma_portrait.shader').read_text();defs=[]
    for key in ['portrait_skin','portrait_skin_face']:
        effect=re.search(r'Effect\s+'+key+r'\s*\{(.*?)\n\}',shader,re.S)[1];d=re.search(r'Defines\s*=\s*\{(.*?)\}',effect,re.S)[1];defs.append(re.findall(r'"([^"]+)"',d));assert 'MOE_TOON'not in d and 'ENABLE_TEXTURE_OVERRIDE'not in d
    assert defs[0]==defs[1]and 'MOE_FACE_FILL'in defs[1];assert shader.count('Code\n\t\t[[')==shader.count('\n\t\t]]'),'Shader code blocks changed'
    bodyhashes=[]
    for f in(mod/'gfx/models/portraits/uma/0001').glob('uma_0001_body*.mesh'):
        if f.name.endswith('_clothed.mesh'):continue
        inputfile=r/'v5/gfx/models/portraits/uma/0001'/f.name;assert f.read_bytes()==inputfile.read_bytes();bodyhashes.append(f.name)
    report=dict(passed=True,parts=partchecks,resources_resolved=len(resources),asset_definitions=len(assets),stock_head_empty_bs_keys=len(values(new,'blend_shape')),same_head_and_body_skin_effect_defines=True,original_texture_override_disabled=True,body_basis_and_existing_bs_exact=bodyhashes,eye_pivot_probes=gaze,txt_bom=True,gfx_basenames_unique=True,maximum_absolute_path=max(map(len,paths)),four_age_branches_unchanged=True,native_ear_tail_own_pose=True,game_runtime_verified=False)
    (r/'static-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('V6_STATIC_REFERENCES_MASKS_AND_GAZE_VERIFIED',len(partchecks),len(resources),flush=True)
if __name__=='__main__':main()
