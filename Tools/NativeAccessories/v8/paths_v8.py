import os
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
ROOT=Path(os.environ.get('UMA_V8_ROOT','E:/UmaViewer-Exports/2026-10-12-UMA-V8'))
V7=Path(os.environ.get('UMA_V7_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))
REPO=Path(os.environ.get('UMA_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))
PLUGIN=Path(os.environ.get('UMA_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))
GAME=Path(os.environ.get('CK3_GAME','D:/steam/steamapps/common/Crusader Kings III/game'))
MOD=ROOT/'UMA-V8'
