"""Read-only local UMA animation-name catalog. Output stays on E:, no asset extraction."""
import sys,os,re,json,csv,hashlib,collections,datetime
from pathlib import Path
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
REPO=Path(r'E:\UmaViewer-Workspace\UmaViewer-source')
CACHE=Path(r'E:\UmaViewer-Workspace\UmaRaw-CLI\raw-cache\Persistent')
OUT=Path(r'E:\UmaViewer-Exports\2026-10-13-UMA-V10\AnimationCatalog')
sys.path.insert(0,str(REPO/'Tools/RawAssets'))
from sqlite_mc import Database

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf8',newline='\n') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
def save_csv(path,rows,fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or (list(rows[0]) if rows else [])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def save_txt(path,text):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8-sig')
def export_triple(stem,rows,fields=None):
    save_json(stem.with_suffix('.json'),rows);save_csv(stem.with_suffix('.csv'),rows,fields)
    fields=fields or (list(rows[0]) if rows else [])
    save_txt(stem.with_suffix('.txt'),'\t'.join(fields)+'\n'+'\n'.join('\t'.join(str(r.get(k,'')).replace('\t',' ').replace('\n',' / ') for k in fields) for r in rows)+'\n')

OUT.mkdir(parents=True,exist_ok=True)
inventory=json.loads(Path(r'E:\UmaViewer-Workspace\UmaRaw-CLI\archive-inventory.json').read_text(encoding='utf8'))
prefix=inventory['prefix'];members=inventory['items']
archive=Path(inventory['archive'])
parts=sorted(archive.parent.glob(archive.stem+'.z[0-9][0-9]'))+[archive]
fingerprint=[dict(name=p.name,size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in parts]
assert fingerprint==inventory['volumes'],'Archive inventory is stale'

selected_tables=['chara_motion_set','event_motion_data','event_motion_plus_data','chara_motion_act','mini_motion_set','random_ear_tail_motion','face_type_data','mini_face_type_data','mini_bg_chara_motion','chara_category_motion','champions_stand_motion','heroes_skill_motion','jukebox_motion_data','system_voice_standby_motion','team_stadium_race_result_motion','team_stadium_stand_motion','campaign_swap_motion_data','map_event_mini_motion','single_mode_cook_motion_group','single_mode_cook_motion_status','single_mode_cook_stand_motion','factor_research_animation_data']
master_tables={};master_schema=[]
with Database(CACHE/'master/master.mdb',REPO) as db:
    for t in db.rows("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        n=t['name'];cols=list(db.rows('PRAGMA table_info("'+n+'")'))
        motion_cols=[c['name'] for c in cols if 'motion' in c['name'].lower()]
        if motion_cols or n in selected_tables:
            master_schema.append(dict(table=n,columns=';'.join(c['name'] for c in cols),motion_columns=';'.join(motion_cols),count=list(db.rows('SELECT count(*) c FROM "'+n+'"'))[0]['c'],exported=n in selected_tables))
        if n in selected_tables:
            master_tables[n]=list(db.rows('SELECT * FROM "'+n+'"'))
    characters={str(r['index']):r['text'] for r in db.rows('SELECT "index",text FROM text_data WHERE id=6')}
    songs={str(r['index']):r['text'] for r in db.rows('SELECT "index",text FROM text_data WHERE id=16')}
    cards={str(r['id']):str(r['chara_id']) for r in db.rows('SELECT id,chara_id FROM card_data')}
for n,rows in master_tables.items():export_triple(OUT/'MasterTables'/n,rows)
export_triple(OUT/'master_motion_schema',master_schema)

enums=[]
enum_path=REPO/'Assets/Scripts/umamusume/Gallop/Live/Cutt/LiveTimelineDefine.cs'
enum_text=enum_path.read_text(encoding='utf-8-sig')
readable={'Base':'基础','Base_N':'基础 N','Kanasi':'悲伤','Dere':'害羞/亲昵','Yure':'摇动','Biku':'惊跳','Ikari':'生气','Tanosi':'开心','Up':'抬起','Down':'低垂','Front':'向前','Side':'向侧','Back':'向后','Roll':'转动','Warai':'笑','Doya':'得意','Odoroki':'惊讶','Jito':'盯视','Komari':'困扰','Kusyo':'苦笑','Urei':'忧虑','Run':'奔跑','Serious':'认真','Half':'半闭','Close':'闭合','Normal':'普通','Talk':'说话口形'}
for m in re.finditer(r'public enum (Facial(?:Ear|Eyebrow|Eye|Mouth)Id)\s*\{([^}]+)\}',enum_text,re.S):
    for e in re.finditer(r'([A-Za-z_]\w*)\s*=\s*(\d+)',m[2]):
        label=e[1];base=next((v for k,v in readable.items() if label.startswith(k)), '')
        enums.append(dict(enum=m[1],id=int(e[2]),symbol=label,source=str(enum_path),line=enum_text[:m.start(2)+e.start()].count('\n')+1,中文辅助释义=base,释义来源='导出者对符号的译释，非数据库官方中文注释' if base else '无'))
export_triple(OUT/'facial_component_enum_ids',enums)
ear_enum={e['id']:e['symbol'] for e in enums if e['enum']=='FacialEarId'}
for r in master_tables['random_ear_tail_motion']:r['ear_type_enum_symbol']=ear_enum.get(r['ear_type'],'')
export_triple(OUT/'random_ear_tail_number_map',master_tables['random_ear_tail_motion'])

lookup=collections.defaultdict(list)
for table,fields in [('event_motion_data',['command_name','base_state_name']),('event_motion_plus_data',['command_name','base_state_name']),('mini_motion_set',['body_motion','ear_motion','tail_motion','facial_motion']),('random_ear_tail_motion',['motion_name'])]:
    for r in master_tables[table]:
        for field in fields:
            value=r.get(field)
            if isinstance(value,str) and value:
                label=r.get('label') or r.get('command_name') or value
                item=f"{table}.id={r.get('id')}:{field}={value}:label={label}"
                if item not in lookup[value.lower()]:lookup[value.lower()].append(item)

def classify(n):
    p=n.lower().split('/');b=p[-1]
    if 'tail' in p or re.search(r'(^|_)tail(?:_|$)',b):return 'tail','path_or_tail_token'
    if re.search(r'(^|_)ear[a-z]?(?:\d|_|$)',b) or '_ear' in b:return 'ear','UmaViewer clip.name.Contains(_ear) / ear token'
    if 'facial' in p or 'head' in p or re.search(r'(^|_)face(?:_|$)',b):return 'head_face','facial/head path or face suffix'
    if 'body' in p:return 'body','body path segment; may include multiple skeleton regions'
    if 'camera' in p or re.search(r'_cam(?:_|$)',b):return 'camera','camera path/cam suffix'
    if 'position' in p or re.search(r'_pos(?:\d|_|$)',b):return 'position','position path/pos suffix'
    if 'prop' in p or 'belt' in p or 'prop' in b:return 'prop','prop/belt name'
    if 'bg' in p or re.search(r'_bg(?:_|$)',b):return 'background','bg path/suffix'
    return 'unclassified','name alone does not establish module'
def annotation(b):
    words=[]
    glossary={'idle':'待机','walk':'行走','run':'跑步','bow':'鞠躬','talk':'说话','nod':'点头','turn':'转身','sit':'坐下','sleep':'睡眠','jump':'跳跃','cry':'哭泣','win':'获胜','lose':'失利','wave':'挥手','clap':'鼓掌','book':'书本相关','chair':'椅子相关','eat':'进食','drink':'喝水','smile':'微笑','angry':'生气','laugh':'笑'}
    tokens=b.lower().split('_')
    for k,v in glossary.items():
        if any(re.fullmatch(k+r'(?:\d+[a-z]*)?',t) for t in tokens):words.append(v)
    for k,v in [('loop','循环'),('mirror','镜像'),('pose','姿势'),('driven','驱动数据')]:
        if k in tokens:words.append(v)
    if b.endswith('_s'):words.append('起始段（UmaViewer播放分支）')
    if b.endswith('_e'):words.append('结束段（UmaViewer播放分支）')
    return ' / '.join(words)
def master_matches(b,mini):
    toks=b.lower().split('_');matches=[]
    # Only an exact suffix at a token boundary, allowing explicitly named clip variants.
    variants={b.lower()};cur=b.lower()
    while re.search(r'_(?:mirror|driven|face|ear|loop|pose|s|e|\d{1,2})$',cur):
        cur=re.sub(r'_(?:mirror|driven|face|ear|loop|pose|s|e|\d{1,2})$','',cur);variants.add(cur)
    for v in variants:
        ts=v.split('_')
        for i in range(len(ts)):
            key='_'.join(ts[i:])
            for item in lookup.get(key,[]):
                if item.startswith('mini_motion_set') and not mini:continue
                if item.startswith('event_motion') and mini:continue
                if item not in matches:matches.append(item)
    return ' | '.join(sorted(matches))

SQL="""SELECT n,h,m,d FROM a WHERE n LIKE '3d/motion/%' OR n LIKE '%/motion/%' OR n LIKE '%/motions/%' OR n LIKE '%/animation/%' OR n LIKE '%/animations/%' OR n LIKE '%/anm_%' ORDER BY n"""
with Database(CACHE/'meta',REPO) as db:
    meta_count=list(db.rows('SELECT count(*) c FROM a'))[0]['c'];rawrows=list(db.rows(SQL))
rows=[]
for r in rawrows:
    n=r['n'];b=n.rsplit('/',1)[-1];module,basis=classify(n);is_main=n.startswith('3d/motion/')
    role='motion_index' if is_main else 'supplementary_animation_name_candidate'
    asset_kind='animation_name_candidate'
    if n.startswith('3d/motionse/'):asset_kind='motion_sound_event_support'
    elif any(p in n.lower().split('/') for p in ('animator','prefab')) or b.startswith('pfb_') or 'animator' in b.lower() or 'animatior' in b.lower():asset_kind='prefab_or_animator_support'
    elif b.endswith('_driven'):asset_kind='driven_support_candidate'
    if not is_main and n.startswith('3d/motionse/'):role='motion_sound_event_support'
    chrmatch=re.search(r'(?:^|[/_])(?:chr|mchr)(\d{4})(?:_|/|$)',n);cardmatch=re.search(r'(?:^|[/_])crd(\d{6})(?:_|/|$)',n);songmatch=re.search(r'(?:^|[/_])son(\d+)(?:_|/|$)',n)
    chrid=chrmatch[1] if chrmatch else '';cardid=cardmatch[1] if cardmatch else '';songid=songmatch[1] if songmatch else ''
    if not chrid and cardid:chrid=cards.get(cardid,'')
    member=f'{prefix}/dat/{r["h"][:2]}/{r["h"]}' if prefix else f'dat/{r["h"][:2]}/{r["h"]}'
    inferred=annotation(b);matches=master_matches(b,'/mini/' in n)
    rows.append(dict(catalog_row_id=len(rows)+1,scope_role=role,module=module,module_basis=basis,asset_kind=asset_kind,logical_name=n,basename=b,meta_type=r['m'],raw_hash=r['h'],archive_present=member in members,archive_size_bytes=members.get(member,{}).get('size',''),mini='/mini/' in n,character_id=chrid,character_name=characters.get(chrid,''),card_id=cardid,music_id=songid,music_title=songs.get(songid,''),filename_number_tokens=';'.join(re.findall(r'\d+',b)),master_number_label_candidates=matches,master_match_status='suffix/variant candidate; not verified runtime resolver' if matches else 'no matching known label',辅助中文动作说明=inferred,说明来源='filename token translation/inference; not official comment' if inferred else 'no known comment',dependency_count=len([x for x in (r['d'] or '').split(';') if x])))

fields=list(rows[0]);export_triple(OUT/'animation_catalog_all',rows,fields)
modules=['body','head_face','ear','tail','camera','position','prop','background','cross_module','unclassified']
counts={};maincounts={};supportcounts={}
for module in modules:
    selected=[r for r in rows if r['module']==module];counts[module]=len(selected);maincounts[module]=sum(r['scope_role']=='motion_index' for r in selected);supportcounts[module]=len(selected)-maincounts[module]
    export_triple(OUT/'Modules'/module,selected,fields)
main=[r for r in rows if r['scope_role']=='motion_index'];extra=[r for r in rows if r['scope_role']!='motion_index']
export_triple(OUT/'motion_index_only',main,fields)
export_triple(OUT/'supplementary_candidates_only',extra,fields)
module_summary=[dict(module=m,total=counts[m],motion_index=maincounts[m],supplementary=supportcounts[m],archive_present=sum(r['archive_present'] for r in rows if r['module']==m)) for m in modules]
export_triple(OUT/'module_summary',module_summary)

# Evidence samples are database records, not claims that clips were decoded.
samples=[]
for module in ['body','head_face','ear','tail','camera','unclassified']:
    candidates=[r for r in main if r['module']==module]
    if candidates:samples.extend(candidates[:2])
export_triple(OUT/'database_samples',samples,fields)
report=dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),original_source=str(archive.parent),archive_inventory_verified=True,meta=dict(path=str(CACHE/'meta'),sha256=digest(CACHE/'meta'),rows=meta_count),master=dict(path=str(CACHE/'master/master.mdb'),sha256=digest(CACHE/'master/master.mdb'),exported_tables={k:len(v) for k,v in master_tables.items()}),query=SQL,unique_logical_names=len({r['logical_name'] for r in rows}),total_records=len(rows),motion_index_records=len(main),supplementary_records=len(extra),modules=module_summary,closed=sum(counts.values())==len(rows),archive_present=sum(r['archive_present'] for r in rows),master_candidate_match_records=sum(bool(r['master_number_label_candidates']) for r in rows),enum_records=len(enums),actual_clip_extraction_count=0,full_library_decode=False,coverage='All meta names under 3d/motion plus broad named-motion/animation/anm supplementary candidates. Does not find unnamed AnimationClip objects hidden in arbitrary other bundles.',number_boundaries='catalog_row_id is export row number. Filename number tokens are raw name tokens, not a universal animation ID. IDs retain their table or enum namespaces.',cross_module_boundary='No bundle-wide curve scan was performed. Body clips may animate head/ear/tail bones. cross_module is reserved for directly verified multiple-module clips; zero here does not imply none exist.',source_code=[str(REPO/'Assets/Scripts/UmaContainerCharacter.cs')+':1948-2210',str(REPO/'Assets/Scripts/UmaViewerUI.cs')+':1129-1194',str(REPO/'Assets/Scripts/UmaDatabase/UmaDatabaseController.cs')+':476-539',str(enum_path)+':140-285'],warnings=['_3d_cutt category also contains prefab/animator/driven support; resource-name catalog is not a verified list of actual AnimationClip objects.','Master suffix/variant matches are candidate correspondences, and can be one-to-many. Original master tables are exported separately so raw IDs remain reviewable.','Chinese action/enum descriptions are author translation or filename inference, not official game comments.','Archive presence is checked against freshly fingerprint-verified ZIP index, not extracted destination files.'])
save_json(OUT/'coverage_report.json',report)
save_txt(OUT/'README.txt',f'''UMA 原数据库动画名称与编号清单\n\n总计 {len(rows):,} 条资源命名记录，其中 3d/motion/ 原索引 {len(main):,} 条，补充候选/配套 {len(extra):,} 条。\n本清单只读取 meta/master 与现有 ZIP 目录索引，不全量解包，不修改1001/1002或任何mod。所有 TXT 为 UTF-8-BOM；CSV 同样带 BOM。\n\n阅读入口：module_summary.csv / Modules/body.txt、head_face.txt、ear.txt、tail.txt。完整路径和哈希在 animation_catalog_all.csv/json/txt。motion_index_only 只含 UmaViewer MotionPath=3d/motion/；supplementary_candidates_only 保留 MotionSE、头部眼睛/泪水、其他场景命名动画候选，以免混成95,910个已解码Clip。\n\n分类依据：路径和 UmaViewer LoadAnimation 的 tail / _face / _ear / _pos / _cam 分支。耳和尾优先于 /body 路径。body 是播放模块，不能据此断言仅影响身体骨骼。cross_module 保留空表，因为没有全面检查实际曲线；未知或无法按名字判断的记录在 unclassified。\n\n编号边界：catalog_row_id 是导出行号。filename_number_tokens 保留名字里的原数字，不冒充动画ID。真正编号在 MasterTables 和 facial_component_enum_ids，必须连同表名或 enum 使用。chara_motion_set.id 是复合动作集（身体/表情/耳/尾）的编号，同一个 body_motion 可以对应许多不同ID。random_ear_tail_number_map 将随机耳尾表的 ear_type 与代码 FacialEarId 对上。face_type_data 没有数字ID，其 label 才是数据库键；眉、眼、嘴数字编号另在 facial_component_enum_ids。\n\n可读说明：数据库 command_name / base_state_name / label 原文保留；角色名来自 text_data.id=6，歌曲名来自 id=16，选取方式与 UmaDatabaseController 相同。文件名 chr/crd/son 到这些表的连接仍是命名规则匹配。master_number_label_candidates 是精确后缀加循环/开始/结束/镜像等变体剥离得到的候选，不代表已运行游戏解析器。辅助中文动作说明和enum释义是导出者的翻译/推断，已逐条注明；没有找到注释的字段保持空白。\n\n本次实际解包/解码 0 个资源，未验收动作视觉表现。database_samples 是只读数据库样本。coverage_report.json 保存条数闭合、来源路径、SHA-256和查询式。\n''')
save_txt(OUT/'sources_and_coverage.txt',json.dumps(report,ensure_ascii=False,indent=2))
assert report['closed'] and report['unique_logical_names']==len(rows)
assert all(p.read_bytes()[:3]==b'\xef\xbb\xbf' for p in OUT.rglob('*.txt'))
manifest=[dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='file_manifest.json']
save_json(OUT/'file_manifest.json',manifest)
print(json.dumps(dict(output=str(OUT),total=len(rows),main=len(main),extra=len(extra),modules=module_summary,files=len(manifest)+1,total_bytes=sum(x['bytes'] for x in manifest),closed=report['closed'],master_matches=report['master_candidate_match_records']),ensure_ascii=False,indent=2))
