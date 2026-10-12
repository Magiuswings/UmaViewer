# V7 → V8 asset 与 customization 只读审查

审查输入：`E:/UmaViewer-Exports/2026-10-11-UMA-V7/UMA-V7`。未修改 V7、原版游戏或全局程序；没有启动 Blender。详单见同目录 `asset-registration-audit.json` 和 `asset-schema-audit.json`。独立扫描器按二进制 typed payload 跳过属性值，并记录原始 null-terminated object key、偏移、十六进制字节、EOF；没有调用 `io_pdx_mesh` 验证名称。

## 已确认

- 155 个 `.asset`，267 个 `pdxmesh` 定义，282 个 `meshsettings` 全部匹配各自实际二进制 object key 与合法 submesh index。目标及纹理文件存在。1397 个唯一实际 binary 被检查（包含三组原版参考及其 shape targets）。没有发现 meshsettings 名字多写或少写 `Shape` 的违例；完整逐项结果在 JSON。
- `uma_0001_shoes_0051_01_00_base.mesh` 的实际 key 是 `uma_0001_shoes_0051_01_00_m00Shape`。name offset=37；字节为 `756d615f303030315f73686f65735f303035315f30315f30305f6d3030536861706500`。对应 `.asset` 的 `meshsettings.name` 完全一致。0050 同样一致。
- 原版 `female_body.mesh` 实际 key 是 `female_bodyShape`；原版 mena 腿装实际 key 是 `female_legwear_secular_mena_nobility_01Shape`，都与自身 `.asset` 一致。`Shape` 本身是原版使用的正常名字，不应因为看到后缀便认定错误。
- `io_pdx_mesh/pdx_data.py`：`writeObject` 直接写 `obj_xml.tag`，不追加 `Shape`；`read_meshfile` / `parseObject` 读原始字符串，不追加、去除或规范化后缀。因此“writer 自动加了 Shape、reader 又去掉，所以 parser 自测漏错”的说法与当前文件源码不符。
- 0051 鞋几何 784 vertices / 878 triangles 非空；tri 范围 0..783，p/n/ta/UV/w 有限；正权重没有负 ix；权重归一误差约 `5.96e-8`。
- 原版 body 与 mena 腿装的 child order 是 `mesh` → `skeleton`；V7 衣装是 `skeleton` → `mesh`。这是真实 schema 差异，应在 V8 输出顺序中消除；是否造成引擎丢弃 geometry，尚无本轮实时引擎证据。
- `w=0` 时的 `ix=-1` 不是违例：0051 鞋有 1785 个；原版 body 有 2383 个；原版 mena 腿装有 1514 个。应保留该原版 sentinel，禁止为了猜修复把它一律改成 0。只有 `w>0 && ix<0` 才列为错误。
- V7 mesh 属性顺序是 p/n/ta/u0/tri/boundingsphere；原版还使用 sfs，腿装还带 u1。缺少 u1 或 sfs 是否受具体 shader/importer 要求约束，不能凭字段差异认定 geometry 无效。不要填造 sfs 或复制另一拓扑的 per-face 数据。
- V7 五个 customization group 全部 `usage=customization`。去掉民族 accessory 块后，它们不会据此承担 game 默认装配；应按下面的同组 `usage=both` 方案迁移。

## 全部脚本违例清单位置

`asset-schema-audit.json.customization.mode_violations`：所有手写 `dna_modifiers.accessory` 的非 `add` 项，包含文件、行号、group/item 路径、gene、template。按本轮明确契约统一 `mode=add`；morph/color 的 replace 不能跟着机械改成 add。`add_accessory_modifiers` 是原版认可的自动生成机制，不能因为它没有显式 mode 字段就列为错误。

`asset-schema-audit.json.customization.ethnicity_accessory_violations`：两个 Uma ethnicity 中每一个 accessory gene 块，列出行号、gene 和模板。全部迁移出 ethnicity，保留已有 morph/color gene 默认值。没有找到当前安装版文本中的 `customization_defaults` 字段，所以不建议凭空新增该字段。

## V8 binary 修复契约

1. 每一个 object 先输出所有 `mesh` 子节点，再输出 `skeleton`。每个 mesh 保持原版次序：p/n/ta/u0（有实际数据才加 u1/u2/u3）/tri/合法原生 sfs（若存在）/boundingsphere，然后 aabb/material/skin。skin 保持 bones/ix/w。不要改变几何、UV、skin 权重、source点或精确 inverse bind 来修名字。
2. 一个 object 的 meshsettings.index 是该 object 内 mesh 的 ordinal，从 0 开始；material override 使用对应槽，不是骨号、材质原生 ID 或整个文件的全局 mesh ordinal。
3. 名称以实际 binary key 为准，全 file/base/全部 BS 必须用同一组 key。推荐保留现有原版风格 `Shape`。若 root 选择 V8 去 `Shape`，必须同时更名所有 base/BS object tag 与所有 pdxmesh aliases 的 meshsettings；不要只改 asset，也不要对已经没有后缀的名字重复裁剪。这属于统一命名，不是已证明的引擎根因修复。
4. writer 验证只能证明编码可读；独立 raw scanner 能证明字节/字段契约。修复后仍须实际引擎重新加载，只启用单一 V8 descriptor，记录当前错误日志路径、时间和 active mod path；若日志报“not in use”，同时核对 geometry 被接受、对象顺序、活跃副本 SHA256、重复 pdxmesh/entity 定义。不要将 raw key 一致误写成 engine 已通过。

## 合法的 1001 / 1002 默认选择

