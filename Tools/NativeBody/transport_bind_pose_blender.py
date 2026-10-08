"""Transport all geometry consistently from the UMA-adapted bind frame to the vanilla bind frame."""
import argparse,copy,json,re
from pathlib import Path
import sys
import numpy as np
from mathutils import Vector

def binds(skeleton):
    return np.asarray([[[t[0],t[3],t[6],t[9]],[t[1],t[4],t[7],t[10]],[t[2],t[5],t[8],t[11]],[0,0,0,1]] for t in (n.attrib['tx'] for n in skeleton)],dtype=float)
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--stock',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--anatomical-directions',action='store_true',default=True);p.add_argument('--positions-only',dest='anatomical_directions',action='store_false',help=argparse.SUPPRESS);p.add_argument('--keep-coordinates',action='store_true',default=True);p.add_argument('--convert-geometry',dest='keep_coordinates',action='store_false',help=argparse.SUPPRESS)
    p.add_argument('--character-id',default='1001');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert re.fullmatch(r'\d{4}',args.character_id);sys.path.insert(0,str(args.repo/'Tools/PDXExporter'));import build_ck3_mod as b
    pdx=b.parser_only(args.plugin);stock=pdx.read_meshfile(str(args.stock));reference=stock.find('object')[0].find('skeleton');stock_world=np.linalg.inv(binds(reference))
    if args.output.exists():raise FileExistsError(args.output)
    meshout=args.output/args.character_id;meshout.mkdir(parents=True);records=[];common_matrices=None
    for file in sorted(args.source.glob('*.mesh')):
        original=pdx.read_meshfile(str(file));data=copy.deepcopy(original)
        for obj in data.find('object'):
            skeleton=obj.find('skeleton');assert [n.tag for n in skeleton]==[n.tag for n in reference]
            old_world=np.linalg.inv(binds(skeleton));transforms=stock_world@binds(skeleton)
            if args.anatomical_directions:
                names=[n.tag for n in reference];lookup={name:i for i,name in enumerate(names)}
                segments={'body_root':'bn_sp_lumbar','bn_sp_lumbar':'bn_sp_thoracic','bn_sp_thoracic':'bn_sp_cervical'}
                for s in ['l','r']:
                    segments.update({f'bn_{s}_clavicle':f'bn_{s}_shoulder',f'bn_{s}_shoulder':f'bn_{s}_elbow',f'bn_{s}_deltoid':f'bn_{s}_elbow',f'bn_{s}_elbow':f'bn_{s}_wrist',f'bn_{s}_forearm':f'bn_{s}_wrist',f'bn_{s}_wrist':f'bn_{s}_fi_mid1',f'bn_{s}_hip':f'bn_{s}_knee',f'bn_{s}_knee':f'bn_{s}_ankle',f'bn_{s}_ankle':f'bn_{s}_ftBall'})
                    for digit in ['thumb','index','mid','ring','pinky']:
                        for number in [1,2]:segments[f'bn_{s}_fi_{digit}{number}']=f'bn_{s}_fi_{digit}{number+1}'
                orientations={}
                for name,end in segments.items():
                    i=lookup[name];j=lookup[end];v=old_world[j,:3,3]-old_world[i,:3,3];u=stock_world[j,:3,3]-stock_world[i,:3,3]
                    if min(np.linalg.norm(v),np.linalg.norm(u))<1e-4:continue
                    rotation=np.asarray(Vector(v).rotation_difference(Vector(u)).to_matrix());direction=v/np.linalg.norm(v);scale=1. if args.keep_coordinates else np.linalg.norm(u)/np.linalg.norm(v)
                    orientations[name]=rotation@(np.eye(3)+(scale-1)*np.outer(direction,direction))
                for i,name in enumerate(names):
                    chosen=name
                    while chosen not in orientations:
                        node=reference[lookup[chosen]];pa=node.attrib.get('pa')
                        if not pa:break
                        chosen=names[pa[0]]
                    linear=orientations.get(chosen,np.eye(3));transforms[i]=np.eye(4);transforms[i,:3,:3]=linear;transforms[i,:3,3]=stock_world[i,:3,3]-linear@old_world[i,:3,3]
            for mesh in obj.findall('mesh'):
                p=np.asarray(mesh.attrib['p']).reshape(-1,3);skin=mesh.find('skin');ix=np.asarray(skin.attrib['ix']).reshape(-1,4);weights=np.asarray(skin.attrib['w']).reshape(-1,4)
                per_vertex=np.zeros((len(p),4,4))
                for slot in range(4):per_vertex+=transforms[np.maximum(ix[:,slot],0)]*weights[:,slot,None,None]
                if common_matrices is None:common_matrices=per_vertex
                else:assert np.max(np.abs(common_matrices-per_vertex))<1e-7
                if args.keep_coordinates:continue
                out=np.einsum('nij,nj->ni',per_vertex,np.column_stack((p,np.ones(len(p)))))[:,:3]
                mesh.attrib['p']=out.astype(np.float32).reshape(-1).tolist();mesh.find('aabb').attrib['min']=out.min(axis=0).astype(np.float32).tolist();mesh.find('aabb').attrib['max']=out.max(axis=0).astype(np.float32).tolist()
                if 'boundingsphere' in mesh.attrib:
                    center=(out.min(axis=0)+out.max(axis=0))/2;radius=np.linalg.norm(out-center,axis=1).max();mesh.attrib['boundingsphere']=np.asarray([*center,radius],dtype=np.float32).tolist()
                rotations=per_vertex[:,:3,:3]
                n=np.asarray(mesh.attrib['n']).reshape(-1,3);n=np.einsum('nij,nj->ni',np.transpose(np.linalg.inv(rotations),(0,2,1)),n);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-10);mesh.attrib['n']=n.astype(np.float32).reshape(-1).tolist()
                if mesh.attrib.get('ta'):
                    tangent=np.asarray(mesh.attrib['ta']).reshape(-1,4);t=np.einsum('nij,nj->ni',rotations,tangent[:,:3]);t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-10);tangent[:,:3]=t;mesh.attrib['ta']=tangent.astype(np.float32).reshape(-1).tolist()
            replacement=copy.deepcopy(reference)
            if args.keep_coordinates:
                corrected=binds(reference)@transforms
                for i,n in enumerate(replacement):n.attrib['tx']=corrected[i,:3,:].T.reshape(-1).astype(np.float32).tolist()
                before_points=np.linalg.inv(binds(skeleton))[:,:3,3];after_points=np.linalg.inv(binds(replacement))[:,:3,3]
                assert np.max(np.linalg.norm(before_points-after_points,axis=1))<.0001
            at=list(obj).index(skeleton);obj.remove(skeleton);obj.insert(at,replacement)
        variants={'base':'base','bust_0':'b0','bust_1':'b1','bust_3':'b3','bust_4':'b4','height_0':'h0','height_2':'h2','shape_1':'s1','shape_2':'s2'};match=re.fullmatch(r'\d{4}_body_(base|b0|b1|b3|b4|h0|h2|s1|s2)',file.stem);variant=match[1]if match else variants[file.stem];target=meshout/(args.character_id+'_body_'+variant+'.mesh');pdx.write_meshfile(str(target),data)
        reread=pdx.read_meshfile(str(target))
        if not args.keep_coordinates:assert all(n.attrib==r.attrib for n,r in zip(reread.find('object')[0].find('skeleton'),reference))
        else:
            for old,new in zip(original.find('object')[0].findall('mesh'),reread.find('object')[0].findall('mesh')):assert old.attrib==new.attrib and old.find('skin').attrib==new.find('skin').attrib
        records.append(dict(file=target.name,source_file=file.name,vanilla_bind_exact=not args.keep_coordinates,coordinates_exact=args.keep_coordinates,bind_points_preserved=args.keep_coordinates,bind_point_max_error_cm=float(np.max(np.linalg.norm(before_points-after_points,axis=1)))if args.keep_coordinates else None,weights_topology_uv_unchanged=True,anatomical_directions=args.anatomical_directions,bind_pose_transport='correct inverse-bind directions only'if args.keep_coordinates else'same per-vertex affine transform for Basis and every endpoint'))
    np.save(meshout/'bind-pose-transforms.npy',np.broadcast_to(np.eye(4),common_matrices.shape).copy()if args.keep_coordinates else common_matrices)
    (meshout/'bind-pose-verification.json').write_text(json.dumps(dict(passed=True,records=records,source_preserved=True,no_per_animation_retargeting=True,policy='Preserve every geometry value and joint point; correct inverse-bind directions'if args.keep_coordinates else'Export-copy bind-pose conversion using unchanged skin weights; exact vanilla skeleton; same transform on every BS endpoint'),ensure_ascii=False,indent=2),encoding='utf8')
    print('VANILLA_BIND_POSE_TRANSPORT_COMPLETE',len(records),flush=True)

if __name__=='__main__':main()
