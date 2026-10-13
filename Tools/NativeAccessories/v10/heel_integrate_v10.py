"""Ship a separate heel test and verify paired head/body seam, never switch shoes silently."""
import sys,json,copy,shutil
import numpy as np
from paths_v10 import ROOT,MOD,REPO,PLUGIN
sys.path[:0]=[str(REPO/'Tools/PDXExporter'),str(REPO/'Tools/NativeAccessories/v7'),str(REPO/'Tools/NativeAccessories/v8')]
from build_ck3_mod import parser_only,clausewitz,one,values,script_block
from head_assembly_math import rigdata,compose,readlocals,deform
from configure_assets_v8 import render
P=parser_only(PLUGIN)
def main():
    source=ROOT/'HeelPose';contract=json.loads((source/'heel-contract.json').read_text(encoding='utf-8-sig'));validation=json.loads((source/'heel-validation.json').read_text(encoding='utf-8-sig'));assert validation['body_bone_order_preserved']and validation['parents_preserved']and validation['all_skinning_finite'];assert validation['max_selected_support_clearance_cm']<.1 and validation['pdx_readback_world_max_error']<.005
    for rel in [contract['body_clip_relative'],contract['private_body_set_asset_relative'],contract['test_body_entity_asset_relative']]:
        dst=MOD/rel;shutil.copy2(source/rel,dst)
    asset=MOD/contract['test_body_entity_asset_relative'];a=clausewitz(asset.read_text(encoding='utf-8-sig'));mapping={}
    for pm in values(a,'pdxmesh'):
        for bs in values(pm,'blend_shape'):
            old=one(bs,'id');new='uma_heel_1001_'+old;mapping[old]=new;bs[:]=[(k,new if k=='id'else v)for k,v in bs]
    for e in values(a,'entity'):
        for attr in values(e,'attribute'):
            if values(attr,'blend_shape'):attr[:]=[(k,mapping.get(v,v)if k=='blend_shape'else v)for k,v in attr]
    asset.write_text(render(a)+'\n',encoding='utf8')
    base=MOD/'gfx/models/portraits/uma/0001';bo=P.read_meshfile(str(base/'uma_0001_body_base.mesh')).find('object')[0];ho=P.read_meshfile(str(base/'uma_0001_head_female.mesh')).find('object')[0];B=rigdata(bo.find('skeleton'));H=rigdata(ho.find('skeleton'));heel=MOD/contract['body_clip_relative'];head=MOD/'gfx/models/portraits/uma/animation/head/uma_head_native_idle.anim';bare=MOD/'gfx/models/portraits/uma/animation/body/uma_body_native_idle.anim';rings=json.loads((ROOT/'Reports/neck-delivery-source.json').read_text());samples=[]
    for f in range(61):
        BW=compose(B,readlocals(P,heel,f));originalBW=compose(B,readlocals(P,bare,f));HW=compose(H,readlocals(P,head,f));ex=BW[B['names'].index('bn_sp_thoracic')]@np.linalg.inv(HW[H['names'].index('head_root')]);originalex=originalBW[B['names'].index('bn_sp_thoracic')]@np.linalg.inv(HW[H['names'].index('head_root')]);helper=0
        for bn,hn in [('bn_sp_thoracic','uma_neck_body_thoracic'),('bn_l_clavicle','uma_neck_body_clavicle_l'),('bn_r_clavicle','uma_neck_body_clavicle_r')]:
            target=np.linalg.inv(ex)@BW[B['names'].index(bn)];helper=max(helper,float(np.max(np.abs(target-HW[H['names'].index(hn)]))))
        body=deform(bo.find('mesh'),B,BW)
        for actor in ['1001','1002']:
            o=P.read_meshfile(str(MOD/f'gfx/models/portraits/uma/{actor}/uma_{actor}_head_00.mesh')).find('object')[0];D=rigdata(o.find('skeleton'));bridge=o.findall('mesh')[-1];p=deform(bridge,D,HW);world=p@ex[:3,:3].T+ex[:3,3];r=next(r for r in rings['actors']if r['row']['actor']==actor);gap=float(np.linalg.norm(world[:6]-body[r['lower_ring_body_vertex_ids']],axis=1).max());assert gap<.005,(actor,f,gap);samples.append(dict(actor=actor,frame=f,neck_gap_cm=gap,helper_matrix_error=helper))
    # Root translation affects body and external head attachment once; head-local helper matrices cancel it.
    assert max(r['helper_matrix_error']for r in samples)<.005
    types=clausewitz((MOD/'common/portrait_types/000_uma_portrait_types.txt').read_text(encoding='utf-8-sig'));uma=one(types,'uma')
    for name in ['uma_female','uma_girl']:
        e=one(uma,name);e[:]=[(k,contract['test_body_entity']if k=='torso'else v)for k,v in e]
    patch=ROOT/'Diagnostics/1001-high-heels/common/portrait_types/000_uma_portrait_types.txt';patch.parent.mkdir(parents=True,exist_ok=True);patch.write_text(script_block(types)+'\n',encoding='utf-8-sig')
    text=ROOT/'Diagnostics/1001-high-heels/README.txt';text.write_text('仅供1001默认bdy1001_00高跟鞋测试。正式V10保留裸足body set；此对照覆盖同名portrait_types文件，把female/girl的torso指向uma_heel_1001_body_entity。测试后恢复正式文件。不要叠加两个同名完整mod。\n新body动作与现有245骨head loop已按所有61帧配对核对：root抬高只经躯干外部挂接施加一次，三个颈桥helper局部矩阵因此抵消同一整体平移，无须另造重复head动画。\n不含按鞋类自动切换动画的机制，不代表其他高跟鞋已适配。裸体或无鞋时应恢复普通版本。CK3实际播放仍待验收。\n',encoding='utf-8-sig')
    report=dict(passed=True,frames=61,actors=2,max_neck_gap_cm=max(r['neck_gap_cm']for r in samples),max_helper_matrix_error=max(r['helper_matrix_error']for r in samples),existing_head_clip_compatible_after_exact_recompute=True,no_duplicate_root_lift=True,automatic_shoe_switching=False,source_family='bdy1001_00',patch=str(patch),samples=samples,CK3_executed=False)
    (ROOT/'Reports/heel-head-integration.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V10_HEEL_HEAD_PAIRED',report['max_neck_gap_cm'],report['max_helper_matrix_error'],flush=True)
if __name__=='__main__':main()
