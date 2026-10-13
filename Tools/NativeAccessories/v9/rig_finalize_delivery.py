import json,hashlib
from pathlib import Path
R=Path('E:/UmaViewer-Exports/2026-10-13-UMA-V9/RigRepair');V8=Path('E:/UmaViewer-Exports/2026-10-12-UMA-V8');V7=Path('E:/UmaViewer-Exports/2026-10-11-UMA-V7');delivery=json.loads((R/'rig-neck-unified-contract.json').read_text());delivery['selected_default']='full_root';delivery['alternative_selector']='translation_only is a paired alternative rig+bridge+clip, never mix its clip with full_root bindings';delivery['default_basis']='Root-only matching the existing stock independent head attachment layout, with seam body-follow motion explicitly encoded. Exact engine matrix semantics remains for fresh game evidence.';coverage=[]
for actor,variants in [('1001',['00','02','30','80','90']),('1002',['00','30','80'])]:
 for variant in variants:
  p=V7/f'HeadSources/partitions/chr{actor}_{variant}/head-components.json';d=json.loads(p.read_text());sets={e:set(d.get(e+'_triangle_ids',[]))for e in ['hair','ear','headwear','neck_patch']};union=set().union(*sets.values());assert sum(map(len,sets.values()))==len(union)
  source=V7/f'HeadSources/parsed/chr{actor}_{variant}/head.json';data=json.loads(source.read_text());hair=next(m for m in data['meshes']if m['name']=='M_Hair');total=sum(len(f['triangles'])//3 for f in hair['faces']);assert len(union)==total
  coverage.append({'actor':actor,'variant':variant,'hair_triangles':len(sets['hair']),'ear_triangles':len(sets['ear']),'headwear_triangles':len(sets['headwear']),'neck_patch_triangles':len(sets['neck_patch']),'ear_headwear_source_triangle_overlap':len(sets['ear']&sets['headwear']),'all_original_hair_triangles_covered':True,'source_partition_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_mesh_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
sourceindex=json.loads((V8/'MotionSources/native-source-local-index.json').read_text());provenance=[]
for rec in sourceindex['records']:
 bundle=rec.get('source_bundle')
 if bundle and Path(bundle).is_file():
  sha=hashlib.sha256(Path(bundle).read_bytes()).hexdigest();assert sha==rec['source_sha256'];provenance.append({k:rec[k]for k in ['key','module','source_bundle','source_sha256','source_clip_name','source_clip_path_id','fps','seconds','native_local_frame_count']if k in rec})
delivery['actual_source_bundle_hashes_reverified']=provenance;delivery['headwear_ear_source_partition_checks']=coverage;delivery['ready_components_index']=str(R/'ready-components-index.json');delivery['node_layout_bounds_audit']=str(R/'rig-node-layout-bounds-audit.json');delivery['attachment_alternative_audit']=str(R/'neck-attachment-assumption-audit.json');(R/'rig-neck-unified-contract.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
text='''V9 RigRepair 接入合同

默认使用 Head245/full_root：head_root 保留 V8 的静态 -d 和原 242 骨点；仅新增3个 seam helpers，完整引用和 .anim 均245j。portrait type保留 root→thoracic 一组，删额外两组 clavicle joint_attachment。

Components245 有两性同245 carrier和65个按骨名重排 skin ix 的临时组件。普通face/headparts/cheek/tear/neck_patch位置、法线、UV、tri和weights保持原输入；两个neck桥仅改lower6的共同bind坐标/权重并复制真实body法线，upper10原输入保持。使用这些neck替换旧RootI颈桥并合并到每actor head，删除独立neck entity。

Head245/full_root/uma_head_native_idle_seam.anim 与carrier必须一起使用，骨数245，61帧30FPS，源home UMA真实帧。新增helper pose=inv(externalRoot)*实际Body当前骨矩阵，不依赖两处clav joint覆盖。

Head245/translation_only 是引擎root attachment若只取平移时的完整对照；它同时变换原242当前pose和helper，不可只拿该动画搭full_root inversebind。精确引擎matrix实现未取得，不能把离线PDX数字验证当游戏通过。

所有外部耳挂点统一bn_h_head；两actor该Head bind点完全相同，独立ear/tail原source和动画不需改。1002私有骨仅保留deform：两眼Rotate与1001相差约0.270318cm，不能单靠inversebind把共同同名current pivot变成两套。

StaticHeadwear含6件真实头饰，不用Ear动画宏/任何state。使用shared_pose_entity=head，正权全部bn_h_head，其他非耳原生点为unweighted reference，原生weights另存.rebind.json。头饰p/n/UV/tri未改，几何仍attachment-local，故其公共bn_h_head自身inversebind必须I：HeaderCurrentHead*I*p正好等于原nodeHead*neutralAccessoryP。不能在不改p情况下把这些wear的inversebind替换为common245的Head inversebind。也可直接公共bn_h_head node静态刚体挂接，避免shared pose，此时保持自己的neutral静态骨架，不加动画。

真实headwear与ear源triangle IDs在8个变体全部互斥且覆盖原M_Hair。无source triangles删失，1001_30 neck_patch明确absent，不能复用80冒充。

所有贴图/颜色/最终asset、gene、modifier由主任务处理。本目录未编辑正式Mod或原版Game。当前现有error.log时间为2026-08-15，并非V8实机日志；没有证据证明242骨造成Ruler Designer故障。
'''
(R/'README-neck-contract.txt').write_text(text,encoding='utf-8-sig');print('READY_V9',len(coverage),'partitions',len(provenance),'sourceSHAs',delivery['candidates'][0]['clip_sha256'])
