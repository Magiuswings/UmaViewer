"""Read-only V7 asset/actual binary object-name audit, independently skip typed payloads."""
import re,json,struct,hashlib,sys
from pathlib import Path
V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/UMA-V7');GAME=Path('D:/steam/steamapps/common/Crusader Kings III/game');OUT=Path(__file__).parent
def tokens(text):return [(m.group(),text.count('\n',0,m.start())+1)for m in re.finditer(r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}=]|[^\s{}=#]+',text)if not m.group().startswith('#')]
def parse(text):
 text=text.lstrip('\ufeff');ts=tokens(text);pos=0
 def level():
  nonlocal pos
  rows=[]
  while pos<len(ts):
   key,line=ts[pos];pos+=1
   if key=='}':break
   if pos<len(ts)and ts[pos][0]=='=':
    pos+=1;value=ts[pos][0];pos+=1;rows.append(dict(key=key.strip('"'),line=line,children=level()if value=='{'else None,value=None if value=='{'else value.strip('"')))
   else:rows.append(dict(key=None,line=line,children=level()if key=='{'else None,value=None if key=='{'else key.strip('"')))
  return rows
 return level()
def children(nodes,key):return [n for n in nodes if n['key']==key]
def value(nodes,key,default=None):return next((n['value']for n in nodes if n['key']==key),default)
def raw_scan(path):
 data=path.read_bytes();assert data[:4]==b'@@b@';p=4;stack=[];objects=[];shapes=[];current=None
 while p<len(data):
  offset=p
  if data[p]==91:
   depth=0
   while data[p]==91:depth+=1;p+=1
   end=data.index(0,p);name=data[p:end].decode('latin1');nameoffset=p;p=end+1;stack=stack[:depth-1]+[name];record=dict(name=name,depth=depth,offset=offset,name_offset=nameoffset,path='/'.join(stack),name_hex=data[nameoffset:end+1].hex());objects.append(record)
   if depth==2 and stack[0]=='object':record['mesh_children']=0;shapes.append(record);current=record
   if depth==3 and name=='mesh'and current is not None:current['mesh_children']+=1
  elif data[p]==33:
   length=data[p+1];p+=2;name=data[p:p+length].decode('latin1');p+=length;kind=chr(data[p]);count=struct.unpack_from('<I',data,p+1)[0];p+=5
   if kind in ['i','f']:p+=count*4
   elif kind=='s':
    for _ in range(count):length=struct.unpack_from('<I',data,p)[0];p+=4+length
   else:raise ValueError((path,p,kind,name))
  else:raise ValueError((path,p,data[p:p+20]))
 assert p==len(data);return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),shape_keys=shapes,object_count=len(objects),consumed_exact_eof=True)
cache={}
def binary(path):
 if str(path)not in cache:cache[str(path)]=raw_scan(path)
 return cache[str(path)]
def asset_audit(asset):
 rows=[]
 for block in children(parse(asset.read_text(encoding='utf-8-sig')),'pdxmesh'):
  fields=block['children'];file=value(fields,'file');name=value(fields,'name');path=asset.parent/file if file else None
  if not path or not path.exists():rows.append(dict(asset=str(asset),line=block['line'],mesh=name,file=file,violation='mesh_file_missing'));continue
  scan=binary(path);keys={s['name']:s for s in scan['shape_keys']};settings=[]
  for setting in children(fields,'meshsettings'):
   nodes=setting['children'];key=value(nodes,'name');index=int(value(nodes,'index','0'));matched=keys.get(key);row=dict(line=setting['line'],name=key,index=index,raw_object_key_exact=key in keys,raw_object_keys=list(keys),raw_object_bytes=matched['name_hex']if matched else None,raw_offset=matched['name_offset']if matched else None,submesh_count=matched['mesh_children']if matched else None,violations=[])
   if not matched:row['violations'].append('meshsettings_name_not_in_raw_binary')
   elif index>=matched['mesh_children']:row['violations'].append('meshsettings_index_out_of_range')
   row['textures']={k:value(nodes,k)for k in ['texture_diffuse','texture_normal','texture_specular']}
   for prop,tex in row['textures'].items():
    if tex and not(asset.parent/tex).exists()and not(V7/tex).exists()and not(GAME/tex).exists():row['violations'].append('texture_missing:'+prop+':'+tex)
   settings.append(row)
  shapechecks=[]
  for target in children(fields,'blend_shape'):
   f=value(target['children'],'type');targetpath=asset.parent/f
   if targetpath.exists():bs=binary(targetpath);shapechecks.append(dict(file=str(targetpath),raw_keys=[s['name']for s in bs['shape_keys']],same_raw_keys=[s['name']for s in bs['shape_keys']]==list(keys)))
   else:shapechecks.append(dict(file=str(targetpath),violation='shape_file_missing'))
  rows.append(dict(asset=str(asset),line=block['line'],mesh=name,file=str(path),binary_sha256=scan['sha256'],binary_raw_keys=list(keys),settings=settings,blend_shape_checks=shapechecks,raw_shape_evidence=scan['shape_keys']))
 return rows
def main():
 OUT.mkdir(exist_ok=True);rows=[]
 for i,asset in enumerate(sorted(V7.rglob('*.asset'))):
  rows+=asset_audit(asset)
  if i%10==0:print('ASSET_AUDIT_PROGRESS',i+1,asset.name,flush=True)
 stockfiles=[GAME/'gfx/models/portraits/female_body/female_body.asset',GAME/'gfx/models/portraits/f_legwear/mena/nob_01/f_legwear_secular_mena_nob_01.asset',GAME/'gfx/models/portraits/f_clothes/western/nob_01/f_clothes_secular_western_nob_01.asset']
 stock=[]
 for asset in stockfiles:
  if asset.exists():stock+=asset_audit(asset)
 violations=[dict(asset=r['asset'],mesh=r['mesh'],file=r.get('file'),setting=s)for r in rows for s in r.get('settings',[])if s['violations']];out=dict(scope=str(V7),read_only=True,method='Independent raw typed-payload scanner records exact depth2 object keys, null termination, offsets and bytes. Does not invoke io_pdx_mesh reader/writer. Not live engine proof.',counts=dict(assets=len(list(V7.rglob('*.asset'))),pdxmesh_definitions=len(rows),meshsettings=sum(len(r.get('settings',[]))for r in rows),unique_binary_meshes=len(cache),violations=len(violations)),rows=rows,violations=violations,stock_comparison=stock,binary_scans=list(cache.values()));(OUT/'asset-registration-audit.json').write_text(json.dumps(out,indent=2),encoding='utf8');print('AUDIT',out['counts']);print('FOCUS',[(r['mesh'],r['binary_raw_keys'],[(s['name'],s['raw_object_key_exact'])for s in r['settings']])for r in rows if r['mesh']in ['uma_0001_shoes_0051_01_00_mesh','uma_0001_shoes_0050_00_00_mesh']]);print('STOCK',[(r['mesh'],r['binary_raw_keys'],[(s['name'],s['raw_object_key_exact'])for s in r['settings']])for r in stock])
if __name__=='__main__':main()
