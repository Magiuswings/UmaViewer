"""Supplement actual raw hierarchy/property order and unused influence semantics; read-only."""
import json,struct,hashlib,re
from pathlib import Path
import numpy as np
from asset_registration_audit import V7,GAME,OUT,parse,children,value
def schema(path):
 data=path.read_bytes();p=4;stack=[];shapes=[];shape=None;mesh=None;skin=None;material=None
 while p<len(data):
  if data[p]==91:
   depth=0
   while data[p]==91:depth+=1;p+=1
   end=data.index(0,p);name=data[p:end].decode('latin1');p=end+1;stack=stack[:depth-1]+[name]
   if depth==2 and stack[0]=='object':shape=dict(name=name,child_order=[],meshes=[]);shapes.append(shape)
   elif depth==3 and shape is not None:
    shape['child_order'].append(name)
    if name=='mesh':mesh=dict(attributes=[],child_order=[],skin={},material={});shape['meshes'].append(mesh)
   elif depth==4 and stack[2]=='mesh':mesh['child_order'].append(name)
  else:
   assert data[p]==33;p+=1;n=data[p];p+=1;prop=data[p:p+n].decode('latin1');p+=n;kind=chr(data[p]);count=struct.unpack_from('<I',data,p+1)[0];p+=5;start=p;val=None
   if kind in ['i','f']:p+=count*4
   elif kind=='s':length=struct.unpack_from('<I',data,p)[0];val=data[p+4:p+4+length].rstrip(b'\0').decode('latin1');p+=4+length
   else:raise ValueError(kind)
   if len(stack)==3 and stack[-1]=='mesh':
    mesh['attributes'].append(prop)
    if prop in ['p','tri','n','ta','u0']:
     values=np.frombuffer(data,dtype='<f4'if kind=='f'else'<i4',count=count,offset=start);mesh[prop+'_count']=int(count);mesh[prop+'_finite']=bool(np.isfinite(values).all());
     if prop=='tri':mesh['tri_min']=int(values.min())if count else None;mesh['tri_max']=int(values.max())if count else None
   elif len(stack)==4 and stack[-1]=='skin':
    mesh['skin'].setdefault('attributes',[]).append(prop)
    if prop in ['ix','w']:mesh['skin'][prop]=np.frombuffer(data,dtype='<f4'if kind=='f'else'<i4',count=count,offset=start).copy()
    elif prop=='bones':mesh['skin']['bones']=np.frombuffer(data,dtype='<i4',count=count,offset=start).tolist()
   elif len(stack)==4 and stack[-1]=='material':mesh['material'][prop]=val if val is not None else dict(kind=kind,count=count)
 for s in shapes:
  for m in s['meshes']:
   sk=m['skin'];ix=sk.pop('ix',np.array([],int));w=sk.pop('w',np.array([],float));m['vertices']=m.get('p_count',0)//3;m['triangles']=m.get('tri_count',0)//3;m['valid_nonempty_geometry']=m['vertices']>0 and m['triangles']>0 and m.get('tri_min',-1)>=0 and m.get('tri_max',m['vertices'])<m['vertices']
   if len(ix)==len(w)and len(ix):
    sk.update(ix_count=len(ix),w_count=len(w),zero_weight_count=int(sum(w==0)),zero_weight_ix_histogram={str(int(k)):int(v)for k,v in zip(*np.unique(ix[w==0],return_counts=True))},weighted_negative_ix_count=int(sum((ix<0)&(w>0))),weighted_max_ix=int(ix[w>0].max()),finite=bool(np.isfinite(w).all()),normalized_max_error=float(np.max(abs(w.reshape(-1,sk['bones'][0]).sum(1)-1))))
 return dict(path=str(path),shapes=shapes)
def walk(nodes,path=[]):
 for n in nodes:
  now=path+[n['key']]if n['key']is not None else path
  yield now,n
  if n['children']is not None:yield from walk(n['children'],now)
