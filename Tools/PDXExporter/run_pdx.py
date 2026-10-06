"""Prepare textures and run a reproducible Blender 4.2 / IO PDX Mesh conversion."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from PIL import Image

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def texture_key(prop):
    return json.dumps([prop['texture'],prop.get('scale',[1,1]),prop.get('offset',[0,0])],separators=(',',':'))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True, help='Reparsed named Unity assets manifest; no Blender 5.x input')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--blender', type=Path, required=True)
    p.add_argument('--pdx-plugin', type=Path, required=True, help='io_pdx_mesh package directory')
    p.add_argument('--body-reference', type=Path, required=True)
    p.add_argument('--head-reference', type=Path, required=True)
    p.add_argument('--families', type=Path, help='Optional JSON: exact job name/source path -> confirmed costume family; topology checks still apply')
    p.add_argument('--only', action='append', default=[], help='Optional category filter for development / partial export')
    p.add_argument('--job', action='append', default=[], help='Optional exact job name filter')
    p.add_argument('--skip-verify', action='store_true')
    p.add_argument('--morphs-only',action='store_true',help='Rebuild morph stage from existing component exports, then verify everything')
    args = p.parse_args()
    out = args.output.resolve()
    src = args.manifest.resolve()
    if out == src.parent or out.is_relative_to(src.parent):
        p.error('Use a separate output directory to preserve source evidence')
    for f in (src, args.blender, args.body_reference, args.head_reference, args.pdx_plugin/'__init__.py'):
        if not f.is_file(): p.error('Missing input: '+str(f))
    out.mkdir(parents=True, exist_ok=True)
    config_path = out/'config.json'
    if config_path.exists():
        old=json.loads(config_path.read_text(encoding='utf8'))
        if old.get('source_manifest_sha256',old['manifest_sha256']) != sha(src): p.error('Output belongs to a different source manifest')
    original_src=src
    from morphs import index_manifest
    families=json.loads(args.families.read_text(encoding='utf8')) if args.families else {}
    original_index=index_manifest(src,families)
    (out/'source-apparel-index.json').write_text(json.dumps(original_index,ensure_ascii=False,indent=2),encoding='utf8')
    from partitions import normalize_manifest
    src=normalize_manifest(src,out/'source-inputs',original_index)
    tex = out/'textures'; tex.mkdir(exist_ok=True)
    manifest = json.loads(src.read_text(encoding='utf8'))
    from skin_colors import collect_skin
    (out/'skin-colors.json').write_text(json.dumps(collect_skin(manifest,src.parent),ensure_ascii=False,indent=2),encoding='utf8')
    diffuse = {}
    for job in manifest['jobs']:
        data = json.loads((src.parent/job['snapshot']).read_text(encoding='utf8'))
        for mat in data['materials']:
            for prop in mat['properties']:
                if prop['name'] == '_MainTex' and prop.get('texture'):
                    original = src.parent/manifest['resources']/prop['texture']
                    scale=prop.get('scale',[1,1]);offset=prop.get('offset',[0,0])
                    transformed=scale!=[1,1] or offset!=[0,0]
                    name = original.stem+('_uv_'+hashlib.sha256(texture_key(prop).encode()).hexdigest()[:8] if transformed else '')+'.dds'
                    target = tex/name
                    if not target.exists():
                        with Image.open(original) as img:
                            img=img.convert('RGBA')
                            if transformed:
                                if not (all(0<=v<=1 for v in offset) and all(s>0 and o+s<=1 for o,s in zip(offset,scale))):
                                    raise ValueError('Unsupported wrapping source texture transform; must bake explicitly: '+texture_key(prop))
                                w,h=img.size
                                img=img.crop((round(offset[0]*w),round((1-offset[1]-scale[1])*h),round((offset[0]+scale[0])*w),round((1-offset[1])*h)))
                            img.save(target, pixel_format='DXT5')
                    diffuse[texture_key(prop)] = dict(dds=name, source_sha256=sha(original), dds_sha256=sha(target),
                                                      source=prop['texture'],scale=scale,offset=offset,transform_baked_into_image=transformed)
    # CK3 portrait shader expects channel-packed normal/properties maps.
    # Source control masks are NOT mislabeled as PDX normals or properties.
    Image.new('RGBA', (4,4), (128,128,255,128)).save(tex/'neutral_normal.dds', pixel_format='DXT5')
    Image.new('RGBA', (4,4), (0,55,0,180)).save(tex/'neutral_properties.dds', pixel_format='DXT5')
    runtime = out/'.runtime'
    env = dict(os.environ)
    for key in ('TEMP','TMP','TMPDIR'):
        env[key] = str(out/'.temp')
    env['APPDATA'] = str(runtime/'Roaming')
    env['LOCALAPPDATA'] = str(runtime/'Local')
    for key in ('TEMP','APPDATA','LOCALAPPDATA'): Path(env[key]).mkdir(parents=True, exist_ok=True)
    settings = Path(env['LOCALAPPDATA'])/'io_pdx_mesh/settings.json'
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({'last_update_check':'2099-01-01','last_set_engine':'crusader_kings_3'}), encoding='utf8')
    config = dict(manifest=str(src),manifest_sha256=sha(src),source_manifest=str(original_src),source_manifest_sha256=sha(original_src),output=str(out),
                  plugin=str(args.pdx_plugin.resolve()),body_reference=str(args.body_reference.resolve()),
                  head_reference=str(args.head_reference.resolve()),
                  reference_hashes={'body':sha(args.body_reference),'head':sha(args.head_reference)},
                  diffuse=diffuse,only=args.only,jobs=args.job,
                  morphs_only=args.morphs_only,
                  mesh_policy='Keep source local vertices, object transforms, UVs and topology; adapt bones to source',
                  version_required=[4,2])
    config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'apparel-index.json').write_text(json.dumps(index_manifest(src,families),ensure_ascii=False,indent=2),encoding='utf8')
    for script, logfile in [('blender_pipeline.py','conversion.log')]+([] if args.skip_verify else [('verify_pdx.py','verification.log')]):
        cmd=[str(args.blender),'--background','--factory-startup','--python-exit-code','1','--python',str(HERE/script),'--',str(config_path)]
        print('Running '+script+'; log='+str(out/logfile),flush=True)
        with (out/logfile).open('w',encoding='utf8') as stream:
            result=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT,env=env)
        if result.returncode:
            print((out/logfile).read_text(encoding='utf8',errors='replace')[-10000:])
            raise SystemExit(result.returncode)
    print('PDX_EXPORT_COMPLETE '+str(out),flush=True)

if __name__ == '__main__': main()
