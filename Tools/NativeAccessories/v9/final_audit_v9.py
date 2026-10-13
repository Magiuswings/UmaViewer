"""Final V8/V9 preservation and designer diagnostics, distinct from CK3 runtime."""
import hashlib,json,sys
from pathlib import Path
from paths_v9 import ROOT,MOD,V8,REPO
from validate_v9 import clausewitz,one,values,P

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def geometry(node):
    return (node.tag,dict(node.attrib),[geometry(child)for child in node if child.tag!='material'])
def render(tree,level=0):
    lines=[]
    for k,v in tree:
        if k is None:lines.append('\t'*level+str(v));continue
        if isinstance(v,list):lines.append('\t'*level+k+' = {');lines.extend(render(v,level+1));lines.append('\t'*level+'}')
        else:lines.append('\t'*level+k+(' = '+v if v is not None else ''))
    return lines
def main():
    checks=[];old=V8/'UMA-V8'
    for f in(MOD/'gfx/FX').rglob('*'):
        if f.is_file():
            o=old/f.relative_to(MOD);assert o.is_file()and sha(f)==sha(o);checks.append(dict(kind='shader_unchanged',file=str(f),sha256=sha(f)))
    for f in(MOD/'gfx/models/portraits/uma/0001').glob('uma_0001_body_*.mesh'):
        o=old/f.relative_to(MOD);assert geometry(P.read_meshfile(str(f)))==geometry(P.read_meshfile(str(o)));checks.append(dict(kind='body_geometry_skin_rig_unchanged_material_paths_shortened',file=str(f),sha256=sha(f)))
    for module in ['body','ear','tail']:
        f=MOD/f'gfx/models/portraits/uma/animation/{module}/uma_{module}_native_idle.anim';o=old/f.relative_to(MOD);assert sha(f)==sha(o);checks.append(dict(kind='non_head_animation_unchanged',file=str(f),sha256=sha(f)))
    body=one(clausewitz((MOD/'common/genes/uma_body_morphs.txt').read_text(encoding='utf-8-sig')),'morph_genes');visible_empty=[];hidden_empty=[]
    for name,entry in body:
        if not isinstance(entry,list):continue
        for k,v in entry:
            if isinstance(v,list)and values(v,'index')and not values(v,'settings'):
                if values(v,'visible')==['yes']:visible_empty.append([name,k])
                else:hidden_empty.append([name,k])
    assert not visible_empty,visible_empty
    config=MOD/'gfx/portraits/customization_rules/uma_portrait_customization.txt';tree=clausewitz(config.read_text(encoding='utf-8-sig'));scope=one(tree,'uma')
    rules=one(scope,'gene_groups');assert not values(one(rules,'anatomy'),'face')
    alt=[(k,[]if k=='accessories'else v)for k,v in scope if k!='color_genes'and not k.startswith('accessory_color_override_block_')]
    dest=ROOT/'Diagnostics/designer_without_custom_ui/gfx/portraits/customization_rules/uma_portrait_customization.txt';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('\n'.join(render([('uma',alt)]))+'\n',encoding='utf-8-sig')
    readme=ROOT/'Diagnostics/README.txt';readme.write_text('此目录不是另一个模组。只进行一次配置对照：先备份正式 UMA-V9 中的 gfx/portraits/customization_rules/uma_portrait_customization.txt，再用 designer_without_custom_ui 中同名文件覆盖，保持其他文件完全一致。\n此对照仅关闭四个自定义衣装 UI 与其颜色选项映射；模型、普通基因、运行时附件、种族、调色盘和动画不变。\n确认设计器是否仍退出后恢复原配置。若对照不退出，只能说明相关 UI 注册值得继续二分，不能直接证明某个模型无问题。正式包没有启用此对照。\n当前没有本轮 CK3 运行结果，不能将静态通过当作沉默退出已修复。\n',encoding='utf-8-sig')
    report=dict(passed=True,preservation_checks=checks,body_mesh_changed=False,body_BS_changed=False,shader_changed=False,visible_empty_body_templates=visible_empty,hidden_empty_templates=hidden_empty,unrepresented_face_category_removed=True,designer_diagnostic=str(dest),diagnostic_changes_only_custom_accessory_UI=True,CK3_engine_executed=False,ruler_designer_root_cause_confirmed=False)
    (ROOT/'Reports/final-preservation-designer-audit.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('V9_FINAL_PRESERVATION',len(checks),'visible empty',len(visible_empty),flush=True)
if __name__=='__main__':main()