def main():
 audit=json.loads((OUT/'asset-registration-audit.json').read_text());files=[Path(x['path'])for x in audit['binary_scans']];rows=[]
 for i,f in enumerate(files):
  rows.append(schema(f))
  if i%200==0:print('RAW_SCHEMA',i,len(files),flush=True)
 stock=[r for r in rows if str(GAME)in r['path']];mod=[r for r in rows if str(V7)in r['path']];issues=[]
 for r in mod:
  for s in r['shapes']:
   if s['child_order']and s['child_order'][0]=='skeleton':issues.append(dict(kind='skeleton_precedes_mesh_schema_difference',file=r['path'],shape=s['name'],child_order=s['child_order'],confirmed=True,engine_rejection_causal=False))
   for i,m in enumerate(s['meshes']):
    if not m['valid_nonempty_geometry']:issues.append(dict(kind='invalid_or_empty_geometry',file=r['path'],shape=s['name'],index=i,confirmed=True))
    if m['skin'].get('weighted_negative_ix_count',0):issues.append(dict(kind='weighted_negative_skin_index',file=r['path'],shape=s['name'],index=i,confirmed=True))
 genesfile=V7/'common/genes/uma_parts.txt';genes=parse(genesfile.read_text());acc=children(children(genes,'special_genes')[0]['children'],'accessory_genes')[0]['children'];accessory_names=[n['key']for n in acc if n['children']is not None];ethfile=V7/'common/ethnicities/uma_ethnicity.txt';eth=[]
 for e in parse(ethfile.read_text()):
  for n in e['children']:
   if n['key']in accessory_names:eth.append(dict(ethnicity=e['key'],gene=n['key'],line=n['line'],templates=[value(weight['children'],'name')for weight in n['children']if weight['children']is not None],file=str(ethfile),violation='accessory_gene_inside_ethnicity'))
 modifierfile=V7/'gfx/portraits/portrait_modifiers/uma_customization.txt';mods=parse(modifierfile.read_text());modes=[];groups=[]
 for group in mods:
  if not group['children']:continue
  groups.append(dict(group=group['key'],usage=value(group['children'],'usage','both'),selection_behavior=value(group['children'],'selection_behavior','weighted_random'),fallback=value(group['children'],'fallback'),priority=value(group['children'],'priority','0'),file=str(modifierfile),line=group['line']))
  for path,n in walk(group['children'],[group['key']]):
   if n['key']=='accessory'and n['children']is not None and'dna_modifiers'in path:
    mode=value(n['children'],'mode');
    if mode!='add':modes.append(dict(file=str(modifierfile),path=path,line=n['line'],mode=mode,gene=value(n['children'],'gene'),template=value(n['children'],'template'),violation='accessory_modifier_mode_not_add'))
 out=dict(raw_schema_files=len(rows),stock_reference=stock,mod_mesh_schemas=mod,schema_differences_and_geometry_failures=issues,unused_index_policy='Retain ix=-1 when w=0: installed stock body/clothes/legwear uses same sentinel. Only positive-weight negative ix is invalid.',customization=dict(accessory_genes=accessory_names,groups=groups,mode_violations=modes,ethnicity_accessory_violations=eth),confirmed_geometry_failures=[i for i in issues if i['kind']in['invalid_or_empty_geometry','weighted_negative_skin_index']],limitations='Hierarchy differences from installed stock are confirmed bytes, not confirmed engine rejection. mode/add and ethnicity diagnostics need current game-log validation after repair. No program/global file modified.');(OUT/'asset-schema-audit.json').write_text(json.dumps(out,indent=2),encoding='utf8');print('SCHEMA_COMPLETE',len(rows),'order',sum(i['kind']=='skeleton_precedes_mesh_schema_difference'for i in issues),'badgeo',len(out['confirmed_geometry_failures']),'badmodes',len(modes),'ethaccessories',len(eth));print('STOCK_ORDER',[(Path(r['path']).name,[(s['child_order'],[m['skin'].get('zero_weight_ix_histogram')for m in s['meshes']])for s in r['shapes']])for r in stock[:3]])
if __name__=='__main__':main()
