import os
import csv,json,re,sys,unicodedata
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path.insert(0,str(REPO/'Tools/RawAssets'))
from raw_source import RawSource
from sqlite_mc import Database
raw=RawSource(Path('E:/uma'),Path('E:/UmaViewer-Workspace/UmaRaw-CLI'));audit=json.loads((R/'Reports/master-audit.json').read_text());roles=audit['roles'];source=(REPO/'Assets/Scripts/localfy/LocalizeEn.cs').read_text(encoding='utf8');local={int(n):name for n,name in re.findall(r'public const string Chara(\d+) = "([^"]+)";',source)}
official={};page=(R/'.temp/official-character-list.md').read_text(encoding='utf8')
for line in page.splitlines():
    m=re.search(r'Image \d+: ([^\]]+)\]\([^)]*\)\s+(.+?)\s+CV:[^\]]*\]\((https://umamusume.jp/character/[^)]+)\)',line)
    if m:
        jp,label,url=m.groups();english=label[:label.rfind(jp)].strip()if jp in label else label.strip();official[jp.replace(' ','')]=(english,url)
with Database(raw.master,REPO,'auto')as db:
    textrows=list(db.rows('SELECT * FROM text_data WHERE category=6'));jpnames={int(row['index']):row['text']for row in textrows}
rows=[];unknown=[]
for role in roles:
    actor=role['id'];jp=jpnames.get(actor,'');entry=official.get(jp.replace(' ',''));english=entry[0]if entry else local.get(actor,'');provenance=entry[1]if entry else'UmaViewer Assets/Scripts/localfy/LocalizeEn.cs fallback'if english else'not found in available naming sources';identifier=''.join(s[0].upper()+s[1:]for s in re.findall('[A-Za-z0-9]+',unicodedata.normalize('NFKD',english)))if english else'Unknown'+str(actor)
    row={'id':actor,'english_identifier':identifier,'english_name':english,'database_display_name':jp,'identifier_is_database_field':False,'name_source':provenance,'official_source_match':bool(entry),'height_type':role['height'],'shape':role['shape'],'bust':role['bust'],'scale_cm':role['scale'],'skin':role['skin'],'socks':role['socks'],'tail_model_id':role['tail_model_id'],'chara_category':role['chara_category']};rows.append(row)
    if not english:unknown.append(actor)
out=R/'Database';out.mkdir(exist_ok=True)
with (out/'uma_characters.csv').open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(out/'uma_characters.json').write_text(json.dumps({'count':len(rows),'original_table':'chara_data','database_english_name_field_present':False,'official_site':'https://umamusume.jp/character/','records':rows,'unresolved_name_ids':unknown},ensure_ascii=False,indent=2),encoding='utf8')
(out/'uma_characters.txt').write_text('\n'.join(f"{r['id']}\t{r['english_identifier']}\t{r['database_display_name']}"for r in rows)+'\n',encoding='utf-8-sig');print('ROSTER',len(rows),'OFFICIAL',sum(r['official_source_match']for r in rows),'UNRESOLVED',unknown,flush=True)
