"""Package only after final static, binary and independent Blender checks pass."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args();r=a.root
    validation=json.loads((r/'mod-verification.json').read_text());blender=json.loads((r/'blender-verification.json').read_text());assert validation['passed']and blender['passed'];assert blender['pdx_plugin_imports']==183
    evidence=r/'Evidence';evidence.mkdir(exist_ok=True)
    for name in ['export-report.json','mod-verification.json','animation-verification.json','blender-verification.json','rig-transfer.json','pdx-vertex-order.json']:shutil.copy2(r/name,evidence/name)
    tools=r/'Tools/FaceCK3';tools.mkdir(parents=True,exist_ok=True)
    for f in(a.repo/'Tools/FaceCK3').iterdir():
        if f.suffix in ('.py','.md'):shutil.copy2(f,tools/f.name)
    description='''# UMA Face Morphs

这版以最终 UMA Canonical Body Rebuild 为基础，只加入通用脸的 CK3 身份 BS 接口；躯干网格、资产、基因、原版动画不变。

共用皮肤壳 875 顶点 / 1334 三角面；Basis 为 1003，182 个身份目标以相同网络导出。完整头部还含 1001 固定口腔/眼白、眉、发、眼测试组件，BS 仅改变皮肤壳。

新基因 gene_uma_face_identity 位于 morph_genes，portrait_group=uma，182 个 uma_face_* 模板对应新 uma_bs_face_* 属性。四组分支补齐，18 岁阈值不变。全部 TXT 为 UTF-8-BOM，gfx 文件名全局唯一，共用 0001，角色四位 ID，uma_ 前缀；头部动画仍在独立 animation 目录且原字节不变，shader 沿用 uma_portrait.shader。

只启用 UMA Face Morphs 这一版，关闭其他 UMA 测试包。默认命令：effect set_ethnicity = uma_ethnicity。交叉验证脸型：effect set_ethnicity = uma_face_1003_ethnicity；NPC：effect set_ethnicity = uma_face_npc_000_ethnicity。默认 1001。

character-face-bindings.json 提供每张脸的基因模板、BS、文件、diffuse、测试 ethnicity。模板的强度 1 为完整端点，0 为 1003 Basis。几何 BS 不自动换贴图；1001 附件及材质保持默认，其余角色重投影 diffuse 单独提供。NPC 没有直接 diffuse 绑定，暂用 1001 中性贴图回退。不同脸型的眼口/耳部贴合与表情还原不属于本轮已通过的验收。

文件结构、二进制、Blender 重开、全部 PDX IO 回读和共用头动画数值抽样已通过；未进入 CK3 实机测试，不能据此承诺游戏内无穿插或所有表情正确。

Models/0001/uma_0001_head_base.blend 是可编辑工程，含 Basis 与 182 个 Shape Keys，默认 1001 并保留真实共用 idle、闭眼、张嘴 Actions。Evidence/uma_1001_head_idle.png 为这份工程的实际渲染。Tools/FaceCK3/README.md 说明生成链与限制。
'''
    (r/'DELIVERY.md').write_text(description,encoding='utf8');(r/'DELIVERY.txt').write_text(description,encoding='utf-8-sig')
    report=dict(passed=True,mod=validation,blender=blender,model_sha256=sha(r/'Models/0001/uma_0001_head_base.blend'),runtime_visual_verified=False)
    (r/'release-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');artifacts=[]
    for name,folders in [('UMA-Face-Morphs-CK3.zip',[r/'Uma-Face-Morphs']),('UMA-Face-Morphs-Models.zip',[r/'Models',evidence]),('UMA-Face-Morphs-Tools.zip',[r/'Tools'])]:
        file=r/name
        with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for folder in folders:
                for f in folder.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(r).as_posix())
            for f in ['DELIVERY.md','DELIVERY.txt','release-verification.json']:z.write(r/f,f)
            if folders==[r/'Uma-Face-Morphs']:z.write(r/'Uma-Face-Morphs.mod','Uma-Face-Morphs.mod')
        with zipfile.ZipFile(file)as z:assert z.testzip()is None
        artifacts.append(dict(file=name,bytes=file.stat().st_size,sha256=sha(file)))
    (r/'packages.json').write_text(json.dumps(dict(artifacts=artifacts),indent=2),encoding='utf8');print('FACE_PACKAGES_VERIFIED',json.dumps(artifacts),flush=True)

if __name__=='__main__':main()
