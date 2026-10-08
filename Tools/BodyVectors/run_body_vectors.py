"""Create a Blender4.2 / PDX common body with one key per scalar parameter value."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from PIL import Image,ImageChops

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--completed-manifest',type=Path,required=True)
    p.add_argument('--decoded-manifest',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--blender',type=Path,required=True)
    p.add_argument('--pdx-plugin',type=Path,required=True)
    p.add_argument('--body-reference',type=Path,required=True)
    args=p.parse_args()
    out=args.output.resolve()
    if out.exists():raise FileExistsError(out)
    analysis=json.loads(args.analysis.read_text(encoding='utf8'))
    if not analysis['all_combinations_exact_within_0_01mm'] or not analysis['database_profiles_available']:raise ValueError('Additive model has not passed all available source profiles')
    out.mkdir(parents=True);tex=out/'meshes';tex.mkdir()
    completed=json.loads(args.completed_manifest.read_text(encoding='utf8'))
    decoded=json.loads(args.decoded_manifest.read_text(encoding='utf8'))
    if decoded['errors']:raise ValueError('Decoded input contains errors')
    basis_name=analysis['basis_job']
    base_job=next(j for j in completed['jobs'] if j['name']==basis_name)
    basis=json.loads((args.completed_manifest.parent/base_job['snapshot']).read_text(encoding='utf8'))
    if len(basis['materials'])!=1 or any(f['category']!='body_skin' for m in basis['meshes'] for f in m['faces']):raise ValueError('Basis is not complete single-material skin')
    main=next(p for p in basis['materials'][0]['properties'] if p['name']=='_MainTex')
    completed_png=args.completed_manifest.parent/completed['resources']/main['texture']
    with Image.open(completed_png) as original:original.convert('RGBA').save(tex/'uma_body_skin_1.dds',pixel_format='DXT5')
    for filename,color in (('neutral_normal.dds',(128,128,255,128)),('neutral_properties.dds',(0,55,0,180))):Image.new('RGBA',(4,4),color).save(tex/filename,pixel_format='DXT5')
    sys.path.insert(0,str(args.repo/'Tools/PDXExporter'));sys.path.insert(0,str(args.repo/'Tools/HeadlessExporter'))
    from skin_colors import skin_average
    default_job=next(j for j in decoded['jobs'] if j['name']==basis_name)
    default_data=json.loads((args.decoded_manifest.parent/default_job['snapshot']).read_text(encoding='utf8'))
    original_main=next(p for p in default_data['materials'][0]['properties'] if p['name']=='_MainTex')
    original_png=args.decoded_manifest.parent/decoded['resources']/original_main['texture']
    # Changed texels are exactly the previously filled/union/gutter region. Keep original skin-X shading elsewhere.
    with Image.open(original_png) as raw,Image.open(completed_png) as new:
        diff=ImageChops.difference(raw.convert('RGB'),new.convert('RGB'))
        channels=diff.split();mask=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2]).point(lambda x:255 if x else 0)
    colors=[];cache={}
    for skin in range(4):
        name='tex_bdy0004_00_00_'+str(skin)+'_2_diff'
        texture=next(t for t in decoded['textures'] if t['name']==name)
        data=copy.deepcopy(default_data);prop=next(p for p in data['materials'][0]['properties'] if p['name']=='_MainTex');prop['texture']=texture['path']
        job=copy.deepcopy(default_job);job['skin_palette']=[]
        stats=skin_average(data,job,'body_skin',args.decoded_manifest.parent/decoded['resources'],cache)
        if not stats or stats['status']!='sampled':raise ValueError('No real skin samples for '+name)
        color=tuple(round(c) for c in stats['rgb_srgb_255'])
        if completed.get('normalized_skin_textures'):
            normalized=args.completed_manifest.parent/completed['resources']/completed['normalized_skin_textures'][str(skin)]
            with Image.open(normalized) as raw:
                raw.convert('RGBA').save(tex/('uma_body_skin_'+str(skin)+'.dds'),pixel_format='DXT5')
        elif skin!=1:
            with Image.open(args.decoded_manifest.parent/decoded['resources']/texture['path']) as raw:
                image=raw.convert('RGBA');image.paste(Image.new('RGBA',image.size,(*color,255)),(0,0),mask);image.save(tex/('uma_body_skin_'+str(skin)+'.dds'),pixel_format='DXT5')
        colors.append(dict(skin=skin,source_texture=name,source_png=texture['path'],source_sha256=sha(args.decoded_manifest.parent/decoded['resources']/texture['path']),statistics=stats,diffuse='meshes/uma_body_skin_'+str(skin)+'.dds',fill_rgb_srgb_255=color))
    write(out/'skin-colors.json',dict(palettes=colors,default_skin=1,includes_lighting=False,source='Actual common-body default diffuse from the raw archive'))
    inventory=json.loads(args.inventory.read_text(encoding='utf8'))
    bindings=[]
    for row in inventory['characters']:
        keys={field+'_'+str(row[field]):1. for field in ('height','shape','bust')}
        bindings.append(dict(character_id=row['id'],parameters=row,keys=keys,
                             diffuse=colors[row['skin']]['diffuse'],average_skin_srgb_255=colors[row['skin']]['statistics']['rgb_srgb_255'],
                             root_scale_metadata=row.get('scale',160.7529)/160.7529,root_scale_applied=False,per_character_body_key=False))
    write(out/'character-body-bindings.json',dict(database_sha256=inventory['database_sha256'],characters=bindings,count=len(bindings),per_character_body_keys=0))
    texture_key=json.dumps([main['texture'],main.get('scale',[1,1]),main.get('offset',[0,0])],separators=(',',':'))
    config=dict(repo=str(args.repo.resolve()),manifest=str(args.completed_manifest.resolve()),decoded_manifest=str(args.decoded_manifest.resolve()),analysis=str(args.analysis.resolve()),inventory=str(args.inventory.resolve()),
                output=str(out),plugin=str(args.pdx_plugin.resolve()),body_reference=str(args.body_reference.resolve()),
                diffuse={texture_key:dict(dds='uma_body_skin_1.dds')},texture_directory='meshes',source_manifest_sha256=sha(args.completed_manifest),analysis_sha256=sha(args.analysis),
                policy='Reconstructed inward within the original 0004 envelope using fixed affine source correspondences; no global registration; common refined topology, UVs, weights and Basis rig; one variable per key')
    write(out/'config.json',config)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for name in ('TEMP','TMP','TMPDIR'):env[name]=str(out/'.temp')
    env['APPDATA']=str(out/'.runtime/Roaming');env['LOCALAPPDATA']=str(out/'.runtime/Local')
    for name in ('TEMP','APPDATA','LOCALAPPDATA'):Path(env[name]).mkdir(parents=True,exist_ok=True)
    settings=Path(env['LOCALAPPDATA'])/'io_pdx_mesh/settings.json';write(settings,dict(last_update_check='2099-01-01',last_set_engine='crusader_kings_3'))
    for script in ('build_vector_body_blender.py','verify_vector_body_blender.py'):
        logfile=out/(script.replace('.py','.log'))
        print('RUNNING',script,flush=True)
        with logfile.open('w',encoding='utf8') as stream:
            result=subprocess.run([str(args.blender),'--background','--factory-startup','--python-exit-code','1','--python',str(Path(__file__).with_name(script)),'--',str(out/'config.json')],stdout=stream,stderr=subprocess.STDOUT,env=env)
        if result.returncode:print(logfile.read_text(encoding='utf8',errors='replace')[-8000:]);raise SystemExit(result.returncode)
    print('BODY_VECTOR_EXPORT_COMPLETE',str(out),flush=True)

if __name__=='__main__':main()
