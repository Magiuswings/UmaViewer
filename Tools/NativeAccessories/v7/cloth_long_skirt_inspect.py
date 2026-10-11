import os
import json,numpy as np
from pathlib import Path
from collections import Counter
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));reg=json.loads((R/'ClothingParts/clothing-registration.json').read_text());f=next(f for f in reg['families']if f['family']=='bdy0020_00_00');d=json.loads(Path(f['source_snapshot']).read_text());names={b['id']:b['name']for b in d['bones']};m=d['meshes'][0];c=Counter()
for w in m['weights']:
 if m['vertices'][w['vertex']]['y']<.60:c[names[w['bone']]]+=w['weight']
print('LONG_SKIRT_SOURCE_WEIGHTS',c.most_common(25))
