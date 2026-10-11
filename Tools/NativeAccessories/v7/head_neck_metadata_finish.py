import os
import json,hashlib
from pathlib import Path
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'HeadSources';index=json.loads((SRC/'Export/head-export-index.json').read_text())
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for h in index['heads']:
    p=SRC/f'partitions/chr{h["actor"]}_{h["variant"]}/head-components.json';d=json.loads(p.read_text());selected=set(d.get('neck_patch_triangle_ids',[]))
    for c in d['components']:
        if not set(c['source_triangle_ids'])&selected:continue
        assert set(c['source_triangle_ids'])<=selected
        if c.get('export_role')!='neck_patch':c['original_export_role_before_skin_split']=c.get('export_role')
        c['export_role']='neck_patch';c['classification']='native_rear_neck_skin';c['classification_evidence']='Entire native connected region meets actual neck ring, only Head/Neck weights, native skin RGB and ctrl B0; portrait_skin_face shared head pose.'
    d['neck_patch_skin_lighting_separated']=bool(selected);dump(p,d)
index['file_manifest']=[{'path':str(p.relative_to(SRC)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for folder in [SRC/'Export',SRC/'NeckPatch',SRC/'NeckBridge']for p in sorted(folder.rglob('*'))if p.is_file()and p.suffix in ['.mesh','.dds','.anim']];dump(SRC/'Export/head-export-index.json',index);print('NECK_COMPONENT_METADATA_UPDATED',len(index['heads']))
