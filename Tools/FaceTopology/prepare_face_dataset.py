"""Select one neutral playable head per database ID and every Mob face prefab."""
import argparse,json,os,re,sys,tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    for name in ('repo','source','workspace','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--extract',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(a.repo/'Tools/RawAssets'))
    from uma_raw import Catalog,decode_selected,write
    from raw_source import RawSource
    from sqlite_mc import Database
    scratch=a.workspace/'.temp';scratch.mkdir(parents=True,exist_ok=True)
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(scratch)
    tempfile.tempdir=str(scratch);raw=RawSource(a.source,a.workspace)
    catalog=Catalog(raw,a.repo,'auto')
    try:
        with Database(raw.master,a.repo,'auto')as db:
            columns={r['name']for r in db.rows('PRAGMA table_info(chara_data)')}
            fields=['id']+([k for k in ('name','default_head_id')if k in columns])
            actors=list(db.rows('SELECT '+','.join(fields)+' FROM chara_data ORDER BY id'))
            mobcolumns={r['name']for r in db.rows('PRAGMA table_info(mob_data)')}
            mobfacecols=[k for k in mobcolumns if 'face' in k.lower()]
            mobid=next(k for k in ('id','mob_id')if k in mobcolumns)
            mobfaces=list(db.rows('SELECT '+','.join([mobid,*mobfacecols])+' FROM mob_data ORDER BY '+mobid))
        entries=catalog.select(prefixes=['3d/chara/head/'])
        prefabs={e.name:e for e in entries if re.fullmatch(r'3d/chara/head/chr\d{4}_\d{2}/pfb_chr\d{4}_\d{2}',e.name)}
        selected=[];missing=[]
        for actor in actors:
            ident=str(actor['id']);candidates=[e for n,e in prefabs.items()if re.search(r'/chr'+ident+r'_\d{2}/',n)]
            candidates.sort(key=lambda e:(e.name.endswith('_80')is False,e.name.endswith('_00')is False,e.name))
            present=[e for e in candidates if raw.has('dat/'+e.file_hash[:2]+'/'+e.file_hash)]
            if not present:missing.append(dict(character=ident,indexed_variants=len(candidates)));continue
            root=present[0];selected.append(dict(id=ident,kind='named',variant=root.name.rsplit('_',1)[-1],source=root.name,present=True))
        npc=[e for e in entries if re.fullmatch(r'3d/chara/head/chr0001_\d{2}/pfb_chr0001_\d{2}_face\d{3}',e.name)]
        for e in sorted(npc,key=lambda x:x.name):
            present=raw.has('dat/'+e.file_hash[:2]+'/'+e.file_hash)
            selected.append(dict(id='npc_'+e.name.rsplit('face',1)[-1],kind='npc',variant=e.name.rsplit('face',1)[-1],source=e.name,present=present))
        manifest=dict(database_character_count=len(actors),selection=selected,missing_characters=missing,mob_count=len(mobfaces),mob_face_columns=mobfacecols,mob_face_usage=mobfaces,
            selection_policy='One available base head per chara_data ID: 80 preferred, then 00, then lowest indexed variant; every indexed generic NPC face prefab once; equal weight per model',
            model_count=len(selected),named_character_count=sum(r['kind']=='named'for r in selected),npc_count=len(npc),all_selected_present=all(r['present']for r in selected),
            source_unmodified=True,private_decoding_fields_serialized=False)
        write(a.output/'selection.json',manifest)
        print(json.dumps({k:manifest[k]for k in ('database_character_count','model_count','named_character_count','npc_count','all_selected_present','missing_characters','mob_face_columns')},ensure_ascii=False,indent=2),flush=True)
        if a.extract:
            roots=[catalog.get(r['source'])for r in selected if r['present']]
            decode_selected(catalog,roots,a.output/'named-assets',dependencies=True,validate=True,allow_missing=False)
    finally:catalog.db.close()

if __name__=='__main__':main()
