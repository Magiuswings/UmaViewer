"""Independent lightweight registration/BS/DDS/rig review of current V8 stage. Expected native anim pending."""
import os,json,sys,hashlib
from pathlib import Path
import numpy as np
from asset_registration_audit import parse,children,value,raw_scan
from asset_schema_audit import schema
from texture_optimize import binary_strings,remap_reference,inspect
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
R=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');M=R/'UMA-V8';OUT=Path(__file__).parent
def main():
 issues=[];pending=[];rows=[];binarycache={};schema_cache={};textures=json.loads((R/'Reports/texture-sharing.json').read_text());pdxdict={};entitydict={};moduleimports=[];targets=set();asset_count=0;settings=0
 def binary(p):
  if str(p)not in binarycache:binarycache[str(p)]=raw_scan(p)
  return binarycache[str(p)]
 def detail(p):
  if str(p)not in schema_cache:schema_cache[str(p)]=schema(p)
  return schema_cache[str(p)]
 for file in sorted(M.rglob('*.asset')):
  asset_count+=1;tree=parse(file.read_text(encoding='utf-8-sig'))
  for block in children(tree,'entity'):
   n=value(block['children'],'name');entitydict.setdefault(n,[]).append(str(file))
  for block in children(tree,'pdxmesh'):
   fields=block['children'];name=value(fields,'name');pdxdict.setdefault(name,[]).append(str(file));path=file.parent/value(fields,'file');base=binary(path);base_detail=detail(path);keys={s['name']:s for s in base['shape_keys']};records=[]
   for setting in children(fields,'meshsettings'):
    settings+=1;f=setting['children'];n=value(f,'name');index=int(value(f,'index','0'))
    if n not in keys or index>=keys.get(n,{}).get('mesh_children',0):issues.append(dict(kind='meshsettings_raw_name_or_index_mismatch',asset=str(file),pdxmesh=name,shape=n,index=index))
    for k in['texture_diffuse','texture_normal','texture_specular']:
     ref=value(f,k)
     if ref:
      resolved=M/ref if ref.startswith('gfx/')else file.parent/ref
      if not resolved.is_file():issues.append(dict(kind='texture_reference_missing',asset=str(file),pdxmesh=name,reference=ref))
      if remap_reference(ref,file,M,textures)!=ref:issues.append(dict(kind='old_texture_reference',asset=str(file),reference=ref))
   for obj in base_detail['shapes']:
    if obj['child_order'][0]!='mesh':issues.append(dict(kind='mesh_not_first',file=str(path),shape=obj['name']))
    if obj['name'].endswith('Shape'):issues.append(dict(kind='v8_shape_suffix_contract',file=str(path),shape=obj['name']))
   for target in children(fields,'blend_shape'):
    targetpath=file.parent/value(target['children'],'type');targets.add(str(targetpath));info=detail(targetpath);body=targetpath.name.startswith('uma_0001_body_')
    for obj in info['shapes']:
     if not body and('skeleton'in obj['child_order']or any(m['skin']for m in obj['meshes'])):issues.append(dict(kind='accessory_BS_has_skeleton_or_skin',file=str(targetpath)))
     if body and'skeleton'not in obj['child_order']:issues.append(dict(kind='body_BS_skeleton_missing',file=str(targetpath)))
    records.append(dict(file=str(targetpath),body=body,shape_count=len(info['shapes']),skeleton_present=any('skeleton'in s['child_order']for s in info['shapes']),skin_present=any(bool(m['skin'])for s in info['shapes']for m in s['meshes'])))
   for imp in children(fields,'import'):
    if value(imp['children'],'type')=='skeletal_animation_set':moduleimports.append(dict(mesh=name,asset=str(file),set=value(imp['children'],'name'),skeletons=[dict(shape=o['name'],bones=o.get('bone_count'))for o in base_detail['shapes']]))
   if children(fields,'additive_animation'):issues.append(dict(kind='additive_remaining',asset=str(file),mesh=name))
   rows.append(dict(asset=str(file),mesh=name,base=str(path),settings=len(children(fields,'meshsettings')),targets=records))
  for path,n in walk(tree):
   if n['key']=='additive_animation':issues.append(dict(kind='additive_remaining',asset=str(file),path=path))
  for macro in children(tree,'skeletal_animation_set'):
   name=value(macro['children'],'name')
   for clip in children(macro['children'],'animation'):
    f=file.parent/value(clip['children'],'type')
    if not f.exists():pending.append(dict(kind='expected_native_animation_pending',macro=name,file=str(f)))
 for name,files in pdxdict.items():
  if len(files)>1:issues.append(dict(kind='duplicate_pdxmesh_name',name=name,files=files))
 for name,files in entitydict.items():
  if len(files)>1:issues.append(dict(kind='duplicate_entity_name',name=name,files=files))
 groups={g['new']:g for g in textures['groups']};originals={r['old']:r for r in textures['original_files']};dds=[]
 for path in sorted(M.rglob('*.dds')):
  relative=path.relative_to(M).as_posix();raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();expected=groups[relative]['new_sha256']if relative in groups else originals.get(relative,{}).get('sha256')
  if sha!=expected:issues.append(dict(kind='DDS_bytes_changed_or_unrecorded',file=relative))
  if relative in groups and groups[relative]['mode']=='uniform':
   p=inspect(raw)
   if p['width']!=1 or p['height']!=1 or p['rgba']!=groups[relative]['source_rgba']:issues.append(dict(kind='shared_uniform_RGBA_or_dimension_mismatch',file=relative))
  dds.append(dict(file=relative,bytes=len(raw),sha256=sha,expected_sha_exact=sha==expected))
 for old in textures['mapping']:
  if(M/old).exists():issues.append(dict(kind='old_redundant_DDS_remains',file=old))
 # Actual attachment node aliases belong to gfx/portraits/accessories, not only gene template file.
 af=M/'gfx/portraits/accessories/uma_parts.txt';access=parse(af.read_text(encoding='utf-8-sig'));node_rows=[]
 for block in access:
  for path,n in walk(block['children'],[block['key']]):
   if n['key']=='node':
    node_rows.append(dict(accessory=block['key'],node=n['value'],line=n['line']))
    if block['key'].startswith('uma_1002_')and n['value']=='bn_h_head':issues.append(dict(kind='actor2_attachment_node_not_aliased',file=str(af),line=n['line'],accessory=block['key']))
 # Root's supplied scope says native anim files are still being sampled; don't label those missing files violations.
 result=dict(root=str(M),counts=dict(assets=asset_count,pdxmesh=len(pdxdict),entities=len(entitydict),meshsettings=settings,unique_base_binary=len(binarycache),unique_BS=len(targets),DDS=len(dds),DDS_bytes=sum(d['bytes']for d in dds),actual_violations=len(issues),expected_pending_native_anim_files=len({r['file']for r in pending})),violations=issues,expected_pending_native_animations=pending,moduleimports=moduleimports,attachment_nodes=node_rows,DDS=dds,registration=rows,limitations=['Static/raw-byte/actual DDS review only; not new live CK3 engine proof.','Root comprehensive validator will validate full joint/animation compatibility after sampling; pending native files explicitly excluded from errors.']);(OUT/'v8-current-lightweight-review.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('V8_CURRENT_REVIEW',result['counts']);print('VIOLATIONS',issues[:10])
def walk(nodes,path=[]):
 for n in nodes:
  now=path+[n['key']]if n['key']is not None else path
  yield now,n
  if n['children']is not None:yield from walk(n['children'],now)
if __name__=='__main__':main()
