"""Full current error-log frequency + registration counterpart/features. No source writes."""
import json,re,csv,struct,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from asset_registration_audit import V7,GAME,OUT,parse,children,value
LOG=Path('C:/Users/33775/Downloads/error.log')
def lods(file,shapes):
 data=Path(file).read_bytes();out={}
 for s in shapes:
  p=s['name_offset']+len(s['name'].encode('latin1'))+1;props=[];lod=None
  while p<len(data)and data[p]==33:
   p+=1;n=data[p];p+=1;key=data[p:p+n].decode('latin1');p+=n;kind=chr(data[p]);count=struct.unpack_from('<I',data,p+1)[0];p+=5
   if kind in['i','f']:
    if key=='lod':lod=list(struct.unpack_from('<'+('i'if kind=='i'else'f')*count,data,p))
    p+=count*4
   elif kind=='s':n=struct.unpack_from('<I',data,p)[0];p+=4+n
   else:raise ValueError(kind)
   props.append(key)
  out[s['name']]=dict(shape_attributes=props,lod=lod)
 return out
def main():
 raw=LOG.read_bytes();text=raw.decode('utf-8-sig',errors='replace');lines=text.splitlines();audit=json.loads((OUT/'asset-registration-audit.json').read_text());schema=json.loads((OUT/'asset-schema-audit.json').read_text());schemas={s['path']:s for s in schema['mod_mesh_schemas']};material=[];outofsync=[];events=[];error_types=Counter();examples={}
 patmat=re.compile(r'Failed to create material with shader (\S+) \(in ([^)]+)\) for mesh \[([^]]+)\] in (\S+)')
 patsync=re.compile(r'pdxmesh \[([^]]+)\] is out of sync with its meshsettings\. \[([^]]+)\] is not in use in file: (\S+)')
 for no,line in enumerate(lines,1):
  body=re.sub(r'^\[[^]]*\]\[[^]]*\]\[[^]]*\]:\s*','',line);typ='material_creation_failed'if patmat.search(line)else'meshsettings_not_in_use'if patsync.search(line)else re.sub(r'\[[^]]*\]','[]',body).split(':')[0][:180];error_types[typ]+=1;examples.setdefault(typ,dict(line=no,text=line))
  if m:=patmat.search(line):shader,shaderfile,shape,file=m.groups();row=dict(line=no,shader=shader,shader_file=shaderfile,shape=shape,file=file);material.append(row);events.append(dict(type='material_creation_failed',**row))
  if m:=patsync.search(line):mesh,shape,file=m.groups();row=dict(line=no,pdxmesh=mesh,shape=shape,file=file);outofsync.append(row);events.append(dict(type='meshsettings_not_in_use',**row))
 matcount=Counter((r['file'],r['shape'])for r in material);synccount=Counter((r['pdxmesh'],r['file'],r['shape'])for r in outofsync);rows=[];matchedmat=set();matchedsync=set();featuregroups=defaultdict(lambda:Counter());lodcache={}
 for r in audit['rows']:
  if not r.get('file')or not r.get('settings'):continue
  relative=Path(r['file']).relative_to(V7).as_posix();s=schemas[r['file']];shapemap={x['name']:x for x in s['shapes']};key=r['file']
  if key not in lodcache:lodcache[key]=lods(key,r['raw_shape_evidence'])
  kind=next((k for k in ['clothes','shoes','socks','headwear','hair','face_parts','face','eye','brow','cheek','tear','neck_patch','neck','ear','tail','body','head']if'_'+k+'_'in r['mesh']),'other')
  for setting in r['settings']:
   shape=setting['name'];actual=shapemap.get(shape);mc=matcount[(relative,shape)];sc=synccount[(r['mesh'],relative,shape)];
   if mc:matchedmat.add((relative,shape))
   if sc:matchedsync.add((r['mesh'],relative,shape))
   mesh=actual['meshes'][setting['index']]if actual and setting['index']<len(actual['meshes'])else {};attributes=lodcache[key].get(shape,{});row=dict(asset=r['asset'],pdxmesh=r['mesh'],file=relative,shape=shape,index=setting['index'],element=kind,material_error_occurrences=mc,out_of_sync_occurrences=sc,logged_error=bool(mc or sc),no_error_is_not_verified_success=True,object_count=len(r['binary_raw_keys']),material_slots_this_object=len(actual['meshes'])if actual else None,lod=attributes.get('lod'),has_lod=attributes.get('lod')is not None,shape_attributes=attributes.get('shape_attributes'),object_child_order=actual.get('child_order')if actual else None,mesh_attributes=mesh.get('attributes'),has_sfs='sfs'in mesh.get('attributes',[]),has_u1='u1'in mesh.get('attributes',[]),material_binary=mesh.get('material'),geometry_valid_nonempty=mesh.get('valid_nonempty_geometry'),vertices=mesh.get('vertices'),triangles=mesh.get('triangles'),unused_ix_histogram=mesh.get('skin',{}).get('zero_weight_ix_histogram'),raw_name_exact=setting['raw_object_key_exact']);rows.append(row)
   features=dict(element=kind,lod='present'if row['has_lod']else'missing',node_order='/'.join(row['object_child_order']or[]),sfs='present'if row['has_sfs']else'missing',objects='multi'if row['object_count']>1 else'single',index=str(row['index']),object_material_slots=str(row['material_slots_this_object']),binary_shader=mesh.get('material',{}).get('shader','missing'))
   for feature,cat in features.items():c=featuregroups[feature+'='+cat];c['registered_meshsettings']+=1;c['logged_error_meshsettings']+=int(row['logged_error']);c['no_log_error_meshsettings']+=int(not row['logged_error']);c['material_error_occurrences']+=mc;c['out_of_sync_occurrences']+=sc
 counters=dict(total_log_lines=len(lines),log_bytes=len(raw),material_error_occurrences=len(material),material_unique_file_shape=len(matcount),material_unique_files=len({r['file']for r in material}),out_of_sync_occurrences=len(outofsync),out_of_sync_unique_pdxmesh=len({r['pdxmesh']for r in outofsync}),out_of_sync_unique_file_shape=len({(r['file'],r['shape'])for r in outofsync}),out_of_sync_unique_files=len({r['file']for r in outofsync}),registered_meshsettings=len(rows),registered_pdxmesh=len({r['pdxmesh']for r in rows}),registered_unique_file_shape_index=len({(r['file'],r['shape'],r['index'])for r in rows}),registered_unique_files=len({r['file']for r in rows}),logged_error_settings=sum(r['logged_error']for r in rows),no_log_error_settings=sum(not r['logged_error']for r in rows),logged_error_unique_file_shape_index=len({(r['file'],r['shape'],r['index'])for r in rows if r['logged_error']}),no_log_error_pdxmesh=len({r['pdxmesh']for r in rows if not r['logged_error']}));result=dict(log=str(LOG),log_sha256=hashlib.sha256(raw).hexdigest(),counts=counters,error_type_frequencies=[dict(type=k,count=v,example=examples[k])for k,v in error_types.most_common()],material_frequency=[dict(file=f,shape=s,occurrences=n)for(f,s),n in matcount.items()],out_of_sync_frequency=[dict(pdxmesh=p,file=f,shape=s,occurrences=n)for(p,f,s),n in synccount.items()],events=events,unmatched_material_events=[e for e in material if(e['file'],e['shape'])not in matchedmat],unmatched_sync_events=[e for e in outofsync if(e['pdxmesh'],e['file'],e['shape'])not in matchedsync],feature_comparison={k:dict(v)for k,v in featuregroups.items()},registered_rows=rows,logged_error_rows=[r for r in rows if r['logged_error']],no_log_error_control_rows=[r for r in rows if not r['logged_error']],limitations=['No log error is not proof of load/render success; lazy loading and instance sampling can affect coverage.','No active-mod path or installed binary hashes supplied; source-package comparison may differ from active files.','Material failures reference gfx/FX/pdxmesh.shader in the log. The asset declares another shader_file; causality must consider import fallback and LOD/material override registration.']);(OUT/'error-log-asset-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf8');fields=['pdxmesh','file','shape','index','element','material_error_occurrences','out_of_sync_occurrences','logged_error','object_count','material_slots_this_object','has_lod','lod','object_child_order','has_sfs','has_u1','geometry_valid_nonempty','vertices','triangles','raw_name_exact'];
 with(OUT/'error-log-asset-comparison.csv').open('w',encoding='utf-8-sig',newline='')as stream:
  writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
 print('LOG_COMPARISON',counters);print('FEATURES',json.dumps(result['feature_comparison'],ensure_ascii=False));print('UNMATCHED',len(result['unmatched_material_events']),len(result['unmatched_sync_events']))
if __name__=='__main__':main()
