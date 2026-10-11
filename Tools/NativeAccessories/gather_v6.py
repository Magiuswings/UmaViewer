"""Stage the user's v5 and select real 1001 ear/tail/garment resources."""
import argparse,json,os,re,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath

ROOT=Path(os.environ.get("UMA_V6_ROOT", "E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001"))
def write(f,v):f.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--zip',type=Path,required=True);a=p.parse_args();ROOT.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(a.zip)as z:
        for n in z.namelist():
            if n.endswith('/'):continue
            rel=PurePosixPath(n);assert not rel.is_absolute()and'..'not in rel.parts;f=ROOT/'v5'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(n))
    sys.path.insert(0,str(a.repo/'Tools/RawAssets'));from uma_raw import Catalog,decode_selected;from raw_source import RawSource;from sqlite_mc import Database
    scratch=ROOT/'.temp';scratch.mkdir();tempfile.tempdir=str(scratch)
    for key in ['TEMP','TMP','TMPDIR']:os.environ[key]=str(scratch)
    raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'));cat=Catalog(raw,a.repo,'auto')
    with Database(raw.master,a.repo,'auto')as db:
        rows=list(db.rows('SELECT * FROM chara_data WHERE id=1001'));assert len(rows)==1;actor=rows[0]
    write(ROOT/'actor.json',{k:actor[k]for k in ['id','name','height','shape','bust','skin','tail_model_id']if k in actor})
    tail='tail'+str(actor['tail_model_id']).zfill(4)+'_00';tailprefix='3d/chara/tail/'+tail+'/'
    roots=[cat.get(tailprefix+'pfb_'+tail)];roots+=[e for e in cat.select(prefixes=[tailprefix+'textures/'])if '_1001' in e.name or '_0000'in e.name]
    # A short skirt is a meaningful sitting test; select available character
    # 1001 normal outfit before falling back to the common exposed-waist outfit.
    garments=cat.select(prefixes=['3d/chara/body/bdy1001_'])
    prefabs=[e for e in garments if re.fullmatch(r'3d/chara/body/bdy1001_\d\d/pfb_bdy1001_\d\d',e.name)and raw.has('dat/'+e.file_hash[:2]+'/'+e.file_hash)]
    prefabs.sort(key=lambda e:('_00/'not in e.name,'_01/'not in e.name,e.name))
    assert prefabs;clothing=prefabs[0];roots.append(clothing)
    prefix=clothing.name.rsplit('/',1)[0]+'/textures/';roots+=cat.select(prefixes=[prefix])
    ears=[e for e in cat.select(prefixes=['3d/motion/'],contains='_ear')if e.name.endswith('_ear')and e.size and e.size>9000 and raw.has('dat/'+e.file_hash[:2]+'/'+e.file_hash)]
    ears.sort(key=lambda e:('1001'not in e.name,'home'not in e.name,-e.size));ears=ears[:14]
    tails=[e for e in cat.select(prefixes=['3d/motion/'],contains='tail')if raw.has('dat/'+e.file_hash[:2]+'/'+e.file_hash)and not e.name.endswith(('_pose','_driven'))][:20]
    roots+=[e for e in [*ears,*tails]if e.kind]
    assert all(e is not None for e in roots)
    selected={'clothing':clothing.name,'tail_prefab':tailprefix+'pfb_'+tail,'ear_candidates':[e.name for e in ears],'tail_candidates':[e.name for e in tails]};write(ROOT/'resource-selection.json',selected)
    decode_selected(cat,roots,ROOT/'named-native',dependencies=True,validate=True,allow_missing=False);cat.db.close();print('SELECTED_REAL_NATIVE_RESOURCES',json.dumps(selected,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
