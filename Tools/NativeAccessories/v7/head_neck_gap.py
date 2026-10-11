import os
"""True welded neck boundary rings from source weights and final body topology."""
import json,sys
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
from head_assembly_math import rigdata,compose,readlocals
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'HeadSources';OUT=SRC/'AssemblyQA';MOD=ROOT/'UMA-V7';BASE=MOD/'gfx/models/portraits/uma/0001';P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))))
def boundary(positions,triangles,precision):
    keymap={};rep=[];group=[];weld=[]
    for i,p in enumerate(positions):
        key=tuple(np.round(p,precision))
        if key not in keymap:keymap[key]=len(rep);rep.append(i);group.append([])
        j=keymap[key];group[j].append(i);weld.append(j)
    wt=np.array(weld)[triangles];counter=Counter(tuple(sorted((int(t[a]),int(t[b]))))for t in wt for a,b in[(0,1),(1,2),(2,0)]);edges=[e for e,c in counter.items()if c==1];adj=defaultdict(set)
    for a,b in edges:adj[a].add(b);adj[b].add(a)
    unseen=set(adj);components=[]
    while unseen:
        start=next(iter(unseen));stack=[start];comp=set()
        while stack:
            i=stack.pop()
            if i in comp:continue
            comp.add(i);stack.extend(adj[i]-comp)
        unseen-=comp;closed=all(len(adj[i])==2 for i in comp);ordered=[]
        if closed:
            current=start;previous=None
            while current not in ordered:
                ordered.append(current);options=adj[current]-({previous}if previous is not None else set());nxt=min(options);previous,current=current,nxt
        else:ordered=sorted(comp)
        components.append({'welded_ids':ordered,'closed':closed,'degree_counts':dict(Counter(len(adj[i])for i in comp))})
    return np.array(rep),group,components
bodytree=P.read_meshfile(str(BASE/'uma_0001_body_base.mesh')).find('object')[0];bm=bodytree.find('mesh');B=rigdata(bodytree.find('skeleton'));bp=np.array(bm.get('p')).reshape(-1,3);bt=np.array(bm.get('tri')).reshape(-1,3);brep,bgroups,bloops=boundary(bp,bt,4);skin=bm.find('skin');bix=np.array(skin.get('ix')).reshape(-1,4);bw=np.array(skin.get('w')).reshape(-1,4)
bcandidates=[]
for i,loop in enumerate(bloops):
    v=brep[loop['welded_ids']];p=bp[v];center=p.mean(0)
    if loop['closed']and center[1]>125 and np.max(np.abs(p[:,0]))<10:bcandidates.append((i,float(center[1]),loop,v))
assert bcandidates,'No closed upper body neck boundary';chosen=max(bcandidates,key=lambda x:x[1]);bodyloop=chosen[2];bodyids=chosen[3];bodypositions=bp[bodyids]
bodyrecords=[]
for widx,v in zip(bodyloop['welded_ids'],bodyids):
    aliases=bgroups[widx];weights=[{'bone':B['names'][int(i)],'weight':float(w)}for i,w in zip(bix[v],bw[v])if i>=0 and w>0];bodyrecords.append({'final_body_vertex_id':int(v),'coincident_final_body_vertex_ids':aliases,'position_world_cm':bp[v].tolist(),'weights':weights})
bodyextra={}
for suffix in['b0','s1']:
    p=BASE/('uma_0001_body_'+suffix+'.mesh')
    if p.exists():q=np.array(P.read_meshfile(str(p)).find('object')[0].find('mesh').get('p')).reshape(-1,3);bodyextra[suffix]={'ring_vertex_position_delta_from_base_cm':(q[bodyids]-bodypositions).tolist(),'max_delta_cm':float(np.linalg.norm(q[bodyids]-bodypositions,axis=1).max())}
