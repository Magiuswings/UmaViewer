# UMA V9 independent designer / color / post-dedup contract

输入：只读 V7、V8 与本机 CK3 原版，另核对 root 当前 V9 合并后注册。未启动游戏 UI，未修改最终 mod、原版或全局程序。`designer-dedup-audit.json` 是完整清单，六个 `.diff` 是精确文本差异；`minimal_designer_contract.py` 提供只操作传入 tree 的 apply API 与可审阅文件稿。

## 确认的 V8 新差异与候选

1. V7 `uma_head_points` 声明 `group=face`；V8 删除该 gene 后，没有显式 UMA face group gene，但 rules 仍列 `gene_groups.anatomy.face=face`。此配置与显式声明不闭合。`face` 右值是原版合法镜头，不是 gene group 名；检查的是左边 group key。最小规则删除该空 face 类别，保留 body/hair，并添加已有眼色 group `eyes=face`。
2. V8 `gene_bs_body_shape` 的11个原有模板全无 model setting，但仍默认可见；V7部分模板实际有 setting。应全部 `visible=no`，仍保留 `body_shape_average` 以满足 ethnicity/modifier 引用。body 分类仍有带真实属性的 bodyType 和 bust，不必删除 body 分类。
3. V8删除了 UMA自定义 hair group 与 rules 的 hair color binding；头部选择已合并在 `uma_custom_headwear`，应以 `color_genes={hair=uma_custom_headwear}` 指向实际存在的选择组，不能误指原版 `custom_hair`。
4. 八对 explicit UI item 的 `dna_modifiers` 完全相同：1001/1002 headwear80与none；clothes/shoes/socks的默认1001/1002与普通00。这不是八个缺失模型，而是 UI 重复。删除默认重复项时，必须把 default weight 转给00 survivor并同步fallback，否则会造成新的未闭合。runtime gene模板不删。

这些是文件上的真实输入差异；**没有本轮实机重现、退出堆栈或错误日志，不能声称已证明 silent 退出由其中任何一项造成。** 也不能排除引擎默认 group 继承逻辑会隐藏空组，需修复后的独立 designer 运行确认。

## 不能当作 V8 新增退出原因的项目

- `uma_colors.txt`、`uma_parts.txt`、`uma_portrait_types.txt` 在 V7/V8 完全相同。新旧色 gene key 都是 `uma_hair_color/uma_skin_color/uma_eye_color`，因此虽然违反本轮恢复原 key 的要求，它们不是 V8 唯一代码增量。
- body root `morph_genes` 与安装原版 `01_genes_morph.txt` 第369行相同，不能改成凭空的 `regular_genes` 或称其语法错误。
- type index缺4、shape缺0、bust缺0/1在V7已存在，不能当V8新增crash根因。原版这些位置有hidden/reserved模板。API可补hidden无属性no-op并保留原编号，而不驱动 `bs_body_clothed` 或任何额外模型。
- 四个 UMA type 的 adult minimum_age=18 / child maximum_age=18 在两版本相同；本合同保持所有四个18边界，不改年龄规则。

## 正确的颜色树、精度与加载次序

原版文件为 `D:/steam/steamapps/common/Crusader Kings III/game/common/genes/00_genes_color.txt`，345bytes；原key及顺序：hair_color、skin_color、eye_color。skin/eye 的 sync_inheritance_with 均为 hair_color。保持原group hair/body/eyes、color hair/skin/eye与blend_range；只在复制树根加 `portrait_group=uma`。

新文件名 `000_uma_genes_color.txt`，保留原版 `00_genes_color.txt` 完整不变。移除V9旧`uma_colors.txt`，不能两个自定义颜色定义并存。所有UMA ethnicity/DNA/modifier里的color gene引用换回原key；颜色坐标值最多2位小数，不能顺带舍入 body morph 的原0.499等非颜色参数。

同理 portrait_types 文件名为 `000_uma_portrait_types.txt`，原版为 `00_human_types.txt`。两组静态lex排序均验证000在00前。原版human最后状态保持。实际虚拟文件系统/多mod加载仍需root新启动验证，此合同不把字典序检查当引擎运行证明。

最小 UMA规则：

```text
gene_groups = {
    anatomy = { body = full_body eyes = face }
    hair = { hair = face }
}
color_genes = { hair = uma_custom_headwear }
```

继续保留 four accessory customization映射、sex_only_genes female gene_bs_bust、四个color_override_block及原默认年龄。这是已声明 body/hair/eyes的最小集合；不要恢复已取消的head_points additive来填空face类别。

## Body/UI apply API

`minimal_designer_contract.py`输入输出采用 `build_ck3_mod.clausewitz` 的 `(key,value)` tree：

- `apply_body_compatibility(tree)`：隐藏13个无binding模板（11shape + body_average + bust_default），保留key/index/ethnicity引用；添加hidden无属性no_portrait4、body_shape_average_clothed0、bust_clothes0、bust_clothes_light1。bodyType/Bust有setting的模板不改。
- `apply_minimal_rules(tree, declared_groups, hair_modifier_group)`：只删除没有显式gene声明的groupkey，添加eyes相机、恢复hair颜色选择组绑定。
- `build_original_color_tree(stock_tree)`：保留原版三个key、顺序及内部树，新增UMA scope。
- `rename_round_color_references(tree)`：仅原/旧颜色key、引用和颜色子树decimal改名/2位小数；不改其他gene数值。
- `deduplicate_ui_choices(tree)`：只有匹配且DNA完全相同才删8重复UI，weight/fallback转移，runtime genes不动。headwear保留none选项，删除重复80 UI项，80 runtime模板仍存在。

文件稿均在本目录 `.contract.txt`；它们基于只读V8供参考，root在V9重建tree中调用API时，匹配条件不满足会保留当前项，不会强删新定义。已自检无可见no-binding body模板、indexes唯一完整、fallback目标存在。

## 头部与 cheek 去重

V8两个actor的cheek整文件SHA不同（object name及无权aux不同），不能硬说byte-identical。但是可见payload：p/n/ta/UV/tri/w、正权骨名+bind与material完全相同，1001的00/30/80/90为一组，1002的00/30/80为一组。这提供同actor复用一个render mesh的证据，不支持跨actor硬合。

各actor的head/core(face+faceparts+neckpatch+bridge)与可选cheek/tear可以在同actor一个asset中定义；服装只切hair/ear/headwear，eye/brow每actor一套复用。cheek、tear仍为可选 overlay，不能为了合并把默认tear永久加入核心几何。合并/删除模型后必须重建gene index/模板→accessory→entity→pdxmesh→actual file闭环；不可仅删文件。

V8注册267pdxmesh/267entities，旧闭环缺失0，但752个nonshader `.asset` 纹理引用带路径，违反本轮basename要求；shader_file保留完整shader路径例外。root已在V9处理，最新V9闭环结果另见 `v9-postmerge-registration-closure.json`。

载入顺序相关的另一事实：UMA placeholders复用了257个原版stock blend id。ID复用本身不证明全局冲突，因为SDK可能按pdxmesh作用域解析；后载空head targets污染默认UI cache是推断，前载UMA、让human最终态归原版是本轮约束，不宣称已证明内部缓存机制。

## 验证边界

确认：文件差异、显式group/setting缺失、重复DNA选择、颜色key/precision/lex排序、模型注册与哈希。推断：这些不闭合输入可能触发无日志designer退出；late placeholders影响原版默认缓存。未验证：退出实际调用栈、Root V9修复后的GUI稳定性、人类默认颜色和运行时排序。不得用静态脚本通过替代这些验收。
