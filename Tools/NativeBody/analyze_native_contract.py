"""Measure source endpoint semantics and inspect the installed vanilla contracts."""
import argparse,json,sys
from pathlib import Path
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--meshes',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--character-id',default='1001');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b
    pdx=b.parser_only(a.plugin)
    variants={'base':'base','shape_1':'s1','shape_2':'s2','height_0':'h0','height_2':'h2','bust_0':'b0','bust_1':'b1','bust_3':'b3','bust_4':'b4'}
    def file(name):
        old=a.meshes/(name+'.mesh');return old if old.exists()else a.meshes/(a.character_id+'_body_'+variants[name]+'.mesh')
    def coords(name):return np.asarray(pdx.read_meshfile(str(file(name))).find('object')[0].find('mesh').attrib['p']).reshape(-1,3)
    base=coords('base');bs={v:coords('bust_'+str(v))-base for v in [0,1,3,4]};fits=[]
    for v,endpoint in [(1,0),(3,4)]:
        d=bs[v];e=bs[endpoint];factor=float(np.sum(d*e)/np.sum(e*e));errors=np.linalg.norm(d-factor*e,axis=1)
        fits.append(dict(bust=v,endpoint=endpoint,factor=factor,max_error_cm=float(errors.max()),rms_error_cm=float(np.sqrt(np.mean(errors**2)))))
    sys.path.insert(0,str(Path(__file__).parent));from test_vanilla_body_animation_blender import mesh_info,globals_for
    sk,parts,bind=mesh_info(pdx.read_meshfile(str(file('base'))));_,ix,w,_=parts[0];heightanim=pdx.read_meshfile(str(a.game/'gfx/models/portraits/female_body/female_body_height.anim'));height_fits=[]
    for value,frame,sign in [(0,0,-1),(2,heightanim.find('info').attrib['sa'][0]-1,1)]:
        matrices=globals_for(heightanim.find('info'),heightanim.find('samples'),frame,sk)@bind;points=np.column_stack((base,np.ones(len(base))));deformed=np.zeros_like(base)
        for slot in range(4):deformed+=np.einsum('nij,nj->ni',matrices[np.maximum(ix[:,slot],0)],points)[:,:3]*w[:,slot,None]
        target=coords('height_'+str(value))-base;delta=deformed-base;factor=float(np.sum(target*delta)/np.sum(delta*delta));errors=np.linalg.norm(target-factor*delta,axis=1)
        height_fits.append(dict(height=value,additive_endpoint_factor=factor,estimated_normal_height_gene_strength=(.4+sign*.5*factor)/.8,max_source_fit_error_cm=float(errors.max()),rms_source_fit_error_cm=float(np.sqrt(np.mean(errors**2))),exact_source_profile=False))
    shapes=[]
    for name in ['base','shape_1','shape_2']:
        q=coords(name);rows=[]
        for y in np.linspace(55,110,12):
            subset=q[np.abs(q[:,1]-y)<1.5]
            if len(subset):rows.append(dict(y_cm=float(y),x_width_cm=float(np.ptp(subset[:,0])),z_depth_cm=float(np.ptp(subset[:,2]))))
        shapes.append(dict(name=name,sections=rows,bounds_min=q.min(axis=0).tolist(),bounds_max=q.max(axis=0).tolist()))
    genes=b.clausewitz((a.game/'common/genes/01_genes_morph.txt').read_text(encoding='utf-8-sig'));morph=b.one(genes,'morph_genes');gene_contract={}
    def attrs(node):
        result=[]
        for key,value in node:
            if key=='attribute':result.append(value)
            if isinstance(value,list):result.extend(attrs(value))
        return result
    for key in ['gene_height','gene_bs_body_type','gene_bs_body_shape','gene_bs_bust']:
        node=b.one(morph,key);gene_contract[key]=[dict(name=n,index=b.one(v,'index'),attributes=sorted(set(attrs(v))))for n,v in node if isinstance(v,list)and b.values(v,'index')]
    asset=b.clausewitz((a.game/'gfx/models/portraits/female_body/female_body.asset').read_text(encoding='utf-8-sig'));body=b.one(asset,'pdxmesh');entity=b.one(asset,'entity')
    report=dict(bust_endpoint_fits=fits,height_additive_fits=height_fits,shape_sections=shapes,genes=gene_contract,stock_bs=[dict(id=b.one(v,'id'),file=b.one(v,'type'))for v in b.values(body,'blend_shape')],stock_additives=[dict(id=b.one(v,'id'),file=b.one(v,'type'))for v in b.values(body,'additive_animation')],stock_attributes=[dict(v)for v in b.values(entity,'attribute')])
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('NATIVE_CONTRACT_ANALYZED',json.dumps(fits),flush=True)

if __name__=='__main__':main()
