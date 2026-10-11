import os
import copy,json,sys
from pathlib import Path
import numpy as np
R=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeBody')]
from build_ck3_mod import parser_only
from test_vanilla_body_animation_blender import inverse_bind
pdx=parser_only(Path(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh')))))
for actor in ['1001','1002']:
    file=R/'Rigs'/('head_'+actor+'.mesh');data=pdx.read_meshfile(str(file));obj=data.find('object')[0];sk=obj.find('skeleton');oldbyix={b.attrib['ix'][0]:b for b in sk};ordered=[];done=set()
    def visit(b):
        old=b.attrib['ix'][0]
        if old in done:return
        if b.attrib.get('pa'):visit(oldbyix[b.attrib['pa'][0]])
        done.add(old);ordered.append(b)
    for b in sk:visit(b)
    remap={b.attrib['ix'][0]:i for i,b in enumerate(ordered)}
    for b in ordered:
        b.attrib['ix']=[remap[b.attrib['ix'][0]]]
        if b.attrib.get('pa'):b.attrib['pa']=[remap[b.attrib['pa'][0]]]
    sk[:]=ordered
    # The template's tiny triangle was copied from the old carrier; its joint
    # corresponds by original bone name, not the arbitrary source ordinal.
    for mesh in obj.findall('mesh'):
        skin=mesh.find('skin')
        if skin is not None:skin.attrib['ix']=[remap.get(i,i)if i>=0 else i for i in skin.attrib['ix']]
    pdx.write_meshfile(str(file),data);world=np.linalg.inv(inverse_bind(sk));meta={'names':[b.tag for b in sk],'parents':{b.tag:sk[b.attrib['pa'][0]].tag if b.attrib.get('pa')else None for b in sk},'world':{b.tag:w.tolist()for b,w in zip(sk,world)},'bones':len(sk),'xml_order_equals_ix':True,'parents_before_children':True};(R/'Rigs'/('head_'+actor+'.json')).write_text(json.dumps(meta,indent=2),encoding='utf8')
    assert all(not b.attrib.get('pa')or b.attrib['pa'][0]<b.attrib['ix'][0]for b in sk);print('ORDERED_HEAD_RIG',actor,len(sk),flush=True)
