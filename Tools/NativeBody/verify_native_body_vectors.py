"""Check consistent affine transport, all provided combinations, and PDX roundtrip ordering."""
import argparse,json,sys
from pathlib import Path
import numpy as np

def main():
    p=argparse.ArgumentParser()
    for name in ['repo','plugin','before','after','analysis','roundtrip','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--character-id',default='1001');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,str(a.repo/'Tools/PDXExporter'));import build_ck3_mod as b;pdx=b.parser_only(a.plugin)
    variants={'base':'base','shape_1':'s1','shape_2':'s2','height_0':'h0','height_2':'h2','bust_0':'b0','bust_1':'b1','bust_3':'b3','bust_4':'b4'}
    def node(folder,stem):
        file=folder/(stem+'.mesh')
        if not file.exists():file=folder/(a.character_id+'_body_'+variants[stem]+'.mesh')
        return pdx.read_meshfile(str(file)).find('object')[0].find('mesh')
    def coords(folder,stem):return np.asarray(node(folder,stem).attrib['p']).reshape(-1,3)
    base=coords(a.before,'base');newbase=coords(a.after,'base');transforms=np.load(a.after/'bind-pose-transforms.npy');definitions=json.loads(a.analysis.read_text(encoding='utf8'));rows=[];keys={};newkeys={};basenode=node(a.after,'base');roundtrips=[]
    names={'base':'base','shape_1':'s1','shape_2':'s2','height_0':'h0','height_2':'h2','bust_0':'b0','bust_1':'b1','bust_3':'b3','bust_4':'b4'}
    for key in definitions['keys']:
        if not key['identity']:keys[key['key']]=coords(a.before,key['key'])-base;newkeys[key['key']]=coords(a.after,key['key'])-newbase
    for record in definitions['combinations']:
        profile=record['profile'];old=base.copy();new=newbase.copy()
        for variable,value in profile.items():
            key=variable+'_'+str(value)
            if key in keys:old+=keys[key];new+=newkeys[key]
        expected=np.einsum('nij,nj->ni',transforms,np.column_stack((old,np.ones(len(old)))))[:,:3];error=float(np.linalg.norm(new-expected,axis=1).max());assert error<.0002
        rows.append(dict(profile=profile,affine_composition_max_error_cm=error))
    for stem,variant in names.items():
        source=node(a.after,stem);target=node(a.roundtrip,a.character_id+'_body_'+variant)
        rtbase=node(a.roundtrip,a.character_id+'_body_base')
        for key in ['tri','u0','u1','u2','u3']:assert target.attrib.get(key)==rtbase.attrib.get(key),(stem,'shared BS '+key)
        def triangles(m):
            return [min(tuple(face[j:]+face[:j])for j in range(3))for face in np.asarray(m.attrib['tri']).reshape(-1,3).tolist()]
        assert triangles(source)==triangles(target),(stem,'oriented triangles')
        uverror=max(float(np.max(np.abs(np.asarray(target.attrib[k])-np.asarray(source.attrib[k]))))for k in ['u0','u1','u2','u3']if k in source.attrib);assert uverror<1e-6
        def weights(m):
            s=m.find('skin');ix=np.asarray(s.attrib['ix']).reshape(-1,4);w=np.asarray(s.attrib['w']).reshape(-1,4);dense=np.zeros((len(ix),134));np.add.at(dense,(np.arange(len(ix))[:,None],np.maximum(ix,0)),w);return dense
        weight_error=float(np.max(np.abs(weights(target)-weights(basenode))));assert weight_error<1e-7
        assert target.find('skin').attrib==rtbase.find('skin').attrib,(stem,'shared BS skin')
        p1=np.asarray(source.attrib['p']).reshape(-1,3);p2=np.asarray(target.attrib['p']).reshape(-1,3);error=float(np.linalg.norm(p1-p2,axis=1).max());assert error<.0001,(stem,error)
        roundtrips.append(dict(variant=variant,shared_endpoint_topology_uv_skin_exact=True,source_oriented_triangles_equal=True,source_uv_max_error=uverror,source_semantic_weight_max_error=weight_error,coordinate_max_error_cm=error))
    report=dict(passed=True,profiles_verified=len(rows),combinations=rows,max_affine_composition_error_cm=max(x['affine_composition_max_error_cm']for x in rows),pdx_roundtrips=roundtrips,weights_topology_uv_preserved=True,geometry_delta_basis_policy='One fixed affine matrix per vertex shared by Basis and every source endpoint',live_height_gene_policy='Stock additive height; source height endpoints are editable references')
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('NATIVE_VECTOR_COMPOSITION_VERIFIED',len(rows),'profiles',flush=True)

if __name__=='__main__':main()
