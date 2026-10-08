"""UmaViewer-compatible command-line reader for local raw Persistent assets."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass,field

from raw_source import RawSource,safe_relative,raw_relative
from sqlite_mc import Database,repository_bytes

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def sql_quote(value):return "'"+str(value).replace("'","''")+"'"
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

@dataclass
class Asset:
    name:str
    file_hash:str
    kind:str
    dependencies:list
    size:int|None
    encrypted:bool
    _key:int=field(repr=False,default=0)

class Catalog:
    def __init__(self,source,repo,region):
        self.source=source;self.repo=Path(repo);self.db=Database(source.meta,self.repo,region);self.cache={}
        self.columns={r['name'] for r in self.db.rows('PRAGMA table_info(a)')}
        if not {'n','h','m','d'}<=self.columns:raise ValueError('Unsupported meta schema')
    def _entry(self,row):
        member=self.source.member_name(raw_relative(row['h']))
        if self.source.archive:size=self.source.items.get(member,{}).get('size')
        else:
            raw_path=self.source.path_for_hash(row['h']);size=raw_path.stat().st_size if raw_path.is_file() else None
        return Asset(row['n'],row['h'],row.get('m') or '',[s.strip() for s in (row.get('d') or '').split(';') if s.strip()],size,bool(row.get('e') or 0),int(row.get('e') or 0))
    def select(self,names=(),prefixes=(),contains=None,limit=None):
        clauses=[]
        if names:clauses.append('n IN ('+','.join(sql_quote(n) for n in names)+')')
        for prefix in prefixes:
            value=prefix.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            clauses.append('n LIKE '+sql_quote(value)+" ESCAPE '\\'")
        where='('+' OR '.join(clauses)+')' if clauses else '1'
        if contains:where+=' AND instr(n,'+sql_quote(contains)+')>0'
        fields='n,h,m,d'+(',e' if 'e' in self.columns else '')
        query='SELECT '+fields+' FROM a WHERE '+where+' AND n IS NOT NULL AND h IS NOT NULL ORDER BY n'
        if limit is not None:query+=' LIMIT '+str(int(limit))
        result=[]
        for row in self.db.rows(query):
            entry=self._entry(row);self.cache[entry.name]=entry;result.append(entry)
        return result
    def get(self,name):
        if name not in self.cache:
            values=self.select(names=[name]);return values[0] if values else None
        return self.cache[name]
    def closure(self,roots):
        found={};visiting=set();cycles=[];missing=[]
        def visit(entry):
            if entry.name in visiting:cycles.append(entry.name);return
            if entry.name in found:return
            visiting.add(entry.name);found[entry.name]=entry
            for name in entry.dependencies:
                child=self.get(name)
                if child is None:missing.append(dict(parent=entry.name,name=name))
                else:visit(child)
            visiting.remove(entry.name)
        for root in roots:visit(root)
        return list(found.values()),missing,cycles
    def public(self,entry):
        return dict(name=entry.name,hash=entry.file_hash,type=entry.kind,size_bytes=entry.size,encrypted=entry.encrypted,
                    dependency_count=len(entry.dependencies),present=self.source.has(raw_relative(entry.file_hash)))

def decrypt_bundle(raw,entry,ab_base):
    if not entry.encrypted or len(raw)<=256:return raw
    integer=entry._key.to_bytes(8,'little',signed=True)
    key=bytes(base^integer[j] for base in ab_base for j in range(8))
    if not key:raise ValueError('Asset decoding configuration unavailable')
    output=bytearray(raw)
    for offset in range(len(key)):
        start=256+offset
        if start>=len(raw):break
        value=key[start%len(key)]
        output[start::len(key)]=raw[start::len(key)].translate(bytes(v^value for v in range(256)))
    return bytes(output)

def decode_selected(catalog,roots,output,dependencies=True,validate=True,allow_missing=False):
    output=Path(output).resolve()
    if output.exists() or output.with_name(output.name+'-manifest.json').exists():raise FileExistsError('Use a fresh decoded output name: '+str(output))
    if output.is_relative_to(catalog.source.source if catalog.source.source.is_dir() else catalog.source.source.parent):raise ValueError('Decoded output must preserve the input directory')
    entries,missing_index,cycles=catalog.closure(roots) if dependencies else (roots,[],[])
    missing_files=[catalog.public(e) for e in entries if not catalog.source.has(raw_relative(e.file_hash))]
    if (missing_index or missing_files) and not allow_missing:
        raise ValueError('Dependency closure incomplete: '+str(len(missing_index))+' unindexed, '+str(len(missing_files))+' uncached. Use --allow-missing only for a deliberate partial extraction.')
    present=[e for e in entries if catalog.source.has(raw_relative(e.file_hash))]
    catalog.source.fetch([raw_relative(e.file_hash).as_posix() for e in present])
    output.mkdir(parents=True);ab_base=repository_bytes(catalog.repo,'ABKey');records=[];errors=[]
    if validate:
        import UnityPy
    for index,entry in enumerate(present):
        original=catalog.source.path_for_hash(entry.file_hash);raw=original.read_bytes()
        bundle=Path(entry.name).suffix=='' and raw.startswith(b'UnityFS\0')
        decoded=decrypt_bundle(raw,entry,ab_base) if bundle else raw
        path=output/safe_relative(entry.name);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(decoded)
        record=dict(catalog.public(entry),decoded_file=path.relative_to(output).as_posix(),source_sha256=hashlib.sha256(raw).hexdigest(),decoded_sha256=hashlib.sha256(decoded).hexdigest(),bytes=len(decoded),bundle=bundle,
                    decoded_encryption=bundle and entry.encrypted,dependencies=entry.dependencies)
        if validate and bundle:
            try:
                env=UnityPy.Environment();env.load_file(decoded,name=entry.name);record['unity_object_types']=dict(Counter(o.type.name for o in env.objects));record['unitypy_validated']=True
            except Exception as ex:
                record['unitypy_validated']=False;errors.append(dict(name=entry.name,error=type(ex).__name__+': '+str(ex)))
        records.append(record)
        if (index+1)%100==0:print('DECODE_PROGRESS '+str(index+1)+'/'+str(len(present)),flush=True)
    manifest=dict(source=catalog.source.description(),roots=[r.name for r in roots],region_profile=catalog.db.region,meta_sha256=sha(catalog.source.meta),
                  assets=records,missing_dependencies=missing_index,missing_files=missing_files,dependency_cycles=cycles,errors=errors,
                  source_original_files_unmodified=True,private_keys_serialized=False,passed=not errors and not missing_index and not missing_files)
    # Keep reports outside named assets so the existing Package parser receives only real assets.
    write(output.with_name(output.name+'-manifest.json'),manifest)
    if errors:raise RuntimeError('Decoded bundle validation failed for '+str(len(errors))+' resources; see manifest')
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Persistent folder, folder containing final split .zip, or final .zip')
    parser.add_argument('--workspace',type=Path,required=True,help='Separate workspace/cache volume; E drive recommended here')
    parser.add_argument('--umaviewer-source',type=Path,default=Path(__file__).resolve().parents[2],help='Existing repository; defaults to the parent repo after installation. Native DLL/configuration are read without key dumps')
    parser.add_argument('--seven-zip',type=Path)
    parser.add_argument('--region',choices=['auto','jp','global'],default='auto')
    sub=parser.add_subparsers(dest='command',required=True)
    doctor=sub.add_parser('doctor',help='Read meta/master, compare raw cache availability and report source layout')
    doctor.add_argument('--report',type=Path)
    listing=sub.add_parser('list',help='List meaningful logical asset names without expanding dat')
    listing.add_argument('--prefix',action='append',default=[]);listing.add_argument('--contains');listing.add_argument('--limit',type=int,default=50);listing.add_argument('--json',type=Path)
    extracting=sub.add_parser('extract',help='Resolve dependencies and produce named decoded assets for HeadlessExporter')
    extracting.add_argument('--name',action='append',default=[]);extracting.add_argument('--prefix',action='append',default=[])
    extracting.add_argument('--output',type=Path,required=True);extracting.add_argument('--no-dependencies',action='store_true');extracting.add_argument('--allow-missing',action='store_true');extracting.add_argument('--skip-validate',action='store_true');extracting.add_argument('--zip',type=Path)
    inspecting=sub.add_parser('inspect',help='Decode one selected dependency closure and list actual Unity object types')
    inspecting.add_argument('--name',required=True);inspecting.add_argument('--output',type=Path,required=True)
    master=sub.add_parser('master',help='Query a selected master table read-only')
    master.add_argument('--table',required=True);master.add_argument('--columns',default='*');master.add_argument('--id',type=int);master.add_argument('--id-column',default='id');master.add_argument('--limit',type=int,default=20);master.add_argument('--json',type=Path)
    args=parser.parse_args()
    source=RawSource(args.source,args.workspace,args.seven_zip)
    scratch=args.workspace.resolve()/'.temp';scratch.mkdir(parents=True,exist_ok=True)
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(scratch)
    tempfile.tempdir=str(scratch)
    catalog=Catalog(source,args.umaviewer_source,args.region)
    try:
        if args.command=='doctor':
            present_hashes=source.raw_hashes();total=present=encrypted=0;types=Counter();chara=Counter();generic_faces=[]
            encrypted_sql='CASE WHEN e!=0 THEN 1 ELSE 0 END' if 'e' in catalog.columns else '0'
            for row in catalog.db.rows('SELECT n,h,m,'+encrypted_sql+' AS encrypted FROM a'):
                if not row['n'] or not row['h']:continue
                total+=1;present+=row['h'] in present_hashes;encrypted+=row['encrypted'];types[row['m']]+=1
                match=re.match(r'3d/chara/(?:head/chr|body/bdy)(\d{4})_',row['n'])
                if match:chara[match[1]]+=1
                if re.fullmatch(r'3d/chara/head/chr0001_00/pfb_chr0001_00_face\d{3}',row['n']):generic_faces.append(dict(name=row['n'],present=row['h'] in present_hashes))
            result=dict(source=source.description(),meta_encrypted=catalog.db.encrypted,region_profile=catalog.db.region,meta_entries=total,locally_present_entries=present,missing_local_entries=total-present,
                        encrypted_asset_entries=encrypted,raw_unique_files=len(present_hashes),type_distribution=dict(types),character_asset_counts=dict(chara),generic_face_prefabs=generic_faces,private_keys_serialized=False)
            if source.master.is_file():
                with Database(source.master,args.umaviewer_source,args.region) as db:
                    result['master']=dict(bytes=source.master.stat().st_size,encrypted=db.encrypted,characters=list(db.rows('SELECT count(*) AS count FROM chara_data'))[0]['count'],mobs=list(db.rows('SELECT count(*) AS count FROM mob_data'))[0]['count'])
            write(args.report or args.workspace/'doctor.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
        elif args.command=='list':
            entries=catalog.select(prefixes=args.prefix,contains=args.contains,limit=args.limit);result=[catalog.public(e) for e in entries]
            if args.json:write(args.json,result)
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        elif args.command in ('extract','inspect'):
            names=[args.name] if args.command=='inspect' else args.name;prefixes=[] if args.command=='inspect' else args.prefix
            if not names and not prefixes:parser.error('Select --name and/or --prefix; bulk all-assets extraction is not implicit')
            roots=catalog.select(names=names,prefixes=prefixes)
            absent=set(names)-{r.name for r in roots}
            if absent:raise ValueError('Requested logical names not in meta: '+', '.join(sorted(absent)))
            if not roots:raise ValueError('No resources matched')
            manifest=decode_selected(catalog,roots,args.output,not getattr(args,'no_dependencies',False),not getattr(args,'skip_validate',False),getattr(args,'allow_missing',False))
            if getattr(args,'zip',None):
                if args.zip.exists():raise FileExistsError(args.zip)
                args.zip.parent.mkdir(parents=True,exist_ok=True)
                with zipfile.ZipFile(args.zip,'w',zipfile.ZIP_DEFLATED) as archive:
                    for file in sorted(args.output.rglob('*')):
                        if file.is_file():archive.write(file,file.relative_to(args.output).as_posix())
                with zipfile.ZipFile(args.zip) as archive:
                    if archive.testzip() is not None:raise RuntimeError('Named ZIP CRC verification failed')
            if args.command=='inspect':print(json.dumps([dict(name=e['name'],types=e.get('unity_object_types'),validated=e.get('unitypy_validated')) for e in manifest['assets'] if e['bundle']],ensure_ascii=False,indent=2),flush=True)
            else:print(json.dumps(dict(passed=manifest['passed'],roots=len(roots),named_assets=len(manifest['assets']),encrypted_bundles_decoded=sum(e['decoded_encryption'] for e in manifest['assets']),output=str(args.output.resolve()),manifest=str(args.output.with_name(args.output.name+'-manifest.json'))),ensure_ascii=False),flush=True)
        elif args.command=='master':
            identifiers=[args.table,args.id_column]+([] if args.columns=='*' else args.columns.split(','))
            if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',s) for s in identifiers):raise ValueError('Master identifiers must be SQL column/table names')
            with Database(source.master,args.umaviewer_source,args.region) as db:
                query='SELECT '+args.columns+' FROM '+args.table
                if args.id is not None:query+=' WHERE '+args.id_column+'='+str(args.id)
                query+=' LIMIT '+str(args.limit);result=list(db.rows(query))
                if args.json:write(args.json,result)
                print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    finally:catalog.db.close()

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,sqlite3.Error) as error:
        print('ERROR: '+str(error),file=sys.stderr);raise SystemExit(2)
