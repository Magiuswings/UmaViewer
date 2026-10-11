import os
"""Export native V7 head components; no final mod or root rig mutation."""
import json,sys,copy,hashlib,gc
from pathlib import Path
import numpy as np,UnityPy
from PIL import Image
sys.path[:0]=[str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source')) / 'Tools/PDXExporter'),'C:/Users/33775/Desktop/网页制作/UmaV6Scripts']
from build_ck3_mod import parser_only
from native_motion import sample_clip,transform_paths,ear_local_frames
from head_pdx_tools import pts,world,skeleton,make_mesh,make_anim
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7'))));SRC=ROOT/'HeadSources';OUT=SRC/'Export';OUT.mkdir(exist_ok=True);OLD=Path(str(Path(os.environ.get('UMA_V6_INPUT','E:/UmaViewer-Exports/2026-10-11-UMA-V6-1001'))));P=parser_only(str(Path(os.environ.get('UMA_V7_PLUGIN','E:/UmaViewer-Workspace/PDX-vendor/io_pdx_mesh'))));contract=json.loads((ROOT/'rig-contract.json').read_text());C3=np.array(contract['head_source_to_engine']);C=np.eye(4);C[:3,:3]=C3;CI=np.linalg.inv(C);anchor=np.array(contract['head_anchor']);index=json.loads((SRC/'head-parts-index.json').read_text());loc=UnityPy.load(str(SRC/'decoded/locator/3d/animator/drivenkeylocator'));hashes=transform_paths(loc);records=[]
ear1001={r['key']:r for r in json.loads((OLD/'native-motion-index.json').read_text())};ear1002={r['key']:r for r in json.loads((SRC/'motions/native-ear-1002-index.json').read_text())};locator_tracks={}
for char,keys in [('1001',['ear_04','ear_03','ear_05']),('1002',['ear1002_14','ear1002_11','ear1002_22'])]:
    for ck in keys:
        rec=(ear1001 if char=='1001'else ear1002)[ck];path=(OLD/'more-native'/rec['source'])if char=='1001'else(SRC/'decoded/ear-motion-1002'/rec['source']);env=UnityPy.load(str(path));clip=next(o.read()for o in env.objects if o.type.name=='AnimationClip');times,tracks=sample_clip(clip);locator_tracks[char,ck]=(times,tracks,rec)
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def texture(mat,resources,element):
    props=mat['properties'];tex=next((p for p in props if p['name']=='_MainTex'and p.get('texture')),None)
    if tex is None:tex=next((p for p in props if 'Cheek'in p['name']and p.get('texture')),None)
    if tex is None:return np.full((32,32,4),255,np.uint8),None,'Source has no bound diffuse texture; optional procedural effect uses neutral conservative placeholder.'
    pixels=np.array(Image.open(resources/tex['texture']).convert('RGBA'));note='Source atlas preserved.'
    if element=='eye':
        scale=tex.get('scale',[1,1]);offset=tex.get('offset',[0,0]);hh,ww=pixels.shape[:2];pixels=pixels[int((1-offset[1]-scale[1])*hh):int((1-offset[1])*hh),int(offset[0]*ww):int((offset[0]+scale[0])*ww)].copy();note='Native eye _MainTex scale/offset baked by atlas crop; UV remains source normalized.'
    return pixels,tex,note
def textures(folder,prefix,mat,resources,element):
    pixels,tex,note=texture(mat,resources,element);normal=np.tile([0,128,0,128],(*pixels.shape[:2],1)).astype(np.uint8);mask=None
    if element in ['face','eye','face_parts','brow']:pixels[:,:,3]=255
    if element in ['hair','ear']:
        ctrl=next((p for p in mat['properties']if p['name']=='_OptionMaskMap'and p.get('texture')),None)
        rgb=pixels[:,:,:3].astype(float)/255.;white=(rgb.min(2)>.7)&((rgb.max(2)-rgb.min(2))<.2);control=np.array(Image.open(resources/ctrl['texture']).convert('RGBA'))if ctrl else np.tile([0,0,255,255],(*pixels.shape[:2],1));mask=(control[:,:,2]>127)&~white;lum=rgb@np.array([.2126,.7152,.0722]);valid=lum[mask&(pixels[:,:,3]>10)];ref=float(np.percentile(valid,85))if len(valid)else .5;grey=np.clip(lum/max(ref,1e-8)*.82,0,1);pixels[:,:,:3]=np.where(mask[:,:,None],np.rint(grey[:,:,None]*255),pixels[:,:,:3]);normal[:,:,2]=mask.astype(np.uint8)*255
    if element=='brow':lum=pixels[:,:,:3].astype(float)@np.array([.2126,.7152,.0722]);pixels[:,:,:3]=np.rint(lum[:,:,None]);normal[:,:,2]=255
    for ending,arr in [('diffuse',pixels),('normal',normal),('properties',np.tile([0,38,0,180],(32,32,1))),('ssao',np.tile([255,255,255,96],(32,32,1)))]:Image.fromarray(np.asarray(arr,np.uint8),'RGBA').save(folder/(prefix+'_'+ending+'.dds'),pixel_format='DXT5')
    return {'source_material':mat['name'],'source_texture':tex.get('texture')if tex else None,'source_texture_note':note,'palette_mask':'normal B'if element in ['hair','ear','brow']else'diffuse alpha'if element in ['face','face_parts','eye']else'none original ornament/effect color','masked_pixels':int(mask.sum())if mask is not None else None,'white_hair_marking_preserved':element in ['hair','ear'],'shader_source_reused_v6':True}
def source_rig(data,H,attach=True):
    names=[b['name']for b in data['bones']];byid={b['id']:i for i,b in enumerate(data['bones'])};parents=[byid.get(b['parent'])for b in data['bones']];sw=np.array([np.array(b['matrix']).reshape(4,4)for b in data['bones']]);K=np.eye(4);K[:3,3]=-C3@H;bw=np.array([K@C@w@CI for w in sw]);return names,parents,sw,K,bw,skeleton(names,parents,bw),byid
def carrier_rig(char,data,H):
    sk=P.read_meshfile(str(ROOT/f'Rigs/head_{char}.mesh')).find('object')[0].find('skeleton');nodes=sorted(sk,key=lambda b:b.get('ix')[0]);names=[b.tag for b in nodes];parents=[b.get('pa')[0]if b.get('pa')else None for b in nodes];bw=list(world(sk));base=json.loads((SRC/f'parsed/chr{char}_80/head.json').read_text());mapping=json.loads((ROOT/f'Rigs/head_{char}-source-map.json').read_text());named={b['name']:mapping[b['id']]for b in base['bones']};named[data['bones'][0]['name']]='uma_head_base';byid={b['id']:b for b in data['bones']};resolved={};transform=np.eye(4);transform[:3,:3]=C3;transform[:3,3]=anchor-C3@H
    for b in data['bones']:
        target=named.get(b['name'],'uma_src_'+b['name']);resolved[b['id']]=target
        if target not in names:
            pa=resolved.get(b['parent'],'bn_h_head');names.append(target);parents.append(names.index(pa));sw=np.array(b['matrix']).reshape(4,4);bw.append(transform@sw@CI)
        elif target.startswith('uma_src_'):
            j=names.index(target);sw=np.array(b['matrix']).reshape(4,4);bw[j]=transform@sw@CI
            if b['parent']in resolved:parents[j]=names.index(resolved[b['parent']])
    assert len(names)<=255,(char,len(names));ordered=[];seen=set();visiting=set()
    def visit(i):
        if i in seen:return
        assert i not in visiting,('bone parent cycle',names[i]);visiting.add(i)
        if parents[i]is not None:visit(parents[i])
        visiting.remove(i);seen.add(i);ordered.append(i)
    for i in range(len(names)):visit(i)
    remap={old:new for new,old in enumerate(ordered)};names=[names[i]for i in ordered];parents=[remap[parents[i]]if parents[i]is not None else None for i in ordered];bw=[bw[i]for i in ordered];core={n for n in names if not n.startswith('uma_src_')}
    def weight_target(ident):
        cur=ident
        while cur:
            target=resolved[cur]
            if target in core or 'pivot'in target.lower()or'driver'in target.lower():return names.index(target)
            cur=byid[cur]['parent']
        return names.index('bn_h_head')
    return skeleton(names,parents,bw),weight_target,resolved
for rec in index['records']:
    if rec['kind']!='head':continue
    char=rec['character_id'];variant=rec['variant'];data=json.loads(Path(rec['parsed_json']).read_text());resources=Path(rec['texture_root']);folder=OUT/f'chr{char}_{variant}';folder.mkdir(exist_ok=True);H=np.array(next(b for b in data['bones']if b['name']=='Head')['matrix']).reshape(4,4)[:3,3];parts={m['name']:m for m in data['meshes']};partition=json.loads((SRC/f'partitions/chr{char}_{variant}/head-components.json').read_text());native=source_rig(data,H);core,coretarget,source_mapping=carrier_rig(char,data,H);driven=json.loads(Path(rec['driven_targets_json']).read_text());target=next(t['data']for t in driven if 'ear_target'in t['data'].get('m_Name',''));component_records=[]
    selections={}
    face=parts['M_Face']
    for element,category in [('face','face'),('eye','eyes')]:selections[element]=[(face,np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in face['faces']if f['category']==category]),next(f['material']for f in face['faces']if f['category']==category))]
    for element,name in [('face_parts','M_Line00'),('brow','M_Mayu'),('cheek','M_Cheek')]:m=parts[name];selections[element]=[(m,np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in m['faces']]),m['faces'][0]['material'])]
    selections['tear']=[(parts[n],np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in parts[n]['faces']]),parts[n]['faces'][0]['material'])for n in ['M_Tear_L','M_Tear_R']]
    hair=parts['M_Hair'];ht=np.concatenate([np.array(f['triangles']).reshape(-1,3)for f in hair['faces']])
    for element in ['hair','ear','headwear']:selections[element]=[(hair,ht[partition[element+'_triangle_ids']],hair['faces'][0]['material'])]
    for element in ['face','eye','face_parts','brow','hair','ear','headwear','cheek','tear']:
        prefix=f'uma_{char}_{variant}_{element}';selected=selections[element];total=sum(len(t)for m,t,ma in selected);optional=element in ['cheek','tear'];independent=element in ['ear','headwear'];entry={'actor':char,'variant':variant,'element':element,'present':bool(total),'source_triangles':total,'optional_expression_overlay':optional,'enabled_in_default_preset':not optional and bool(total),'independent_native_pose':independent,'attachment_node':'bn_h_head'if independent else None,'shared_pose_entity':None if independent else'head','original_inactive_flags':{m['name']:not m['active']for m,t,ma in selected},'shader':'portrait_hair'if element in ['hair','ear']else'portrait_eye'if element=='eye'else'portrait_hair_brow_overlay'if element=='brow'else'portrait_skin_face'if element in ['face','face_parts']else'portrait_attachment','prefix':prefix}
        if not total:component_records.append(entry);continue
        vertices=[];normals=[];uvs=[];faces=[];ixes=[];weights=[];source_ids=[];raw_weights=[];sk=native[5]if independent else core
        for m,tri,ma in selected:
            if not len(tri):continue
            ids=np.unique(tri);lookup={int(v):i for i,v in enumerate(ids)};raw=pts(m['vertices'])[ids];p=(raw-H)@C3.T+(np.zeros(3)if independent else anchor);n=pts(m['normals'])[ids]@C3.T;n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-20);uv0=next(u['values']for u in m['uvs']if u['channel']==0);uv=np.array([[v['x'],1-v['y']]for v in uv0])[ids];f=np.array([[lookup[int(v)]+len(vertices)for v in row]for row in tri]);byv={int(v):{}for v in ids};rw=[]
            for w in m['weights']:
                if w['vertex']in byv:
                    ix=native[6][w['bone']]if independent else coretarget(w['bone']);byv[w['vertex']][ix]=byv[w['vertex']].get(ix,0)+w['weight'];rw.append(w)
            ix=np.full((len(ids),4),-1,int);weight=np.zeros((len(ids),4))
            for v,ws in byv.items():
                j=lookup[v];ordered=sorted(ws.items(),key=lambda v:-v[1]);assert len(ordered)<=4;ss=sum(w for i,w in ordered);assert ss>0
                for k,(i,w)in enumerate(ordered):ix[j,k]=i;weight[j,k]=w/ss
            vertices.extend(p);normals.extend(n);uvs.extend(uv);faces.extend(f);ixes.extend(ix);weights.extend(weight);source_ids.append({'source_mesh':m['name'],'source_vertex_ids':ids.tolist(),'export_vertex_offset':len(vertices)-len(ids)});raw_weights.append({'source_mesh':m['name'],'weights':rw})
        entry.update(make_mesh(P,folder/(prefix+'.mesh'),prefix,np.array(vertices),np.array(normals),np.array(uvs),np.array(faces),np.array(ixes),np.array(weights),copy.deepcopy(sk),entry['shader'],prefix));entry['mesh_path']=str(folder/(prefix+'.mesh'));entry['source_vertex_mapping']=source_ids;entry['texture_policy']=textures(folder,prefix,data['materials'][selected[0][2]],resources,element);dump(folder/(prefix+'-source-weights.json'),raw_weights);entry['original_source_weights_json']=str(folder/(prefix+'-source-weights.json'))
        if independent:
            entry['animations']=[];keys=['ear_04','ear_03','ear_05']if char=='1001'else['ear1002_14','ear1002_11','ear1002_22']
            for ck,state in zip(keys,['idle_entry','idle','frontEnd_middle_entry']):
                times,tracks,sourceclip=locator_tracks[char,ck];frames,used=ear_local_frames(times,tracks,hashes,target);animpath=folder/'animation'/element/(prefix+'_'+state+'.anim');verified=make_anim(P,animpath,*native[:3],native[3],C,frames,len(times));entry['animations'].append({'state':state,'source_key':ck,'source_asset':sourceclip['source'],'source_target_variant':variant,'file':str(animpath),**verified})
        component_records.append(entry)
    dump(folder/'head-component-delivery.json',{'actor':char,'variant':variant,'components':component_records,'all_9_component_records':len(component_records)==9,'source_native_transforms_retained':len(data['bones']),'source_geometry_cut':False,'source_json':rec['parsed_json'],'shared_core_rig':str(ROOT/f'Rigs/head_{char}.mesh'),'source_map':source_mapping,'shaders_rewritten':False,'procedural_expression_overlays_not_runtime_recreated':True,'blender_verification_executed':False});records.append({'actor':char,'variant':variant,'delivery_json':str(folder/'head-component-delivery.json'),'components':component_records});dump(OUT/'head-export-index.json',{'heads':records,'complete':False});print('V7_HEAD_EXPORTED',char,variant,[(p['element'],p.get('triangles',0),p.get('bones',0))for p in component_records],flush=True);gc.collect()
dump(OUT/'head-export-index.json',{'heads':records,'complete':True,'raw_originals_modified':False,'root_rigs_modified':False,'all_variant_native_bones_retained':True,'notes':['Absent component stays absent; no synthetic headwear/ear geometry added.','Cheek/tear optional expression geometry retained; shader procedural effect controls are not falsely claimed reconstructed.']})
print('V7_ALL_HEAD_COMPONENTS_EXPORTED',len(records),flush=True)
