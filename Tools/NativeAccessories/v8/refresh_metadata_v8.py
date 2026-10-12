"""Refresh copied manifests from final outputs; source evidence paths remain provenance."""
import json
from pathlib import Path
from paths_v8 import ROOT,MOD,V7
from apply_models_v8 import P
manifest=json.loads((ROOT/'Reports/texture-sharing.json').read_text());headsfile=ROOT/'Reports/head-registration.json';heads=json.loads(headsfile.read_text())
for row in heads:
    tree=P.read_meshfile(row['mesh']);row['bones']=len(tree.find('object')[0].find('skeleton'));row['vertices']=sum(len(m.get('p'))//3 for o in tree.find('object')for m in o.findall('mesh'));row['triangles']=sum(len(m.get('tri'))//3 for o in tree.find('object')for m in o.findall('mesh'));row['version']='V8';row['head_points_additive']=False
headsfile.write_text(json.dumps(heads,ensure_ascii=False,indent=2),encoding='utf8')
file=ROOT/'Reports/clothing-registration.json';wardrobe=json.loads(file.read_text())
for family in wardrobe['families']:
    for part in family['parts'].values():
        for setting in part.get('meshsettings',[]):
            setting['shape']=setting['shape'].removesuffix('Shape')
            for k in ['diffuse','normal','properties','ssao']:
                if k in setting:
                    p=Path(setting[k]);old=p.relative_to(MOD).as_posix()
                    if old in manifest['mapping']:setting[k]=str(MOD/manifest['mapping'][old])
        part['BS_contains_skeleton']=False;part['BS_contains_skin']=False;part['base_contains_skeleton_and_skin']=True
wardrobe['version']=8;file.write_text(json.dumps(wardrobe,ensure_ascii=False,indent=2),encoding='utf8')
file=ROOT/'Reports/configuration.json';conf=json.loads(file.read_text());conf['version']=8;conf['supported_body_attributes']=['bs_body_breast_shape_'+str(i)for i in range(1,5)]+['bs_body_fat_1','bs_body_gaunt_1'];conf['custom_gene_names']=[g for g in conf['custom_gene_names']if g not in ['uma_height','uma_head_points']];conf['accessory_source']='portrait modifiers with add only; never ethnicity';conf['animation_policy']='one real native loop per head/body/ear/tail private module';file.write_text(json.dumps(conf,indent=2),encoding='utf8')
records=json.loads((ROOT/'Reports/binary-normalization.json').read_text());lean=[r for r in records if r['accessory_bs_skeleton_and_skin_removed']];old=sum((V7/'UMA-V7'/r['file']).stat().st_size for r in lean);new=sum((MOD/r['file']).stat().st_size for r in lean)
(ROOT/'Reports/accessory-bs-size-savings.json').write_text(json.dumps(dict(unique_accessory_targets=len(lean),old_bytes=old,new_bytes=new,net_bytes_saved=old-new,removed_fields=['skeleton','skin'],body_targets_skeleton_retained=True,all_target_geometry_uv_topology_preserved=True),indent=2),encoding='utf8');print('METADATA_UPDATED','accessoryBS',len(lean),'BSbytesSaved',old-new,flush=True)
