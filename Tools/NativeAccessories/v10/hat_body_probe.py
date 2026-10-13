import os,sys,json
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.spatial.transform import Rotation
sys.path[:0]=['E:/UmaViewer-Workspace/UmaViewer-source/Tools/PDXExporter','E:/UmaViewer-Workspace/UmaViewer-source/Tools/NativeAccessories/v7']
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,compose,readlocals
V=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V10');M=V/'UMA-V10/gfx/models/portraits/uma';P=parser_only('E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh');B=rigdata(P.read_meshfile(str(M/'0001/uma_0001_body_base.mesh')).find('object')[0].find('skeleton'));H=rigdata(P.read_meshfile(str(M/'0001/uma_0001_head_female.mesh')).find('object')[0].find('skeleton'));BW=np.array([compose(B,readlocals(P,M/'animation/body/uma_body_native_idle.anim',f))for f in range(61)]);HW=np.array([compose(H,readlocals(P,M/'animation/head/uma_head_native_idle.anim',f))for f in range(61)]);ti=B['names'].index('bn_sp_thoracic');bi=B['names'].index('uma_src_Head');hi=H['names'].index('bn_h_head');ri=H['names'].index('head_root');visible=np.array([BW[f,ti]@np.linalg.inv(HW[f,ri])@HW[f,hi]for f in range(61)]);X=np.linalg.inv(BW[:,bi])@visible
print('head_relative_offset_first',X[0]);print('translation_range',X[:,:3,3].min(0),X[:,:3,3].max(0));print('relative_delta_matrix_max',np.abs(X-X[0]).max());print('angle_relative_delta',np.rad2deg((Rotation.from_matrix(X[0,:3,:3]).inv()*Rotation.from_matrix(X[:,:3,:3])).magnitude()).max());print('bodyHead_bind',B['bind'][bi]);print('visible_bind',B['bind'][ti]@np.linalg.inv(H['bind'][ri])@H['bind'][hi]);print('core_source_aux',[n for n in B['names']if n.startswith('uma_src_')]);print('head_delta_upper_max_cm',np.linalg.norm(X[:,:3,3]-X[0,:3,3],axis=1).max())
