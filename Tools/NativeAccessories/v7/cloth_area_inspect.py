import os
from PIL import Image
import numpy as np
from pathlib import Path
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources/parsed/bdy0013_00_00/resources/textures'));p=next(R.glob('*area*'));a=np.array(Image.open(p));v,c=np.unique(a.reshape(-1,a.shape[-1]),axis=0,return_counts=True);ids=np.argsort(-c)[:15];print('AREA_PUBLIC_COLOR_CODES',[(v[i].tolist(),int(c[i]))for i in ids]);print('CHANNEL_VALUES',[np.unique(a[:,:,i]).tolist()[:50]for i in range(3)])
