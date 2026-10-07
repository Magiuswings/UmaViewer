"""Combine exposed-skin coverage, then always complete the fixed 0004 body as skin."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image,ImageDraw,ImageFilter

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',action='append',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--blender',type=Path,required=True)
    p.add_argument('--headless-tools',type=Path,required=True)
    p.add_argument('--pdx-tools',type=Path,required=True)
    p.add_argument('--distance',type=float,default=.015)
    args=p.parse_args()
    if not 0<args.distance<=.03:p.error('Skin correspondence distance must be >0 and <=0.03 source metres')
    sys.path.insert(0,str(args.headless_tools));sys.path.insert(0,str(args.pdx_tools))
    from body_profiles import body_profile,select_body_bases
    from skin_colors import skin_average
    from segmentation import classify
    out=args.output.resolve()
    if out.exists():raise FileExistsError(out)
    if any(out.is_relative_to(m.resolve().parent) for m in args.manifest):p.error('Output must preserve source directories')
    out.mkdir(parents=True);(out/'work').mkdir()
    entries={};inputs=[]
    for path in args.manifest:
        manifest=json.loads(path.read_text(encoding='utf8'))
        inputs.append(dict(manifest=str(path.resolve()),sha256=sha(path),input=manifest.get('input'),input_sha256=manifest.get('input_sha256')))
        for job in manifest['jobs']:
            profile=body_profile(job['source'],job['kind'])
            if not profile or profile['costume_id'] not in ('0004','0009'):continue
            data=json.loads((path.parent/job['snapshot']).read_text(encoding='utf8'))
            classify(data,None,path.parent/manifest['resources'])
            snapshot=out/'work'/(job['name']+'.uma.json');write(snapshot,data)
            entries[job['source']]=dict(name=job['name'],profile=profile,job=copy.deepcopy(job),data=data,
                                      snapshot_path=str(snapshot),resources_path=str(path.parent/manifest['resources']))
    # Bundle the selected real inputs so the completion can be rerun without the large packages.
    raw=out/'raw-inputs';raw_jobs=[]
    for entry in entries.values():
        job=copy.deepcopy(entry['job']);data=entry['data']
        job['snapshot']='snapshots/'+entry['name']+'.uma.json'
        write(raw/job['snapshot'],data)
        for material in data['materials']:
            for prop in material['properties']:
                if not prop.get('texture'):continue
                src=Path(entry['resources_path'])/prop['texture'];dst=raw/'resources'/prop['texture']
                dst.parent.mkdir(parents=True,exist_ok=True)
                if not dst.exists():os.link(src,dst)
        raw_jobs.append(job)
        entry['snapshot_path']=str(raw/job['snapshot']);entry['resources_path']=str(raw/'resources')
    write(raw/'manifest.json',dict(version=1,input='Selected real 0004/0009 input snapshots',resources='resources',jobs=raw_jobs,characters=['1001','1002','1003'],errors=[],warnings=[],body_bases=[],upstream_inputs=inputs))
    bodies=[]
    for entry in entries.values():
        profile=entry['profile']
        if profile['costume_id']!='0004' or profile['body_type_sub']!='00' or profile['body_setting']!='00':continue
        refs=[r for r in entries.values() if r['profile']['costume_id']=='0009' and all(r['profile'][k]==profile[k] for k in ('height','shape','bust'))]
        bodies.append(dict(name=entry['name'],profile=profile,snapshot_path=entry['snapshot_path'],references=[{k:r[k] for k in ('name','snapshot_path','resources_path')} for r in refs]))
    if not bodies:raise ValueError('No complete 0004 competitive-swimsuit templates')
    config=dict(bodies=bodies,distance=args.distance,normal_dot=.5,minimum_votes=5,coverage_output=str(out/'coverage-detail.json'))
    write(out/'coverage-config.json',config)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for k in ('TEMP','TMP','TMPDIR'):env[k]=str(out/'.temp')
    (out/'.temp').mkdir()
    with (out/'coverage.log').open('w',encoding='utf8') as log:
        subprocess.run([str(args.blender),'--background','--factory-startup','--python-exit-code','1','--python',str(Path(__file__).with_name('analyze_skin_union_blender.py')),'--',str(out/'coverage-config.json')],stdout=log,stderr=subprocess.STDOUT,env=env,check=True)
    coverage=json.loads((out/'coverage-detail.json').read_text(encoding='utf8'));jobs=[];reports=[];source_hashes={};cache={}
    for body in bodies:
        entry=next(e for e in entries.values() if e['name']==body['name'])
        data=copy.deepcopy(entry['data']);job=copy.deepcopy(entry['job']);resources=Path(entry['resources_path'])
        avg=skin_average(data,job,'body_skin',resources,cache)
        if not avg or avg['status']!='sampled':raise ValueError('No default diffuse skin colour: '+job['name'])
        fill_rgb=tuple(round(c) for c in avg['rgb_srgb_255'])
        old_signature={k:[copy.deepcopy(m[k]) for m in data['meshes']] for k in ('vertices','normals','uvs','weights','shapes')}
        old_bones=copy.deepcopy(data['bones']);old_triangles=[sorted(tuple(sorted(f['triangles'][i:i+3])) for f in m['faces'] for i in range(0,len(f['triangles']),3)) for m in data['meshes']]
        material_images={};masks={};summaries=[]
        for mi,mesh in enumerate(data['meshes']):
            rec=next(r for r in coverage['records'] if r['job']==job['name'] and r['mesh_index']==mi)
            uv=next(u['values'] for u in mesh['uvs'] if u['channel']==0);index=0;indices=[]
            for section in mesh['faces']:
                matid=section['material'];mat=data['materials'][matid]
                prop=next(p for p in mat['properties'] if p['name']=='_MainTex' and p.get('texture'))
                if matid not in material_images:
                    src=resources/prop['texture'];source_hashes[str(src)]=sha(src)
                    material_images[matid]=Image.open(src).convert('RGBA')
                    masks[matid]=Image.new('L',material_images[matid].size)
                img=material_images[matid];draw=ImageDraw.Draw(img);maskdraw=ImageDraw.Draw(masks[matid])
                scale=prop.get('scale',[1,1]);offset=prop.get('offset',[0,0])
                if scale!=[1,1] or offset!=[0,0]:raise ValueError('Canonical 0004 atlas has an unexpected UV transform')
                for i in range(0,len(section['triangles']),3):
                    tri=section['triangles'][i:i+3];indices.extend(tri)
                    label=rec['labels'][index]
                    if label!='0004_skin':
                        color=fill_rgb
                        samples=[]
                        if label=='0009_skin':
                            for hit in rec['transfers'][index]:
                                path=Path(hit['texture'])
                                if path not in cache:cache[path]=Image.open(path).convert('RGBA')
                                ref=cache[path];u,v=hit['uv'];u=(u*hit['scale'][0]+hit['offset'][0])%1;v=(v*hit['scale'][1]+hit['offset'][1])%1
                                rgb=ref.getpixel((min(ref.width-1,int(u*ref.width)),min(ref.height-1,int((1-v)*ref.height))))[:3]
                                if sum((x-y)**2 for x,y in zip(rgb,fill_rgb))<=42**2:samples.append(rgb)
                            if samples:color=tuple(round(sum(c[k] for c in samples)/len(samples)) for k in range(3))
                        poly=[(uv[v]['x']*(img.width-1),(1-uv[v]['y'])*(img.height-1)) for v in tri]
                        draw.polygon(poly,fill=(*color,255));maskdraw.polygon(poly,fill=255)
                    index+=1
            # One anatomical section, no separate competitive-swimsuit material slot.
            mesh['faces']=[dict(part='body',category='body_skin',material=0,triangles=indices)]
            summaries.append({k:v for k,v in rec.items() if k not in ('labels','transfers')})
        if len(material_images)!=1:raise ValueError('Canonical 0004 must have one source atlas; refusing a silent material merge')
        matid,img=next(iter(material_images.items()));mask=masks[matid]
        # Two-pixel gutters remove coloured swimsuit outlines from bilinear/mipmap sampling.
        expanded=mask.filter(ImageFilter.MaxFilter(5));gutter=Image.new('RGBA',img.size,(*fill_rgb,255));gutter.paste(img,(0,0),mask)
        img.paste(gutter,(0,0),expanded)
        original_mat=data['materials'][matid];main=next(p for p in original_mat['properties'] if p['name']=='_MainTex' and p.get('texture'))
        path=Path(main['texture']);name=path.stem+'__skin_completed.png';newrel=(path.parent/name).as_posix()
        dst=out/'resources'/newrel;dst.parent.mkdir(parents=True,exist_ok=True);img.save(dst)
        for prop in original_mat['properties']:
            if prop.get('texture') and prop['name']!='_MainTex':
                src=resources/prop['texture'];target=out/'resources'/prop['texture'];target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():os.link(src,target)
        main['texture']=newrel
        original_mat['name']='uma_completed_body_skin'
        data['materials']=[original_mat]
        assert data['bones']==old_bones
        for k,values in old_signature.items():assert [m[k] for m in data['meshes']]==values,k
        assert [sorted(tuple(sorted(f['triangles'][i:i+3])) for f in m['faces'] for i in range(0,len(f['triangles']),3)) for m in data['meshes']]==old_triangles
        data['warnings']=['Complete 0004 mesh is a tight-clothing body proxy; missing skin uses its original geometry, not reconstructed anatomy.']
        data['skin_completion']=dict(method=coverage['method'],fill_rgb_srgb_255=fill_rgb,source_diffuse_skin_statistics=avg,canonical_geometry_unchanged=True,separate_swimsuit_material=False)
        snapshot=out/'snapshots'/(job['name']+'.uma.json');write(snapshot,data)
        job.update(snapshot=snapshot.relative_to(out).as_posix(),categories=['body_skin'],category_triangles={'body_skin':sum(len(m['faces'][0]['triangles'])//3 for m in data['meshes'])},body_profile=entry['profile'])
        jobs.append(job)
        reports.append(dict(job=job['name'],profile=entry['profile'],meshes=summaries,fill_rgb_srgb_255=fill_rgb,default_diffuse_skin_statistics=avg,texture=newrel,geometry_uv_weights_bones_shapes_preserved=True,all_triangles_skin=True,material_slots=1))
    manifest=dict(version=1,input='Real decoded 0004 + 0009 skin completion',jobs=jobs,resources='resources',characters=['1001','1002','1003'],errors=[],warnings=[],body_bases=select_body_bases(jobs,lambda j:json.loads((out/j['snapshot']).read_text(encoding='utf8'))))
    write(out/'manifest.json',manifest)
    assert all(sha(Path(path))==value for path,value in source_hashes.items())
    write(out/'skin-union-report.json',dict(passed=True,inputs=inputs,method=coverage['method'],parameters=coverage['parameters'],bodies=reports,source_diffuse_hashes_unchanged=source_hashes,clothing_material_slots_in_completed_bodies=0,missing_skin_always_filled=True,bs_policy='Fixed original complete 0004 topology for each profile; source vertices/UV/weights and whole-combination BS correspondence preserved'))
    print('BODY_SKIN_COMPLETION_COMPLETE',str(out/'manifest.json'),flush=True)

if __name__=='__main__':main()
