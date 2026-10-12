"""Join readonly audit conclusions and original BS schema evidence; source files untouched."""
import json,csv,collections
from pathlib import Path
from asset_registration_audit import OUT
from asset_log_compare import lods
def main():
 mainfile=OUT/'asset-registration-audit.json';a=json.loads(mainfile.read_text());s=json.loads((OUT/'asset-schema-audit.json').read_text());d=json.loads((OUT/'error-log-asset-comparison.json').read_text());rows=d['registered_rows'];unique={}
 for row in rows:unique.setdefault((row['file'],row['shape']),row)
 table={}
 for feature in ['object_child_order','has_lod','has_sfs','object_count','element']:
  groups=collections.defaultdict(lambda:dict(unique_file_shape=0,with_log_error=0,without_log_error=0))
  for row in unique.values():key=str(row[feature]);g=groups[key];g['unique_file_shape']+=1;g['with_log_error']+=int(row['logged_error']);g['without_log_error']+=int(not row['logged_error'])
  table[feature]=dict(groups)
 stocklod=[dict(file=r['file'],shapes=lods(r['file'],r['raw_shape_evidence']))for r in a['stock_comparison']];bs=[]
 for r in s['stock_reference']:
  if'_bs_'not in Path(r['path']).name or not any(k in r['path'].replace('\\','/')for k in ['/f_clothes/','/f_legwear/']):continue
  bs.append(dict(file=r['path'],skeleton_present=any('skeleton'in sh['child_order']for sh in r['shapes']),skin_present=any(bool(m['skin'])for sh in r['shapes']for m in sh['meshes']),material_present=any(bool(m['material'])for sh in r['shapes']for m in sh['meshes']),shape_data=r['shapes']))
 bs_contract=dict(stock_accessory_BS_samples=len(bs),without_skeleton=sum(not r['skeleton_present']for r in bs),without_skin=sum(not r['skin_present']for r in bs),without_material=sum(not r['material_present']for r in bs),examples=bs,contract=dict(accessory_base='Retain full exact rig/source bones and skin; mesh before skeleton.',accessory_targets='User explicitly requests no skeleton in clothing/accessory BS. Original mena8targets prove no-skeleton+no-skin workable; remove target skin/ix/w/bones too.',body_targets='Retain skeleton as explicitly requested. Do not apply accessory stripping to body.',geometry='Retain p/n/ta/u0/(native u1 if actually present)/tri; topology and vertex order match corresponding base slot, common weights inherited from base.',bounds='Retain aabb and boundingsphere, updated for target geometry.',material='All sampled original targets retain material. No actual material-free sample in this audit; recommend keep small original material node rather than claim no-material engine proven.',lod='Optional explicit lod=[0] for project consistency; three working stock bases lack lod, so not a universal requirement.',name='Stock BS target names can differ from base names, even truncated Shape suffix. Same-name requirement is project discipline, not a general SDK necessity.'),game_validation='Root performs final SDK readback and live engine verification; this audit does not run Blender/engine.')
 (OUT/'accessory-bs-schema-contract.json').write_text(json.dumps(bs_contract,indent=2),encoding='utf8');d['unique_file_shape_cross_tables']=table;d['aggregation_caution']='Raw log191 occurrences vs187unique file+shape; pdxmesh aliases reuse physical file; log messages have no material index. registered settings199 associated rows are not199distinct engine failure events. Per-setting occurrence attribution repeats material events across aliases or slots; use event frequency tables for true log counts.';d['stock_base_lod_counterexamples']=stocklod;(OUT/'error-log-asset-comparison.json').write_text(json.dumps(d,indent=2),encoding='utf8');a.update(schema_audit=str(OUT/'asset-schema-audit.json'),current_log_comparison=str(OUT/'error-log-asset-comparison.json'),current_log_csv=str(OUT/'error-log-asset-comparison.csv'),accessory_bs_contract=str(OUT/'accessory-bs-schema-contract.json'),current_log_counts=d['counts'],unique_file_shape_cross_tables=table,script_contract_violations=dict(accessory_mode_nonadd=s['customization']['mode_violations'],accessory_in_ethnicity=s['customization']['ethnicity_accessory_violations']),confirmed_observations=['All282 meshsettings exact-match binary keys/index. No extra-Shape mismatch in source package.','All187unique skeleton-first physical shapes show both material/out-of-sync errors; all83mesh-first shapes show none in this log.','All three inspected working stock bases have no lod; absence of lod alone is not invalid.','All282mod settings lack sfs, including83no-log-error controls; sfs not a discriminating explanation.','Original zero-weight skin ix=-1 sentinel is legitimate.','30accessory ethnicity entries are directly rejected by current log ethnicity.cpp:304.'],unverified_causality=['Node order is a complete separator in supplied sample, strongest repair candidate; not an isolated engine A/B proof.','Shader fallback to gfx/FX/pdxmesh.shader occurs before out-of-sync; exact loader cause still requires root fresh engine test.','88non-add accessory instructions violate requested migration contract; current log alone does not prove all88 produce a mode-specific error.','Actual active installed mod hashes were not supplied; analysis correlates supplied log paths with V7 source package.']);mainfile.write_text(json.dumps(a,indent=2),encoding='utf8');print('FINAL_AUDIT','unique',len(unique),'BS',bs_contract['stock_accessory_BS_samples'],bs_contract['without_skeleton'],bs_contract['without_skin'],bs_contract['without_material'],'scripts',len(s['customization']['mode_violations']),len(s['customization']['ethnicity_accessory_violations']));print('UNIQUE_TABLE',table)
 appendix='''

## 当前真实 error.log 全量关联结果（补充，优先于前面的缺日志说明）

输入 `C:/Users/33775/Downloads/error.log`，共10530行、1831749bytes。完整比较见 `error-log-asset-comparison.json` / `.csv`。191条材质失败、191条out-of-sync是同一批失败的两类诊断，不是382件衣装；材质错误为187unique(file,shape)、180unique.mesh，out-of-sync为184unique pdxmesh、187unique(file,shape)、180unique.mesh。4个file/shape重复各2次来自共享赛车衣/袜material aliases，不是新几何。

当前源包实际267pdxmesh、282meshsettings，去alias/slot重复后270unique(file,shape)。分组：

|实际object顺序|unique file+shape|有对应日志失败|该日志未报此错|
|---|---:|---:|---:|
|skeleton→mesh（含多mesh）|187|187|0|
|mesh→skeleton|83|0|83|

因此“只有一部分失败”与不同生成链高度吻合：全部衣装/鞋/袜以及两件源body headwear进入失败组；body、head及其余原生head accessories属于mesh先的对照组。日志未报错仍不是已成功显示的证明。

按282注册settings计：199关联失败、83无该错误。此199包含aliases及同一个object的多个index，不能拿它作为真实失败事件数。index1/2各4settings关联失败，single与multi object都存在失败，故不能归为只有多material或index>0的问题。binary portrait_attachment的223settings中199报错、24未报错，也不能仅归为shader名字本身不同。

LOD是次级相关特征：80有lod settings均未报错，202缺lod中199关联失败/3未报错；那3个反例是body与男女head scaffold。更强原版反证是本审查的female_body、mena腿装、western衣装三个working base全无lod。可以为V8加明确lod=0，但不应把缺lod称为SDK必然非法。所有282都缺sfs，所以sfs不能区分本次失败组；没有在io_pdx_mesh源码找到sfs含义/默认生成证据，不伪造补值。

日志先显示 material creation 在 `gfx/FX/pdxmesh.shader` 失败，后显示同shape not in use，而asset指定的是`uma_portrait.shader`。raw名字相同，故out-of-sync不能直接解释成额外Shape：更符合active geometry/material注册失败导致后续setting无对象可用。nodeOrder是当前最强且完整分离的修复候选，最终是否单独致因必须通过V8新引擎A/B或修复后新log确认；本审查未运行游戏。

## 原版 accessory BS 最小schema证据

`accessory-bs-schema-contract.json`保存17个原版目标。mena腿装9目标中8个无skeleton；western衣装9目标中9个保留skeleton，此外mena的clothes目标也保留。所有这些目标都没有skin/ix/w/bones，而全部保留material。计数以JSON为准。

按用户新要求，V8衣装/鞋/袜/headwear等accessory BS可去skeleton，并可同时去skin/ix/w/bones，base保留完整rig+skin。保留对应slot的p/n/ta/u0/实际native u1/tri、aabb、boundingsphere；body BS仍保留skeleton。原版的BS名字不一定等于base名字，故匹配原版target按slot/顶点顺序/拓扑检查，咱们仍可用统一名字作工程契约。

材料不能据本轮原版证据声称可无条件去除：所有样本仍有material，体积也很小。建议保留轻量material并由root最终SDK回读；若root另外实测geometry-only target后才可记录无需material。
'''
 # Correct sample wording from actual count, including target alias types.
 appendix=appendix.replace('保存17个原版目标','保存'+str(len(bs))+'个原版目标');(OUT/'asset-registration-audit.md').open('a',encoding='utf8').write(appendix)
if __name__=='__main__':main()