原版 `_portrait_modifiers.info` 支持 `usage=both`（默认也是 both）、`selection_behavior=max`、`fallback`、priority、weight；原版 `01_clothes_base.txt` 实际使用 selection_behavior/max/fallback；`02_all_developer_characters.txt` 使用 `mode=add` 和具体角色条件选择 outfit。`01_hairstyles_base.txt` / `01_beards_base.txt` 实际使用 `has_character_flag`。

采用同一个 customization group 提供手动选择与 game 初始默认，避免另建一个高优先级 game group 永久覆盖用户的脱衣/换装选择。1001 是默认，1002 使用 root 明确设置的角色身份 flag `uma_actor_1002`；该 flag 是 V8 新契约，原版不会自动生成它，必须在测试角色创建/导入时由 root 设置。如果使用固定历史/测试角色 ID，也可以照原版 developer group 的 `exists=character:<id>` + `this=character:<id>` 条件替换 flag。不能假造未经原版佐证的 `has_ethnicity` 或读取 accessory DNA 的 trigger。

示例仅是可实施契约，不写入 V7：

```text
uma_custom_clothes = {
    usage = both
    selection_behavior = max
    fallback = uma_default_clothes_1001
    interface_position = 2

    uma_default_clothes_1001 = {
        dna_modifiers = {
            accessory = {
                mode = add
                gene = uma_clothes
                template = uma_bdy1001_00_clothes
                value = 1.0
            }
        }
        weight = { base = 10 }
    }
    uma_default_clothes_1002 = {
        dna_modifiers = {
            accessory = {
                mode = add
                gene = uma_clothes
                template = uma_bdy1002_00_clothes
                value = 1.0
            }
        }
        weight = {
            base = 0
            modifier = { add = 200 has_character_flag = uma_actor_1002 }
        }
    }
    add_accessory_modifiers = {
        gene = uma_clothes
        template = uma_clothes_none
        weight = { base = 0 }
    }
    # Preserve all family choices/actor material variants with base=0.
    # They remain selectable in customization and do not randomly win defaults.
}
```

同样迁移 shoes/socks：对应 gene=`uma_shoes` / `uma_socks`，默认 template=`uma_bdy1001_00_shoes/socks`、`uma_bdy1002_00_shoes/socks`；fallback 指向该组显式 1001 默认 item。headwear 使用现有 `uma_1001_headwear_00` / `uma_1002_headwear_00` 组合 item：其 accessory 指令都改为 add，保留 morph `uma_head_points` 的 replace 和正确模板，所有非默认组合 base=0。hair 的同组默认同理，并统一处理 headwear 组合与 hair group 的同时写入/priority，确保一个可见 slot 最终只有选定结果。衣服、鞋、袜、headwear 的 none 仍可手动选择；不能给 body-clothed 添加恒定默认值。

这套机制的原版语法有据，V8 接入后仍要验证两个测试角色的默认、切换、none、保存重载和肤色/体型；身份 flag 生命周期以及 barbershop 已存选择的实际优先级尚未在本轮引擎中验证。

## 原版佐证位置

- `D:/steam/steamapps/common/Crusader Kings III/game/gfx/models/portraits/female_body/female_body.asset`，meshsettings 从第 11 行起；对应 `.mesh` 的 raw offset=37。
- `.../gfx/models/portraits/f_legwear/mena/nob_01/f_legwear_secular_mena_nob_01.asset`，meshsettings 从第 15 行起；对应 raw offset=37。
- `.../gfx/models/portraits/f_clothes/western/nob_01/f_clothes_secular_western_nob_01.asset`，第三组衣装字节参考，详见 JSON stock_comparison。
- `.../gfx/portraits/portrait_modifiers/_portrait_modifiers.info`：usage 第 10 行，selection/fallback 第 39–44 行，accessory 第 120–140 行，add_accessory_modifiers 第 158 行。
- `.../gfx/portraits/portrait_modifiers/01_clothes_base.txt`：clothes_effect 第 28–31 行实际 game/max/fallback。
- `.../gfx/portraits/portrait_modifiers/02_all_developer_characters.txt`：第 1–25 行实际 game/max + mode add + 具体角色条件。
- `.../gfx/portraits/portrait_modifiers/01_beards_base.txt`：第 42 行实际 has_character_flag。
- `E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh/pdx_data.py`：parseObject 第 113 行、read_meshfile 第 197 行、writeObject 第 275 行、write_meshfile 第 388 行。

注意 `_portrait_modifiers.info` 也有历史/通用 replace 示例，不能仅凭例子声称当前引擎支持所有 accessory mode。本轮按明确要求统一 add；最终支持情况以新引擎日志为准。

## 尚未确认的具体引擎根因

当前可读 V7 源包没有名字错配；缺少当前错误日志对应的真正 active 文件副本，因此无法把“多 Shape”或“not in use”准确归到某一个引擎内部失败。确认存在的 candidate root cause 是与 working stock 不同的 object child order；不支持 sentinel 错误假说。请将“schema差异修正候选”和“引擎根因已证实”分开记录。


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

`accessory-bs-schema-contract.json`保存18个原版目标。mena腿装9目标中8个无skeleton；western衣装9目标中9个保留skeleton，此外mena的clothes目标也保留。所有这些目标都没有skin/ix/w/bones，而全部保留material。计数以JSON为准。

按用户新要求，V8衣装/鞋/袜/headwear等accessory BS可去skeleton，并可同时去skin/ix/w/bones，base保留完整rig+skin。保留对应slot的p/n/ta/u0/实际native u1/tri、aabb、boundingsphere；body BS仍保留skeleton。原版的BS名字不一定等于base名字，故匹配原版target按slot/顶点顺序/拓扑检查，咱们仍可用统一名字作工程契约。

材料不能据本轮原版证据声称可无条件去除：所有样本仍有material，体积也很小。建议保留轻量material并由root最终SDK回读；若root另外实测geometry-only target后才可记录无需material。
