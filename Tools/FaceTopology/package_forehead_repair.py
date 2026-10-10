"""Validate and package repaired forehead boundaries without overwriting earlier releases."""
import argparse,hashlib,json,pickle,shutil,zipfile
from pathlib import Path
import numpy as np
from face_graph import network_distance

def write(path,v):path.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    for name in ('repo','root','targets','models','original-optimization'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();forehead=json.loads((a.targets/'forehead-verification.json').read_text());blender=json.loads((a.models/'blender-verification.json').read_text());assert forehead['passed'] and blender['passed'];assert forehead['maximum_forehead_contour_error_mm']<=.51 and blender['intermediate_degenerate_faces']==0
    d=np.load(a.targets/'face-targets.npz');top=json.loads((a.targets/'common-topology.json').read_text());manifest=json.loads((a.models/'blend-manifest.json').read_text());assert manifest['vertices']==875 and manifest['triangles']==1334
    with(a.original_optimization/'best-state.pkl').open('rb')as f:s=pickle.load(f)
    for m in s['source_models']:m.pop('source_data',None);m.pop('source_mesh',None)
    oldids=np.asarray(s.get('canonical_global_ids',s['global_ids'][s['candidate_index']]));maximum=max(v for g in s['graphs']for v in g['nodes']);ids=np.r_[oldids,np.arange(maximum+1,maximum+21)];faces=d['faces']
    graph=dict(nodes=set(map(int,ids)),edges={tuple(sorted((int(ids[t[i]]),int(ids[t[(i+1)%3]]))))for t in faces for i in range(3)},triangles={tuple(sorted(int(ids[v])for v in t))for t in faces});differences=[dict(id=m['id'],**network_distance(graph,g))for m,g in zip(s['source_models'],s['graphs'])]
    score=sum(r['total']for r in differences);write(a.root/'network-score.json',dict(original_objective=s['score'],repaired_objective_fixed_original_correspondence=score,new_nodes_counted_as_unmatched=True,score_is_not_a_new_global_optimality_claim=True,differences=differences))
    evidence=a.root/'Evidence';evidence.mkdir(exist_ok=True)
    for f in [a.targets/'forehead-verification.json',a.targets/'common-topology.json',a.targets/'targets-report.json',a.models/'blender-verification.json',a.models/'blend-manifest.json',a.root/'network-score.json']:
        shutil.copy2(f,evidence/f.name)
    for f in a.targets.glob('*.png'):shutil.copy2(f,evidence/f.name)
    tools=a.root/'Tools/FaceTopology';tools.mkdir(parents=True,exist_ok=True)
    for f in(a.repo/'Tools/FaceTopology').iterdir():
        if f.is_file()and f.suffix in ('.py','.md','.txt'):shutil.copy2(f,tools/f.name)
    message='''通用脸额头裁边修复版

共 182 个身份 BS，统一 875 顶点 / 1,334 三角面。新增的 20 个顶点及 20 个面只位于上边界；全部角色使用相同的扩展和连接关系。

旧版整圈边界配准未恢复各脸额头转角。新版使用有序轮廓节点：原轮廓节点数较少时全部保留，剩余槽位在原边上采样；较多时保留端点和主要转角，再以受控误差简化。边界作为精确位置约束，内部以带保留项的双调和位移平滑衔接，眼、嘴和下半脸尽量保持前版。

通用 Basis 使用修正后的 1003 几何，额头轮廓完整。1001 原脸本身有裁边，1001 BS 仍跟随其原始轮廓；不会再把这个裁边统一施加给其他角色。

全部 182 张脸的上轮廓最大采样误差不超过 0.391 毫米；1003 从旧版约 21.317 毫米降至数值精度内一致。855 节点原型的额头边界只有 11 个物理节点，不足以保留所有复杂轮廓，因此统一扩展到 31 个上边界节点。

最终 Blender4.2 文件已独立重开，182 个端点及 546 个中间权重采样无退化三角面，顶点编号、边和有向面数组一致。原版 855 节点包保留，不应再作为本次修复结果使用。

Models/uma_0001_face_base.blend 为可编辑工程，按四位 ID 分目录的 OBJ 是每个身份的对应副本。Targets 包提供坐标、对应与边界报告。UV/权重样本按新增边界节点插值，角色贴图重烘焙、表情骨架和 CK3 接入仍未在这一轮完成；耳部及其他区域的既有映射限制仍保留。

原始输入、已有躯干模组和以前的脸模型包不改。网络成本已按旧对应关系重新统计，新增节点作为未匹配节点计入，不沿用旧 432,226 得分宣称新结果全局最优。
'''
    (a.root/'DELIVERY.txt').write_text(message,encoding='utf-8-sig');(a.root/'DELIVERY.md').write_text(message,encoding='utf8')
    release=dict(passed=True,vertices=875,triangles=1334,keys=182,new_vertices=20,new_triangles=20,forehead_max_error_mm=forehead['maximum_forehead_contour_error_mm'],reopened_blend_verified=True,endpoint_checks=182,intermediate_checks=546,intermediate_degenerate_faces=0,basis_geometry='1003',old_body_mods_unchanged=True,game_materials_expression_rigs_unverified=True,blend_sha256=sha(a.models/'uma_0001_face_base.blend'))
    write(a.root/'release-verification.json',release);artifacts=[]
    for name,folders in [('UMA-Common-Face-Corner-Repair-Models.zip',[a.models,evidence]),('UMA-Common-Face-Corner-Repair-Data.zip',[a.targets]),('UMA-Common-Face-Corner-Repair-Tools.zip',[a.root/'Tools'])]:
        file=a.root/name
        with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for folder in folders:
                for f in folder.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(a.root).as_posix())
            z.write(a.root/'DELIVERY.txt','DELIVERY.txt');z.write(a.root/'release-verification.json','release-verification.json')
        with zipfile.ZipFile(file)as z:assert z.testzip()is None
        artifacts.append(dict(file=name,bytes=file.stat().st_size,sha256=sha(file)))
    write(a.root/'packages.json',dict(artifacts=artifacts));print(json.dumps(dict(release=release,artifacts=artifacts),indent=2))

if __name__=='__main__':main()
