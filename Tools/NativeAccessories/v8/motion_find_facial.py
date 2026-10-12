import json,sys
from pathlib import Path
sys.path.insert(0,'E:/UmaViewer-Workspace/UmaViewer-source/Tools/RawAssets')
from sqlite_mc import Database
ROOT=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8/MotionSources');db=Database(Path('E:/UmaViewer-Workspace/UmaRaw-CLI/raw-cache/Persistent/meta'),Path('E:/UmaViewer-Workspace/UmaViewer-source'),'auto');rows=[]
for prefix in ['3d/motion/event/facial/type00/','3d/motion/home/facial/type01/','3d/motion/mini/mode/facial/type00/']:
    rs=list(db.rows("SELECT n,h FROM a WHERE n >= '"+prefix+"' AND n < '"+prefix+"~' ORDER BY n"))
    selected=[r for r in rs if r['n'].endswith('_face')and('loopl01'in r['n']or'blink'in r['n']or'000_001'in r['n']or'06_03_1001'in r['n'])];rows.extend(selected);print(prefix,len(rs),selected[:30],flush=True)
(ROOT/'face-dynamic-candidates.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8');db.close()
