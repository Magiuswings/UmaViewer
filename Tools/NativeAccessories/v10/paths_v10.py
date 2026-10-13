import os
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
ROOT=Path(os.environ.get('UMA_V10_ROOT','E:/UmaViewer-Exports/2026-10-13-UMA-V10'))
V9=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9')
MOD=ROOT/'UMA-V10'
REPO=Path(os.environ.get('UMA_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))
PLUGIN=Path(os.environ.get('UMA_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))
GAME=Path(os.environ.get('CK3_GAME','D:/steam/steamapps/common/Crusader Kings III/game'))
