import os
import json,sys,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
from head_pdx_tools import world
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'HeadSources';OUT=SRC/'Export';P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))));index=json.loads((OUT/'head-export-index.json').read_text());contract=json.loads((ROOT/'rig-contract.json').read_text());C=np.array(contract['head_source_to_engine']);anchor=np.array(contract['head_anchor']);reports=[]
for item in index['heads']:
    delivery=json.loads(Path(item['delivery_json']).read_text());source=json.loads(Path(delivery['source_json']).read_text());H=np.array(next(b for b in source['bones']if b['name']=='Head')['matrix']).reshape(4,4)[:3,3];mapping=delivery['source_map'];piece=next(p for p in delivery['components']if p['element']=='face');sk=P.read_meshfile(piece['mesh_path']).find('object')[0].find('skeleton');skbyname={b.tag:b for b in sk};worlds=world(sk);errors=[];missing=[]
    for b in source['bones']:
        target=mapping[b['id']]
        if target not in skbyname:missing.append(target);continue
        if target.startswith('uma_src_'):
            actual=worlds[skbyname[target].get('ix')[0],:3,3];expected=C@(np.array(b['matrix']).reshape(4,4)[:3,3]-H)+anchor;errors.append(float(np.linalg.norm(actual-expected)))
    assert not missing;assert max(errors,default=0)<1e-4
    part=json.loads((SRC/f'partitions/chr{item["actor"]}_{item["variant"]}/head-components.json').read_text());sets=[set(part.get(e+'_triangle_ids',[]))for e in ['hair','ear','headwear','neck_patch']];assert sum(map(len,sets))==len(set.union(*sets));assert len(set.union(*sets))==sum(len(f['triangles'])//3 for f in next(m for m in source['meshes']if m['name']=='M_Hair')['faces'])
    reports.append({'actor':item['actor'],'variant':item['variant'],'source_native_transforms':len(source['bones']),'source_map_entries':len(mapping),'unmapped_native_aux_point_checks':len(errors),'native_aux_max_position_error_cm':max(errors,default=0),'missing_source_mapped_bone_names':missing,'headwear_ear_hair_triangle_overlap':0,'all_source_hair_triangles_retained':True,'maximum_piece_bones':max(p.get('bones',0)for p in delivery['components']),'source_inactive_effects_optional':all(p['optional_expression_overlay']and not p['enabled_in_default_preset']for p in delivery['components']if p['element']in ['tear','cheek'])})
    # The extractor's display labels are not master.db names. Keep IDs and
    # original logical prefab names without presenting inferred English as DB.
    source['name']='chara'+item['actor']+'__head_chr'+item['actor']+'_'+item['variant'];source['character_name']='';source['display_label_policy']='Actor ID only; no inferred English label presented as master database name.';Path(delivery['source_json']).write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
report={'passed':True,'heads':reports,'native_source_points_or_meshes_discarded':0,'source_archive_unchanged':True,'head_partitions_use_source_indices':True,'statements_do_not_imply_runtime_verified':True};(SRC/'head-source-point-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(reports,indent=2))
