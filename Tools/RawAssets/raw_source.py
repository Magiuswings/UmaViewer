"""Read raw Persistent directories or lazily extract selected files from split ZIPs."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import shutil
import subprocess
import tempfile

def safe_relative(name):
    path=PurePosixPath(str(name).replace('\\','/'))
    if path.is_absolute() or not path.parts or any(p in ('','..','.') or ':' in p or p.endswith((' ','.')) for p in path.parts):
        raise ValueError('Unsafe resource path')
    return Path(*path.parts)

def raw_relative(file_hash):
    if not re.fullmatch(r'[A-Za-z0-9]{20,128}',file_hash):raise ValueError('Invalid raw asset identifier')
    return Path('dat')/file_hash[:2]/file_hash

class RawSource:
    def __init__(self,source,workspace,seven_zip=None):
        self.source=Path(source).resolve();self.workspace=Path(workspace).resolve()
        if self.source==self.workspace or self.workspace.is_relative_to(self.source if self.source.is_dir() else self.source.parent):
            raise ValueError('Workspace must be separate from the original input directory')
        self.workspace.mkdir(parents=True,exist_ok=True)
        self.archive=None;self.root=None;self.items={};self.prefix='';self.parts=[]
        if self.source.is_dir():
            for root in (self.source,self.source/'Persistent'):
                if (root/'meta').is_file() and (root/'dat').is_dir():self.root=root;break
            if self.root is None:
                archives=list(self.source.glob('*.zip'))
                if len(archives)!=1:raise ValueError('Expected one split ZIP final .zip, or a Persistent directory with meta/dat')
                self.archive=archives[0]
        elif self.source.is_file() and self.source.suffix.lower()=='.zip':self.archive=self.source
        else:raise FileNotFoundError('Raw source directory or final ZIP does not exist')
        self.seven_zip=Path(seven_zip).resolve() if seven_zip else None
        if self.archive:
            if self.seven_zip is None:
                found=shutil.which('7z') or str(Path('C:/Program Files/7-Zip/7z.exe'))
                self.seven_zip=Path(found)
            if not self.seven_zip.is_file():raise FileNotFoundError('Split ZIP support requires an existing 7-Zip executable; supply --seven-zip')
            self.parts=sorted(self.archive.parent.glob(self.archive.stem+'.z[0-9][0-9]'))+[self.archive]
            self._inventory()
            self.root=self.workspace/'raw-cache'/self.prefix if self.prefix else self.workspace/'raw-cache'
            self.fetch(['meta','master/master.mdb'])
        self.meta=self.root/'meta';self.master=self.root/'master/master.mdb'
        if not self.meta.is_file():raise FileNotFoundError('meta is absent in the selected raw source')

    def _inventory(self):
        fingerprint=[dict(name=p.name,size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in self.parts]
        cache=self.workspace/'archive-inventory.json'
        if cache.exists():
            data=json.loads(cache.read_text(encoding='utf8'))
            if data.get('archive')==str(self.archive) and data.get('volumes')==fingerprint:
                self.items=data['items'];self.prefix=data['prefix'];return
        result=subprocess.run([str(self.seven_zip),'l','-slt','-sccUTF-8',str(self.archive)],capture_output=True,text=True,encoding='utf8',errors='replace')
        if result.returncode:raise RuntimeError('Archive inventory failed: '+result.stderr[:500])
        for block in result.stdout.split('\n\n'):
            fields=dict(line.split(' = ',1) for line in block.splitlines() if ' = ' in line)
            if fields.get('Folder')!='-' or 'Size' not in fields:continue
            name=fields['Path'].replace('\\','/');safe_relative(name)
            self.items[name]=dict(size=int(fields['Size']),crc32=fields.get('CRC'),volume=int(fields.get('Volume Index','0')))
        candidates=[name for name in self.items if name=='meta' or name.endswith('/meta')]
        if len(candidates)!=1:raise ValueError('Archive must contain one identifiable meta database')
        self.prefix=candidates[0][:-5] if candidates[0]!='meta' else ''
        cache.write_text(json.dumps(dict(archive=str(self.archive),volumes=fingerprint,prefix=self.prefix,items=self.items),ensure_ascii=False,separators=(',',':')),encoding='utf8')

    def member_name(self,relative):
        rel=safe_relative(relative).as_posix()
        return self.prefix+'/'+rel if self.prefix else rel

    def has(self,relative):
        return self.member_name(relative) in self.items if self.archive else (self.root/safe_relative(relative)).is_file()

    def fetch(self,relatives):
        if not self.archive:return []
        needed=[]
        for relative in relatives:
            name=self.member_name(relative)
            if name not in self.items:continue
            target=self.workspace/'raw-cache'/safe_relative(name)
            if target.is_file() and target.stat().st_size==self.items[name]['size']:continue
            needed.append(name)
        if not needed:return []
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=self.workspace,prefix='selected-',suffix='.txt',delete=False) as selected:
            selected.write('\n'.join(needed)+'\n');listfile=Path(selected.name)
        destination=self.workspace/'raw-cache';destination.mkdir(exist_ok=True)
        try:result=subprocess.run([str(self.seven_zip),'x','-y','-bsp0','-sccUTF-8','-scsUTF-8','-o'+str(destination),str(self.archive),'@'+str(listfile)],capture_output=True,text=True,encoding='utf8',errors='replace')
        finally:listfile.unlink()
        if result.returncode:raise RuntimeError('Selected archive extraction failed: '+result.stderr[:500])
        for name in needed:
            path=destination/safe_relative(name)
            if not path.is_file() or path.stat().st_size!=self.items[name]['size']:raise RuntimeError('Selected member was not extracted correctly: '+name)
        return needed

    def path_for_hash(self,file_hash):return self.root/raw_relative(file_hash)

    def raw_hashes(self):
        if self.archive:
            prefix=self.member_name('dat')+'/'
            return {name.rsplit('/',1)[-1] for name in self.items if name.startswith(prefix) and len(name.rsplit('/',1)[-1])>=20}
        return {file.name for folder in (self.root/'dat').iterdir() if folder.is_dir() for file in folder.iterdir() if file.is_file()}

    def description(self):
        return dict(source=str(self.source),kind='split_zip' if self.archive and len(self.parts)>1 else 'zip' if self.archive else 'directory',
                    archive_volumes=len(self.parts),archive_members=len(self.items) if self.archive else None,
                    archive_original_bytes=sum(p.stat().st_size for p in self.parts) if self.archive else None,
                    extracted_root=str(self.root),workspace=str(self.workspace))
