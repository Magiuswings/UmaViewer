import os
import json
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingParts'));files=list(R.rglob('native-source-points.json'));print('FAMILIES_READY',len(files));print('MAX_BONES',max(json.loads(f.read_text())['total_bones']for f in files))
