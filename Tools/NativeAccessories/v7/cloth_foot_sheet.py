import os
from PIL import Image,ImageDraw
from pathlib import Path
import json
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'));idx=json.loads((R/'cloth-source-index.json').read_text(encoding='utf8'));records=[r for r in idx['records']if (R/'source-previews'/(r['family']+'.png')).exists()]
for start in range(0,len(records),18):
 chunk=records[start:start+18];im=Image.new('RGB',(6*220,3*335),(35,38,44));draw=ImageDraw.Draw(im)
 for i,r in enumerate(chunk):
  p=Image.open(R/'source-previews'/(r['family']+'.png')).convert('RGB');tile=p.crop((130,285,510,875)).resize((212,310));x=(i%6)*220;y=(i//6)*335;im.paste(tile,(x,y+22));draw.text((x+4,y+3),r['family'],fill=(240,240,240))
 out=R/'source-previews'/('footwear-sheet-'+str(start//18+1)+'.jpg');im.save(out,quality=92);print(out,flush=True)
