"""Inventory only bdy00 common bodies and the read-only character parameter table."""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import re
import sys

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--decode',action='store_true')
    p.add_argument('--named-directory',default='named-common')
    args=p.parse_args()
    sys.path.insert(0,str(args.repo/'Tools/RawAssets'))
    sys.path.insert(0,str(args.repo/'Tools/HeadlessExporter'))
    from uma_raw import Catalog,RawSource,sha,decode_selected
    from sqlite_mc import Database
    from body_profiles import body_profile
    source=RawSource(args.source,args.workspace)
    catalog=Catalog(source,args.repo,'auto')
    try:
        # Only common-body logical metadata is queried; no character-specific body bundles.
        entries=catalog.select(prefixes=['3d/chara/body/bdy00'])
        prefabs=[]
        for e in entries:
            profile=body_profile(e.name)
            if profile and re.search(r'/pfb_bdy00\d\d_',e.name):
                prefabs.append(dict(catalog.public(e),profile=profile))
        with Database(source.master,args.repo,'auto') as db:
            columns={r['name'] for r in db.rows('PRAGMA table_info(chara_data)')}
            fields=[f for f in ('id','height','shape','bust','skin','scale','sex') if f in columns]
            rows=list(db.rows('SELECT '+','.join(fields)+' FROM chara_data ORDER BY id'))
        distribution=Counter((r['height'],r['shape'],r['bust']) for r in rows)
        result=dict(scope='Only bdy00-prefixed common body metadata; dedicated bodies not queried or extracted',
                    source=source.description(),database_sha256=sha(source.master),database=str(source.master),
                    characters=rows,total_characters=len(rows),
                    character_profile_distribution=[dict(height=h,shape=s,bust=b,characters=n) for (h,s,b),n in sorted(distribution.items())],
                    variable_values={f:sorted({r[f] for r in rows}) for f in ('height','shape','bust','skin')},
                    common_body_prefabs=prefabs,
                    common_family_distribution=dict(Counter(r['profile']['costume_id']+'_'+r['profile']['body_type_sub']+'_'+r['profile']['body_setting'] for r in prefabs)),
                    bundle_geometry_not_read=True,private_keys_serialized=False)
        write(args.output/'common-body-inventory.json',result)
        print(json.dumps({k:result[k] for k in ('total_characters','variable_values','common_family_distribution')},ensure_ascii=False,indent=2),flush=True)
        canonical=[r for r in prefabs if r['profile']['costume_id']=='0004' and r['profile']['body_type_sub']=='00']
        print('CANONICAL_0004',len(canonical),'present',sum(r['present'] for r in canonical),flush=True)
        print('CANONICAL_PROFILES',json.dumps([dict(name=r['name'],present=r['present']) for r in canonical],ensure_ascii=False),flush=True)
        if args.decode:
            roots=[]
            for e in entries:
                profile=body_profile(e.name)
                if profile:
                    family=(profile['costume_id'],profile['body_type_sub'],profile['body_setting'])
                    if family in (('0004','00','00'),('0009','00','00'),('0009','01','00')):
                        roots.append(e)
                    elif family in (('0002','00','00'),('0002','00','03')) and (profile['height'],profile['shape'],profile['bust']) in (('1','0','1'),('1','0','2')):
                        roots.append(e)
                elif '/textures/' in e.name:
                    stem=e.name.rsplit('/',1)[-1]
                    # Canonical body: all 4 actual skin palettes, all 5 bust atlases.
                    # Coverage donor: only default outfit colour, classification skin 0 and display skin 1.
                    if re.fullmatch(r'tex_bdy0004_00_00_[0-3]_[0-4]_(diff|shad_c|base|ctrl)',stem):roots.append(e)
                    elif re.fullmatch(r'tex_bdy0009_(00|01)_00_[01]_[0-4]_00_(diff|shad_c|base|ctrl)',stem):roots.append(e)
                    elif re.fullmatch(r'tex_bdy0002_00_(00|03)_[01]_[12]_(diff|shad_c|base|ctrl)',stem):roots.append(e)
            roots=list({r.name:r for r in roots}.values())
            assert all(r.name.startswith('3d/chara/body/bdy00') for r in roots)
            closure,missing,cycles=catalog.closure(roots)
            write(args.output/'selected-common-inputs.json',dict(roots=[catalog.public(r) for r in roots],dependency_closure_count=len(closure),estimated_decoded_bytes=sum(r.size or 0 for r in closure),missing_dependencies=missing))
            print('SELECTED_COMMON_INPUTS',len(roots),'roots',len(closure),'closure','bytes',sum(r.size or 0 for r in closure),flush=True)
            manifest=decode_selected(catalog,roots,args.output/args.named_directory,True,True,False)
            print('NAMED_COMMON_DECODED',len(manifest['assets']),'assets',manifest['passed'],flush=True)
    finally:catalog.db.close()

if __name__=='__main__':main()