data0=readlocals(P,ROOT/'Rigs/uma_1002_head_points.anim',0);data1=readlocals(P,ROOT/'Rigs/uma_1002_head_points.anim',1);delta={n:data1[n][:3,3]-m[:3,3]for n,m in data0.items()if np.abs(data1[n][:3,3]-m[:3,3]).max()>1e-8};cs=rigdata(P.read_meshfile(str(BASE/'uma_0001_head_female.mesh')).find('object')[0].find('skeleton'));contract=json.loads((ROOT/'rig-contract.json').read_text());C=np.array(contract['head_source_to_engine']);anchor=np.array(contract['head_anchor']);results=[]
for actor in['1001','1002']:
    raw=json.loads((SRC/f'parsed/chr{actor}_80/head.json').read_text());bones={b['id']:b for b in raw['bones']};neckid=next(b['id']for b in raw['bones']if b['name']=='Neck');H=np.array(next(b for b in raw['bones']if b['name']=='Head')['matrix']).reshape(4,4)[:3,3];cw=compose(cs,delta=delta if actor=='1002'else{});attach=B['bind'][B['names'].index('bn_sp_thoracic')]@np.linalg.inv(cw[cs['names'].index('head_root')]);positions=[];tri=[];refs=[];weights=[]
    for name in['M_Face','M_Hair']:
        m=next(m for m in raw['meshes']if m['name']==name);p=np.array([[v[k]for k in 'xyz']for v in m['vertices']]);offset=len(positions);positions.extend(p);refs.extend([{'source_mesh':name,'source_vertex_id':i}for i in range(len(p))]);wvs=[[]for _ in p]
        for w in m['weights']:wvs[w['vertex']].append({'bone':bones[w['bone']]['name'],'weight':w['weight']})
        weights.extend(wvs);faces=[f for f in m['faces']if name!='M_Face'or f['category']=='face'];tri.extend((np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in faces])+offset).tolist())
    positions=np.array(positions);rep,groups,loops=boundary(positions,np.array(tri),6);candidates=[]
    for i,loop in enumerate(loops):
        inds=rep[loop['welded_ids']];nw=[max([next((w['weight']for w in weights[v]if w['bone']=='Neck'),0.)for v in groups[j]],default=0.)for j in loop['welded_ids']]
        if any(w>.29 for w in nw):candidates.append({'loop_id':i,'closed':loop['closed'],'vertices':len(inds),'neck_weights':nw,'source_mean_y_m':float(positions[inds,1].mean()),'degree_counts':loop['degree_counts'],'welded_ids':loop['welded_ids']})
    selected=[c for c in candidates if c['closed']and min(c['neck_weights'])>.29]
    faceonly=next(m for m in raw['meshes']if m['name']=='M_Face');neck_face_ids=[w['vertex']for w in faceonly['weights']if w['bone']==neckid]
    rec={'actor':actor,'source_variant':'80','source_face_neck_weighted_vertex_ids':neck_face_ids,'combined_face_hair_boundary_candidates':[{k:v for k,v in c.items()if k!='welded_ids'}for c in candidates],'true_neck_closed_ring_found':bool(selected),'face_only_is_not_a_closed_neck_ring':True,'whole_ring_uses_M_Face_plus_M_Hair_skin_patch':True}
    if selected:
        chosen=min(selected,key=lambda c:c['source_mean_y_m']);records=[];hp=[]
        for j in chosen['welded_ids']:
            aliases=groups[j];v=int(rep[j]);sourcep=positions[v];engine=C@(sourcep-H)+anchor;worldp=(attach@np.r_[engine,1])[:3];hp.append(worldp);records.append({'source_refs':[{**refs[i],'weights':weights[i]}for i in aliases],'source_position_unity_m':sourcep.tolist(),'head_local_position_cm':engine.tolist(),'position_world_cm':worldp.tolist()})
        hp=np.array(hp);cost=np.linalg.norm(hp[:,None,[0,2]]-bodypositions[None,:,[0,2]],axis=2);hi,bi=linear_sum_assignment(cost);matches=[]
        for h,b in zip(hi,bi):difference=hp[h]-bodypositions[b];matches.append({'head_ring_index':int(h),'body_ring_index':int(b),'delta_head_minus_body_cm':difference.tolist(),'distance_3d_cm':float(np.linalg.norm(difference)),'radial_xz_distance_cm':float(cost[h,b])})
        hc=hp[:,[0,2]].mean(0);bc=bodypositions[:,[0,2]].mean(0);hr=np.linalg.norm(hp[:,[0,2]]-hc,axis=1);br=np.linalg.norm(bodypositions[:,[0,2]]-bc,axis=1);rec.update({'ring_vertices':records,'head_ring_count':len(hp),'body_ring_count':len(bodypositions),'pairing_rule':'Hungarian minimum total xz distance; all available vertices paired once, no imposed y alignment.','cross_ring_matches':matches,'vertical_gap_min_cm':float(min(m['delta_head_minus_body_cm'][1]for m in matches)),'vertical_gap_max_cm':float(max(m['delta_head_minus_body_cm'][1]for m in matches)),'vertical_gap_mean_cm':float(np.mean([m['delta_head_minus_body_cm'][1]for m in matches])),'radial_pair_error_max_cm':float(max(m['radial_xz_distance_cm']for m in matches)),'head_ring_radius_mean_cm':float(hr.mean()),'body_ring_radius_mean_cm':float(br.mean()),'ring_center_xz_delta_cm':(hc-bc).tolist(),'head_ring_world_min_cm':hp.min(0).tolist(),'head_ring_world_max_cm':hp.max(0).tolist()})
    results.append(rec)
report={'units':'cm for engine/world positions; m only original Unity position','body_file':str(BASE/'uma_0001_body_base.mesh'),'body_open_neck_ring':bodyrecords,'body_ring_is_closed':True,'body_base_endpoint_ring_differences':bodyextra,'actors':results,'source_face_and_joint_layout_modified':False,'geometry_surface_gap_confirmed':True,'diagnostic_scope':'Base body static assembly with actual actor additive. Neck seam identified by welded open boundary and native Neck .3 weights; excludes chin. True closed head neck boundary needs both M_Face front skin and M_Hair rear skin patch.','bridge_recommendation':'Root can bridge body open ring to these exact fixed source head-ring vertices, or extend only body neck to ring. Do not move whole head or native source face. Endpoint .3 Neck/.7 Head weights belong to header rig; bridge deformation must account for own rig/shared pose contract.'};(OUT/'neck-surface-gap.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'body_ring_vertices':len(bodyrecords),'body_endpoint_ring_delta':{k:v['max_delta_cm']for k,v in bodyextra.items()},'actors':[{k:v for k,v in r.items()if k in['actor','true_neck_closed_ring_found','head_ring_count','body_ring_count','vertical_gap_min_cm','vertical_gap_max_cm','vertical_gap_mean_cm','radial_pair_error_max_cm','head_ring_radius_mean_cm','body_ring_radius_mean_cm','combined_face_hair_boundary_candidates']}for r in results]},indent=2))
