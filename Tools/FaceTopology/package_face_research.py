"""Seal the common-network research model, evidence and reproducible source tools."""
import argparse,csv,hashlib,json,pickle,shutil,sys,zipfile
from pathlib import Path
from face_graph import network_distance

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,v):path.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def main():
    p=argparse.ArgumentParser()
    for name in ('repo','root','optimization','targets','models'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();opt=json.loads((a.optimization/'optimization.json').read_text());verification=json.loads((a.models/'blender-verification.json').read_text());targets=json.loads((a.targets/'targets-report.json').read_text());assert verification['passed'] and verification['identity_keys']==182
    with(a.optimization/'best-state.pkl').open('rb')as f:s=pickle.load(f)
    for m in s['source_models']:m.pop('source_data',None);m.pop('source_mesh',None)
    ids=s.get('canonical_global_ids',s['global_ids'][s['candidate_index']]);faces=s['faces'];graph=dict(nodes=set(map(int,ids)),edges={tuple(sorted((int(ids[t[i]]),int(ids[t[(i+1)%3]]))))for t in faces for i in range(3)},triangles={tuple(sorted(int(ids[v])for v in t))for t in faces})
    actual=sum(network_distance(graph,g)['total']for g in s['graphs']);assert actual==opt['total_objective']
    assert all(row['output_geometry']['degenerate_faces']==0 for row in targets['per_model']);assert verification['intermediate_degenerate_faces']==0
    evidence=a.root/'Evidence';evidence.mkdir(exist_ok=True)
    for f in [a.optimization/'optimization.json',a.targets/'targets-report.json',a.targets/'common-topology.json',a.models/'blender-verification.json',a.models/'blend-manifest.json',a.root/'selection.json']:
        shutil.copy2(f,evidence/f.name)
    for f in a.targets.glob('*.png'):shutil.copy2(f,evidence/f.name)
    fields=['id','source_vertices','source_triangles','canonical_vertices','canonical_triangles','direct_correspondences','inserted_surface_samples','discarded_source_samples','sampled_source_to_retopo_rms_mm','sampled_source_to_retopo_p95_mm','sampled_source_to_retopo_max_mm']
    with(evidence/'face-modifications.csv').open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k]for k in fields}for r in targets['per_model'])
    tools=a.root/'Tools/FaceTopology';tools.mkdir(parents=True,exist_ok=True)
    for f in(a.repo/'Tools/FaceTopology').iterdir():
        if f.suffix in ('.py','.md','.txt')and f.is_file():shutil.copy2(f,tools/f.name)
    readme='''通用脸顶点网络研究原型（2026-10-10）

182 个身份差分：172 张有实际脸面壳的命名角色，以及 mob_data 使用的全部 10 种 NPC 通用脸。173 个命名条目中的 2008 / ST-2 是机器人式头模，原始输入保留，未强行当作脸。

统一对象是 M_Face 内最大几何连通的皮肤壳。独立眼白、眼睑附片、牙齿、口腔等保留在原始快照，暂未统一其动画或材质。

共同网络：855 顶点 / 1,314 三角面。五组参考起点搜索后选中 1001 的网络；42 次合法边翻转将顶点/边/三角面差异总计数从 439,396 降至 432,226。顶点增删搜索未发现满足结构约束的进一步改进。评分不使用坐标距离；解剖对应初始化使用骨骼、左右和局部位置，故这是有约束的启发式结果，不是全局最优证明。

Models/uma_0001_face_base.blend：Blender4.2，Basis + 182 个角色/NPC Shape Keys。每次只启用一个身份键。隐藏集合 SOURCE_REFERENCES_DO_NOT_EXPORT 包含原始脸壳和算术平均几何参考。每个角色的修改副本以相同网络导出为 OBJ，按四位 ID 分文件夹。NPC 副本放在 0001。

已独立重开最终工程并实际求值全部 182 个端点；855 个顶点编号及相同边、面数组全部一致。546 个中间权重样本同样无退化面。此检查证明共网格 BS 条件满足，不证明所有面型精确还原或已兼容表情动画。

Evidence/face-modifications.csv 记录各角色的顶点增删量和采样表面误差。多数脸的采样 P95 误差在毫米级；9007、9006 等人类 NPC 的耳部、特殊裁边仍有明显误差，需要进一步人工标志点或附件分离。不要把这些差分直接当作已验收的 CK3 模组；共同 UV 的贴图转移/重烘焙和表情骨架尚未处理。

Input-Faces 保留完整原始 M_Face，包括眼部/口腔附片，用于后续对比。所有原始输入文件不写回。已有躯干模组未改动。本包不包含数据库、解码配置、seed 或原始加密数据。

Source common-face-network.png 为统一网络正面、侧面和线框；source-common-front.png 为左原脸、右共网络差分的相同相机对照。
'''
    (a.root/'DELIVERY.txt').write_text(readme,encoding='utf-8-sig');(a.root/'DELIVERY.md').write_text(readme,encoding='utf8')
    summary=dict(passed=True,models=182,vertices=855,triangles=1314,network_objective_recomputed=actual,graph_distance_has_no_coordinate_term=True,globally_optimal_proven=False,
        independent_blender_reopen=True,endpoint_checks=182,intermediate_checks=546,endpoint_and_intermediate_zero_degenerate_faces=True,
        textures_expression_skeletons_and_game_runtime_verified=False,source_geometry_and_old_body_mods_unmodified=True,blend_sha256=sha(a.models/'uma_0001_face_base.blend'))
    write(a.root/'release-verification.json',summary);artifacts=[]
    for name,folders in [('UMA-Common-Face-Models.zip',[a.models,evidence]),('UMA-Common-Face-Data.zip',[a.targets]),('UMA-Common-Face-Source-Inputs.zip',[a.root/'face-inputs']),('UMA-Common-Face-Tools.zip',[a.root/'Tools'])]:
        file=a.root/name
        with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for folder in folders:
                for f in folder.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(a.root).as_posix())
            z.write(a.root/'DELIVERY.txt','DELIVERY.txt');z.write(a.root/'release-verification.json','release-verification.json')
        with zipfile.ZipFile(file)as z:assert z.testzip()is None
        artifacts.append(dict(file=name,bytes=file.stat().st_size,sha256=sha(file)))
    write(a.root/'packages.json',dict(artifacts=artifacts));print(json.dumps(dict(verification=summary,artifacts=artifacts),indent=2))

if __name__=='__main__':main()
