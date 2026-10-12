"""Lossless DDS stage optimizer. V7 may be scanned but never modified.

scan: decode every byte-unique DDS/all supported mip levels; plan uniform1x1 and identical-byte sharing.
stage: write verified shared DDS + old->new manifest only. Caller rewrites asset/mesh references.
prune: after rewrite, prove no asset/mesh DDS references remain to old files, then remove exact originals.
No Blender, resampling of nonuniform pixels, palette/mask shrink, or external dependency installation.
"""
import argparse,hashlib,io,json,os,re,struct,time
from pathlib import Path
from collections import defaultdict,Counter
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import numpy as np
from PIL import Image
V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7/UMA-V7')
KIND_CODES={'normal':'n','properties':'p','ssao':'s','diffuse':'d','mask':'m','texture':'t'}
def kind_for(path):
 n=Path(path).stem.lower()
 if any(k in n for k in ['mask','_area','palette']):return 'mask'
 if any(k in n for k in ['normal','_nrm']):return 'normal'
 if any(k in n for k in ['properties','_props','specular','gloss','roughness']):return 'properties'
 if any(k in n for k in ['ssao','occlusion']):return 'ssao'
 if any(k in n for k in ['diffuse','_diff','albedo']):return 'diffuse'
 return 'texture'
def digest(data):return hashlib.sha256(data).hexdigest()
def layout(data):
 if data[:4]!=b'DDS 'or len(data)<128:raise ValueError('not DDS')
 h,w=struct.unpack_from('<II',data,12);mips=max(1,struct.unpack_from('<I',data,28)[0]);caps2=struct.unpack_from('<I',data,112)[0];fourcc=data[84:88];header=128;block=None;space='legacy';dimension='2D'
 if caps2:dimension='cube_or_volume_or_special'
 if fourcc in [b'DXT1']:block=8
 elif fourcc in [b'DXT3',b'DXT5',b'BC5U',b'BC5S',b'ATI2']:block=16
 elif fourcc in [b'BC4U',b'BC4S',b'ATI1']:block=8
 elif fourcc==b'DX10':
  if len(data)<148:raise ValueError('short DX10 header')
  fmt,rd,misc,array,misc2=struct.unpack_from('<IIIII',data,128);header=148;space='dxgi_'+str(fmt)
  if rd!=3 or array!=1 or misc&4:dimension='cube_array_volume_or_special'
  if fmt in [70,71,72,79,80,81]:block=8
  elif fmt in [73,74,75,76,77,78,82,83,84,94,95,96,97,98,99]:block=16
 return dict(width=w,height=h,mips=mips,fourcc=fourcc.decode('latin1'),header_bytes=header,block_bytes=block,color_space=space,dimension=dimension)
