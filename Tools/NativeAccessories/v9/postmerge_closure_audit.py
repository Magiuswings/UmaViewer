"""Post-dedup closed registry audit, no final-mod writes."""
import sys,json,re,hashlib
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).parent));from designer_dedup_audit import parse,children,value,walk,models
ROOT=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9');MOD=ROOT/'UMA-V9';OUT=Path(__file__).parent
def main():
 registry=ROOT/'Reports/head-registration.json';input_sha=hashlib.sha256(registry.read_bytes()).hexdigest();regs=json.loads(registry.read_text());meshes={};entities={};imports={};issues=[];files=[]
 for file in sorted(MOD.rglob('*.asset')):
  data=parse(file.read_text(encoding='utf-8-sig'));files.append(str(file))
  for row in children(data,'pdxmesh'):
   f=row['children'];name=value(f,'name');base=value(f,'file');path=file.parent/base;meshes[name]=dict(asset=str(file),base=base,path=str(path));imports[name]=[value(i['children'],'name')for i in children(f,'import')if value(i['children'],'type')=='skeletal_animation_set']
   if not path.exists():issues.append(dict(kind='base_mesh_missing',mesh=name,path=str(path)))
   for b in children(f,'blend_shape'):
    p=file.parent/value(b['children'],'type')
    if not p.exists():issues.append(dict(kind='BS_mesh_missing',mesh=name,path=str(p)))
  for row in children(data,'entity'):
   f=row['children'];entities[value(f,'name')]=dict(mesh=value(f,'pdxmesh'),asset=str(file))
 for name,entity in entities.items():
  if entity['mesh']not in meshes:issues.append(dict(kind='entity_pdxmesh_missing',entity=name,mesh=entity['mesh']))
 owners=defaultdict(set);regrows=[]
 for row in regs:
  name=row['entity'];mesh=row.get('mesh');p=Path(mesh);entity=entities.get(name);asset=entity['asset']if entity else None
  if not entity:issues.append(dict(kind='head_registration_entity_missing',prefix=row['prefix'],entity=name))
  if not p.is_file():issues.append(dict(kind='head_registration_binary_missing',prefix=row['prefix'],file=mesh))
  if asset:owners[(row['actor'],row['element'])].add(asset)
  if row['element']=='headwear'and entity:
   modules=imports.get(entity['mesh'],[])
   if modules:issues.append(dict(kind='headwear_has_own_skeletal_animation_import',prefix=row['prefix'],imports=modules))
  regrows.append(dict(prefix=row['prefix'],actor=row['actor'],element=row['element'],variant=row['variant'],entity=name,pdxmesh=entity['mesh']if entity else None,asset=asset,mesh=mesh))
 container=[dict(actor=a,element=e,asset_count=len(s),assets=sorted(s))for(a,e),s in sorted(owners.items())]
 for row in container:
  if row['element']in['head','cheek','tear','eye','brow']and row['asset_count']!=1:issues.append(dict(kind='actor_element_multi_asset_after_dedup',**row))
 comparison=models(MOD);issues+=comparison['registration_closure_missing'];input_unchanged=hashlib.sha256(registry.read_bytes()).hexdigest()==input_sha
 result=dict(source=str(MOD),readonly=True,input_head_registration_sha256=input_sha,input_registration_unchanged_during_read=input_unchanged,counts=dict(assets=len(files),pdxmesh=len(meshes),entity=len(entities),head_registration=len(regs),cheek_models=len(comparison['cheeks']),closure_violations=len(issues),nonshader_path_refs=len(comparison['nonshader_path_references'])),violations=issues,actor_element_asset_containers=container,registrations=regrows,cheek_duplicates=comparison['cheek_duplicates'],nonshader_path_refs=comparison['nonshader_path_references'],headwear_imports=[dict(prefix=r['prefix'],imports=imports.get(entities.get(r['entity'],{}).get('mesh'),[]))for r in regs if r['element']=='headwear'],limitations=['Root is still rebuilding V9; this captures source hashes at audit time.','Actual ruler-designer runtime silent exit is not reproduced or attributed by this static graph.','Merged neck full-attachment/animation verification belongs to root current model tests.'])
 (OUT/'v9-postmerge-registration-closure.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('POSTMERGE_CLOSURE',result['counts'],'stable',input_unchanged,'violations',issues[:10]);print('CONTAINERS',container)
if __name__=='__main__':main()
