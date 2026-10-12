import json,re
from pathlib import Path
from collections import Counter
V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/UMA-V7');OUT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/MotionSources');definitions={};sets=[];imports=[];duplicate=[]
for asset in V7.rglob('*.asset'):
    text=asset.read_text(encoding='utf-8-sig');kind=re.match(r'\s*(\w+)\s*=',text)
    if not kind:continue
    name=re.search(r'\bname\s*=\s*"([^"]+)"',text)
    if kind[1]=='pdxmesh'and name:definitions[name[1]]=str(asset)
    if kind[1]=='skeletal_animation_set':
        ref=re.search(r'\breference_skeleton\s*=\s*"([^"]+)"',text);ids=re.findall(r'\banimation\s*=\s*\{\s*id\s*=\s*"([^"]+)"',text);counts=Counter(ids);sets.append({'asset':str(asset),'name':name[1]if name else None,'reference_skeleton':ref[1]if ref else None,'animation_ids':len(ids),'duplicate_ids':{n:c for n,c in counts.items()if c>1}})
    for m in re.finditer(r'\bimport\s*=\s*\{\s*type\s*=\s*skeletal_animation_set\s+name\s*=\s*"([^"]+)"',text):imports.append({'asset':str(asset),'set':m[1]})
for s in sets:s['reference_mesh_defined_in_V7']=s['reference_skeleton']in definitions
descriptor=(V7/'descriptor.mod').read_text(encoding='utf-8-sig');out={'read_only_actual_V7':True,'macro_sets':sets,'mesh_imports':imports,'macro_name_collision_with_unprefixed_stock_names':[s for s in sets if not s['name'].startswith('uma_')],'replace_path_directives':re.findall(r'\breplace_path\s*=\s*"([^"]+)"',descriptor),'confirmed_error':'Private uma_natural_common_head references undefined uma_0001_head_carrier_mesh; actual head female/male pdxmesh names differ.','confirmed_original_macro_pollution':False,'limits':'Private set and intended stock animation id reuse alone do not establish global pollution. No CK3 engine execution in this audit. Invalid reference may cause resolution failure; fallback/global side-effects require current game log/isolated reproduction.','V8_required_reference':'An actually defined namespaced carrier pdxmesh, with private per-module sets and existing state ids redirected to one true-source .anim per module.'};(OUT/'v7-motion-macro-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print([(s['name'],s['reference_skeleton'],s['reference_mesh_defined_in_V7'],s['animation_ids'],len(s['duplicate_ids']))for s in sets]);print('IMPORTED_SETS',sorted({x['set']for x in imports}))
