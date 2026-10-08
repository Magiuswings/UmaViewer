"""Read-only SQLite/SQLite3MC access. Runtime asset keys are never logged or serialized."""
import ctypes as c
from pathlib import Path
import re
import sqlite3

def repository_bytes(repo,name):
    text=(Path(repo)/'Assets/Scripts/Config.cs').read_text(encoding='utf8')
    text=re.sub(r'/\*.*?\*/','',text,flags=re.S);text=re.sub(r'//[^\n]*','',text)
    match=re.search(r'\b'+re.escape(name)+r'\s*=\s*new\s+byte\s*\[\s*\]\s*\{([^}]+)\}',text,re.S)
    if not match:raise ValueError('Runtime key definition not found in source: '+name)
    tokens=[t.strip() for t in match[1].split(',') if t.strip()]
    return bytes(int(t,0) for t in tokens)

class Database:
    def __init__(self,path,repo=None,region='auto'):
        self.path=Path(path).resolve();self.connection=None;self.handle=None;self.dll=None
        with self.path.open('rb') as f:plain=f.read(16)==b'SQLite format 3\0'
        self.encrypted=not plain;self.region='plain'
        if plain:
            self.connection=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
            self.connection.row_factory=sqlite3.Row
            self.connection.execute('PRAGMA query_only=ON');self.connection.execute('PRAGMA temp_store=MEMORY')
            return
        if repo is None:raise ValueError('Encrypted meta requires --umaviewer-source for the native reader and runtime configuration')
        native=Path(repo)/'Assets/Plugins/sqlite3mc_x64.dll'
        if not native.is_file():raise FileNotFoundError('SQLite3MC runtime missing: '+str(native))
        self.dll=c.CDLL(str(native));d=self.dll
        d.sqlite3_open_v2.argtypes=[c.c_char_p,c.POINTER(c.c_void_p),c.c_int,c.c_void_p];d.sqlite3_open_v2.restype=c.c_int
        d.sqlite3_close.argtypes=[c.c_void_p];d.sqlite3_close.restype=c.c_int
        d.sqlite3mc_config.argtypes=[c.c_void_p,c.c_char_p,c.c_int];d.sqlite3mc_config.restype=c.c_int
        d.sqlite3_key.argtypes=[c.c_void_p,c.c_void_p,c.c_int];d.sqlite3_key.restype=c.c_int
        d.sqlite3_prepare_v2.argtypes=[c.c_void_p,c.c_char_p,c.c_int,c.POINTER(c.c_void_p),c.c_void_p];d.sqlite3_prepare_v2.restype=c.c_int
        d.sqlite3_step.argtypes=[c.c_void_p];d.sqlite3_step.restype=c.c_int
        d.sqlite3_finalize.argtypes=[c.c_void_p];d.sqlite3_finalize.restype=c.c_int
        d.sqlite3_column_count.argtypes=[c.c_void_p];d.sqlite3_column_count.restype=c.c_int
        d.sqlite3_column_name.argtypes=[c.c_void_p,c.c_int];d.sqlite3_column_name.restype=c.c_char_p
        d.sqlite3_column_type.argtypes=[c.c_void_p,c.c_int];d.sqlite3_column_type.restype=c.c_int
        d.sqlite3_column_int64.argtypes=[c.c_void_p,c.c_int];d.sqlite3_column_int64.restype=c.c_int64
        d.sqlite3_column_double.argtypes=[c.c_void_p,c.c_int];d.sqlite3_column_double.restype=c.c_double
        d.sqlite3_column_text.argtypes=[c.c_void_p,c.c_int];d.sqlite3_column_text.restype=c.c_char_p
        d.sqlite3_errmsg.argtypes=[c.c_void_p];d.sqlite3_errmsg.restype=c.c_char_p
        base=repository_bytes(repo,'DBBaseKey')
        for candidate in (['jp','global'] if region=='auto' else [region]):
            handle=c.c_void_p()
            if d.sqlite3_open_v2(str(self.path).encode('utf8'),c.byref(handle),1,None):
                if handle:d.sqlite3_close(handle)
                raise RuntimeError('Cannot open encrypted meta read-only')
            self.handle=handle
            try:
                d.sqlite3mc_config(handle,b'cipher',3)
                original=repository_bytes(repo,'DBKey' if candidate=='jp' else 'GlobalDBKey')
                key=bytes(v^base[i%13] for i,v in enumerate(original));buffer=c.create_string_buffer(key)
                if d.sqlite3_key(handle,buffer,len(key))!=0:raise RuntimeError('Database key setup failed')
                list(self.rows("SELECT name FROM sqlite_master LIMIT 1"))
                self.region=candidate
                # Read-only handle; keep all temporary SQL work in memory.
                list(self.rows('PRAGMA query_only=ON'));list(self.rows('PRAGMA temp_store=MEMORY'))
                return
            except RuntimeError:
                d.sqlite3_close(handle);self.handle=None
        raise RuntimeError('Meta could not be read with the repository supported region profiles; no source files changed')

    def rows(self,sql):
        if self.connection:
            for row in self.connection.execute(sql):yield dict(row)
            return
        statement=c.c_void_p();raw=sql.encode('utf8');d=self.dll
        rc=d.sqlite3_prepare_v2(self.handle,raw,len(raw),c.byref(statement),None)
        if rc!=0:
            if statement:d.sqlite3_finalize(statement)
            raise RuntimeError('Read-only SQLite query failed: '+d.sqlite3_errmsg(self.handle).decode('utf8','replace'))
        try:
            count=d.sqlite3_column_count(statement);names=[d.sqlite3_column_name(statement,i).decode('utf8') for i in range(count)]
            while True:
                rc=d.sqlite3_step(statement)
                if rc==101:break
                if rc!=100:raise RuntimeError('Read-only SQLite step failed')
                row={}
                for i,name in enumerate(names):
                    kind=d.sqlite3_column_type(statement,i)
                    if kind==5:value=None
                    elif kind==1:value=d.sqlite3_column_int64(statement,i)
                    elif kind==2:value=d.sqlite3_column_double(statement,i)
                    else:
                        data=d.sqlite3_column_text(statement,i);value=data.decode('utf8','replace') if data else ''
                    row[name]=value
                yield row
        finally:d.sqlite3_finalize(statement)

    def close(self):
        if self.connection:self.connection.close();self.connection=None
        if self.handle:self.dll.sqlite3_close(self.handle);self.handle=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
