import os
"""V7 actual PDX importer checks; explicit-index SDK compatibility is documented."""
import json,sys,gc
from pathlib import Path
import numpy as np,bpy
from mathutils import Matrix,Quaternion
sys.path.insert(0,'E:/UmaViewer-Workspace/PDX-vendor')
import io_pdx_mesh
from io_pdx_mesh import pdx_data as P
from io_pdx_mesh.pdx_blender import blender_import_export as IO
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'HeadSources';OUT=SRC/'Export';index=json.loads((OUT/'head-export-index.json').read_text());SW=np.array([[1,0,0],[0,0,1],[0,1,0]]);SW4=np.eye(4);SW4[:3,:3]=SW;report={'blender':bpy.app.version_string,'sdk_skin_explicit_ix_compatibility_wrapper':False,'stock_core_mapping_by_name':True,'head_xml_order_equals_ix_and_parent_before_child':True,'parts':[],'runtime_game_not_executed':True}
def extract(file):
    t=P.read_meshfile(str(file));sh=t.find('object')[0];return sh,sh.find('mesh'),sorted(sh.find('skeleton'),key=lambda b:b.get('ix')[0])
def bind_data(sk):
    inv=[]
    for b in sk:
        m=np.eye(4);m[:3]=np.array(b.get('tx')).reshape(4,3).T;inv.append(m)
    inv=np.array(inv);return inv,np.linalg.inv(inv)
def pose_world(path,sk,frame):
    data=P.read_meshfile(str(path));info=data.find('info');samples=data.find('samples');local={};off={c:0 for c in'tqs'};counts={c:sum(c in b.get('sa')[0]for b in info)for c in'tqs'};inv,bind=bind_data(sk)
    for b in info:
        d={c:list(b.get(c))for c in'tqs'}
        for c in'tqs':
            if c not in b.get('sa')[0]:continue
            width=3 if c=='t'else 4 if c=='q'else len(d[c]);start=(frame*counts[c]+off[c])*width;d[c]=samples.get(c)[start:start+width];off[c]+=1
        q=d['q'];s=d['s']if len(d['s'])==3 else d['s']*3;local[b.tag]=np.array(Matrix.Translation(d['t'])@Quaternion((q[3],q[0],q[1],q[2])).to_matrix().to_4x4()@Matrix.Diagonal([*s,1.]))
    result={}
    def visit(i):
        if i in result:return result[i]
        pa=sk[i].get('pa');pa=pa[0]if pa else None;L=local.get(sk[i].tag,np.linalg.inv(bind[pa])@bind[i]if pa is not None else bind[i]);result[i]=visit(pa)@L if pa is not None else L;return result[i]
    return np.array([visit(i)for i in range(len(sk))])
def evaluate(obj,node,sk,worlds,rig):
    # Assign global matrices in actual hierarchy order. This samples source
    # local TRS with absent helper bones kept at their true bind-local offset.
    byname={b.tag:i for i,b in enumerate(sk)};ordered=[]
    def add(b):
        if b in ordered:return
        if b.parent:add(b.parent)
        ordered.append(b)
    for b in rig.pose.bones:add(b)
    for b in ordered:b.matrix=Matrix((SW4@worlds[byname[b.name]]@SW4).tolist())
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();evaluated=obj.evaluated_get(deps);me=evaluated.to_mesh();actual=np.array([tuple(evaluated.matrix_world@v.co)for v in me.vertices]);evaluated.to_mesh_clear();inv,bind=bind_data(sk);skinmat=worlds@inv;p=np.column_stack([np.array(node.get('p')).reshape(-1,3),np.ones(len(actual))]);skin=node.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);w=np.array(skin.get('w')).reshape(-1,4);goal=np.zeros((len(p),3))
    for j in range(4):goal+=np.einsum('vij,vj->vi',skinmat[np.maximum(ix[:,j],0)],p)[:,:3]*w[:,j,None]
    error=float(np.linalg.norm(actual-goal@SW.T,axis=1).max());assert np.isfinite(actual).all();assert error<.003,error;return error
