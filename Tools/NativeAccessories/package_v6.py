"""Seal verified 1001 test archives, keeping source data and installed assets intact."""
import argparse,hashlib,json,shutil,sys,zipfile
from pathlib import Path
import numpy as np
from PIL import Image

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    for name in ['root','repo','plugin','game','scripts']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=a.root;mod=r/'UMA-V6-1001';static=json.loads((r/'static-verification.json').read_text());head=json.loads((r/'blender-verification.json').read_text());full=json.loads((r/'full-chain-verification.json').read_text());assert static['passed']and head['passed']and full['passed'];assert sha(Path(full['model']))==full['sha256'];assert sha(Path(head['model']))==head['model_sha256']
    sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));from build_ck3_mod import parser_only
    pdx=parser_only(a.plugin);skin=[]
    for element,file,texture in [('body','0001/uma_0001_body_base.mesh','0001/uma_0001_body_skin1_diffuse.dds'),('face','1001/uma_1001_face_base.mesh','1001/uma_1001_face_base_diffuse.dds')]:
        folder=mod/'gfx/models/portraits/uma';mesh=pdx.read_meshfile(str(folder/file)).find('object')[0].find('mesh');q=np.array(mesh.attrib['p']).reshape(-1,3);tri=np.array(mesh.attrib['tri']).reshape(-1,3);uv=np.array(mesh.attrib['u0']).reshape(-1,2);pix=np.array(Image.open(folder/texture).convert('RGBA'));sample=uv[tri].mean(1);ix=np.minimum((sample[:,0]%1*pix.shape[1]).astype(int),pix.shape[1]-1);iy=np.minimum((sample[:,1]%1*pix.shape[0]).astype(int),pix.shape[0]-1);rgb=pix[iy,ix,:3].astype(float);valid=(rgb[:,0]>rgb[:,1]+5)&(rgb[:,1]>rgb[:,2]+3)&(rgb[:,1]>170);area=np.linalg.norm(np.cross(q[tri[:,1]]-q[tri[:,0]],q[tri[:,2]]-q[tri[:,0]]),axis=1)*.5;assert np.sum(area[valid])>0;mean=np.average(rgb[valid],axis=0,weights=area[valid]);skin.append(dict(element=element,texture=texture,method='triangle-centroid UV samples, surface-area weighted, excluding non-skin colors',area_weighted_rgb_255=mean.tolist(),color_space='decoded sRGB bytes, before palette/lighting',skin_triangles_sampled=int(valid.sum())))
    skinrecord=dict(character_id='1001',database_skin_index=1,default_body_skin_texture='uma_0001_body_skin1_diffuse.dds',samples=skin,rendered_game_color=False);skinfile=r/'Models/1001/uma_1001_skin_color.json';skinfile.write_text(json.dumps(skinrecord,ensure_ascii=False,indent=2),encoding='utf8')
    evidence=r/'Evidence';evidence.mkdir(exist_ok=True)
    for f in ['static-verification.json','blender-verification.json','full-chain-verification.json','material-policy.json','head-materials.json','head-policy.json','head-export.json','integration.json','actor.json','resource-selection.json','native-motion-index.json']:shutil.copy2(r/f,evidence/f)
    for sub,files in [('motion-parts',['motion-delivery.json','blender-pdx-io-verification.json','root-integration-review.json','ear-material-source-regions.json','ear-native-pose-proof.png','tail-native-pose-proof.png']),('clothing-parts',['clothing-delivery.json','clothing-validation.json','split-delivery.json','body-clothed-coverage-mask.json','body-clothed-animation-collision.json','clothing-clothed-neutral-sitting-front-side.png','clothing-native-source-front-side.png'])]:
        for f in files:shutil.copy2(r/sub/f,evidence/f)
    tools=r/'Tools/NativeAccessories';tools.mkdir(parents=True,exist_ok=True)
    for file in (a.repo/'Tools/NativeAccessories').iterdir():
        if file.is_file()and file.suffix in ['.py','.md']:shutil.copy2(file,tools/file.name)
    doc=(tools/'README.md').read_text(encoding='utf8');(r/'DELIVERY.md').write_text(doc,encoding='utf8');(r/'DELIVERY.txt').write_text(doc,encoding='utf-8-sig')
    release=dict(passed=True,scope='1001 only; staged v5 input and real source snapshots',game_version_reference='1.20.0.4',accessories=9,stock_head_empty_bs=129,placeholder_triangles=1,body_clothing_shared_bones=134,native_ear_tail_clips=6,native_idle_keys=72,body_basis_existing_bs_unchanged=True,original_head_animation_files_unchanged=True,original_body_animation_references_preserved=True,txt_utf8_bom=True,maximum_asset_path=static['maximum_absolute_path'],resources_resolved=static['resources_resolved'],head_skinning_component_samples=60,body_animation_samples=len(full['body_animation_samples']),maximum_body_clothing_skinning_error_cm=max(max(c['skin_errors_cm'].values())for c in full['body_animation_samples']),maximum_joint_attachment_error=max(max(c['joint_attachment_matrix_errors'].values())for c in full['body_animation_samples']),eye_palette_metadata_corrected=True,models_reopened=True,model_sha256=full['sha256'],game_runtime_verified=False,brow_late_pass_runtime_verified=False,remaining_court_body_intersections=359,clothing_collision_free=False,installed_vanilla_files_modified=False)
    (r/'release-verification.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8');packages=[]
    for name,folders in [('UMA-V6-1001-CK3.zip',[mod]),('UMA-V6-1001-Models.zip',[r/'Models',evidence]),('UMA-V6-1001-Tools.zip',[r/'Tools'])]:
        file=r/name
        with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for folder in folders:
                for f in folder.rglob('*'):
                    if f.is_file()and f.suffix not in ['.blend1','.pyc']:z.write(f,f.relative_to(r).as_posix())
            for f in ['DELIVERY.md','DELIVERY.txt','release-verification.json']:z.write(r/f,f)
            if folders==[mod]:z.write(r/'UMA-V6-1001.mod','UMA-V6-1001.mod')
        with zipfile.ZipFile(file)as z:assert z.testzip()is None
        packages.append(dict(file=name,bytes=file.stat().st_size,sha256=sha(file)))
    (r/'packages.json').write_text(json.dumps(packages,indent=2),encoding='utf8');print('V6_PACKAGES_SEALED',json.dumps(packages),flush=True)
if __name__=='__main__':main()
