"""Numerical direct-skinning audit of every stock body clip using unchanged stock animation bytes."""
import argparse,json,math
from pathlib import Path
import sys
import numpy as np

def matrix(t,q,s):
    x,y,z,w=q;rot=np.asarray([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)], [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)], [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    scale=np.asarray(s*3 if len(s)==1 else s);m=np.eye(4);m[:3,:3]=rot@np.diag(scale);m[:3,3]=t;return m
def inverse_bind(skeleton):
    result=[]
    for bone in skeleton:
        t=bone.attrib['tx'];result.append(np.asarray([[t[0],t[3],t[6],t[9]],[t[1],t[4],t[7],t[10]],[t[2],t[5],t[8],t[11]],[0,0,0,1]],dtype=float))
    return np.asarray(result)
def mesh_info(data):
    obj=data.find('object')[0];skeleton=obj.find('skeleton');parts=[]
    for mesh in obj.findall('mesh'):
        p=np.asarray(mesh.attrib['p']).reshape(-1,3);skin=mesh.find('skin');ix=np.asarray(skin.attrib['ix']).reshape(-1,4);w=np.asarray(skin.attrib['w']).reshape(-1,4);edges=np.asarray(mesh.attrib['tri']).reshape(-1,3)[:,[0,1]]
        parts.append((p,ix,w,edges))
    return skeleton,parts,inverse_bind(skeleton)
def deform(parts,matrices):
    results=[]
    for p,ix,w,edges in parts:
        points=np.column_stack((p,np.ones(len(p))));out=np.zeros((len(p),3))
        for slot in range(4):
            ids=np.maximum(ix[:,slot],0);transformed=np.einsum('nij,nj->ni',matrices[ids],points)[:,:3];out+=transformed*w[:,slot,None]
        lengths=np.linalg.norm(out[edges[:,0]]-out[edges[:,1]],axis=1);base=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1);valid=base>.005
        ratios=lengths[valid]/base[valid];results.append(dict(bounds_min=out.min(axis=0).tolist(),bounds_max=out.max(axis=0).tolist(),edge_ratio_p99=float(np.quantile(ratios,.99)),edge_ratio_max=float(ratios.max()),nonfinite=int(np.count_nonzero(~np.isfinite(out)))))
    return results
def globals_for(info,samples,frame,skeleton):
    names=[b.tag for b in skeleton];lookup={name:i for i,name in enumerate(names)};local={};offset={c:0 for c in 'tqs'}
    count={c:sum(c in ''.join(b.attrib.get('sa',[])) for b in info) for c in 'tqs'}
    for bone in info:
        name=bone.tag.rsplit(':',1)[-1];values={c:list(bone.attrib[c]) for c in 'tqs'};sa=''.join(bone.attrib.get('sa',[]))
        for c in 'tqs':
            if c not in sa:continue
            size=3 if c=='t' else 4 if c=='q' else len(values[c]);start=(frame*count[c]+offset[c])*size;values[c]=samples.attrib[c][start:start+size];offset[c]+=1
        local[name]=matrix(values['t'],values['q'],values['s'])
    world=np.zeros((len(names),4,4));done=set()
    def visit(i):
        if i in done:return
        pa=skeleton[i].attrib.get('pa');parent=pa[0] if pa else None
        if parent is not None:visit(parent)
        # Stock animation sets include all deforming joints; absent helper bones
        # retain their vanilla bind-local transform.
        if names[i] not in local:
            bind=np.linalg.inv(inverse_bind(skeleton)[i]);local[names[i]]=np.linalg.inv(np.linalg.inv(inverse_bind(skeleton)[parent]))@bind if parent is not None else bind
        world[i]=world[parent]@local[names[i]] if parent is not None else local[names[i]];done.add(i)
    for i in range(len(names)):visit(i)
    return world
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--stock-folder',type=Path,required=True);p.add_argument('--working',type=Path,required=True);p.add_argument('--before',type=Path,required=True);p.add_argument('--fixed',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(args.repo/'Tools/PDXExporter'));import build_ck3_mod as b
    pdx=b.parser_only(args.plugin);stock_skel,stock_parts,stock_bind=mesh_info(pdx.read_meshfile(str(args.stock_folder/'female_body.mesh')))
    models={}
    for name,file in (('working_sample',args.working),('before',args.before),('fixed',args.fixed)):
        sk,parts,bind=mesh_info(pdx.read_meshfile(str(file)));assert [b.tag for b in sk]==[b.tag for b in stock_skel];models[name]=(parts,bind)
    tree=b.clausewitz((args.stock_folder/'female_body.asset').read_text(encoding='utf-8-sig'));body=b.one(tree,'pdxmesh')
    clips=[('animation',v) for v in b.values(body,'animation')]+[('additive_animation',v) for v in b.values(body,'additive_animation')];reports=[]
    for number,(kind,entry) in enumerate(clips):
        file=args.stock_folder/b.one(entry,'type')
        if not file.exists():raise FileNotFoundError(file)
        data=pdx.read_meshfile(str(file));info=data.find('info');samples=data.find('samples');frames=info.attrib['sa'][0];tests=[]
        for frame in sorted({0,frames//2,frames-1}):
            world=globals_for(info,samples,frame,stock_skel);result={name:deform(parts,world@bind) for name,(parts,bind) in models.items()}
            assert all(r['nonfinite']==0 for values in result.values() for r in values)
            tests.append(dict(frame=frame,models=result))
        reports.append(dict(id=b.one(entry,'id'),kind=kind,file=file.name,frames=frames,tests=tests,source_sha256=b.sha(file)))
        if (number+1)%25==0:print('STOCK_ANIMATION_AUDITED',number+1,'/',len(clips),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(passed=True,stock_bind_exact=np.array_equal(models['fixed'][1],stock_bind),animations=len(reports),reports=reports,method='Direct evaluation of unmodified stock local t/q/s and skinning matrices against original working mesh, before, and corrected bind'),ensure_ascii=False,indent=2),encoding='utf8')
    print('STOCK_BODY_ANIMATION_AUDIT_COMPLETE',len(reports),flush=True)

if __name__=='__main__':main()