def level_header(data,w,h,payload_size):
 info=layout(data);head=bytearray(data[:info['header_bytes']]);flags=struct.unpack_from('<I',head,8)[0];flags&=~(0x20000|0x800000);flags|=0x1007
 if info['block_bytes']:flags|=0x80000;flags&=~8
 struct.pack_into('<I',head,8,flags);struct.pack_into('<II',head,12,h,w);struct.pack_into('<I',head,20,payload_size if info['block_bytes']else w*max(1,struct.unpack_from('<I',head,88)[0]//8));struct.pack_into('<II',head,24,0,1);struct.pack_into('<IIII',head,108,0x1000,0,0,0);return bytes(head)
def decode_level(data):
 with Image.open(io.BytesIO(data))as im:im.load();return np.asarray(im.convert('RGBA'))
def inspect(data):
 info=layout(data);top=decode_level(data);rgba=[int(x)for x in top[0,0]];uniform=bool(np.all(top==top[0,0]));levels=[dict(level=0,width=info['width'],height=info['height'],uniform=uniform,rgba=rgba if uniform else None)];mip_verified=info['mips']==1
 if uniform and info['mips']>1 and info['block_bytes']and info['dimension']=='2D':
  p=info['header_bytes'];levels=[];mip_verified=True
  for level in range(info['mips']):
   w=max(1,info['width']>>level);h=max(1,info['height']>>level);n=max(1,(w+3)//4)*max(1,(h+3)//4)*info['block_bytes'];payload=data[p:p+n];p+=n
   if len(payload)!=n:mip_verified=False;break
   pixels=decode_level(level_header(data,w,h,n)+payload);same=bool(np.all(pixels==rgba));levels.append(dict(level=level,width=w,height=h,uniform_same_rgba=same));uniform&=same
 return dict(**info,rgba=rgba if uniform else None,uniform_all_verified_levels=uniform and mip_verified,mip_levels_verified=mip_verified,levels=levels,pixel_decoder='Pillow actual DDS->RGBA; all pixels compared; byte-identical files reuse exactly equal source byte validation')
def encode_uniform(data,proof):
 expected=proof['rgba'];stream=io.BytesIO();Image.new('RGBA',(1,1),tuple(expected)).save(stream,format='DDS',pixel_format='DXT5');encoded=stream.getvalue();decoded=decode_level(encoded)
 source_info=layout(data)
 if source_info['fourcc']!='DX10'and decoded.shape==(1,1,4)and decoded[0,0].tolist()==expected:return encoded,'Pillow DXT5 1x1, exact decoded RGBA including alpha'
 # Reuse first native compressed block; only width/height/mips/bounds DDS header changes.
 # First texel and all verified pixels/mips are equal, so preserve source quantized RGB565/alpha exactly.
 info=layout(data)
 if info['block_bytes']and info['dimension']=='2D':
  payload=data[info['header_bytes']:info['header_bytes']+info['block_bytes']];encoded=level_header(data,1,1,len(payload))+payload;decoded=decode_level(encoded)
  if decoded.shape==(1,1,4)and decoded[0,0].tolist()==expected:return encoded,'Original first compressed block retained; DDS1x1 header only; exact decoded RGBA/alpha'
 return None,'No exact1x1 encoding found; preserve original DDS dimensions/bytes'
def validate_root(root,mutation=False):
 root=Path(root).resolve()
 if not root.is_dir():raise ValueError('root does not exist')
 if mutation and(root==V7.resolve()or V7.resolve()in root.parents or '2026-10-11-UMA-V7'in str(root)):raise ValueError('V7 is read-only; stage/prune requires distinct V8 root')
 return root
def collect(root,shared_relative):
 paths=[];excluded=[];shared=(root/shared_relative).resolve()
 for p in sorted(root.rglob('*.dds'),key=lambda x:x.relative_to(root).as_posix()):
  real=p.resolve()
  if not real.is_relative_to(root):excluded.append(dict(path=str(p),reason='resolved outside intended root'));continue
  if real==shared or shared in real.parents:continue
  paths.append(p)
 return paths,excluded
def plan(root,shared_relative):
 paths,excluded=collect(root,shared_relative);proofs={};records=[];datarefs={};errors=[]
 for i,p in enumerate(paths):
  raw=p.read_bytes();sha=digest(raw);relative=p.relative_to(root).as_posix();kind=kind_for(p)
  if sha not in proofs:
   try:proofs[sha]=inspect(raw)
   except Exception as e:proofs[sha]=dict(error=type(e).__name__+': '+str(e));errors.append(dict(path=relative,error=proofs[sha]['error']))
  proof=proofs[sha];record=dict(old=relative,old_bytes=len(raw),sha256=sha,kind=kind,proof=proof);records.append(record);datarefs.setdefault(sha,p)
  if(i+1)%40==0:print('DDS_RGBA_SCAN',i+1,'/',len(paths),'byte_unique',len(proofs),flush=True)
 groups=defaultdict(list)
 for record in records:
  proof=record['proof'];pure=proof.get('uniform_all_verified_levels',False)and record['kind']not in['mask','texture']and proof.get('dimension')=='2D'
  group=('uniform',record['kind'],tuple(proof['rgba']),proof['color_space'])if pure else('identical_bytes',record['kind'],record['sha256']);groups[group].append(record)
 counters=Counter();plans=[];ordinal=Counter();new_payloads={};skipped=[]
 for key,members in sorted(groups.items(),key=lambda x:(x[0][1],x[1][0]['old'])):
  mode,kind=key[:2];source=members[0];raw=datarefs[source['sha256']].read_bytes()
  if mode=='uniform':
   encoded,method=encode_uniform(raw,source['proof'])
   if encoded is None:skipped.append(dict(files=[r['old']for r in members],reason=method));continue
  elif len(members)>1:encoded=raw;method='Byte-identical DDS whole-file copy; preserve dimensions/pixels/mips/metadata exactly'
  else:continue
  old_total=sum(r['old_bytes']for r in members)
  if mode!='uniform'and old_total<=len(encoded):skipped.append(dict(files=[r['old']for r in members],reason='No net byte saving'));continue
  n=ordinal[kind];ordinal[kind]+=1;new=(Path(shared_relative)/f'uma_0001_shared_{KIND_CODES[kind]}{n:02d}_{kind}.dds').as_posix();proof=source['proof'];plan=dict(new=new,kind=kind,mode=mode,source=source['old'],source_rgba=proof.get('rgba'),original_dimensions=[dict(file=r['old'],width=r['proof'].get('width'),height=r['proof'].get('height'))for r in members],new_dimensions=[1,1]if mode=='uniform'else[proof.get('width'),proof.get('height')],method=method,old_files=[r['old']for r in members],original_bytes=old_total,shared_bytes=len(encoded),net_bytes_saved=old_total-len(encoded),new_sha256=digest(encoded));plans.append(plan);new_payloads[new]=encoded;counters[mode+'_groups']+=1;counters[mode+'_old_files']+=len(members)
 mapping={old:g['new']for g in plans for old in g['old_files']};summary=dict(input_dds_files=len(records),input_dds_bytes=sum(r['old_bytes']for r in records),byte_unique_dds=len(proofs),decoded_uniform_all_mips=sum(r['proof'].get('uniform_all_verified_levels',False)for r in records),decode_error_unique_files=len(errors),optimized_old_files=len(mapping),shared_files=len(plans),original_bytes_removed_if_pruned=sum(g['original_bytes']for g in plans),shared_bytes=sum(g['shared_bytes']for g in plans),net_bytes_saved_if_pruned=sum(g['net_bytes_saved']for g in plans),**dict(counters));manifest=dict(version=1,root=str(root),read_only_plan=True,shared_directory=shared_relative,policy='Only all-verified-level uniform actual RGBA textures become1x1; masks/palettes/unknown kinds never shrink; nonuniform only byte-identical sharing, no resampling. Kind and color-space remain distinct.',summary=summary,mapping=mapping,groups=plans,original_files=records,decode_errors=errors,excluded_paths=excluded,skipped_optimization=skipped,references_rewritten=False,old_files_pruned=False);return manifest,new_payloads
def remap_reference(reference,referring_file,root,manifest):
 """Return game-root-relative DDS path; caller updates asset/material/authoring refs.
 Exact path first; basename fallback only if uniquely maps to one original within this root.
 """
 root=Path(root).resolve();ref=reference.replace('\\','/');file=Path(referring_file).resolve();candidate=(root/ref if ref.startswith('gfx/')else file.parent/ref).resolve();mapping=manifest['mapping']
 try:old=candidate.relative_to(root).as_posix()
 except ValueError:old=None
 if old in mapping:return mapping[old]
 matches=[key for key in mapping if Path(key).name==Path(ref).name]
 if len(matches)==1:return mapping[matches[0]]
 return reference
def binary_strings(path):
 data=path.read_bytes()
 if data[:4]!=b'@@b@':raise ValueError('unsupported mesh header')
 p=4;strings=[]
 while p<len(data):
  if data[p]==91:
   while data[p]==91:p+=1
   p=data.index(0,p)+1
  elif data[p]==33:
   p+=1;n=data[p];p+=1+n;kind=chr(data[p]);count=struct.unpack_from('<I',data,p+1)[0];p+=5
   if kind in['i','f']:p+=4*count
   elif kind=='s':
    for _ in range(count):n=struct.unpack_from('<I',data,p)[0];p+=4;strings.append(data[p:p+n].rstrip(b'\0').decode('latin1'));p+=n
   else:raise ValueError('unknown mesh property type')
  else:raise ValueError('unknown mesh token')
 return strings
def prune(root,manifest,report_file):
 originals={r['old']:r for r in manifest['original_files']};referenced=[];failed_scans=[]
 for p in sorted(root.rglob('*')):
  if p.suffix.lower()not in['.asset','.mesh']:continue
  if not p.resolve().is_relative_to(root):raise ValueError('reference file resolved outside root')
  try:
   if p.suffix.lower()=='.mesh':strings=binary_strings(p)
   else:
    text=p.read_text(encoding='utf-8-sig');text=re.sub(r'#[^\n]*','',text);strings=[s.strip('"')for s in re.findall(r'"[^"\n]*"|[^\s{}=]+',text)]
   for ref in strings:
    if not ref.lower().endswith('.dds'):continue
    changed=remap_reference(ref,p,root,manifest)
    if changed!=ref:referenced.append(dict(file=p.relative_to(root).as_posix(),reference=ref,should_be=changed))
  except Exception as e:failed_scans.append(dict(file=str(p),error=str(e)))
 if referenced or failed_scans:
  manifest['prune_blocked']=dict(old_references=referenced,failed_scans=failed_scans);report_file.write_text(json.dumps(manifest,indent=2),encoding='utf8');raise ValueError('prune blocked: old references or unverified reference files remain')
 targets=[]
 for old,new in manifest['mapping'].items():
  p=(root/old).resolve();shared=(root/new).resolve()
  if not p.is_relative_to(root)or not shared.is_relative_to(root)or p==shared:raise ValueError('unsafe prune target')
  if not shared.is_file():raise ValueError('shared texture missing')
  group=next(g for g in manifest['groups']if g['new']==new)
  if digest(shared.read_bytes())!=group['new_sha256']:raise ValueError('verified shared texture changed since stage: '+new)
  if p.exists():
   if digest(p.read_bytes())!=originals[old]['sha256']:raise ValueError('original changed since scan: '+old)
   targets.append((p,p.stat().st_size))
 deleted=0
 for p,size in targets:p.unlink();deleted+=size
 manifest.update(read_only_plan=False,references_rewritten=True,old_files_pruned=True,deleted_original_files=len(targets),deleted_duplicate_and_replaced_bytes=deleted,net_bytes_saved=deleted-sum(g['shared_bytes']for g in manifest['groups']));report_file.write_text(json.dumps(manifest,indent=2),encoding='utf8');return manifest
def selftest():
 cases=[(0,128,0,128),(30,180,0,210),(255,255,255,255),(3,97,183,17),(255,0,3,0)]
 for color in cases:
  stream=io.BytesIO();Image.new('RGBA',(17,9),color).save(stream,format='DDS',pixel_format='DXT5');raw=stream.getvalue();proof=inspect(raw);encoded,method=encode_uniform(raw,proof);assert encoded is not None;assert decode_level(encoded)[0,0].tolist()==proof['rgba'];assert layout(encoded)['width']==layout(encoded)['height']==1
 print('DDS_SELFTEST_EXACT_RGBA_ALPHA',len(cases),flush=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['scan','stage','prune','selftest']);ap.add_argument('--root');ap.add_argument('--manifest');ap.add_argument('--shared-directory',default='gfx/models/portraits/uma/0001/shared');args=ap.parse_args()
 if args.action=='selftest':selftest();return
 if not args.root or not args.manifest:ap.error('root and manifest required')
 root=validate_root(args.root,args.action!='scan');report=Path(args.manifest).resolve();report.parent.mkdir(parents=True,exist_ok=True)
 if args.action=='prune':manifest=json.loads(report.read_text());assert Path(manifest['root']).resolve()==root;result=prune(root,manifest,report);print('DDS_PRUNED',result['deleted_original_files'],result['net_bytes_saved'],flush=True);return
 manifest,payloads=plan(root,args.shared_directory)
 if args.action=='stage':
  for group in manifest['groups']:
   destination=(root/group['new']).resolve()
   if not destination.is_relative_to(root):raise ValueError('shared path outside root')
   destination.parent.mkdir(parents=True,exist_ok=True);data=payloads[group['new']]
   if destination.exists()and destination.read_bytes()!=data:raise ValueError('shared ordinal name collision: '+str(destination))
   destination.write_bytes(data)
   if group['mode']=='uniform':
    proof=inspect(destination.read_bytes());assert proof['width']==proof['height']==1 and proof['rgba']==group['source_rgba']
   else:assert digest(destination.read_bytes())==group['new_sha256']
  manifest.update(read_only_plan=False,shared_files_written=True,old_files_pruned=False)
 report.write_text(json.dumps(manifest,indent=2),encoding='utf8');print('DDS_PLAN',manifest['summary'],str(report),flush=True)
if __name__=='__main__':main()
