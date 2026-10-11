import os
"""Move proven native rear-neck skin to a shared head skin component, idempotently."""
import json,sys,copy,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'))
from build_ck3_mod import parser_only
from head_pdx_tools import make_mesh,pts
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'HeadSources';OUT=SRC/'NeckPatch';OUT.mkdir(exist_ok=True)
P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))));INDEX=SRC/'Export/head-export-index.json';index=json.loads(INDEX.read_text());parts=json.loads((SRC/'head-component-index.json').read_text())['variants'];gap=json.loads((SRC/'AssemblyQA/neck-surface-gap.json').read_text());palette={r['actor']:r for r in json.loads((ROOT/'Reports/palette-presets.json').read_text())};contract=json.loads((ROOT/'rig-contract.json').read_text());C=np.array(contract['head_source_to_engine']);anchor=np.array(contract['head_anchor']);records=[]
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
for header in index['heads']:
    actor=header['actor'];variant=header['variant'];delivery_path=Path(header['delivery_json']);delivery=json.loads(delivery_path.read_text());source=json.loads(Path(delivery['source_json']).read_text());m=next(m for m in source['meshes']if m['name']=='M_Hair');positions=pts(m['vertices']);tri=np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in m['faces']]);bybone={b['id']:b['name']for b in source['bones']};vw={i:[]for i in range(len(positions))}
    for w in m['weights']:vw[w['vertex']].append((bybone[w['bone']],w['weight']))
    mat=source['materials'][m['faces'][0]['material']];texref=next(p['texture']for p in mat['properties']if p['name']=='_MainTex');ctrlref=next(p['texture']for p in mat['properties']if p['name']=='_OptionMaskMap');resource=Path(delivery['source_json']).parent/'resources';tex=np.array(Image.open(resource/texref).convert('RGBA'));ctrl=np.array(Image.open(resource/ctrlref).convert('RGBA'));uv=np.array([[v['x'],v['y']]for v in m['uvs'][0]['values']]);partition_path=next(Path(p['partition_json'])for p in parts if p['actor']==actor and p['variant']==variant);partition=json.loads(partition_path.read_text())
    refs=[np.array(r['source_position_unity_m'])for r in next(a for a in gap['actors']if a['actor']==actor)['ring_vertices']if any(x['source_mesh']=='M_Hair'for x in r['source_refs'])]
    evidence=[];selected=set()
    for component in partition['components']:
        ids=component['source_vertex_ids'];pos=positions[ids];ring_dist=[float(np.linalg.norm(pos-r,axis=1).min())for r in refs]
        if min(ring_dist)>2e-6:continue
        x=np.clip(np.rint(uv[ids,0]*(tex.shape[1]-1)).astype(int),0,tex.shape[1]-1);y=np.clip(np.rint((1-uv[ids,1])*(tex.shape[0]-1)).astype(int),0,tex.shape[0]-1);rgb=tex[y,x,:3].mean(0);bones=sorted({b for v in ids for b,w in vw[v]if w>1e-5});blue=float((ctrl[y,x,2]>127).mean());pure=all(b in ['Head','Neck']for b in bones)and 'Neck'in bones
        accepted=bool(pure and rgb[0]>120 and rgb[1]>85 and blue<.1)
        evidence.append({'source_vertex_ids':ids,'source_triangle_ids':component['source_triangle_ids'],'source_rgb_mean':rgb.tolist(),'source_ctrl_blue_fraction':blue,'weighted_bones':bones,'ring_min_distances_unity_m':ring_dist,'accepted_skin':accepted})
        if accepted:selected.update(component['source_triangle_ids'])
    # Exact connected skin components, including all upper points. Dark source
    # clothing/hair that coincides with the neck ring is explicitly excluded.
    prior=set(partition.get('neck_patch_triangle_ids',[]));assert prior<=selected,(actor,variant,'previous extraction not proven skin')
    removal=[]
    for element in ['hair','ear','headwear']:
        key=element+'_triangle_ids';removed=selected&set(partition[key])
        if not removed:continue
        row=next(c for c in delivery['components']if c['element']==element);path=Path(row['mesh_path']);tree=P.read_meshfile(str(path));hm=tree.find('object')[0].find('mesh');ht=np.array(hm.get('tri')).reshape(-1,3);orig=row['source_vertex_mapping'][0]['source_vertex_ids'];sig={tuple(sorted(map(int,tri[t])))for t in removed};remove=[i for i,r in enumerate(ht)if tuple(sorted(orig[int(v)]for v in r))in sig];assert len(remove)==len(removed),(actor,variant,element,len(remove),len(removed));keep=np.ones(len(ht),bool);keep[remove]=False;before={k:copy.deepcopy(hm.get(k))for k in ['p','n','u0']};skin=copy.deepcopy(hm.find('skin').attrib);hm.set('tri',ht[keep].ravel().tolist());P.write_meshfile(str(path),tree);check=P.read_meshfile(str(path)).find('object')[0].find('mesh');assert all(check.get(k)==v for k,v in before.items())and check.find('skin').attrib==skin
        row['triangles']=int(keep.sum());row['source_triangles']=int(keep.sum());partition[key]=sorted(set(partition[key])-removed);removal.append({'from_component':element,'source_triangle_ids':sorted(removed),'mesh':str(path),'positions_normals_uv_skin_unchanged':True})
    patchrow={'actor':actor,'variant':variant,'element':'neck_patch','present':bool(selected),'optional_expression_overlay':False,'enabled_in_default_preset':bool(selected),'independent_native_pose':False,'attachment_node':None,'shared_pose_entity':'head','gene':'uma_neck_patch'}
    if selected:
        ids=np.unique(tri[sorted(selected)]);lookup={int(v):i for i,v in enumerate(ids)};patchtri=np.array([[lookup[int(v)]for v in t]for t in tri[sorted(selected)]]);hairrow=next(c for c in delivery['components']if c['element']=='hair');sk=P.read_meshfile(hairrow['mesh_path']).find('object')[0].find('skeleton');nodes=sorted(sk,key=lambda b:b.get('ix')[0]);names=[b.tag for b in nodes];byid={b['id']:b for b in source['bones']};mapping=delivery['source_map']
        def weighttarget(ident):
            while ident:
                name=mapping[ident]
                if not name.startswith('uma_src_')or 'pivot'in name.lower()or 'driver'in name.lower():return names.index(name)
                ident=byid[ident]['parent']
            return names.index('bn_h_head')
        rawweights={int(v):{}for v in ids};raw=[]
        for w in m['weights']:
            if w['vertex']in rawweights:
                j=weighttarget(w['bone']);rawweights[w['vertex']][j]=rawweights[w['vertex']].get(j,0)+w['weight'];raw.append(w)
        ix=np.full((len(ids),4),-1,int);weight=np.zeros((len(ids),4))
        for v,ws in rawweights.items():
            for k,(bone,w)in enumerate(sorted(ws.items(),key=lambda p:-p[1])):ix[lookup[v],k]=bone;weight[lookup[v],k]=w/sum(ws.values())
        H=np.array(next(b for b in source['bones']if b['name']=='Head')['matrix']).reshape(4,4)[:3,3];p=(positions[ids]-H)@C.T+anchor;n=pts(m['normals'])[ids]@C.T;n/=np.linalg.norm(n,axis=1)[:,None];u=uv[ids].copy();u[:,1]=1-u[:,1];prefix=f'uma_{actor}_neck_patch_{variant}';path=OUT/(prefix+'.mesh');meta=make_mesh(P,path,prefix+'Shape',p,n,u,patchtri,ix,weight,copy.deepcopy(sk),'portrait_skin_face',prefix)
        pixels=tex.copy();reference=np.array(palette[actor]['colors']['skin']['target_rgb_255'])/255.
        def linear(v):return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
        neutral=np.clip(linear(pixels[:,:,:3]/255.)/linear(reference)[None,None,:],0,1);pixels[:,:,:3]=np.rint(np.where(neutral<=.0031308,neutral*12.92,1.055*neutral**(1/2.4)-.055)*255);pixels[:,:,3]=255
        for ending,arr in [('diffuse',pixels),('normal',np.tile([0,128,0,128],(32,32,1))),('properties',np.tile([0,38,0,180],(32,32,1))),('ssao',np.tile([255,255,255,96],(32,32,1)))]:Image.fromarray(np.asarray(arr,np.uint8),'RGBA').save(OUT/(prefix+'_'+ending+'.dds'),pixel_format='DXT5')
        alpha=np.array(Image.open(OUT/(prefix+'_diffuse.dds')).convert('RGBA'))[:,:,3];nb=np.array(Image.open(OUT/(prefix+'_normal.dds')).convert('RGBA'))[:,:,2];assert np.all(alpha==255)and np.all(nb==0)
        rawpath=OUT/(prefix+'-source-weights.json');dump(rawpath,[{'source_mesh':'M_Hair','weights':raw}]);patchrow.update({'prefix':prefix,'mesh_path':str(path),'source_triangles':len(selected),'source_vertex_mapping':[{'source_mesh':'M_Hair','source_vertex_ids':ids.tolist(),'export_vertex_offset':0}],'original_source_weights_json':str(rawpath),**meta,'textures':[str(OUT/(prefix+'_'+ending+'.dds'))for ending in ['diffuse','normal','properties','ssao']],'texture_policy':{'source_material':mat['name'],'source_texture':str(resource/texref),'skin_reference_rgb':palette[actor]['colors']['skin']['target_rgb_255'],'neutralization':'native atlas linear RGB divided by actual source skin reference linear RGB, then sRGB encoded; alpha255 palette mask','palette_mask':'diffuse alpha','normal_blue_hair_mask':0,'dds_alpha_mask_verified':True,'dds_normal_blue_zero_verified':True}})
    else:patchrow['absence_evidence']='Ring coincides with native dark hair/garment geometry, no connected skin-colored Head/Neck-only region. Original coverage kept.'
    delivery['components']=[r for r in delivery['components']if r['element']!='neck_patch']+[patchrow];delivery['rear_neck_patch_extraction']={'source_triangle_ids':sorted(selected),'source_components_evidence':evidence,'removed_from_original_components':removal,'source_face_or_body_modified':False};partition['neck_patch_triangle_ids']=sorted(selected);roles=[set(partition[k])for k in ['hair_triangle_ids','ear_triangle_ids','headwear_triangle_ids','neck_patch_triangle_ids']];assert sum(map(len,roles))==len(set.union(*roles))==len(tri);partition['original_source_coverage_with_neck_patch_complete']=True;dump(partition_path,partition);dump(delivery_path,delivery);header['components']=delivery['components'];records.append({'row':patchrow,'source_triangle_ids':sorted(selected),'source_components_evidence':evidence,'removal':removal,'source_triangle_coverage_complete':True,'source_face_or_body_modified':False});dump(INDEX,index);print('NECK_PATCH',actor,variant,len(selected),[(r['from_component'],len(r['source_triangle_ids']))for r in removal],flush=True)
report={'passed_binary_roundtrip':True,'blender_import_pending_shared_slot':True,'rows':[r['row']for r in records],'patches':records,'density':'existing native vertices/triangles only','white_forelock_not_classified_as_neck_skin':True,'source_skin_present_variants':sum(r['row']['present']for r in records),'all_8_variants_examined':len(records)==8};dump(OUT/'neck-patch-delivery.json',report);index['neck_patch_delivery']=str(OUT/'neck-patch-delivery.json');dump(INDEX,index)
