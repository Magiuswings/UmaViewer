"""Focused regressions for UmaViewer's decoding boundaries and read-only SQL."""
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from raw_source import safe_relative,raw_relative
from sqlite_mc import Database
from uma_raw import Asset,decrypt_bundle

class DecodeTests(unittest.TestCase):
    def test_header_and_absolute_key_position(self):
        rng=random.Random(611)
        for count in (0,1,255,256,257,344,1025,8197):
            raw=bytes(rng.randrange(256) for _ in range(count));base=bytes(range(11))
            for integer in (0x102030405060708,-72623859790382856):
                entry=Asset('3d/test', 'A'*32, 'chara',[],count,True,integer)
                word=integer.to_bytes(8,'little',signed=True)
                keys=bytes(b^w for b in base for w in word)
                expected=bytes(v if i<256 else v^keys[i%len(keys)] for i,v in enumerate(raw))
                result=decrypt_bundle(raw,entry,base)
                self.assertEqual(result,expected)
                self.assertEqual(result[:256],raw[:256])
                self.assertEqual(decrypt_bundle(result,entry,base),raw)
    def test_unencrypted_passthrough(self):
        raw=b'UnityFS\0'+b'a'*1024
        self.assertEqual(decrypt_bundle(raw,Asset('test','A'*32,'chara',[],len(raw),False),b''),raw)
    def test_sensitive_seed_not_in_repr(self):
        self.assertNotIn('_key',repr(Asset('test','A'*32,'chara',[],1,True,987654321)))
        self.assertNotIn('987654321',repr(Asset('test','A'*32,'chara',[],1,True,987654321)))

class SourceTests(unittest.TestCase):
    def test_safe_asset_paths(self):
        self.assertEqual(safe_relative('3d/chara/head/pfb_test').as_posix(),'3d/chara/head/pfb_test')
        for path in ('../outside','/absolute','C:/outside','3d/../outside','name.','name '):
            with self.assertRaises(ValueError):safe_relative(path)
        self.assertEqual(raw_relative('ABCDEFGH12345678ABCDEFGH12345678').as_posix(),'dat/AB/ABCDEFGH12345678ABCDEFGH12345678')
    def test_plain_database_is_read_only(self):
        scratch=Path(__file__).resolve().parent/'.test-temp';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            self.assertTrue(Path(d).resolve().is_relative_to(scratch.resolve()))
            path=Path(d)/'meta';connection=sqlite3.connect(path);connection.execute('create table a(n text)');connection.execute("insert into a values('one')");connection.commit();connection.close()
            before=path.read_bytes()
            with Database(path) as db:
                self.assertEqual(list(db.rows('select n from a')),[{'n':'one'}])
                with self.assertRaises(sqlite3.OperationalError):list(db.rows("insert into a values('two')"))
            self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