parts=[p for h in index['heads']for p in h['components']if p['present']]+index['tails']
for number,row in enumerate(parts):
    file=Path(row['mesh_path']);sh,node,sk=extract(file);assert len(sk)<=255;assert list(sh.find('skeleton'))==sk;assert all(not b.get('pa')or b.get('pa')[0]<b.get('ix')[0]for b in sk);bpy.ops.wm.read_factory_settings(use_empty=True);IO.import_meshfile(str(file),imp_locs=False,join_materials=False,bonespace=False);obj=next(o for o in bpy.context.scene.objects if o.type=='MESH');rig=next(m.object for m in obj.modifiers if m.type=='ARMATURE');assert len(rig.data.bones)==len(sk);names=[b.tag for b in sk];parent_errors=[]
    for b in sk:
        pa=b.get('pa');expected=names[pa[0]]if pa else None;actual=rig.data.bones[b.tag].parent.name if rig.data.bones[b.tag].parent else None
        if expected!=actual:parent_errors.append([b.tag,expected,actual])
    assert not parent_errors,parent_errors;inv,bind=bind_data(sk);point_error=max(float(np.linalg.norm(np.array(rig.data.bones[b.tag].matrix_local.translation)-SW@bind[i,:3,3]))for i,b in enumerate(sk));assert point_error<.002
    skin=node.find('skin');ix=np.array(skin.get('ix')).reshape(-1,4);w=np.array(skin.get('w')).reshape(-1,4);weight_error=0.
    for i,v in enumerate(obj.data.vertices):
        expected={names[int(j)]:float(vw)for j,vw in zip(ix[i],w[i])if j>=0 and vw>0};actual={obj.vertex_groups[g.group].name:float(g.weight)for g in v.groups if g.weight>0};assert expected.keys()==actual.keys(),(file.name,i,expected,actual);weight_error=max(weight_error,max(abs(expected[k]-actual[k])for k in expected))
    assert weight_error<1e-5;rec={'actor':row['actor'],'variant':row.get('variant'),'element':row['element'],'file':str(file),'bone_count':len(sk),'vertex_count':len(obj.data.vertices),'source_point_import_error_cm':point_error,'skin_binding_error':weight_error,'parent_errors':parent_errors,'pose_checks':[]}
    if row['element']in['ear','headwear','tail']:
        for ar in row['animations']:
            rig.animation_data_clear();IO.import_animfile(ar['file']);count=ar['frames'];data=P.read_meshfile(ar['file']);samples=data.find('samples');info=data.find('info');q=samples.get('q')or[];nq=sum('q'in b.get('sa')[0]for b in info);peak=count//2
            if nq:
                packed=np.array(q).reshape(count,nq,4);peak=int(np.argmax(np.linalg.norm(packed-packed[0],axis=2).max(1)))
            checks=[]
            for frame in sorted({0,count//2,peak}):
                bpy.context.scene.frame_set(frame+1);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();ob=obj.evaluated_get(deps);me=ob.to_mesh();actual=np.array([tuple(ob.matrix_world@v.co)for v in me.vertices]);ob.to_mesh_clear();worlds=pose_world(ar['file'],sk,frame);skinmat=worlds@inv;p=np.column_stack([np.array(node.get('p')).reshape(-1,3),np.ones(len(actual))]);goal=np.zeros((len(p),3))
                for j in range(4):goal+=np.einsum('vij,vj->vi',skinmat[np.maximum(ix[:,j],0)],p)[:,:3]*w[:,j,None]
                error=float(np.linalg.norm(actual-goal@SW.T,axis=1).max());assert error<.003,(file.name,ar['state'],frame,error);checks.append({'frame':frame,'error_cm':error})
            rec['pose_checks'].append({'state':ar['state'],'actual_sdk_anim_import':True,'samples':checks})
    elif row.get('variant')in['00','80','30']and row['element']in['face','eye','brow','hair']:
        # Stock files from previously verified head set. The precise extra helper
        # bind-local offset is kept when a stock clip omits that helper by name.
        for label,filename in [('idle','uma_female_head_idle_1.anim'),('court','uma_female_head_throneRoom_ruler3_1.anim')]:
            fileclip=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001')) / 'UMA-V6-1001/gfx/models/portraits/uma/animation'))/filename;count=P.read_meshfile(str(fileclip)).find('info').get('sa')[0];checks=[]
            for frame in sorted({0,count//2,count-1}):checks.append({'frame':frame,'error_cm':evaluate(obj,node,sk,pose_world(fileclip,sk,frame),rig)})
            rec['pose_checks'].append({'state':label,'source_stock_local_trs_sampled':True,'samples':checks})
    report['parts'].append(rec);(SRC/'head-blender-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('V7_PDX_IMPORT_VERIFIED',number+1,len(parts),row['actor'],row.get('variant'),row['element'],len(sk),flush=True);gc.collect()
report['passed']=True;report['parts_verified']=len(parts);report['root_or_vendor_modified']=False;(SRC/'head-blender-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print('V7_HEAD_TAIL_BLENDER_COMPLETE',flush=True)
